"""Tests for ToolGateway permission checking."""
from __future__ import annotations

import pytest
import pytest_asyncio

from aeco.models.agent import AgentDefinition, LLMConfig
from aeco.tools.gateway import ToolGateway, ToolPermissionError


def _make_agent(
    agent_id: str = "test_agent",
    tools: list[str] | None = None,
    permissions: list[str] | None = None,
) -> AgentDefinition:
    return AgentDefinition(
        agent_id=agent_id,
        name="Test Agent",
        role="engineer",
        system_prompt_path="prompts/test.md",
        llm_config=LLMConfig(),
        tools=tools or [],
        permissions=permissions or [],
    )


async def _dummy_tool(**kwargs):
    return {"ok": True, **kwargs}


class TestToolGatewayPermissions:
    def test_agent_gets_only_permitted_tools(self) -> None:
        gw = ToolGateway()
        gw.register("file_read", _dummy_tool, required_permissions={"workspace:read"})
        gw.register("file_write", _dummy_tool, required_permissions={"workspace:write"})

        agent = _make_agent(
            tools=["file_read", "file_write"],
            permissions=["workspace:read"],
        )
        allowed = gw.get_tools_for_agent(agent)

        assert "file_read" in allowed
        assert "file_write" not in allowed

    def test_agent_with_all_permissions_gets_all_tools(self) -> None:
        gw = ToolGateway()
        gw.register("file_read", _dummy_tool, required_permissions={"workspace:read"})
        gw.register("file_write", _dummy_tool, required_permissions={"workspace:write"})

        agent = _make_agent(
            tools=["file_read", "file_write"],
            permissions=["workspace:read", "workspace:write"],
        )
        allowed = gw.get_tools_for_agent(agent)

        assert set(allowed.keys()) == {"file_read", "file_write"}

    def test_unregistered_tool_is_skipped(self) -> None:
        gw = ToolGateway()
        agent = _make_agent(tools=["nonexistent_tool"], permissions=[])
        allowed = gw.get_tools_for_agent(agent)

        assert allowed == {}

    def test_tool_with_no_required_permissions(self) -> None:
        gw = ToolGateway()
        gw.register("open_tool", _dummy_tool, required_permissions=None)

        agent = _make_agent(tools=["open_tool"], permissions=[])
        allowed = gw.get_tools_for_agent(agent)

        assert "open_tool" in allowed


class TestToolGatewayExecute:
    @pytest.mark.asyncio
    async def test_execute_with_valid_permissions(self) -> None:
        gw = ToolGateway()
        gw.register("file_read", _dummy_tool, required_permissions={"workspace:read"})

        result = await gw.execute(
            "file_read",
            agent_id="test_agent",
            agent_permissions={"workspace:read"},
            path="/tmp/file.txt",
        )
        assert result == {"ok": True, "path": "/tmp/file.txt"}

    @pytest.mark.asyncio
    async def test_execute_raises_permission_error(self) -> None:
        gw = ToolGateway()
        gw.register("file_write", _dummy_tool, required_permissions={"workspace:write"})

        with pytest.raises(ToolPermissionError, match="lacks permissions"):
            await gw.execute(
                "file_write",
                agent_id="test_agent",
                agent_permissions={"workspace:read"},
            )

    @pytest.mark.asyncio
    async def test_execute_raises_key_error_for_unknown_tool(self) -> None:
        gw = ToolGateway()
        with pytest.raises(KeyError, match="ghost_tool"):
            await gw.execute(
                "ghost_tool",
                agent_id="test_agent",
                agent_permissions=set(),
            )
