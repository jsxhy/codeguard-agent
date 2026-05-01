from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = settings.notification.enabled
        self._channels = settings.notification.channels

    async def send(self, title: str, message: str, data: Optional[dict[str, Any]] = None) -> None:
        if not self._enabled:
            logger.debug("Notifications disabled, skipping")
            return

        for channel in self._channels:
            channel_type = channel.get("type", "")
            try:
                if channel_type == "slack":
                    await self._send_slack(channel, title, message, data)
                elif channel_type == "email":
                    await self._send_email(channel, title, message, data)
                else:
                    logger.warning(f"Unknown notification channel type: {channel_type}")
            except Exception as e:
                logger.error(f"Failed to send notification via {channel_type}: {e}")

    async def _send_slack(
        self,
        channel: dict[str, Any],
        title: str,
        message: str,
        data: Optional[dict[str, Any]] = None,
    ) -> None:
        webhook_url = channel.get("webhook_url", "")
        if not webhook_url:
            return

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": title},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
        ]

        if data:
            fields = []
            for key, value in data.items():
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{key}:* {value}",
                })
            if fields:
                blocks.append({
                    "type": "section",
                    "fields": fields[:10],
                })

        payload = {"blocks": blocks}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()

        logger.info(f"Slack notification sent: {title}")

    async def _send_email(
        self,
        channel: dict[str, Any],
        title: str,
        message: str,
        data: Optional[dict[str, Any]] = None,
    ) -> None:
        smtp_host = channel.get("smtp_host", "")
        smtp_port = channel.get("smtp_port", 587)
        recipients = channel.get("recipients", [])

        if not smtp_host or not recipients:
            logger.warning("Email notification skipped: missing SMTP config or recipients")
            return

        logger.info(f"Email notification would be sent to {recipients}: {title}")

    async def notify_review_complete(
        self,
        review_id: str,
        pr_id: str,
        summary: dict[str, Any],
    ) -> None:
        critical = summary.get("critical", 0)
        warning = summary.get("warning", 0)
        total = summary.get("total_issues", 0)

        severity_emoji = "🔴" if critical > 0 else "🟡" if warning > 0 else "🟢"

        await self.send(
            title=f"{severity_emoji} 代码审查完成 - PR #{pr_id}",
            message=f"审查 ID: {review_id}\n发现问题: {total} 个",
            data={
                "Critical": critical,
                "Warning": warning,
                "Info": summary.get("info", 0),
                "规范违反": summary.get("compliance_violations", 0),
                "重构建议": summary.get("refactoring_items", 0),
            },
        )

    async def notify_debt_created(
        self,
        debt_id: str,
        title: str,
        priority: str,
        category: str,
    ) -> None:
        priority_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

        await self.send(
            title=f"{priority_emoji.get(priority, '⚪')} 新技术债 - {debt_id}",
            message=f"标题: {title}\n类别: {category}\n优先级: {priority}",
        )

    async def notify_debt_resolved(
        self,
        debt_id: str,
        title: str,
    ) -> None:
        await self.send(
            title=f"✅ 技术债已修复 - {debt_id}",
            message=f"标题: {title}",
        )
