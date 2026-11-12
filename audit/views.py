from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework.viewsets import ReadOnlyModelViewSet

from accounts.permissions import IsAdminRole
from audit.models import AuditLog
from audit.serializers import AuditLogSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List Audit Logs",
        description="Admin only: who viewed, downloaded, created, updated or deleted which document",
    ),
    retrieve=extend_schema(
        summary="Audit Log Details",
        description="Admin only: retrieve a specific audit log",
    ),
)
class AuditLogViewSet(ReadOnlyModelViewSet):
    """Logs cannot be changed or deleted through the API."""

    queryset = AuditLog.objects.select_related("user")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["action", "document_id"]
