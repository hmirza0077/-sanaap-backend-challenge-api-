import os

from django.http import FileResponse
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from common.services import SoftDeleteService
from user.permissions import DocumentPermission
from audit.models import AuditLog
from audit.services import AuditLogService
from documents import const
from documents.filters import DocumentFilter
from documents.models import Document
from documents.notifications import DocumentNotification
from documents.serializers import DocumentSerializer
from documents.services import DocumentService


@extend_schema_view(
    list=extend_schema(
        summary="List Documents",
        description="Retrieve a list of documents",
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
        description="Soft delete: the document is hidden, but kept in the database and MinIO",
    ),
    download=extend_schema(
        summary="Download Document",
        description="Download the file of a document. Returns 409 while the file is not ready",
        responses={200: None},
    ),
    retry=extend_schema(
        summary="Retry Upload",
        description="Send a failed upload to the background task again. "
        "Returns 409 if the upload has not failed, 410 if the file has expired and must be uploaded again",
        request=None,
    ),
)
class DocumentViewSet(ModelViewSet):
    queryset = Document.objects.select_related("uploaded_by")
    serializer_class = DocumentSerializer
    permission_classes = [DocumentPermission]
    filterset_class = DocumentFilter

    def perform_create(self, serializer):
        # the file is stored by the background task, not inside the request
        uploaded_file = serializer.validated_data.pop("file")
        instance = serializer.save(uploaded_by=self.request.user)
        DocumentService(instance).queue_file_storage(uploaded_file)

        AuditLogService.log_action(self.request.user, AuditLog.Action.CREATE, instance)
        DocumentNotification.send_document_event(const.DOCUMENT_EVENT_CREATED, instance)

    def perform_update(self, serializer):
        uploaded_file = serializer.validated_data.pop("file", None)
        instance = serializer.save()
        if uploaded_file:
            DocumentService(instance).queue_file_storage(uploaded_file)

        AuditLogService.log_action(self.request.user, AuditLog.Action.UPDATE, instance)
        DocumentNotification.send_document_event(const.DOCUMENT_EVENT_UPDATED, instance)

    def perform_destroy(self, instance):
        # nothing is really deleted: the row and the file in MinIO are kept
        SoftDeleteService.delete(instance, self.request.user)
        AuditLogService.log_action(self.request.user, AuditLog.Action.DELETE, instance)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        AuditLogService.log_action(request.user, AuditLog.Action.VIEW, instance)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Secure download: only authenticated users with read access get the file."""
        instance = self.get_object()
        if instance.status != Document.Status.READY:
            return Response({"detail": "File is not ready."}, status=status.HTTP_409_CONFLICT)

        AuditLogService.log_action(request.user, AuditLog.Action.DOWNLOAD, instance)
        filename = os.path.basename(instance.file.name)
        return FileResponse(instance.file.open("rb"), as_attachment=True, filename=filename)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        """The user retries a failed upload without sending the file again."""
        instance = self.get_object()
        if instance.status != Document.Status.FAILED:
            return Response({"detail": "Only failed uploads can be retried."}, status=status.HTTP_409_CONFLICT)

        if not DocumentService(instance).retry_file_storage():
            return Response(
                {"detail": "The file has expired. Please upload it again."}, status=status.HTTP_410_GONE
            )

        AuditLogService.log_action(request.user, AuditLog.Action.UPDATE, instance)
        DocumentNotification.send_document_event(const.DOCUMENT_EVENT_UPDATED, instance)
        return Response(self.get_serializer(instance).data, status=status.HTTP_202_ACCEPTED)
