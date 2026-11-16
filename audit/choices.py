from django.db import models
from django.utils.translation import gettext_lazy as _


class Action(models.TextChoices):
    VIEW = "view", "View"
    DOWNLOAD = "download", "Download"
    CREATE = "create", "Create"
    UPDATE = "update", "Update"
    DELETE = "delete", "Delete"
    SHARE = "share", "Share"
    UNSHARE = "unshare", "Unshare"