from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken

from docvault.asgi import application
from documents import const
from documents.models import Document
from documents.notifications import DocumentNotification
from user.models import User


# TransactionTestCase: the consumer reads the user in another thread (database_sync_to_async),
# so the data must be committed, not hidden inside the test transaction.
# Uses the real Redis channel layer (run inside Docker).
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

        # what the view sends after create / update
        await sync_to_async(DocumentNotification.send_document_event)(const.DOCUMENT_EVENT_CREATED, self.document)
        message = await communicator.receive_json_from()

        self.assertEqual(message["action"], const.DOCUMENT_EVENT_CREATED)
        self.assertEqual(message["id"], self.document.id)
        self.assertEqual(message["title"], "contract")
        await communicator.disconnect()
