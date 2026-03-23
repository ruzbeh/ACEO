"""Factory for creating the appropriate agent executor."""

from typing import Any

from aeco.models.agent import AgentDefinition


def create_executor(agent_def: AgentDefinition, audit_logger: Any = None):
    """Return a ClaudeCodeExecutor or AgentRuntime based on agent config.

    Both share the same interface: async execute(context: dict) -> dict
    """
    if agent_def.executor == "claude_code":
        # Ensure claude_code_config has defaults if not explicitly set
        if agent_def.claude_code_config is None:
            from aeco.models.agent import ClaudeCodeConfig
            agent_def.claude_code_config = ClaudeCodeConfig()
        from aeco.agents.claude_code_executor import ClaudeCodeExecutor
        return ClaudeCodeExecutor(agent_def, audit_logger)

    from aeco.agents.runtime import AgentRuntime
    return AgentRuntime(agent_def, audit_logger)
