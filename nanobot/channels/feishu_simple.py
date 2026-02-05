"""飞书自定义机器人 Channel（基于 Webhook）."""

from typing import Any

from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.channels.feishu_webhook import FeishuWebhookBot
from nanobot.config.schema import FeishuConfig


class FeishuWebhookChannel(BaseChannel):
    """
    飞书自定义机器人 Channel（基于 Webhook）.

    适用于简单的群消息推送场景，不需要接收消息。
    如果需要双向通信（接收+发送），请使用 FeishuChannel。
    """

    name = "feishu_webhook"

    def __init__(self, config: FeishuConfig, bus: MessageBus, webhook_url: str):
        """
        初始化飞书 Webhook Channel.

        Args:
            config: 飞书配置
            bus: 消息总线
            webhook_url: 飞书自定义机器人的 webhook URL
        """
        super().__init__(config, bus)
        self.webhook_url = webhook_url
        self._bot: FeishuWebhookBot | None = None

    async def start(self) -> None:
        """启动飞书 Webhook Channel."""
        self._running = True
        self._bot = FeishuWebhookBot(self.webhook_url)

        logger.info(f"飞书 Webhook Channel 已启动: {self.webhook_url[-20:]}")

        # 由于 webhook 模式只支持发送，不支持接收，
        # 这里我们只需要保持运行状态
        import asyncio
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """停止飞书 Webhook Channel."""
        self._running = False

        if self._bot:
            self._bot.close()
            self._bot = None

        logger.info("飞书 Webhook Channel 已停止")

    async def send(self, msg: OutboundMessage) -> None:
        """发送消息到飞书群聊."""
        if not self._bot:
            logger.warning("飞书 Webhook Bot 未初始化")
            return

        try:
            # 发送文本消息
            self._bot.send_text(msg.content)
            logger.debug(f"飞书消息已发送: {msg.content[:50]}...")
        except Exception as e:
            logger.error(f"发送飞书消息失败: {e}")

    async def send_markdown(self, title: str, content: str) -> None:
        """
        发送 Markdown 格式消息.

        Args:
            title: 消息标题
            content: Markdown 格式的内容
        """
        if not self._bot:
            logger.warning("飞书 Webhook Bot 未初始化")
            return

        try:
            self._bot.send_markdown(title, content)
            logger.debug(f"飞书 Markdown 消息已发送: {title}")
        except Exception as e:
            logger.error(f"发送飞书 Markdown 消息失败: {e}")
