import logging

from celery import shared_task

from documents import const
from documents.models import Document
from documents.notifications import DocumentNotification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=const.STORE_FILE_MAX_RETRIES, default_retry_delay=const.STORE_FILE_RETRY_DELAY)
def store_document_file(self, document_id):
    from documents.services import DocumentService

    logger.info(f"Store file for document {document_id} Starts.")
    document = Document.objects.filter(id=document_id).first()
    if not document:
        logger.warning(f"Document {document_id} not found.")
        return

    try:
        DocumentService(document).store_file()
    except Exception as exc:
        if self.request.retries < self.max_retries:
            logger.warning(f"Store file for document {document_id} Failed, retry {self.request.retries + 1}.")
            raise self.retry(exc=exc)

        logger.exception(f"Store file for document {document_id} Failed after {self.max_retries} retries.")
        DocumentService(document).mark_failed()
        DocumentNotification.send_document_event(const.DOCUMENT_EVENT_UPDATED, document)
        return

    DocumentNotification.send_document_event(const.DOCUMENT_EVENT_UPDATED, document)
    logger.info(f"Store file for document {document_id} Complete.")
