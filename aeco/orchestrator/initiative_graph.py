"""LangGraph StateGraph assembly for the initiative-level workflow.
Flow:
    START → intake → pm_spec → architect → security_review → task_planning → execute_tasks → evaluate
    security_review --[critical & not cleared]→ close → END
    evaluate --[iterate & under max]→ task_planning (loop)
    evaluate --[scale]→ acceptance_test → [pass]→ close → END
    evaluate --[scale]→ acceptance_test → [fail & can iterate]→ task_planning (loop)
    evaluate --[kill | max reached]→ close → END
"""
from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.budget.engine import BudgetEngine
from aeco.context.builder import ContextBuilder
from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.orchestrator.initiative_nodes import InitiativeNodes
from aeco.orchestrator.initiative_state import InitiativeState

logger = logging.getLogger(__name__)


def _post_security_review(state: InitiativeState) -> str:
    """After security review, proceed to task planning or close if critical."""
    if state.get("current_phase") == "closed":
        return "close"
    return "task_planning"


def _post_evaluate(state: InitiativeState) -> str:
    """After evaluation: scale → acceptance_test, iterate → task_planning, kill → close."""
    phase = state.get("current_phase", "")

    if phase == "closed":
        return "close"
    if phase == "task_planning":
        return "task_planning"
    if phase == "acceptance_testing":
        return "acceptance_test"

    # Fallback: if phase is unknown, close
    return "close"


def _post_acceptance_test(state: InitiativeState) -> str:
    """After acceptance test: approved → close, rejected → task_planning or close."""
    phase = state.get("current_phase", "")
    if phase == "closed":
        return "close"
    # rejected but can iterate
    return "task_planning"


def build_initiative_graph(
    registry: AgentRegistry,
    audit_logger: AuditLogger,
    context_builder: ContextBuilder,
    decision_ledger: DecisionLedgerStore,
    budget_engine: BudgetEngine | None = None,
) -> StateGraph:
    """Build and compile the initiative-level workflow graph."""

    nodes = InitiativeNodes(
        registry=registry,
        audit_logger=audit_logger,
        context_builder=context_builder,
        decision_ledger=decision_ledger,
        budget_engine=budget_engine,
    )

    graph = StateGraph(InitiativeState)

    # Nodes
    graph.add_node("intake", nodes.intake)
    graph.add_node("pm_spec", nodes.pm_spec)
    graph.add_node("architect", nodes.architect)
    graph.add_node("security_review", nodes.security_review)
    graph.add_node("task_planning", nodes.task_planning)
    graph.add_node("execute_tasks", nodes.execute_tasks)
    graph.add_node("evaluate", nodes.evaluate)
    graph.add_node("acceptance_test", nodes.acceptance_test)
    graph.add_node("close", nodes.close)

    # Edges: linear pipeline with gates
    graph.set_entry_point("intake")
    graph.add_edge("intake", "pm_spec")
    graph.add_edge("pm_spec", "architect")
    graph.add_edge("architect", "security_review")

    # Security review: cleared → task_planning, critical → close
    graph.add_conditional_edges(
        "security_review",
        _post_security_review,
        {
            "task_planning": "task_planning",
            "close": "close",
        },
    )

    graph.add_edge("task_planning", "execute_tasks")
    graph.add_edge("execute_tasks", "evaluate")

    # Evaluate: scale → acceptance_test, iterate → task_planning, kill → close
    graph.add_conditional_edges(
        "evaluate",
        _post_evaluate,
        {
            "acceptance_test": "acceptance_test",
            "task_planning": "task_planning",
            "close": "close",
        },
    )

    # Acceptance test: approved → close (merge+deploy), rejected → task_planning or close
    graph.add_conditional_edges(
        "acceptance_test",
        _post_acceptance_test,
        {
            "close": "close",
            "task_planning": "task_planning",
        },
    )

    graph.add_edge("close", END)

    return graph.compile()
