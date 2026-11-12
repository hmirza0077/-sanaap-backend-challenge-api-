import uuid

from django.conf import settings
from django.db import models
from .managers import SoftDeleteManager


class BaseModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(BaseModel):
    """Nothing is really deleted in this project: rows are only marked as deleted."""

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()  # includes deleted rows

    class Meta:
        abstract = True


class ReferenceModel(BaseModel):
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
