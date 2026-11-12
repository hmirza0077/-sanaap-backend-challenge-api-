from django.core.cache import cache
from django.core.files.base import ContentFile

from documents import const
from documents.models import Document
from documents.tasks import store_document_file


class DocumentService:
    def __init__(self, document):
        self.document = document
        # the uploaded file waits here (Redis) until the worker stores it in MinIO
        self.cache_key = f"document_pending_file_{document.id}"

    def queue_file_storage(self, uploaded_file):
        """The request returns right away; the Celery worker stores the file in MinIO."""
        pending_file = {"name": uploaded_file.name, "content": uploaded_file.read()}
        cache.set(self.cache_key, pending_file, timeout=const.PENDING_FILE_TIMEOUT)
        self._send_to_worker()

    def retry_file_storage(self):
        """Called by the user after a failed upload. Returns False if the file is no longer in Redis."""
        if cache.get(self.cache_key) is None:
            return False
        self._send_to_worker()
        return True

    def store_file(self):
        pending_file = cache.get(self.cache_key)
        if pending_file is None:
            raise ValueError(f"Pending file of document {self.document.id} was not found in cache.")

        old_file_name = self.document.file.name

        self.document.file.save(pending_file["name"], ContentFile(pending_file["content"]), save=False)
        self.document.status = Document.Status.READY
        self.document.save(update_fields=["file", "status", "updated_at"])
        cache.delete(self.cache_key)

        # on update, the old file is no longer needed
        if old_file_name:
            self.document.file.storage.delete(old_file_name)

    def mark_failed(self):
        # the file stays in Redis, so the user can retry
        self.document.status = Document.Status.FAILED
        self.document.save(update_fields=["status", "updated_at"])

    def _send_to_worker(self):
        self.document.status = Document.Status.PENDING
        self.document.save(update_fields=["status", "updated_at"])
        store_document_file.apply_async(args=[self.document.id])
