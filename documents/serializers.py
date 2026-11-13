from django.core.validators import FileExtensionValidator
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from documents import const
from documents.models import Document


class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(
        write_only=True,
        validators=[FileExtensionValidator(const.ALLOWED_DOCUMENT_EXTENSIONS)],
    )
    uploaded_by = serializers.CharField(source="uploaded_by.username", read_only=True, default=None)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ["id", "title", "file", "status", "download_url", "uploaded_by", "created_at", "updated_at"]
        read_only_fields = ["status"]

    def validate_file(self, file):
        if file.size > const.MAX_DOCUMENT_SIZE:
            raise serializers.ValidationError(_("File size must be at most 10 MB."))
        return file

    def get_download_url(self, obj):
        # The real MinIO path is never exposed; the file is served by an authenticated endpoint.
        path = reverse("document-download", args=[obj.id])
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path
