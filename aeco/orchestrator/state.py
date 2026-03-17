"""LangGraph state schema for the AECO workflow."""

import operator
from typing import Annotated, TypedDict


class AECOState(TypedDict):
    # Task info
    task_id: str
    clickup_task_id: str | None
    task_title: str
    task_description: str
    status: str

    # Agent messages (append-only via operator.add)
    messages: Annotated[list[dict], operator.add]

    # Artifacts produced by agents
    design_document: str | None
    code_artifacts: Annotated[list[dict], operator.add]
    test_results: dict | None
    review_feedback: str | None

    # Routing control
    current_agent: str | None
    next_action: str | None
    iteration_count: int
    max_iterations: int

    # Errors (append-only)
    errors: Annotated[list[str], operator.add]
