from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    ADMIN = "admin", _("Admin")
    EDITOR = "editor", _("Editor")
    VIEWER = "viewer", _("Viewer")