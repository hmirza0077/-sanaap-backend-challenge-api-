from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from user.models import User
from user.choices import Role
from documents import const
from documents.models import Document
from documents.services import DocumentService
from documents.tasks import store_document_file

IMAGE_CONTENT = b"fake-image-content"


def make_image(name="test.png"):
    return SimpleUploadedFile(name, IMAGE_CONTENT, content_type="image/png")


class DocumentTestMixin:
    """Tests use the real MinIO bucket and Redis (run them inside Docker), so they are cleaned after each test."""

    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="pass12345", role=Role.ADMIN)
        self.editor = User.objects.create_user(username="editor", password="pass12345", role=Role.EDITOR)
        self.viewer = User.objects.create_user(username="viewer", password="pass12345", role=Role.VIEWER)
        self.list_url = reverse("document-list")

    def tearDown(self):
        for document in Document.all_objects.all():
            cache.delete(DocumentService(document).cache_key)
            if document.file:
                document.file.delete(save=False)

    def create_document(self, title="doc", user=None):
        """A ready document with a file in MinIO."""
        return Document.objects.create(
            title=title, file=make_image(), uploaded_by=user or self.admin, status=Document.Status.READY
        )

    def put_file_in_cache(self, document, content=IMAGE_CONTENT, name="photo.png"):
        """What queue_file_storage does before sending the task."""
        cache.set(DocumentService(document).cache_key, {"name": name, "content": content})


