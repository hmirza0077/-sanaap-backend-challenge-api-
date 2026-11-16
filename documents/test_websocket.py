from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken

from user.models import User
from user.choices import Role
from docvault.asgi import application
from documents import const
from documents.models import Document, DocumentShare
from documents.notifications import DocumentNotification


class DocumentWebSocketTests(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="ali", password="pass12345", role=Role.EDITOR)
        self.shared_user = User.objects.create_user(username="sara", password="pass12345")
        self.other_user = User.objects.create_user(username="reza", password="pass12345")
        self.admin = User.objects.create_user(username="admin", password="pass12345", role=Role.ADMIN)

        self.document = Document.objects.create(title="contract", uploaded_by=self.owner)
        DocumentShare.objects.create(document=self.document, user=self.shared_user, shared_by=self.owner)

    async def connect(self, user):
        token = str(AccessToken.for_user(user))
        communicator = WebsocketCommunicator(application, f"/ws/documents/?token={token}")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        return communicator

    async def send_event(self):
        await sync_to_async(DocumentNotification.send_document_event)(const.DOCUMENT_EVENT_CREATED, self.document)

    async def test_connection_without_token_is_rejected(self):
        communicator = WebsocketCommunicator(application, "/ws/documents/")
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    async def test_connection_with_invalid_token_is_rejected(self):
        communicator = WebsocketCommunicator(application, "/ws/documents/?token=wrong")
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    async def test_owner_shared_user_and_admin_receive_notification(self):
        communicators = [await self.connect(user) for user in (self.owner, self.shared_user, self.admin)]
        await self.send_event()

        for communicator in communicators:
            message = await communicator.receive_json_from()
            self.assertEqual(message["action"], const.DOCUMENT_EVENT_CREATED)
            self.assertEqual(message["title"], "contract")
            await communicator.disconnect()

    async def test_other_user_does_not_receive_notification(self):
        communicator = await self.connect(self.other_user)
        await self.send_event()

        self.assertTrue(await communicator.receive_nothing())
        await communicator.disconnect()
