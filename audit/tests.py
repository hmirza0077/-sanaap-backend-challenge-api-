from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from user.models import User
from user.choices import Role
from audit.models import AuditLog
from audit.choices import Action
from documents.models import Document, DocumentShare
from documents.choices import Status


def make_image():
    return SimpleUploadedFile("test.png", b"fake-image-content", content_type="image/png")


class AuditLogTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="pass12345", role=Role.ADMIN)
        self.viewer = User.objects.create_user(username="viewer", password="pass12345", role=Role.VIEWER)
        self.document = Document.objects.create(
            title="contract", file=make_image(), uploaded_by=self.admin, status=Status.READY
        )
        # the viewer can only see documents shared with them
        DocumentShare.objects.create(document=self.document, user=self.viewer, shared_by=self.admin)

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
        self.assertEqual(log.action, Action.CREATE)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.document_title, "new")

    def test_update_is_logged(self):
        self.client.force_authenticate(self.admin)
        self.client.patch(reverse("document-detail", args=[self.document.id]), {"title": "changed"})
        self.assertEqual(self.last_log().action, Action.UPDATE)

    def test_view_is_logged(self):
        self.client.force_authenticate(self.viewer)
        self.client.get(reverse("document-detail", args=[self.document.id]))

        log = self.last_log()
        self.assertEqual(log.action, Action.VIEW)
        self.assertEqual(log.user, self.viewer)

    def test_download_is_logged(self):
        self.client.force_authenticate(self.viewer)
        self.client.get(reverse("document-download", args=[self.document.id]))
        self.assertEqual(self.last_log().action, Action.DOWNLOAD)

    def test_log_is_kept_after_delete(self):
        self.client.force_authenticate(self.admin)
        self.client.delete(reverse("document-detail", args=[self.document.id]))

        log = self.last_log()
        self.assertEqual(log.action, Action.DELETE)
        self.assertEqual(log.document_id, self.document.id)
        self.assertEqual(log.document_title, "contract")

    def test_share_and_unshare_are_logged(self):
        self.client.force_authenticate(self.admin)
        self.client.post(reverse("document-unshare", args=[self.document.id]), {"username": "viewer"})
        self.assertEqual(self.last_log().action, Action.UNSHARE)

        self.client.post(reverse("document-share", args=[self.document.id]), {"username": "viewer"})
        self.assertEqual(self.last_log().action, Action.SHARE)

    def test_filter_by_action(self):
        self.client.force_authenticate(self.viewer)
        self.client.get(reverse("document-detail", args=[self.document.id]))
        self.client.get(reverse("document-download", args=[self.document.id]))

        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("audit-log-list"), {"action": Action.DOWNLOAD})
        self.assertEqual(response.data["count"], 1)

    def test_only_admin_can_read_logs(self):
        self.client.force_authenticate(self.viewer)
        response = self.client.get(reverse("audit-log-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("audit-log-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
