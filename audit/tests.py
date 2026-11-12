from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from audit.models import AuditLog
from documents.models import Document


def make_image():
    return SimpleUploadedFile("test.png", b"fake-image-content", content_type="image/png")


class AuditLogTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="pass12345", role=User.Role.ADMIN)
        self.viewer = User.objects.create_user(username="viewer", password="pass12345", role=User.Role.VIEWER)
        self.document = Document.objects.create(
            title="contract", file=make_image(), uploaded_by=self.admin, status=Document.Status.READY
        )

    def tearDown(self):
        # remove test files from MinIO (soft deleted documents too)
        for document in Document.all_objects.all():
            if document.file:
                document.file.delete(save=False)

    def last_log(self):
        return AuditLog.objects.order_by("-id").first()

    @patch("documents.services.store_document_file.apply_async")
    def test_create_is_logged(self, mock_apply_async):
        self.client.force_authenticate(self.admin)
        self.client.post(reverse("document-list"), {"title": "new", "file": make_image()}, format="multipart")

        log = self.last_log()
        self.assertEqual(log.action, AuditLog.Action.CREATE)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.document_title, "new")

    def test_update_is_logged(self):
        self.client.force_authenticate(self.admin)
        self.client.patch(reverse("document-detail", args=[self.document.id]), {"title": "changed"})
        self.assertEqual(self.last_log().action, AuditLog.Action.UPDATE)

    def test_view_is_logged(self):
        self.client.force_authenticate(self.viewer)
        self.client.get(reverse("document-detail", args=[self.document.id]))

        log = self.last_log()
        self.assertEqual(log.action, AuditLog.Action.VIEW)
        self.assertEqual(log.user, self.viewer)

    def test_download_is_logged(self):
        self.client.force_authenticate(self.viewer)
        self.client.get(reverse("document-download", args=[self.document.id]))
        self.assertEqual(self.last_log().action, AuditLog.Action.DOWNLOAD)

    def test_log_is_kept_after_delete(self):
        self.client.force_authenticate(self.admin)
        self.client.delete(reverse("document-detail", args=[self.document.id]))

        log = self.last_log()
        self.assertEqual(log.action, AuditLog.Action.DELETE)
        self.assertEqual(log.document_id, self.document.id)
        self.assertEqual(log.document_title, "contract")

    def test_filter_by_action(self):
        self.client.force_authenticate(self.viewer)
        self.client.get(reverse("document-detail", args=[self.document.id]))
        self.client.get(reverse("document-download", args=[self.document.id]))

        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("audit-log-list"), {"action": AuditLog.Action.DOWNLOAD})
        self.assertEqual(response.data["count"], 1)

    def test_only_admin_can_read_logs(self):
        self.client.force_authenticate(self.viewer)
        response = self.client.get(reverse("audit-log-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("audit-log-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
