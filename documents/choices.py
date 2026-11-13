from django.db import models
from django.utils.translation import gettext_lazy as _


class Status(models.TextChoices):
    PENDING = "pending", _("Pending")
    READY = "ready", _("Ready")
    FAILED = "failed", _("Failed")
