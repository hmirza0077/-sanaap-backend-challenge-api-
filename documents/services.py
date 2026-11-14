import os

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from minio import Minio

from common.services import SoftDeleteService
from documents import const
from documents.models import DocumentShare
from documents.tasks import store_document_file
from documents.choices import Status

minio_external_client = Minio(
    settings.MINIO_EXTERNAL_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_EXTERNAL_ENDPOINT_USE_HTTPS,
    region=settings.MINIO_REGION,
)


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

    def get_download_url(self):
        filename = os.path.basename(self.document.file.name)
        return minio_external_client.presigned_get_object(
            settings.MINIO_APP_PRIVATE_BUCKET,
            self.document.file.name,
            expires=const.DOWNLOAD_URL_EXPIRY,
            response_headers={"response-content-disposition": f'attachment; filename="{filename}"'},
        )

    def share(self, user, shared_by):
        DocumentShare.objects.get_or_create(document=self.document, user=user, defaults={"shared_by": shared_by})

    def unshare(self, user, unshared_by):
        share = DocumentShare.objects.filter(document=self.document, user=user).first()
        if share:
            SoftDeleteService.delete(share, unshared_by)

    def _send_to_worker(self):
        self.document.status = Status.PENDING
        self.document.save(update_fields=["status", "updated_at"])
        store_document_file.apply_async(args=[self.document.id])
