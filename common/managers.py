from django.db import models


class SoftDeleteManager(models.Manager):
    """Deleted rows are hidden everywhere (views, serializers, admin, login)."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)