"""Tests for AgentRegistry – loading, lookup, and listing."""

import textwrap
from pathlib import Path

import pytest

from aeco.agents.registry import AgentRegistry


@pytest.fixture()
def agents_yaml(tmp_path: Path) -> Path:
    """Write a minimal agents YAML file for testing."""
    content = textwrap.dedent("""\
        agents:
          - agent_id: alpha
            name: Alpha Agent
            role: engineer
            system_prompt_path: prompts/alpha.md
            llm_config:
              provider: anthropic
              model: claude-sonnet-4-20250514
              temperature: 0.4
              max_tokens: 2048
            tools:
              - file_read
            permissions:
              - workspace:read

          - agent_id: beta
            name: Beta Agent
            role: qa
            system_prompt_path: prompts/beta.md
            llm_config:
              provider: openai
              model: gpt-4o
              temperature: 0.2
              max_tokens: 1024
            tools: []
            permissions: []
    """)
    yaml_file = tmp_path / "agents.yaml"
    yaml_file.write_text(content)
    return yaml_file


class TestAgentRegistryLoadFromYAML:
    def test_load_agents_from_yaml(self, agents_yaml: Path) -> None:
        registry = AgentRegistry()
        registry.load_from_yaml(agents_yaml)

        agents = registry.list_agents()
        assert len(agents) == 2

    def test_loaded_agent_fields(self, agents_yaml: Path) -> None:
        registry = AgentRegistry()
        registry.load_from_yaml(agents_yaml)

        alpha = registry.get("alpha")
        assert alpha.name == "Alpha Agent"
        assert alpha.role == "engineer"
        assert alpha.llm_config.provider == "anthropic"
        assert alpha.llm_config.temperature == 0.4
        assert alpha.tools == ["file_read"]
        assert alpha.permissions == ["workspace:read"]

    def test_loaded_agent_different_provider(self, agents_yaml: Path) -> None:
        registry = AgentRegistry()
        registry.load_from_yaml(agents_yaml)

        beta = registry.get("beta")
        assert beta.llm_config.provider == "openai"
        assert beta.llm_config.model == "gpt-4o"


class TestAgentRegistryGet:
    def test_get_raises_key_error_for_unknown_agent(self) -> None:
        registry = AgentRegistry()
        with pytest.raises(KeyError, match="not_real"):
            registry.get("not_real")

    def test_get_returns_correct_agent(self, agents_yaml: Path) -> None:
        registry = AgentRegistry()
        registry.load_from_yaml(agents_yaml)

        agent = registry.get("beta")
        assert agent.agent_id == "beta"


class TestAgentRegistryListAgents:
    def test_list_agents_empty(self) -> None:
        registry = AgentRegistry()
        assert registry.list_agents() == []

    def test_list_agents_returns_all(self, agents_yaml: Path) -> None:
        registry = AgentRegistry()
        registry.load_from_yaml(agents_yaml)

        ids = {a.agent_id for a in registry.list_agents()}
        assert ids == {"alpha", "beta"}
