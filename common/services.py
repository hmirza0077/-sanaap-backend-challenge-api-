from django.utils import timezone


class SoftDeleteService:

    @staticmethod
    def delete(instance, user=None):
        if instance.is_deleted:
            return instance

        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = user

        instance.save(
            update_fields=[
                "is_deleted",
                "deleted_at",
                "deleted_by",
                "updated_at",
            ]
        )

        return instance
