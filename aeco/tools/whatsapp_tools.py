"""WhatsApp Business API tools for notifications.

Uses the Meta WhatsApp Cloud API to send notifications to the founder
when important events happen (approvals needed, initiatives completed,
budget alerts, etc).

When no token is configured, logs the message instead of sending.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from aeco.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://graph.facebook.com/v19.0"


def _get_config() -> tuple[str | None, str, str]:
    """Return (token, phone_number_id, recipient_number) or (None, ...) if not configured."""
    token = getattr(settings, "whatsapp_token", None) or None
    phone_id = getattr(settings, "whatsapp_phone_number_id", "") or ""
    recipient = getattr(settings, "whatsapp_recipient_number", "") or ""
    return token, phone_id, recipient


async def whatsapp_send_message(**kwargs: Any) -> dict:
    """Send a text message via WhatsApp to the founder."""
    message = kwargs.get("message", "")
    if not message:
        return {"error": "No message provided"}

    token, phone_id, recipient = _get_config()

    if not token or not phone_id or not recipient:
        logger.info(f"[WhatsApp] (not configured) Would send: {message[:200]}")
        return {
            "mock": True,
            "message": f"[NOT CONFIGURED] Would send to WhatsApp: {message[:200]}",
            "hint": "Set WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_RECIPIENT_NUMBER in .env",
        }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_BASE_URL}/{phone_id}/messages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "text",
                    "text": {"body": message},
                },
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"WhatsApp message sent: {message[:100]}")
            return {"sent": True, "message_id": result.get("messages", [{}])[0].get("id")}
    except Exception as e:
        logger.error(f"WhatsApp send failed: {e}")
        return {"error": str(e), "sent": False}


async def whatsapp_send_approval_request(**kwargs: Any) -> dict:
    """Send a formatted approval request notification via WhatsApp."""
    title = kwargs.get("title", "Unknown")
    action = kwargs.get("action", "fund")
    budget = kwargs.get("budget", 0)
    reasoning = kwargs.get("reasoning", "")
    blast_radius = kwargs.get("blast_radius", "unknown")

    message = (
        f"🔔 *AECO Approval Required*\n\n"
        f"*Action:* {action.upper()} — {title}\n"
        f"*Budget:* ${budget:.2f}\n"
        f"*Blast Radius:* {blast_radius}\n"
        f"*Reasoning:* {reasoning[:300]}\n\n"
        f"Open the AECO dashboard to approve or reject."
    )

    return await whatsapp_send_message(message=message)


async def whatsapp_send_portfolio_update(**kwargs: Any) -> dict:
    """Send a portfolio cycle status update via WhatsApp."""
    phase = kwargs.get("phase", "")
    cycle = kwargs.get("cycle", 0)
    opportunities = kwargs.get("opportunities", 0)
    funded = kwargs.get("funded", 0)
    killed = kwargs.get("killed", 0)
    budget_spent = kwargs.get("budget_spent", 0)

    message = (
        f"📊 *AECO Portfolio Update*\n\n"
        f"*Phase:* {phase}\n"
        f"*Cycle:* {cycle}\n"
        f"*Opportunities found:* {opportunities}\n"
        f"*Initiatives funded:* {funded}\n"
        f"*Initiatives killed:* {killed}\n"
        f"*Budget spent:* ${budget_spent:.2f}"
    )

    return await whatsapp_send_message(message=message)


async def whatsapp_send_alert(**kwargs: Any) -> dict:
    """Send an urgent alert via WhatsApp."""
    alert_type = kwargs.get("alert_type", "general")
    severity = kwargs.get("severity", "info")
    message_text = kwargs.get("message", "")

    emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(severity, "📌")

    message = (
        f"{emoji} *AECO Alert: {alert_type}*\n\n"
        f"*Severity:* {severity.upper()}\n"
        f"{message_text}"
    )

    return await whatsapp_send_message(message=message)
