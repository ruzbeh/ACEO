import logging
from collections.abc import Callable
from typing import Any, Optional

from aeco.models.agent import AgentDefinition

logger = logging.getLogger(__name__)


class ToolPermissionError(Exception):
    pass


class ToolGateway:
    """Permission-checked tool dispatch. Agents can only use tools they're allowed."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}
        self._tool_permissions: dict[str, set[str]] = {}

    def register(
        self, name: str, fn: Callable, required_permissions: Optional[set[str]] = None
    ) -> None:
        self._tools[name] = fn
        self._tool_permissions[name] = required_permissions or set()

    def get_tools_for_agent(self, agent_def: AgentDefinition) -> dict[str, Callable]:
        """Return only tools this agent is permitted to use."""
        agent_perms = set(agent_def.permissions)
        allowed = {}
        for tool_name in agent_def.tools:
            if tool_name not in self._tools:
                logger.warning(f"Tool '{tool_name}' not registered, skipping for {agent_def.agent_id}")
                continue
            required = self._tool_permissions.get(tool_name, set())
            if required <= agent_perms:
                allowed[tool_name] = self._tools[tool_name]
            else:
                missing = required - agent_perms
                logger.warning(
                    f"Agent '{agent_def.agent_id}' lacks permissions {missing} for tool '{tool_name}'"
                )
        return allowed

    async def execute(
        self, tool_name: str, agent_id: str, agent_permissions: set[str], **kwargs: Any
    ) -> Any:
        if tool_name not in self._tools:
            raise KeyError(f"Tool '{tool_name}' not registered")

        required = self._tool_permissions.get(tool_name, set())
        if not required <= agent_permissions:
            missing = required - agent_permissions
            raise ToolPermissionError(
                f"Agent '{agent_id}' lacks permissions {missing} for tool '{tool_name}'"
            )

        fn = self._tools[tool_name]
        return await fn(**kwargs)


# Global gateway instance
tool_gateway = ToolGateway()
