"""
WebSocket consumers.

Logs connection lifecycle so rejections are diagnosable.
"""

import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        user = self.scope.get("user")
        path = self.scope.get("path")

        if not user or not user.is_authenticated:
            logger.warning(
                "WS consumer: rejecting unauthenticated connection to %s", path
            )
            await self.close(code=4401)
            return

        self.group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "userId": str(user.id)})
        logger.info(
            "WS consumer: accepted user=%s group=%s channel=%s",
            user.university_id,
            self.group_name,
            self.channel_name,
        )

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(
                "WS consumer: disconnected group=%s code=%s",
                self.group_name,
                code,
            )

    async def notification_created(self, event):
        await self.send_json(
            {"type": "notification.created", "payload": event["payload"]}
        )

    async def grade_published(self, event):
        await self.send_json({"type": "grade.published", "payload": event["payload"]})

    async def announcement_published(self, event):
        await self.send_json(
            {"type": "announcement.published", "payload": event["payload"]}
        )

    async def discussion_post_created(self, event):
        await self.send_json(
            {"type": "discussion.post_created", "payload": event["payload"]}
        )
