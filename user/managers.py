from django.contrib.auth import models as auth_models
from common.models import SoftDeleteManager
from .choices import Role


class UserManager(SoftDeleteManager, auth_models.UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)