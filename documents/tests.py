import base64
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from user.models import User
from documents.tasks import store_document_file
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken

from docvault.asgi import application
from documents import const
from .models import Document
from .notifications import DocumentNotification

IMAGE_CONTENT = b"fake-image-content"


def make_image(name="test.png"):
    return SimpleUploadedFile(name, IMAGE_CONTENT, content_type="image/png")


class DocumentTestMixin:
    """Tests use the real MinIO bucket (run them inside Docker), so files are removed after each test."""

    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="pass12345", role=User.Role.ADMIN)
        self.editor = User.objects.create_user(username="editor", password="pass12345", role=User.Role.EDITOR)
        self.viewer = User.objects.create_user(username="viewer", password="pass12345", role=User.Role.VIEWER)
        self.list_url = reverse("document-list")

    def tearDown(self):
        for document in Document.objects.all():
            if document.file:
                document.file.delete(save=False)

    def create_document(self, title="doc", user=None):
        """A ready document with a file in MinIO."""
        return Document.objects.create(
            title=title, file=make_image(), uploaded_by=user or self.admin, status=Document.Status.READY
        )


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

        # the file is sent to the worker, not stored in the request
        mock_apply_async.assert_called_once()
        document_id, file_content, file_name = mock_apply_async.call_args.kwargs["args"]
        self.assertEqual(document_id, document.id)
        self.assertEqual(base64.b64decode(file_content), IMAGE_CONTENT)
        self.assertEqual(file_name, "test.png")

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

    # --- delete ---
    def test_editor_cannot_delete(self, mock_apply_async):
        document = self.create_document()
        self.client.force_authenticate(self.editor)
        response = self.client.delete(reverse("document-detail", args=[document.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_delete(self, mock_apply_async):
        document = self.create_document()
        file_name = document.file.name
        self.client.force_authenticate(self.admin)
        response = self.client.delete(reverse("document-detail", args=[document.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Document.objects.exists())
        self.assertFalse(document.file.storage.exists(file_name))  # removed from MinIO

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
        file_content = base64.b64encode(IMAGE_CONTENT).decode()
        store_document_file(document.id, file_content, "photo.png")

        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.READY)
        self.assertTrue(document.file.name.startswith("documents/"))
        with document.file.open("rb") as f:
            self.assertEqual(f.read(), IMAGE_CONTENT)

    def test_task_replaces_old_file(self):
        document = self.create_document()
        old_file_name = document.file.name
        file_content = base64.b64encode(b"new-image").decode()
        store_document_file(document.id, file_content, "new.png")

        document.refresh_from_db()
        self.assertNotEqual(document.file.name, old_file_name)
        self.assertFalse(document.file.storage.exists(old_file_name))

    def test_task_with_deleted_document_does_nothing(self):
        store_document_file(999999, base64.b64encode(IMAGE_CONTENT).decode(), "photo.png")
        self.assertFalse(Document.objects.exists())


class DocumentWebSocketTests(TransactionTestCase):
    def setUp(self):
        user = User.objects.create_user(username="ali", password="pass12345")
        self.token = str(AccessToken.for_user(user))
        self.document = Document.objects.create(title="contract")

    async def test_connection_without_token_is_rejected(self):
        communicator = WebsocketCommunicator(application, "/ws/documents/")
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    async def test_connection_with_invalid_token_is_rejected(self):
        communicator = WebsocketCommunicator(application, "/ws/documents/?token=wrong")
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    async def test_logged_in_user_receives_notification(self):
        communicator = WebsocketCommunicator(application, f"/ws/documents/?token={self.token}")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await sync_to_async(DocumentNotification.send_document_event)(const.DOCUMENT_EVENT_CREATED, self.document)
        message = await communicator.receive_json_from()

        self.assertEqual(message["action"], const.DOCUMENT_EVENT_CREATED)
        self.assertEqual(message["title"], "contract")
        await communicator.disconnect()