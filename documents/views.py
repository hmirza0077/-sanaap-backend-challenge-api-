from django.db.models import Prefetch, Q
from django.http import HttpResponseRedirect
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from common.services import SoftDeleteService
from user.permissions import DocumentPermission
from audit.models import AuditLog
from audit.services import AuditLogService
from audit.choices import Action
from documents import const
from documents.filters import DocumentFilter
from documents.models import Document, DocumentShare
from documents.notifications import DocumentNotification
from documents.serializers import DocumentSerializer, DocumentShareSerializer
from documents.services import DocumentService
from documents.choices import Status


@extend_schema_view(
    list=extend_schema(
        summary="List Documents",
        description="Own documents and documents shared with you (admin: all documents)",
    ),
    create=extend_schema(
        summary="Upload Document",
        description="Upload a document. The file is stored in MinIO by a background task",
    ),
    retrieve=extend_schema(
        summary="Document Details",
        description="Retrieve details of a specific document",
    ),
    destroy=extend_schema(
        summary="Delete Document",
        description="Admin only. Soft delete: the document is hidden, but kept in the database and MinIO",
    ),
    download=extend_schema(
        summary="Download Document",
        description="Checks access, then redirects (302) to a presigned MinIO link that expires after 60 seconds. "
        "Returns 409 while the file is not ready",
        responses={302: None},
    ),
    retry=extend_schema(
        summary="Retry Upload",
        description="Owner or admin: send a failed upload to the background task again. "
        "Returns 409 if the upload has not failed, 410 if the file has expired and must be uploaded again",
        request=None,
    ),
    share=extend_schema(
        summary="Share Document",
        description="Owner or admin: give a user read-only access (view and download)",
        request=DocumentShareSerializer,
    ),
    unshare=extend_schema(
        summary="Unshare Document",
        description="Owner or admin: take the read-only access back",
        request=DocumentShareSerializer,
    ),
)
class DocumentViewSet(ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [DocumentPermission]
    filterset_class = DocumentFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation for Swagger has no real user
            return Document.objects.none()

        user = self.request.user
        queryset = Document.objects.select_related("uploaded_by").prefetch_related(
            Prefetch("shares", queryset=DocumentShare.objects.filter(user__is_deleted=False).select_related("user"))
        )
        if user.is_admin_role:
            return queryset

        # Own documents + documents shared with this user. Anything else returns 404,
        # so a link to another user's document is useless even if it is shared.
        shared_document_ids = DocumentShare.objects.filter(user=user).values("document_id")
        return queryset.filter(Q(uploaded_by=user) | Q(id__in=shared_document_ids))

    def perform_create(self, serializer):
        # the file is stored by the background task, not inside the request
        uploaded_file = serializer.validated_data.pop("file")
        instance = serializer.save(uploaded_by=self.request.user)
        DocumentService(instance).queue_file_storage(uploaded_file)

        AuditLogService.log_action(self.request.user, Action.CREATE, instance)
        DocumentNotification.send_document_event(const.DOCUMENT_EVENT_CREATED, instance)

    def perform_update(self, serializer):
        uploaded_file = serializer.validated_data.pop("file", None)
        instance = serializer.save()
        if uploaded_file:
            DocumentService(instance).queue_file_storage(uploaded_file)

        AuditLogService.log_action(self.request.user, Action.UPDATE, instance)
        DocumentNotification.send_document_event(const.DOCUMENT_EVENT_UPDATED, instance)

    def perform_destroy(self, instance):
        SoftDeleteService.delete(instance, self.request.user)
        AuditLogService.log_action(self.request.user, Action.DELETE, instance)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        AuditLogService.log_action(request.user, Action.VIEW, instance)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Only users who can see the document get a (short-lived) MinIO link."""
        instance = self.get_object()
        if instance.status != Status.READY:
            return Response({"detail": "File is not ready."}, status=status.HTTP_409_CONFLICT)

        AuditLogService.log_action(request.user, Action.DOWNLOAD, instance)
        return HttpResponseRedirect(DocumentService(instance).get_download_url())

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        """The user retries a failed upload without sending the file again."""
        instance = self.get_object()
        if instance.status != Status.FAILED:
            return Response({"detail": "Only failed uploads can be retried."}, status=status.HTTP_409_CONFLICT)

        if not DocumentService(instance).retry_file_storage():
            return Response(
                {"detail": "The file has expired. Please upload it again."}, status=status.HTTP_410_GONE
            )

        AuditLogService.log_action(request.user, Action.UPDATE, instance)
        DocumentNotification.send_document_event(const.DOCUMENT_EVENT_UPDATED, instance)
        return Response(self.get_serializer(instance).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        instance = self.get_object()
        serializer = DocumentShareSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["username"]
        if user == instance.uploaded_by:
            return Response({"detail": "The owner already has access."}, status=status.HTTP_400_BAD_REQUEST)

        DocumentService(instance).share(user, shared_by=request.user)
        AuditLogService.log_action(request.user, Action.SHARE, instance)
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=["post"])
    def unshare(self, request, pk=None):
        instance = self.get_object()
        serializer = DocumentShareSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        DocumentService(instance).unshare(serializer.validated_data["username"], unshared_by=request.user)
        AuditLogService.log_action(request.user, Action.UNSHARE, instance)
        return Response(self.get_serializer(self.get_object()).data)
