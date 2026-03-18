"""LangGraph state schema for the AECO workflow."""

import operator
from typing import Annotated, List, Optional, TypedDict


class AECOState(TypedDict):
    # Workflow run (for logging)
    workflow_run_id: Optional[str]

    # Task info
    task_id: str
    clickup_task_id: Optional[str]
    task_title: str
    task_description: str
    status: str

    # Workspace / project context
    workspace_path: str
    project_context: Optional[dict]

    # Agent messages (append-only via operator.add)
    messages: Annotated[List[dict], operator.add]

    # Artifacts produced by agents
    design_document: Optional[str]
    code_artifacts: Annotated[List[dict], operator.add]
    test_results: Optional[dict]
    review_feedback: Optional[str]

    # Routing control
    current_agent: Optional[str]
    next_action: Optional[str]
    iteration_count: int
    max_iterations: int

    # Budget tracking
    budget_spent: float
    budget_remaining: float
    budget_warnings: Annotated[List[dict], operator.add]
    budget_optimization_hints: Annotated[List[str], operator.add]
    budget_approved: bool

    # Errors (append-only)
    errors: Annotated[List[str], operator.add]
