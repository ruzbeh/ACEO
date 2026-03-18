"""Integration tests for task and initiative graph wiring.

These tests verify that the graphs compile correctly, edges are wired properly,
and state schemas are valid — without making actual LLM calls.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.budget.engine import BudgetEngine
from aeco.context.builder import ContextBuilder
from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.memory.vector import VectorMemory
from aeco.orchestrator.state import AECOState
from aeco.orchestrator.initiative_state import InitiativeState


# ---------------------------------------------------------------------------
# Task graph compilation
# ---------------------------------------------------------------------------

class TestTaskGraphCompilation:
    """Verify the task-level graph compiles and has correct structure."""

    def _build_graph(self):
        from aeco.orchestrator.graph import build_graph
        registry = AgentRegistry()
        registry.load_from_yaml("aeco/agents/definitions/v1_agents.yaml")
        audit = MagicMock(spec=AuditLogger)
        return build_graph(registry, audit, vector_memory=None, budget_engine=None)

    def test_graph_compiles(self) -> None:
        graph = self._build_graph()
        assert graph is not None

    def test_graph_has_all_nodes(self) -> None:
        graph = self._build_graph()
        node_names = set(graph.nodes.keys())
        expected = {"intake", "route", "budget_check", "architect", "engineer", "frontend", "qa", "publish"}
        # LangGraph adds __start__ and __end__ nodes
        assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"


class TestInitiativeGraphCompilation:
    """Verify the initiative-level graph compiles and has correct structure."""

    def _build_graph(self):
        from aeco.orchestrator.initiative_graph import build_initiative_graph
        registry = AgentRegistry()
        registry.load_from_yaml("aeco/agents/definitions/v1_agents.yaml")
        audit = MagicMock(spec=AuditLogger)
        ctx = ContextBuilder()
        ledger = MagicMock(spec=DecisionLedgerStore)
        return build_initiative_graph(registry, audit, ctx, ledger, budget_engine=None)

    def test_graph_compiles(self) -> None:
        graph = self._build_graph()
        assert graph is not None

    def test_graph_has_all_nodes(self) -> None:
        graph = self._build_graph()
        node_names = set(graph.nodes.keys())
        expected = {"intake", "pm_spec", "architect", "task_planning", "execute_tasks", "evaluate", "close"}
        assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"


# ---------------------------------------------------------------------------
# Edge routing logic
# ---------------------------------------------------------------------------

class TestTaskEdgeRouting:
    """Test task-level routing decisions."""

    def test_route_decision_needs_design(self) -> None:
        from aeco.orchestrator.edges import route_decision
        state: AECOState = {
            "workflow_run_id": None, "task_id": "x", "clickup_task_id": None,
            "task_title": "t", "task_description": "d", "status": "intake",
            "workspace_path": ".", "project_context": None,
            "messages": [], "design_document": None, "code_artifacts": [],
            "test_results": None, "review_feedback": None,
            "current_agent": None, "next_action": "needs_design",
            "iteration_count": 0, "max_iterations": 5,
            "budget_spent": 0, "budget_remaining": 0,
            "budget_warnings": [], "budget_optimization_hints": [],
            "budget_approved": True, "errors": [],
        }
        assert route_decision(state) == "budget_check"

    def test_route_decision_all_done(self) -> None:
        from aeco.orchestrator.edges import route_decision
        state: AECOState = {
            "workflow_run_id": None, "task_id": "x", "clickup_task_id": None,
            "task_title": "t", "task_description": "d", "status": "done",
            "workspace_path": ".", "project_context": None,
            "messages": [], "design_document": None, "code_artifacts": [],
            "test_results": None, "review_feedback": None,
            "current_agent": None, "next_action": "all_done",
            "iteration_count": 2, "max_iterations": 5,
            "budget_spent": 0, "budget_remaining": 0,
            "budget_warnings": [], "budget_optimization_hints": [],
            "budget_approved": True, "errors": [],
        }
        assert route_decision(state) == "publish"

    def test_route_decision_max_iterations(self) -> None:
        from aeco.orchestrator.edges import route_decision
        state: AECOState = {
            "workflow_run_id": None, "task_id": "x", "clickup_task_id": None,
            "task_title": "t", "task_description": "d", "status": "engineering",
            "workspace_path": ".", "project_context": None,
            "messages": [], "design_document": None, "code_artifacts": [],
            "test_results": None, "review_feedback": None,
            "current_agent": None, "next_action": "needs_implementation",
            "iteration_count": 5, "max_iterations": 5,
            "budget_spent": 0, "budget_remaining": 0,
            "budget_warnings": [], "budget_optimization_hints": [],
            "budget_approved": True, "errors": [],
        }
        assert route_decision(state) == "publish"

    def test_post_budget_approved(self) -> None:
        from aeco.orchestrator.edges import post_budget_decision
        state: AECOState = {
            "workflow_run_id": None, "task_id": "x", "clickup_task_id": None,
            "task_title": "t", "task_description": "d", "status": "intake",
            "workspace_path": ".", "project_context": None,
            "messages": [], "design_document": None, "code_artifacts": [],
            "test_results": None, "review_feedback": None,
            "current_agent": None, "next_action": "needs_qa",
            "iteration_count": 0, "max_iterations": 5,
            "budget_spent": 0, "budget_remaining": 0,
            "budget_warnings": [], "budget_optimization_hints": [],
            "budget_approved": True, "errors": [],
        }
        assert post_budget_decision(state) == "qa"

    def test_post_budget_denied(self) -> None:
        from aeco.orchestrator.edges import post_budget_decision
        state: AECOState = {
            "workflow_run_id": None, "task_id": "x", "clickup_task_id": None,
            "task_title": "t", "task_description": "d", "status": "intake",
            "workspace_path": ".", "project_context": None,
            "messages": [], "design_document": None, "code_artifacts": [],
            "test_results": None, "review_feedback": None,
            "current_agent": None, "next_action": "needs_implementation",
            "iteration_count": 0, "max_iterations": 5,
            "budget_spent": 0, "budget_remaining": 0,
            "budget_warnings": [], "budget_optimization_hints": [],
            "budget_approved": False, "errors": [],
        }
        assert post_budget_decision(state) == "publish"


class TestInitiativeEdgeRouting:
    """Test initiative-level routing decisions."""

    def test_post_evaluate_iterate(self) -> None:
        from aeco.orchestrator.initiative_graph import _post_evaluate
        state: InitiativeState = {
            "initiative_id": str(uuid.uuid4()), "title": "t", "goal": "g",
            "hypothesis": "h", "workspace_path": ".", "project_context": None,
            "prd": None, "design_document": None, "task_graph": [],
            "execution_results": [], "evaluation": None,
            "north_star_metric": None, "local_metrics": [],
            "success_threshold": None, "evaluation_window_days": 7,
            "decisions": [], "current_phase": "task_planning",
            "verdict": None, "iteration_count": 1, "max_iterations": 3,
            "messages": [], "errors": [], "budget_spent": 0, "budget_remaining": 0,
        }
        assert _post_evaluate(state) == "task_planning"

    def test_post_evaluate_close(self) -> None:
        from aeco.orchestrator.initiative_graph import _post_evaluate
        state: InitiativeState = {
            "initiative_id": str(uuid.uuid4()), "title": "t", "goal": "g",
            "hypothesis": "h", "workspace_path": ".", "project_context": None,
            "prd": None, "design_document": None, "task_graph": [],
            "execution_results": [], "evaluation": None,
            "north_star_metric": None, "local_metrics": [],
            "success_threshold": None, "evaluation_window_days": 7,
            "decisions": [], "current_phase": "closed",
            "verdict": "kill", "iteration_count": 3, "max_iterations": 3,
            "messages": [], "errors": [], "budget_spent": 0, "budget_remaining": 0,
        }
        assert _post_evaluate(state) == "close"


# ---------------------------------------------------------------------------
# Agent registry completeness
# ---------------------------------------------------------------------------

class TestAgentRegistryCompleteness:
    """Verify all agents required by the graphs are registered."""

    def test_all_task_agents_registered(self) -> None:
        registry = AgentRegistry()
        registry.load_from_yaml("aeco/agents/definitions/v1_agents.yaml")
        required = ["coo_orchestrator", "chief_architect", "backend_engineer",
                     "frontend_engineer", "qa_engineer", "budget_controller"]
        for agent_id in required:
            assert registry.has(agent_id), f"Missing agent: {agent_id}"

    def test_all_initiative_agents_registered(self) -> None:
        registry = AgentRegistry()
        registry.load_from_yaml("aeco/agents/definitions/v1_agents.yaml")
        required = ["pm_agent", "chief_architect", "task_planner",
                     "agent_evaluator", "postmortem_writer"]
        for agent_id in required:
            assert registry.has(agent_id), f"Missing agent: {agent_id}"

    def test_new_agents_registered(self) -> None:
        registry = AgentRegistry()
        registry.load_from_yaml("aeco/agents/definitions/v1_agents.yaml")
        assert registry.has("release_manager")
        assert registry.has("postmortem_writer")

    def test_total_agent_count(self) -> None:
        registry = AgentRegistry()
        registry.load_from_yaml("aeco/agents/definitions/v1_agents.yaml")
        agents = registry.list_agents()
        assert len(agents) == 23, f"Expected 23 agents, got {len(agents)}"


# ---------------------------------------------------------------------------
# Tool registry completeness
# ---------------------------------------------------------------------------

class TestToolRegistryCompleteness:
    """Verify all tools declared by agents are registered in the gateway."""

    def test_all_declared_tools_registered(self) -> None:
        from aeco.tools.gateway import ToolGateway
        from aeco.tools.registry import register_all_tools

        gateway = ToolGateway()
        register_all_tools(gateway)

        registry = AgentRegistry()
        registry.load_from_yaml("aeco/agents/definitions/v1_agents.yaml")

        missing = []
        for agent in registry.list_agents():
            for tool_name in agent.tools:
                if tool_name not in gateway._tools:
                    missing.append(f"{agent.agent_id} needs '{tool_name}'")

        assert not missing, f"Unregistered tools: {missing}"


# ---------------------------------------------------------------------------
# Context Builder
# ---------------------------------------------------------------------------

class TestContextBuilder:
    @pytest.mark.asyncio
    async def test_build_for_initiative_without_stores(self) -> None:
        builder = ContextBuilder()
        ctx = await builder.build_for_initiative(
            initiative_title="Test",
            initiative_goal="Test goal",
            agent_role="pm",
        )
        assert ctx["agent_role"] == "pm"

    @pytest.mark.asyncio
    async def test_build_for_task_includes_project_context(self) -> None:
        builder = ContextBuilder()
        ctx = await builder.build_for_task(
            task_title="Test task",
            task_description="Desc",
            agent_role="engineer",
            project_context={"language": "python"},
        )
        assert ctx["project_context"]["language"] == "python"
