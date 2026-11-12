from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class AuditLog(models.Model):
    class Action(models.TextChoices):
        VIEW = "view", "View"
        DOWNLOAD = "download", "Download"
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=10, choices=Action.choices)
    # plain id + title (not a ForeignKey) so the log is kept after the document is deleted
    document_id = models.PositiveBigIntegerField()
    document_title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} {self.action} {self.document_title}"
