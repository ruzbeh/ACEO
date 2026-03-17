from typing import Literal

from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: Literal["anthropic", "openai"] = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7
    max_tokens: int = 4096


class AgentDefinition(BaseModel):
    agent_id: str
    name: str
    role: str
    system_prompt_path: str
    llm_config: LLMConfig = LLMConfig()
    tools: list[str] = []
    permissions: list[str] = []
