from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.db import models
from django_minio_backend import MinioBackend

# from common.utils import upload_document_prefix_helper
# from documents import const
from .choices import Status

User = get_user_model()


class Document(models.Model):
    title = models.CharField(max_length=255)
    # empty until the background task stores the file in MinIO
    file = models.FileField(
        storage=MinioBackend(bucket_name=settings.MINIO_APP_PRIVATE_BUCKET),
        # upload_to=upload_document_prefix_helper,
        # validators=[FileExtensionValidator(const.ALLOWED_DOCUMENT_EXTENSIONS)],
        blank=True,
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="documents")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
