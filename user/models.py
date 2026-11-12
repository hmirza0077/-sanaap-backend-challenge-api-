from django.contrib.auth.models import AbstractUser
from django.db import models
from .choices import Role
from .managers import UserManager


class User(AbstractUser):
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)

    objects = UserManager()

    @property
    def is_admin_role(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_editor_role(self):
        return self.role == self.Role.EDITOR
