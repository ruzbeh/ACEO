"""LangGraph state schema for the fast-track workflow (3-node: architect -> build -> ship)."""

import operator
from typing import Annotated, List, Optional, TypedDict


class FastTrackState(TypedDict):
    # Request identity
    request_id: str
    request: str  # plain-text user request
    workspace_path: str
    project_context: Optional[dict]

    # Architect output
    plan: Optional[dict]  # {approach, files_to_change, estimated_complexity, escalate}
    escalate_to_initiative: bool  # True if architect deems this too complex for fast-track

    # Build output
    build_result: Optional[dict]  # fullstack_engineer output
    files_changed: List[str]

    # Scaffold output (M3)
    scaffold_result: Optional[dict]  # scaffold tool output
    is_new_project: bool  # True if scaffold should run
    stack: Optional[str]  # e.g. "nextjs-supabase-stripe"
    features: Optional[List[str]]  # e.g. ["auth", "payments", "file-upload"]
    project_name: Optional[str]  # extracted project name

    # Ship output
    git_result: Optional[dict]  # commit hash, branch
    deploy_result: Optional[dict]  # preview URL
    preview_url: Optional[str]

    # Verify output (M3)
    smoke_result: Optional[dict]  # post-deploy smoke test result

    # Control flow
    current_phase: str  # intake, architect, scaffold, build, ship, verify, done, escalated
    budget_spent: float
    budget_remaining: float

    # Tracking
    decisions: Annotated[List[dict], operator.add]
    messages: Annotated[List[dict], operator.add]
    errors: Annotated[List[str], operator.add]
