"""LangGraph StateGraph assembly for the initiative-level workflow.
Flow:
    START → intake → pm_spec → architect → task_planning → execute_tasks → evaluate
    evaluate --[iterate & under max]→ task_planning (loop)
    evaluate --[scale | kill | max reached]→ close → END
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


def _post_evaluate(state: InitiativeState) -> str:
    """After evaluation, decide whether to iterate or close."""
    if state.get("current_phase") == "closed":
        return "close"
    # current_phase == "task_planning" means iterate
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
    graph.add_node("task_planning", nodes.task_planning)
    graph.add_node("execute_tasks", nodes.execute_tasks)
    graph.add_node("evaluate", nodes.evaluate)
    graph.add_node("close", nodes.close)

    # Edges: linear pipeline with evaluate → iterate loop
    graph.set_entry_point("intake")
    graph.add_edge("intake", "pm_spec")
    graph.add_edge("pm_spec", "architect")
    graph.add_edge("architect", "task_planning")
    graph.add_edge("task_planning", "execute_tasks")
    graph.add_edge("execute_tasks", "evaluate")

    # Evaluate decides: iterate (back to task_planning) or close
    graph.add_conditional_edges(
        "evaluate",
        _post_evaluate,
        {
            "task_planning": "task_planning",
            "close": "close",
        },
    )

    graph.add_edge("close", END)

    return graph.compile()
