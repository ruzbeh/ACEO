"""LangGraph state schema for the portfolio-level workflow."""
from __future__ import annotations

import operator
from typing import Annotated, List, Optional, TypedDict


class PortfolioState(TypedDict):
    # Identity
    portfolio_id: str
    company_goals: List[str]

    # Opportunity discovery
    opportunities: Annotated[List[dict], operator.add]

    # Active initiative tracking
    active_initiatives: List[dict]  # {id, title, status, verdict, budget_spent}

    # CEO decisions
    portfolio_decisions: Annotated[List[dict], operator.add]
    funded_initiatives: List[dict]   # {title, goal, hypothesis, allocated_budget}
    killed_initiatives: List[str]    # initiative IDs to kill

    # Execution results (from running initiative graphs)
    execution_results: Annotated[List[dict], operator.add]

    # Budget
    total_budget: float
    budget_spent: float
    budget_remaining: float

    # Control flow
    current_phase: str   # opportunity_scan, portfolio_review, executing, evaluating, rebalancing, closed
    cycle_count: int
    max_cycles: int

    # Standard
    workspace_path: str
    messages: Annotated[List[dict], operator.add]
    decisions: Annotated[List[dict], operator.add]
    errors: Annotated[List[str], operator.add]
