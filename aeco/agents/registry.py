from __future__ import annotations

from pathlib import Path

import yaml

from aeco.models.agent import AgentDefinition, LLMConfig


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentDefinition] = {}

    def load_from_yaml(self, path: str | Path) -> None:
        path = Path(path)
        with path.open() as f:
            data = yaml.safe_load(f)

        for agent_data in data.get("agents", []):
            llm_data = agent_data.pop("llm_config", {})
            agent_data["llm_config"] = LLMConfig(**llm_data)
            agent = AgentDefinition(**agent_data)
            self._agents[agent.agent_id] = agent

    def get(self, agent_id: str) -> AgentDefinition:
        if agent_id not in self._agents:
            raise KeyError(f"Agent '{agent_id}' not found in registry")
        return self._agents[agent_id]

    def has(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def list_agents(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    def register(self, agent: AgentDefinition) -> None:
        self._agents[agent.agent_id] = agent

    def get_team_members(self, lead_id: str) -> list[AgentDefinition]:
        """Get all specialist agents managed by a team lead."""
        lead = self.get(lead_id)
        if not lead.team_members:
            return []
        return [self._agents[mid] for mid in lead.team_members if mid in self._agents]

    def get_departments(self) -> dict[str, dict]:
        """Get department → {lead, members} tree for UI."""
        departments: dict[str, dict] = {}
        for agent in self._agents.values():
            dept = agent.department or "unassigned"
            if dept not in departments:
                departments[dept] = {"lead": None, "members": []}
            if agent.is_lead:
                departments[dept]["lead"] = agent
            else:
                departments[dept]["members"].append(agent)
        return departments

    def is_team_lead(self, agent_id: str) -> bool:
        """Check if an agent is a team lead with members."""
        if agent_id not in self._agents:
            return False
        agent = self._agents[agent_id]
        return agent.is_lead and bool(agent.team_members)


# Global registry instance
registry = AgentRegistry()
