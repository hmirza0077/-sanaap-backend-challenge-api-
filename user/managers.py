from django.contrib.auth import models as auth_models
from common.models import SoftDeleteManager
from .choices import Role


class UserManager(SoftDeleteManager, auth_models.UserManager):
    """Django's UserManager (create_user, ...) without deleted users, so they cannot log in."""
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # a superuser (createsuperuser) gets the admin role, so the role field shows the real access
        extra_fields.setdefault("role", Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)