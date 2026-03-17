"""Agent registry API routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from aeco.agents.registry import registry

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    role: str
    tools: list[str]
    llm_provider: str
    llm_model: str


@router.get("", response_model=list[AgentResponse])
async def list_agents():
    """List all registered agents."""
    return [
        AgentResponse(
            agent_id=a.agent_id,
            name=a.name,
            role=a.role,
            tools=a.tools,
            llm_provider=a.llm_config.provider,
            llm_model=a.llm_config.model,
        )
        for a in registry.list_agents()
    ]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    """Get a specific agent's details."""
    a = registry.get(agent_id)
    return AgentResponse(
        agent_id=a.agent_id,
        name=a.name,
        role=a.role,
        tools=a.tools,
        llm_provider=a.llm_config.provider,
        llm_model=a.llm_config.model,
    )
