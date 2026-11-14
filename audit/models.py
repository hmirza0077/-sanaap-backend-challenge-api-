from django.contrib.auth import get_user_model
from django.db import models
from .choices import Action

User = get_user_model()


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=10, choices=Action.choices)
    document_id = models.PositiveBigIntegerField()
    document_title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} {self.action} {self.document_title}"