# apply_async is mocked: the API tests only check that the task is sent to the queue
@patch("documents.services.store_document_file.apply_async")
class DocumentAPITests(DocumentTestMixin, APITestCase):
    # --- authentication ---
    def test_anonymous_cannot_list(self, mock_apply_async):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- upload ---
    def test_editor_can_upload(self, mock_apply_async):
        self.client.force_authenticate(self.editor)
        response = self.client.post(self.list_url, {"title": "my doc", "file": make_image()}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = Document.objects.get()
        self.assertEqual(document.uploaded_by, self.editor)
        self.assertEqual(document.status, Document.Status.PENDING)

        # the file waits in Redis and only the document id is sent to the worker
        mock_apply_async.assert_called_once_with(args=[document.id])
        pending_file = cache.get(DocumentService(document).cache_key)
        self.assertEqual(pending_file["content"], IMAGE_CONTENT)
        self.assertEqual(pending_file["name"], "test.png")

    def test_viewer_cannot_upload(self, mock_apply_async):
        self.client.force_authenticate(self.viewer)
        response = self.client.post(self.list_url, {"title": "x", "file": make_image()}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_apply_async.assert_not_called()

    def test_invalid_file_type_is_rejected(self, mock_apply_async):
        self.client.force_authenticate(self.editor)
        bad_file = SimpleUploadedFile("script.exe", b"bad", content_type="application/octet-stream")
        response = self.client.post(self.list_url, {"title": "x", "file": bad_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_apply_async.assert_not_called()

    def test_large_file_is_rejected(self, mock_apply_async):
        self.client.force_authenticate(self.editor)
        big_file = SimpleUploadedFile("big.png", b"0" * (const.MAX_DOCUMENT_SIZE + 1), content_type="image/png")
        response = self.client.post(self.list_url, {"title": "x", "file": big_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data)
        mock_apply_async.assert_not_called()

    # --- update ---
    def test_editor_can_update_title(self, mock_apply_async):
        document = self.create_document()
        self.client.force_authenticate(self.editor)
        response = self.client.patch(reverse("document-detail", args=[document.id]), {"title": "new title"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        document.refresh_from_db()
        self.assertEqual(document.title, "new title")
        mock_apply_async.assert_not_called()

    def test_update_with_new_file_goes_to_queue(self, mock_apply_async):
        document = self.create_document()
        self.client.force_authenticate(self.editor)
        url = reverse("document-detail", args=[document.id])
        self.client.patch(url, {"file": make_image("new.png")}, format="multipart")

        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.PENDING)
        mock_apply_async.assert_called_once()

    def test_viewer_cannot_update(self, mock_apply_async):
        document = self.create_document()
        self.client.force_authenticate(self.viewer)
        response = self.client.patch(reverse("document-detail", args=[document.id]), {"title": "x"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_status_cannot_be_set_by_client(self, mock_apply_async):
        document = Document.objects.create(title="waiting", uploaded_by=self.admin)  # status = pending
        self.client.force_authenticate(self.editor)
        self.client.patch(reverse("document-detail", args=[document.id]), {"status": "ready"})

        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.PENDING)

    # --- delete (soft) ---
    def test_editor_cannot_delete(self, mock_apply_async):
        document = self.create_document()
        self.client.force_authenticate(self.editor)
        response = self.client.delete(reverse("document-detail", args=[document.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_delete_is_soft(self, mock_apply_async):
        document = self.create_document()
        self.client.force_authenticate(self.admin)
        response = self.client.delete(reverse("document-detail", args=[document.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # hidden from the API ...
        self.assertFalse(Document.objects.exists())
        response = self.client.get(reverse("document-detail", args=[document.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # ... but the row and the file are kept
        deleted_document = Document.all_objects.get(id=document.id)
        self.assertTrue(deleted_document.is_deleted)
        self.assertEqual(deleted_document.deleted_by, self.admin)
        self.assertIsNotNone(deleted_document.deleted_at)
        self.assertTrue(document.file.storage.exists(document.file.name))

    # --- read / download ---
    def test_viewer_can_download(self, mock_apply_async):
        document = self.create_document()
        self.client.force_authenticate(self.viewer)
        response = self.client.get(reverse("document-download", args=[document.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(response.streaming_content), IMAGE_CONTENT)

    def test_pending_document_cannot_be_downloaded(self, mock_apply_async):
        document = Document.objects.create(title="waiting", uploaded_by=self.admin)  # status = pending
        self.client.force_authenticate(self.viewer)
        response = self.client.get(reverse("document-download", args=[document.id]))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_anonymous_cannot_download(self, mock_apply_async):
        document = self.create_document()
        response = self.client.get(reverse("document-download", args=[document.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_storage_path_is_not_exposed(self, mock_apply_async):
        self.create_document()
        self.client.force_authenticate(self.viewer)
        item = self.client.get(self.list_url).data["results"][0]

        self.assertNotIn("file", item)
        self.assertIn("/download/", item["download_url"])

    # --- retry a failed upload ---
    def test_editor_can_retry_failed_upload(self, mock_apply_async):
        document = Document.objects.create(title="broken", uploaded_by=self.editor, status=Document.Status.FAILED)
        self.put_file_in_cache(document)
        self.client.force_authenticate(self.editor)
        response = self.client.post(reverse("document-retry", args=[document.id]))

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.PENDING)
        mock_apply_async.assert_called_once_with(args=[document.id])

    def test_retry_when_file_expired(self, mock_apply_async):
        document = Document.objects.create(title="broken", uploaded_by=self.editor, status=Document.Status.FAILED)
        self.client.force_authenticate(self.editor)
        response = self.client.post(reverse("document-retry", args=[document.id]))

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        mock_apply_async.assert_not_called()

    def test_only_failed_upload_can_be_retried(self, mock_apply_async):
        document = self.create_document()  # status = ready
        self.client.force_authenticate(self.editor)
        response = self.client.post(reverse("document-retry", args=[document.id]))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        mock_apply_async.assert_not_called()

    def test_viewer_cannot_retry(self, mock_apply_async):
        document = Document.objects.create(title="broken", uploaded_by=self.editor, status=Document.Status.FAILED)
        self.client.force_authenticate(self.viewer)
        response = self.client.post(reverse("document-retry", args=[document.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- filter & pagination (documents without files, so nothing is sent to MinIO) ---
    def test_filter_by_title(self, mock_apply_async):
        Document.objects.create(title="invoice 2026", uploaded_by=self.admin)
        Document.objects.create(title="contract", uploaded_by=self.admin)
        self.client.force_authenticate(self.viewer)
        response = self.client.get(self.list_url, {"title": "invoice"})

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "invoice 2026")

    def test_filter_by_uploader(self, mock_apply_async):
        Document.objects.create(title="a", uploaded_by=self.admin)
        Document.objects.create(title="b", uploaded_by=self.editor)
        self.client.force_authenticate(self.viewer)
        response = self.client.get(self.list_url, {"uploaded_by": "editor"})
        self.assertEqual(response.data["count"], 1)

    def test_pagination(self, mock_apply_async):
        for i in range(12):
            Document.objects.create(title=f"doc {i}", uploaded_by=self.admin)
        self.client.force_authenticate(self.viewer)
        response = self.client.get(self.list_url)

        self.assertEqual(response.data["count"], 12)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["next"])


class StoreDocumentFileTaskTests(DocumentTestMixin, APITestCase):
    """The Celery task is called directly here, like the worker would call it."""

    def test_task_stores_file_in_minio(self):
        document = Document.objects.create(title="waiting", uploaded_by=self.admin)  # status = pending
        self.put_file_in_cache(document)
        store_document_file(document.id)

        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.READY)
        self.assertTrue(document.file.name.startswith("documents/"))
        with document.file.open("rb") as f:
            self.assertEqual(f.read(), IMAGE_CONTENT)
        # the file is removed from Redis after it is stored
        self.assertIsNone(cache.get(DocumentService(document).cache_key))

    def test_task_replaces_old_file(self):
        document = self.create_document()
        old_file_name = document.file.name
        self.put_file_in_cache(document, content=b"new-image", name="new.png")
        store_document_file(document.id)

        document.refresh_from_db()
        self.assertNotEqual(document.file.name, old_file_name)
        self.assertFalse(document.file.storage.exists(old_file_name))

    def test_task_with_deleted_document_does_nothing(self):
        store_document_file(999999)
        self.assertFalse(Document.objects.exists())

    @patch("documents.services.DocumentService.store_file", side_effect=ConnectionError("MinIO is down"))
    def test_task_retries_then_marks_failed(self, mock_store_file):
        document = Document.objects.create(title="waiting", uploaded_by=self.admin)
        self.put_file_in_cache(document)
        # apply() runs the task here; its retries also run here, one after another
        store_document_file.apply(args=[document.id])

        self.assertEqual(mock_store_file.call_count, const.STORE_FILE_MAX_RETRIES + 1)
        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.FAILED)
        # the file is kept in Redis, so the user can retry
        self.assertIsNotNone(cache.get(DocumentService(document).cache_key))

    # --- WebSocket notification when the worker is done ---
    @patch("documents.tasks.DocumentNotification.send_document_event")
    def test_task_sends_notification_when_ready(self, mock_send):
        document = Document.objects.create(title="waiting", uploaded_by=self.admin)
        self.put_file_in_cache(document)
        store_document_file(document.id)

        mock_send.assert_called_once()
        action, sent_document = mock_send.call_args.args
        self.assertEqual(action, const.DOCUMENT_EVENT_UPDATED)
        self.assertEqual(sent_document.id, document.id)
        self.assertEqual(sent_document.status, Document.Status.READY)

    @patch("documents.tasks.DocumentNotification.send_document_event")
    @patch("documents.services.DocumentService.store_file", side_effect=ConnectionError("MinIO is down"))
    def test_task_sends_notification_when_failed(self, mock_store_file, mock_send):
        document = Document.objects.create(title="waiting", uploaded_by=self.admin)
        self.put_file_in_cache(document)
        store_document_file.apply(args=[document.id])

        # only once, after the last retry (not on every retry)
        mock_send.assert_called_once()
        action, sent_document = mock_send.call_args.args
        self.assertEqual(action, const.DOCUMENT_EVENT_UPDATED)
        self.assertEqual(sent_document.status, Document.Status.FAILED)
