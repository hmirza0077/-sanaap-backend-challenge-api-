ALLOWED_DOCUMENT_EXTENSIONS = ["jpg", "jpeg", "png", "svg", "webp"]
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB, same as client_max_body_size in nginx

# Background storage
PENDING_FILE_TIMEOUT = 24 * 60 * 60  # the uploaded file is kept in Redis for 1 day, so a failed upload can be retried
STORE_FILE_MAX_RETRIES = 3  # automatic retries of the Celery task before the document is marked as failed
STORE_FILE_RETRY_DELAY = 10  # seconds between automatic retries

# WebSocket
DOCUMENTS_GROUP_NAME = "documents"  # every connected user joins this one group
DOCUMENT_EVENT_CREATED = "created"
DOCUMENT_EVENT_UPDATED = "updated"
