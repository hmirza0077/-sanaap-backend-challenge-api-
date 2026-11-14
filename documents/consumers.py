from channels.generic.websocket import AsyncJsonWebsocketConsumer

from documents import const
from documents.notifications import user_group_name


class DocumentConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        self.group_name = None

        if not user.is_authenticated:
            await self.close()
            return

        self.group_name = const.ADMINS_GROUP_NAME if user.is_admin_role else user_group_name(user.id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def document_event(self, event):
        await self.send_json(event["data"])
