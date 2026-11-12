import uuid

from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(BaseModel):
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        "user.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )


    class Meta:
        abstract = True


class SoftDelete:
    @staticmethod
    def mark(instance, user):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = user
        instance.save(
            update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"]
        )


class ReferenceModel(BaseModel):

    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True