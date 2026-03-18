"""LangGraph StateGraph assembly for the AECO workflow."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.memory.vector import VectorMemory
from aeco.budget.engine import BudgetEngine
from aeco.orchestrator.edges import post_budget_decision, route_decision
from aeco.orchestrator.nodes import WorkflowNodes
from aeco.orchestrator.state import AECOState


def build_graph(
    registry: AgentRegistry,
    audit_logger: AuditLogger,
    vector_memory: VectorMemory | None = None,
    budget_engine: BudgetEngine | None = None,
) -> StateGraph:
    """Build and compile the AECO workflow graph.

    Flow:
        START → intake → route
        route --[needs_*]→ budget_check --[approved]→ agent → route
        route --[needs_*]→ budget_check --[denied]→ publish → END
        route --[all_done | max_iterations]→ publish → END
    """
    nodes = WorkflowNodes(registry, audit_logger, vector_memory, budget_engine)

    graph = StateGraph(AECOState)

    # Add nodes
    graph.add_node("intake", nodes.intake)
    graph.add_node("route", nodes.route)
    graph.add_node("budget_check", nodes.budget_check)
    graph.add_node("architect", nodes.architect)
    graph.add_node("engineer", nodes.engineer)
    graph.add_node("frontend", nodes.frontend)
    graph.add_node("qa", nodes.qa)
    graph.add_node("publish", nodes.publish)

    # Entry point
    graph.set_entry_point("intake")

    # Edges
    graph.add_edge("intake", "route")

    # Route uses conditional edges — agent-bound routes go through budget_check
    graph.add_conditional_edges(
        "route",
        route_decision,
        {
            "budget_check": "budget_check",
            "publish": "publish",
        },
    )

    # Budget check decides: approved → agent, denied → publish
    graph.add_conditional_edges(
        "budget_check",
        post_budget_decision,
        {
            "architect": "architect",
            "engineer": "engineer",
            "frontend": "frontend",
            "qa": "qa",
            "publish": "publish",
        },
    )

    # After each agent, go back to route for next decision
    graph.add_edge("architect", "route")
    graph.add_edge("engineer", "route")
    graph.add_edge("frontend", "route")
    graph.add_edge("qa", "route")

    # Publish ends the workflow
    graph.add_edge("publish", END)

    return graph.compile()
