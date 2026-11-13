from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from documents import const


class DocumentNotification:
    @staticmethod
    def send_document_event(action, document):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            const.DOCUMENTS_GROUP_NAME,
            {
                "type": "document.event",
                "data": {
                    "action": action,
                    "id": document.id,
                    "title": document.title,
                    "status": document.status,
                },
            },
        )
