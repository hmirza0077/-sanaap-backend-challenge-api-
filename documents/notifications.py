from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from documents import const
from documents.models import DocumentShare


def user_group_name(user_id):
    return f"documents_user_{user_id}"


class DocumentNotification:
    @staticmethod
    def send_document_event(action, document):
        message = {
            "type": "document.event",
            "data": {
                "action": action,
                "id": document.id,
                "title": document.title,
                "status": document.status,
            },
        }

        user_ids = list(DocumentShare.objects.filter(document=document).values_list("user_id", flat=True))
        if document.uploaded_by_id:
            user_ids.append(document.uploaded_by_id)
        group_names = [user_group_name(user_id) for user_id in user_ids] + [const.ADMINS_GROUP_NAME]

        channel_layer = get_channel_layer()
        for group_name in group_names:
            async_to_sync(channel_layer.group_send)(group_name, message)
