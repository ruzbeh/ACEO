"""Email tools — send transactional emails via Resend API.

Uses the same mock-fallback pattern as stripe_tools.py and facebook_tools.py:
if RESEND_API_KEY is not configured, returns a mock response describing what would happen.
"""
from __future__ import annotations

import logging
from typing import Any

from aeco.config import settings

logger = logging.getLogger(__name__)

_RESEND_API_URL = "https://api.resend.com/emails"

# Built-in email templates
_TEMPLATES: dict[str, dict[str, str]] = {
    "welcome": {
        "subject": "Welcome to {{APP_NAME}}!",
        "html": (
            "<h1>Welcome to {{APP_NAME}}!</h1>"
            "<p>Thanks for signing up. You're all set to get started.</p>"
            "<p><a href='{{APP_URL}}/dashboard'>Go to your dashboard</a></p>"
        ),
    },
    "receipt": {
        "subject": "Payment receipt — {{APP_NAME}}",
        "html": (
            "<h1>Payment confirmed</h1>"
            "<p>Amount: ${{AMOUNT}}</p>"
            "<p>Thank you for your purchase!</p>"
        ),
    },
    "password_reset": {
        "subject": "Reset your password — {{APP_NAME}}",
        "html": (
            "<h1>Password Reset</h1>"
            "<p>Click the link below to reset your password:</p>"
            "<p><a href='{{RESET_URL}}'>Reset Password</a></p>"
            "<p>If you didn't request this, ignore this email.</p>"
        ),
    },
}


def _substitute(text: str, variables: dict[str, str]) -> str:
    result = text
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result


async def email_send(
    to: str,
    subject: str,
    body: str,
    from_email: str | None = None,
) -> dict[str, Any]:
    """Send a transactional email via Resend API.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body (HTML supported)
        from_email: Sender email (defaults to config)
    """
    api_key = getattr(settings, "resend_api_key", None)
    sender = from_email or getattr(settings, "resend_from_email", "onboarding@resend.dev")

    if not api_key:
        logger.info(f"[MOCK] email_send to={to} subject={subject}")
        return {
            "status": "mock",
            "message": "RESEND_API_KEY not configured. Email would be sent.",
            "to": to,
            "subject": subject,
            "from": sender,
        }

    import httpx

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                _RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": sender,
                    "to": [to],
                    "subject": subject,
                    "html": body,
                },
            )
            data = response.json()

            if response.status_code in (200, 201):
                return {
                    "status": "ok",
                    "email_id": data.get("id"),
                    "to": to,
                    "subject": subject,
                }
            else:
                return {
                    "status": "error",
                    "error": data.get("message", f"HTTP {response.status_code}"),
                    "to": to,
                }
    except Exception as e:
        return {"status": "error", "error": str(e), "to": to}


async def email_send_template(
    to: str,
    template: str,
    variables: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Send a templated email via Resend.

    Args:
        to: Recipient email address
        template: Template name (welcome, receipt, password_reset)
        variables: Template variables (e.g. {"APP_NAME": "Headshot AI", "APP_URL": "https://..."})
    """
    if template not in _TEMPLATES:
        return {
            "status": "error",
            "error": f"Unknown template '{template}'. Available: {list(_TEMPLATES.keys())}",
        }

    tmpl = _TEMPLATES[template]
    variables = variables or {}
    subject = _substitute(tmpl["subject"], variables)
    body = _substitute(tmpl["html"], variables)

    return await email_send(to=to, subject=subject, body=body)
