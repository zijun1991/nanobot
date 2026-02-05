"""飞书 channel 实现."""

import asyncio
import hashlib
import hmac
import json
import time
from typing import Any

import httpx
from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import FeishuConfig


class FeishuChannel(BaseChannel):
    """
    飞书 channel 实现。

    使用飞书机器人的 Webhook 方式接收消息，
    通过飞书 API 发送消息。
    """

    name = "feishu"

    def __init__(self, config: FeishuConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: FeishuConfig = config
        self._access_token: str | None = None
        self._token_expires_at: int = 0
        self._webhook_server: Any = None
        self._http_client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """启动飞书 channel."""
        if not self.config.app_id or not self.config.app_secret:
            logger.error("飞书 App ID 和 Secret 未配置")
            return

        self._running = True
        self._http_client = httpx.AsyncClient(timeout=30.0)

        # 获取初始 access token
        await self._refresh_access_token()

        # 启动 webhook 服务器和 token 刷新任务
        tasks = [
            asyncio.create_task(self._start_webhook_server()),
            asyncio.create_task(self._refresh_token_loop()),
        ]

        # 等待所有任务完成（它们应该一直运行）
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        """停止飞书 channel."""
        self._running = False

        if self._http_client:
            await self._http_client.aclose()

        if self._webhook_server:
            # 关闭 webhook 服务器
            if hasattr(self._webhook_server, 'shutdown'):
                await self._webhook_server.shutdown()
            if hasattr(self._webhook_server, 'wait_closed'):
                await self._webhook_server.wait_closed()

        logger.info("飞书 channel 已停止")

    async def send(self, msg: OutboundMessage) -> None:
        """通过飞书 API 发送消息."""
        if not self._access_token:
            logger.error("飞书 access token 未获取")
            return

        try:
            await self._send_message_via_api(msg.chat_id, msg.content)
        except Exception as e:
            logger.error(f"发送飞书消息失败: {e}")

    async def _start_webhook_server(self) -> None:
        """启动 webhook 服务器接收消息."""
        from aiohttp import web

        app = web.Application()
        app.router.add_post(
            self.config.webhook_path,
            self._handle_webhook_request
        )

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(
            runner,
            self.config.webhook_host,
            self.config.webhook_port
        )
        await site.start()

        self._webhook_server = runner

        logger.info(
            f"飞书 webhook 服务器已启动: "
            f"http://{self.config.webhook_host}:{self.config.webhook_port}"
            f"{self.config.webhook_path}"
        )

        # 保持运行
        while self._running:
            await asyncio.sleep(1)

    async def _handle_webhook_request(self, request: Any) -> Any:
        """处理飞书 webhook 请求."""
        from aiohttp import web

        try:
            # 验证签名
            if self.config.verify_token:
                timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
                nonce = request.headers.get("X-Lark-Request-Nonce", "")
                signature = request.headers.get("X-Lark-Signature", "")
                body = await request.read()

                if not self._verify_signature(timestamp, nonce, body, signature):
                    logger.warning("飞书 webhook 签名验证失败")
                    return web.Response(status=401)

            # 解析请求体
            body = await request.json()

            # 处理 URL 验证挑战
            if body.get("type") == "url_verification":
                challenge = body.get("challenge", "")
                return web.json_response({"challenge": challenge})

            # 处理消息事件
            if body.get("header", {}).get("event_type") == "im.message.receive_v1":
                await self._handle_message_event(body)

            return web.Response(status=200)

        except Exception as e:
            logger.error(f"处理飞书 webhook 请求失败: {e}")
            return web.Response(status=500)

    async def _handle_message_event(self, event: dict) -> None:
        """处理飞书消息事件."""
        try:
            event_data = event.get("event", {})
            message = event_data.get("message", {})
            sender = event_data.get("sender", {})

            sender_id = sender.get("sender_id", {}).get("open_id", "")
            chat_id = sender_id  # 飞书中使用 open_id 作为标识
            message_id = message.get("message_id", "")

            # 解析消息内容
            content_str = message.get("content", "")
            content_json = json.loads(content_str) if content_str else {}

            # 获取文本内容
            text_content = content_json.get("text", "")

            if not text_content:
                logger.debug(f"飞书消息 {message_id} 没有文本内容")
                return

            logger.debug(f"飞书消息来自 {sender_id}: {text_content[:50]}...")

            # 转发到消息总线
            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=text_content,
                media=None,
                metadata={
                    "message_id": message_id,
                    "msg_type": message.get("msg_type", ""),
                    "create_time": message.get("create_time", ""),
                }
            )

        except Exception as e:
            logger.error(f"处理飞书消息事件失败: {e}")

    async def _refresh_token_loop(self) -> None:
        """定期刷新 access token."""
        while self._running:
            try:
                # 计算刷新间隔（提前 5 分钟刷新）
                refresh_interval = max(60, (self._token_expires_at - int(time.time()) - 300))
                if refresh_interval > 0:
                    await asyncio.sleep(refresh_interval)
                else:
                    # token 已过期，立即刷新
                    await asyncio.sleep(10)

                await self._refresh_access_token()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"刷新飞书 access token 失败: {e}")
                await asyncio.sleep(60)  # 出错后等待 1 分钟再试

    async def _refresh_access_token(self) -> None:
        """刷新飞书的 access token."""
        if not self._http_client:
            return

        try:
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            data = {
                "app_id": self.config.app_id,
                "app_secret": self.config.app_secret
            }

            response = await self._http_client.post(url, json=data)
            result = response.json()

            if result.get("code") != 0:
                raise Exception(f"获取 token 失败: {result}")

            self._access_token = result.get("tenant_access_token")
            expire = result.get("expire", 7200)  # 默认 2 小时

            self._token_expires_at = int(time.time()) + expire

            logger.info("飞书 access token 已刷新")

        except Exception as e:
            logger.error(f"刷新飞书 access token 失败: {e}")
            raise

    async def _send_message_via_api(self, chat_id: str, content: str) -> None:
        """通过飞书 API 发送消息."""
        if not self._http_client or not self._access_token:
            return

        try:
            url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json"
            }

            # 构建消息内容（支持富文本）
            message_content = json.dumps({"text": content})

            data = {
                "receive_id": chat_id,
                "content": message_content,
                "msg_type": "text"
            }

            response = await self._http_client.post(url, headers=headers, json=data)
            result = response.json()

            if result.get("code") != 0:
                raise Exception(f"发送消息失败: {result}")

            logger.debug(f"飞书消息已发送到 {chat_id}")

        except Exception as e:
            logger.error(f"发送飞书消息失败: {e}")
            raise

    def _verify_signature(
        self,
        timestamp: str,
        nonce: str,
        body: bytes,
        signature: str
    ) -> bool:
        """
        验证飞书 webhook 签名.

        Args:
            timestamp: 请求时间戳
            nonce: 随机字符串
            body: 请求体（原始字节）
            signature: 请求签名

        Returns:
            验证是否通过
        """
        if not self.config.encrypt_key:
            # 如果没有配置加密密钥，跳过验证
            return True

        try:
            # 构建签名基础字符串
            sign_base = f"{timestamp}{nonce}{body.decode()}".encode('utf-8')

            # 计算 HMAC-SHA256 签名
            key = self.config.encrypt_key.encode('utf-8')
            computed_signature = hmac.new(
                key,
                sign_base,
                hashlib.sha256
            ).hexdigest()

            # 比对签名
            return hmac.compare_digest(computed_signature, signature)

        except Exception as e:
            logger.error(f"验证飞书签名失败: {e}")
            return False
