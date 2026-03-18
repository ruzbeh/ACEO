from typing import List, Literal, Optional

from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: Literal["anthropic", "openai", "openrouter"] = "openrouter"
    model: str = "anthropic/claude-sonnet-4"
    temperature: float = 0.7
    max_tokens: int = 4096


class ClaudeCodeConfig(BaseModel):
    """Configuration for Claude Code CLI executor."""
    max_turns: int = 10
    timeout_seconds: int = 300
    allowed_tools: Optional[List[str]] = None
    model: Optional[str] = None


class AgentDefinition(BaseModel):
    agent_id: str
    name: str
    role: str
    system_prompt_path: str
    llm_config: LLMConfig = LLMConfig()
    tools: List[str] = []
    permissions: List[str] = []
    executor: Literal["langchain", "claude_code"] = "langchain"
    claude_code_config: Optional[ClaudeCodeConfig] = None
