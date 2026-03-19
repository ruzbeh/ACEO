"""Agent registry API routes."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from aeco.agents.registry import registry

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    role: str
    tools: List[str]
    llm_provider: str
    llm_model: str
    department: Optional[str] = None
    is_lead: bool = False
    team_members: Optional[List[str]] = None


def _agent_to_response(a) -> AgentResponse:
    return AgentResponse(
        agent_id=a.agent_id,
        name=a.name,
        role=a.role,
        tools=a.tools,
        llm_provider=a.llm_config.provider,
        llm_model=a.llm_config.model,
        department=a.department,
        is_lead=a.is_lead,
        team_members=a.team_members,
    )


@router.get("", response_model=list[AgentResponse])
async def list_agents():
    """List all registered agents."""
    return [_agent_to_response(a) for a in registry.list_agents()]


@router.get("/teams")
async def get_teams():
    """Get department → team lead → specialists tree."""
    departments = registry.get_departments()
    result = {}
    for dept_name, dept_data in departments.items():
        lead = dept_data["lead"]
        members = dept_data["members"]
        result[dept_name] = {
            "label": dept_name.replace("_", " ").title(),
            "lead": _agent_to_response(lead).model_dump() if lead else None,
            "members": [_agent_to_response(m).model_dump() for m in members],
            "total": len(members) + (1 if lead else 0),
        }
    return result


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    """Get a specific agent's details."""
    return _agent_to_response(registry.get(agent_id))
