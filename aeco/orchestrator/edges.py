"""Conditional edge logic for the AECO workflow graph."""

import logging

from aeco.logging.company_logger import log_route_decision
from aeco.orchestrator.state import AECOState

logger = logging.getLogger(__name__)


def route_decision(state: AECOState) -> str:
    """Determine the next node based on the orchestrator's routing decision.

    All agent-bound routes go through budget_check first. Only publish and
    budget_check itself bypass the budget gate.
    """
    next_action = state.get("next_action", "needs_design")
    iteration = state.get("iteration_count", 0)
    max_iter = state.get("max_iterations", 5)

    # Safety valve: stop if too many iterations
    if iteration >= max_iter:
        logger.warning(f"Max iterations ({max_iter}) reached, forcing publish")
        log_route_decision(
            run_id=state.get("workflow_run_id"),
            task_id=state.get("task_id"),
            next_action="publish",
            iteration=iteration,
            reasoning="max_iterations reached",
            forced=True,
        )
        return "publish"

    if next_action == "all_done":
        return "publish"
    if next_action in ("needs_design", "needs_implementation", "needs_frontend", "needs_qa"):
        return "budget_check"
    logger.warning(f"Unknown next_action '{next_action}', defaulting to publish")
    log_route_decision(
        run_id=state.get("workflow_run_id"),
        task_id=state.get("task_id"),
        next_action=next_action,
        iteration=iteration,
        reasoning="unknown next_action, defaulting to publish",
        forced=True,
    )
    return "publish"


def post_budget_decision(state: AECOState) -> str:
    """After budget_check, route to the actual agent or publish if denied."""
    if not state.get("budget_approved", True):
        logger.warning("Budget denied — forcing publish")
        return "publish"

    next_action = state.get("next_action", "publish")
    if next_action == "needs_design":
        return "architect"
    if next_action == "needs_implementation":
        return "engineer"
    if next_action == "needs_frontend":
        return "frontend"
    if next_action == "needs_qa":
        return "qa"
    return "publish"
