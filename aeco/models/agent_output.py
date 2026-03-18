"""Structured output every agent must emit (governance, truth, evaluation).

Forces explicit assumptions, risks, confidence, and success criteria so the system
can route, evaluate, and learn. See docs/architecture-vision.md.
"""

from pydantic import BaseModel, Field


class AgentOutput(BaseModel):
    """Canonical packet emitted by each agent after performing work."""

    artifact_refs: list[str] = Field(
        default_factory=list,
        description="References to produced artifacts (e.g. doc IDs, file paths, task IDs)",
    )
    decision: str = Field(
        default="",
        description="Summary of what was decided or produced",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions (surfaces hallucination)",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Risks or fragility identified",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the decision (used for routing and escalation)",
    )
    requested_followups: list[str] = Field(
        default_factory=list,
        description="Suggested next steps or agent actions",
    )
    blocking_dependencies: list[str] = Field(
        default_factory=list,
        description="Items that must be satisfied before proceeding",
    )
    success_criteria: list[str] = Field(
        default_factory=list,
        description="Criteria that make this output 'done' or correct (enables evaluation)",
    )
