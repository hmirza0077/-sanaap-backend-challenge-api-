import base64

from django.core.files.base import ContentFile

from documents.models import Document
from documents.tasks import store_document_file


class DocumentService:
    def __init__(self, document):
        self.document = document

    def queue_file_storage(self, uploaded_file):
        """The request returns right away; the Celery worker stores the file in MinIO."""
        # Celery messages are JSON, so the file bytes are sent as base64 text
        file_content = base64.b64encode(uploaded_file.read()).decode()
        store_document_file.apply_async(args=[self.document.id, file_content, uploaded_file.name])

    def store_file(self, file_content, file_name):
        old_file_name = self.document.file.name

        self.document.file.save(file_name, ContentFile(file_content), save=False)
        self.document.status = Document.Status.READY
        self.document.save(update_fields=["file", "status", "updated_at"])

        # on update, the old file is no longer needed
        if old_file_name:
            self.document.file.storage.delete(old_file_name)

    def delete_file(self):
        if self.document.file:
            self.document.file.delete(save=False)
