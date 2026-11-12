import base64
import logging

from celery import shared_task

from documents.models import Document

logger = logging.getLogger(__name__)


@shared_task
def store_document_file(document_id, file_content, file_name):
    """Runs in the Celery worker: stores the uploaded file in MinIO."""
    from documents.services import DocumentService

    logger.info(f"Store file for document {document_id} Starts.")
    document = Document.objects.filter(id=document_id).first()
    if not document:
        # the document was deleted before the worker got to it
        logger.warning(f"Document {document_id} not found.")
        return

    DocumentService(document).store_file(base64.b64decode(file_content), file_name)
    logger.info(f"Store file for document {document_id} Complete.")
