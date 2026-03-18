"""Blast-radius assessment and approval policy for initiatives.

Evaluates how broadly a change affects the system and determines
what level of approval is required before execution proceeds.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BlastRadiusLevel(str, Enum):
    LOW = "low"           # Single service, dev/staging, < 100 users
    MEDIUM = "medium"     # 2-3 services, non-critical path, 100-10K users
    HIGH = "high"         # 3+ services, production data, 10K+ users
    CRITICAL = "critical" # Core auth/payments, DB schema, all users


@dataclass
class BlastRadiusAssessment:
    level: BlastRadiusLevel
    score: int  # 0-100
    factors: list[dict[str, Any]] = field(default_factory=list)
    requires_security_review: bool = False
    requires_founder_approval: bool = False
    reasoning: str = ""


# Scoring weights for blast-radius factors
_FACTOR_WEIGHTS = {
    "production_db_migration": 30,
    "auth_changes": 25,
    "payment_changes": 25,
    "api_breaking_change": 20,
    "multi_service": 15,
    "user_facing": 10,
    "new_dependency": 5,
    "config_change": 5,
}


def assess_blast_radius(
    design_document: str | None = None,
    prd: dict | None = None,
    task_graph: list[dict] | None = None,
    security_review: dict | None = None,
) -> BlastRadiusAssessment:
    """Assess the blast radius of an initiative based on available artifacts.

    Uses keyword analysis on design docs and PRDs to estimate impact scope.
    Returns a BlastRadiusAssessment with level, score, and approval requirements.
    """
    score = 0
    factors: list[dict[str, Any]] = []

    # Combine all text for analysis
    text_parts = []
    if design_document:
        text_parts.append(design_document if isinstance(design_document, str) else json.dumps(design_document))
    if prd:
        text_parts.append(json.dumps(prd))
    if task_graph:
        text_parts.append(json.dumps(task_graph))

    text = " ".join(text_parts).lower()

    # Check for high-impact indicators
    if any(kw in text for kw in ("migration", "alter table", "schema change", "drop column")):
        score += _FACTOR_WEIGHTS["production_db_migration"]
        factors.append({"factor": "production_db_migration", "weight": 30, "detail": "Database schema changes detected"})

    if any(kw in text for kw in ("authentication", "auth", "oauth", "jwt", "session", "login", "password")):
        score += _FACTOR_WEIGHTS["auth_changes"]
        factors.append({"factor": "auth_changes", "weight": 25, "detail": "Authentication/authorization changes"})

    if any(kw in text for kw in ("payment", "billing", "stripe", "invoice", "charge", "subscription")):
        score += _FACTOR_WEIGHTS["payment_changes"]
        factors.append({"factor": "payment_changes", "weight": 25, "detail": "Payment/billing system changes"})

    if any(kw in text for kw in ("breaking change", "deprecat", "remove endpoint", "v2", "migration guide")):
        score += _FACTOR_WEIGHTS["api_breaking_change"]
        factors.append({"factor": "api_breaking_change", "weight": 20, "detail": "API breaking changes"})

    if any(kw in text for kw in ("microservice", "service mesh", "cross-service", "grpc", "message queue")):
        score += _FACTOR_WEIGHTS["multi_service"]
        factors.append({"factor": "multi_service", "weight": 15, "detail": "Multi-service coordination"})

    if any(kw in text for kw in ("user-facing", "frontend", "ui change", "landing page", "onboarding")):
        score += _FACTOR_WEIGHTS["user_facing"]
        factors.append({"factor": "user_facing", "weight": 10, "detail": "User-facing changes"})

    # Task count contributes to blast radius
    if task_graph and len(task_graph) > 5:
        bonus = min(15, (len(task_graph) - 5) * 3)
        score += bonus
        factors.append({"factor": "task_count", "weight": bonus, "detail": f"{len(task_graph)} tasks planned"})

    # Determine level
    if score >= 60:
        level = BlastRadiusLevel.CRITICAL
    elif score >= 35:
        level = BlastRadiusLevel.HIGH
    elif score >= 15:
        level = BlastRadiusLevel.MEDIUM
    else:
        level = BlastRadiusLevel.LOW

    # Approval requirements
    requires_security = level in (BlastRadiusLevel.HIGH, BlastRadiusLevel.CRITICAL)
    requires_founder = level == BlastRadiusLevel.CRITICAL

    # If security review found issues, escalate
    if security_review and security_review.get("risk_level") in ("high", "critical"):
        if level.value in ("low", "medium"):
            level = BlastRadiusLevel.HIGH
            requires_security = True
        factors.append({
            "factor": "security_risk_escalation",
            "weight": 0,
            "detail": f"Escalated due to {security_review.get('risk_level')} security risk",
        })

    reasoning_parts = [f"{f['factor']}: {f['detail']}" for f in factors]
    reasoning = f"Blast radius: {level.value} (score {score}/100). " + "; ".join(reasoning_parts) if reasoning_parts else f"Blast radius: {level.value} (score {score}/100). No significant risk factors detected."

    return BlastRadiusAssessment(
        level=level,
        score=min(score, 100),
        factors=factors,
        requires_security_review=requires_security,
        requires_founder_approval=requires_founder,
        reasoning=reasoning,
    )
