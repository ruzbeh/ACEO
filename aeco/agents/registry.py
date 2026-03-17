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

    def list_agents(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    def register(self, agent: AgentDefinition) -> None:
        self._agents[agent.agent_id] = agent


# Global registry instance
registry = AgentRegistry()
