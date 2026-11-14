from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.db import models
from django_minio_backend import MinioBackend

from common.models import SoftDeleteModel
from common.utils import upload_document_prefix_helper
from documents import const
from .choices import Status

User = get_user_model()


class Document(SoftDeleteModel):

    title = models.CharField(max_length=255)
    file = models.FileField(
        storage=MinioBackend(bucket_name=settings.MINIO_APP_PRIVATE_BUCKET),
        upload_to=upload_document_prefix_helper,
        validators=[FileExtensionValidator(const.ALLOWED_DOCUMENT_EXTENSIONS)],
        blank=True,
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="documents")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class DocumentShare(SoftDeleteModel):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shared_documents")
    shared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "user"],
                condition=models.Q(is_deleted=False),
                name="unique_active_document_share",
            ),
        ]

    def __str__(self):
        return f"{self.document} -> {self.user}"