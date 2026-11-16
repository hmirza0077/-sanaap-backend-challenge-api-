from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.urls import reverse
from rest_framework import serializers

from documents import const
from documents.models import Document

User = get_user_model()


class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(
        write_only=True,
        validators=[FileExtensionValidator(const.ALLOWED_DOCUMENT_EXTENSIONS)],
    )
    uploaded_by = serializers.CharField(source="uploaded_by.username", read_only=True, default=None)
    shared_with = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "file",
            "status",
            "download_url",
            "uploaded_by",
            "shared_with",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status"]

    def get_shared_with(self, obj):
        return [share.user.username for share in obj.shares.all()]

    def get_download_url(self, obj):
        path = reverse("document-download", args=[obj.id])
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path


class DocumentShareSerializer(serializers.Serializer):
    username = serializers.SlugRelatedField(slug_field="username", queryset=User.objects.all())
