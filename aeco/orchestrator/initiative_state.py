"""LangGraph state schema for the initiative-level workflow."""

import operator
from typing import Annotated, List, Optional, TypedDict


class InitiativeState(TypedDict):
    # Initiative identity
    initiative_id: str
    title: str
    goal: str
    hypothesis: str

    # Workspace / project
    workspace_path: str
    project_context: Optional[dict]

    # Artifacts produced at each stage
    prd: Optional[dict]                    # PM Agent output
    design_document: Optional[str]          # Architect output
    task_graph: List[dict]               # Task Planner output
    execution_results: Annotated[List[dict], operator.add]  # Per-task results
    security_review: Optional[dict]           # Security Reviewer output
    evaluation: Optional[dict]              # Evaluator output

    # Metrics defined by PM
    north_star_metric: Optional[str]
    local_metrics: List[str]
    success_threshold: Optional[str]
    evaluation_window_days: int

    # Decision tracking
    decisions: Annotated[List[dict], operator.add]

    # Control flow
    current_phase: str                   # intake, pm_spec, architect, security_review, task_planning, executing, evaluating, closed
    verdict: Optional[str]                  # scale, iterate, kill
    iteration_count: int
    max_iterations: int

    # Messages / errors
    messages: Annotated[List[dict], operator.add]
    errors: Annotated[List[str], operator.add]

    # Budget
    budget_spent: float
    budget_remaining: float
