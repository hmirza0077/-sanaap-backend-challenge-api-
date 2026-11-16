from common.models import BaseModel
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Notification(BaseModel):

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(
        auto_now_add=True
    )