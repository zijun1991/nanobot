"""飞书自定义机器人 Webhook 工具."""

import json
from typing import Any

import httpx


class FeishuWebhookBot:
    """
    飞书自定义机器人 Webhook 客户端.

    使用飞书群聊自定义机器人的 webhook URL 发送消息。
    适用于简单的消息推送场景。
    """

    def __init__(self, webhook_url: str):
        """
        初始化飞书自定义机器人.

        Args:
            webhook_url: 飞书自定义机器人的 webhook URL
        """
        self.webhook_url = webhook_url
        self._client = httpx.Client(timeout=10.0)

    def send_text(self, content: str) -> dict[str, Any]:
        """
        发送文本消息.

        Args:
            content: 消息文本内容

        Returns:
            API 响应结果
        """
        data = {
            "msg_type": "text",
            "content": {"text": content}
        }

        response = self._client.post(self.webhook_url, json=data)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"发送消息失败: {result}")

        return result

    def send_post(
        self,
        title: str,
        content: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        发送富文本/卡片消息.

        Args:
            title: 消息标题
            content: 内容列表，每个元素是一个标签对象

        Returns:
            API 响应结果

        Example:
            bot.send_post(
                title="每日报告",
                content=[
                    {"tag": "text", "text": "今日任务完成情况："},
                    {"tag": "text", "text": "✅ 完成功能开发"},
                ]
            )
        """
        data = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": [content]
                    }
                }
            }
        }

        response = self._client.post(self.webhook_url, json=data)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"发送消息失败: {result}")

        return result

    def send_card(self, card_content: dict[str, Any]) -> dict[str, Any]:
        """
        发送交互式卡片消息.

        Args:
            card_content: 卡片内容（符合飞书卡片规范的 JSON）

        Returns:
            API 响应结果

        Example:
            card = {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"content": "标题", "tag": "plain_text"}},
                "elements": [
                    {"tag": "div", "text": {"content": "内容", "tag": "lark_md"}}
                ]
            }
            bot.send_card(card)
        """
        data = {
            "msg_type": "interactive",
            "card": card_content
        }

        response = self._client.post(self.webhook_url, json=data)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"发送消息失败: {result}")

        return result

    def send_markdown(self, title: str, text: str) -> dict[str, Any]:
        """
        发送 Markdown 消息.

        Args:
            title: 消息标题
            text: Markdown 格式的文本内容

        Returns:
            API 响应结果
        """
        data = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "content": title,
                        "tag": "plain_text"
                    }
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "content": text,
                            "tag": "lark_md"
                        }
                    }
                ]
            }
        }

        response = self._client.post(self.webhook_url, json=data)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"发送消息失败: {result}")

        return result

    def close(self):
        """关闭 HTTP 客户端."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 便捷函数
def send_feishu_message(webhook_url: str, message: str) -> dict[str, Any]:
    """
    快速发送消息到飞书群聊.

    Args:
        webhook_url: 飞书 webhook URL
        message: 消息内容

    Returns:
        API 响应结果

    Example:
        result = send_feishu_message(
            "https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
            "Hello from nanobot!"
        )
    """
    with FeishuWebhookBot(webhook_url) as bot:
        return bot.send_text(message)
