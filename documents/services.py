from django.core.cache import cache
from django.core.files.base import ContentFile

from documents import const
from documents.choices import Status
from documents.tasks import store_document_file


class DocumentService:
    def __init__(self, document):
        self.document = document
        self.cache_key = f"document_pending_file_{document.id}"

    def queue_file_storage(self, uploaded_file):
        pending_file = {"name": uploaded_file.name, "content": uploaded_file.read()}
        cache.set(self.cache_key, pending_file, timeout=const.PENDING_FILE_TIMEOUT)
        self._send_to_worker()

    def retry_file_storage(self):
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
        self.document.status = Status.READY
        self.document.save(update_fields=["file", "status", "updated_at"])
        cache.delete(self.cache_key)

        if old_file_name:
            self.document.file.storage.delete(old_file_name)

    def mark_failed(self):
        self.document.status = Status.FAILED
        self.document.save(update_fields=["status", "updated_at"])

    def _send_to_worker(self):
        self.document.status = Status.PENDING
        self.document.save(update_fields=["status", "updated_at"])
        store_document_file.apply_async(args=[self.document.id])
