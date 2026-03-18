"""Tests for ClickUp sync helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aeco.integrations.clickup.models import ClickUpTask
from aeco.integrations.clickup.sync import (
    CLICKUP_TO_AECO_STATUS,
    aeco_task_from_clickup_task,
    sync_task_from_clickup,
)
from aeco.models.task import Task, TaskStatus


class TestClickUpTaskStatusNormalization:
    """ClickUpTask model normalizes status from API (string or object)."""

    def test_status_string(self) -> None:
        t = ClickUpTask(id="1", name="x", status="to do")
        assert t.status == "to do"

    def test_status_dict(self) -> None:
        t = ClickUpTask(id="1", name="x", status={"status": "in progress"})
        assert t.status == "in progress"

    def test_status_none(self) -> None:
        t = ClickUpTask(id="1", name="x", status=None)
        assert t.status is None


class TestAecoTaskFromClickUpTask:
    def test_maps_name_and_description(self) -> None:
        cu = ClickUpTask(id="cu123", name="Feature X", description="Do the thing")
        task = aeco_task_from_clickup_task(cu)
        assert task.title == "Feature X"
        assert task.description == "Do the thing"
        assert task.clickup_task_id == "cu123"
        assert task.status == TaskStatus.TODO

    def test_maps_clickup_status(self) -> None:
        cu = ClickUpTask(id="1", name="x", status="complete")
        task = aeco_task_from_clickup_task(cu)
        assert task.status == TaskStatus.DONE

    def test_unknown_status_defaults_to_todo(self) -> None:
        cu = ClickUpTask(id="1", name="x", status="custom")
        task = aeco_task_from_clickup_task(cu)
        assert task.status == TaskStatus.TODO


class TestSyncTaskFromClickUp:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_aeco_task(self) -> None:
        from sqlalchemy.ext.asyncio import AsyncSession

        from aeco.integrations.clickup.client import ClickUpClient

        mock_client = AsyncMock(spec=ClickUpClient)
        mock_client.get_task = AsyncMock(
            return_value=ClickUpTask(id="cu1", name="CU Task", description="d")
        )
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        out = await sync_task_from_clickup("cu1", mock_client, mock_session)
        assert out is None
        mock_session.execute.assert_called_once()
        # get_task is not called when no AECO task exists
        mock_client.get_task.assert_not_called()
