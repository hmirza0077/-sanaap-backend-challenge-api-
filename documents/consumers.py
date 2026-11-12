from channels.generic.websocket import AsyncJsonWebsocketConsumer

from documents import const


class DocumentConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # only logged-in users can listen
        if not self.scope["user"].is_authenticated:
            await self.close()
            return
        await self.channel_layer.group_add(const.DOCUMENTS_GROUP_NAME, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(const.DOCUMENTS_GROUP_NAME, self.channel_name)

    # called for messages sent with "type": "document.event"
    async def document_event(self, event):
        await self.send_json(event["data"])
