"""Tests for ClickUp webhook processing."""

from unittest.mock import AsyncMock, patch

import pytest

from aeco.integrations.clickup.webhooks import process_webhook_event


class TestProcessWebhookEvent:
    """Webhook event routing and skip conditions."""

    @pytest.mark.asyncio
    async def test_missing_task_id_returns_ignore(self) -> None:
        out = await process_webhook_event({"event": "taskCreated"})
        assert out["action"] == "ignore"
        assert "task_id" not in out or out.get("reason") == "missing task_id"

    @pytest.mark.asyncio
    async def test_unknown_event_returns_ignore(self) -> None:
        with patch("aeco.integrations.clickup.webhooks.settings") as mock_settings:
            mock_settings.clickup_api_token = "pk_xxx"
            out = await process_webhook_event(
                {"event": "unknownEvent", "task_id": "cu123"}
            )
        assert out["action"] == "ignore"
        assert out["event"] == "unknownEvent"

    @pytest.mark.asyncio
    async def test_no_token_returns_skip(self) -> None:
        with patch("aeco.integrations.clickup.webhooks.settings") as mock_settings:
            mock_settings.clickup_api_token = ""
            out = await process_webhook_event(
                {"event": "taskCreated", "task_id": "cu456"}
            )
        assert out["action"] == "skip"
        assert "clickup_api_token" in out.get("reason", "")
