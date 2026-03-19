"""Node functions for the initiative-level LangGraph workflow.

Flow: intake → pm_spec → architect → task_planning → execute_tasks → evaluate → close
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from aeco.agents.executor_factory import create_executor
from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.config import settings
from aeco.context.builder import ContextBuilder
from aeco.events import (
    INITIATIVE_CLOSED,
    INITIATIVE_DECISION_RECORDED,
    INITIATIVE_PHASE_CHANGED,
    INITIATIVE_SECURITY_REVIEWED,
    INITIATIVE_TASK_COMPLETED,
    INITIATIVE_TASK_STARTED,
    event_bus,
)
from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.orchestrator.initiative_state import InitiativeState

if TYPE_CHECKING:
    from aeco.budget.engine import BudgetEngine

logger = logging.getLogger(__name__)


def _msg(sender: str, msg_type: str, content: Any) -> dict:
    return {
        "sender": sender,
        "type": msg_type,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class InitiativeNodes:
    """Node functions for initiative-level orchestration."""

    def __init__(
        self,
        registry: AgentRegistry,
        audit_logger: AuditLogger,
        context_builder: ContextBuilder,
        decision_ledger: DecisionLedgerStore,
        budget_engine: "BudgetEngine | None" = None,
    ) -> None:
        self.registry = registry
        self.audit = audit_logger
        self.ctx = context_builder
        self.ledger = decision_ledger
        self.budget = budget_engine

    # ------------------------------------------------------------------
    # team delegation: route task to best specialist
    # ------------------------------------------------------------------

    async def _delegate_to_specialist(
        self, lead_id: str, task_title: str, task_desc: str, specialist_hint: str = ""
    ) -> str | None:
        """Ask a team lead to pick the best specialist for a task.

        Returns the specialist agent_id, or None if delegation fails.
        """
        try:
            lead_def = self.registry.get(lead_id)
            runtime = create_executor(lead_def, self.audit)

            members = self.registry.get_team_members(lead_id)
            member_info = [
                {"agent_id": m.agent_id, "name": m.name, "role": m.role}
                for m in members
            ]

            context = {
                "action": "delegate",
                "task_title": task_title,
                "task_description": task_desc,
                "specialist_hint": specialist_hint,
                "available_specialists": member_info,
            }

            result = await asyncio.wait_for(runtime.execute(context), timeout=60)
            delegate_to = result.get("delegate_to", "")
            if delegate_to and self.registry.has(delegate_to):
                return delegate_to

            # Fallback: keyword matching on role/name
            desc_lower = (task_title + " " + task_desc + " " + specialist_hint).lower()
            for m in members:
                if m.role.lower() in desc_lower or m.agent_id.lower() in desc_lower:
                    return m.agent_id

            return members[0].agent_id if members else None
        except Exception as e:
            logger.warning(f"Team delegation failed for {lead_id}: {e}")
            # Fallback to first team member
            lead_def = self.registry.get(lead_id)
            if lead_def.team_members:
                return lead_def.team_members[0]
            return None

    # ------------------------------------------------------------------
    # intake: initialize the initiative workflow
    # ------------------------------------------------------------------

    async def intake(self, state: InitiativeState) -> dict:
        logger.info(f"Initiative intake: {state['title']}")
        await event_bus.emit(INITIATIVE_PHASE_CHANGED, {
            "initiative_id": state["initiative_id"],
            "phase": "pm_spec",
            "title": state["title"],
        })
        return {
            "current_phase": "pm_spec",
            "messages": [_msg("system", "status", f"Initiative started: {state['title']}")],
        }

    # ------------------------------------------------------------------
    # pm_spec: PM Agent writes the PRD
    # ------------------------------------------------------------------

    async def pm_spec(self, state: InitiativeState) -> dict:
        logger.info("PM Agent: writing product spec")

        agent_def = self.registry.get("pm_agent")
        runtime = create_executor(agent_def, self.audit)

        extra = {
            "initiative_id": state["initiative_id"],
            "title": state["title"],
            "goal": state["goal"],
            "hypothesis": state["hypothesis"],
        }
        context = await self.ctx.build_for_initiative(
            initiative_title=state["title"],
            initiative_goal=state["goal"],
            agent_role="product_manager",
            initiative_id=state["initiative_id"],
            workspace_path=state.get("workspace_path", ""),
            extra=extra,
        )

        result = await runtime.execute(context)

        prd = result.get("prd", result)
        metrics = result.get("metrics", {})

        # Record the decision
        await self.ledger.record(
            category="initiative",
            agent_id="pm_agent",
            decision=result.get("decision", "PRD created"),
            reasoning=json.dumps(prd)[:500],
            assumptions=result.get("assumptions", []),
            risks=result.get("risks", []),
            confidence=result.get("confidence", 0.0),
            initiative_id=uuid.UUID(state["initiative_id"]),
        )
        await event_bus.emit(INITIATIVE_DECISION_RECORDED, {
            "initiative_id": state["initiative_id"],
            "agent_id": "pm_agent",
            "phase": "pm_spec",
            "decision": result.get("decision", "PRD created"),
        })
        await event_bus.emit(INITIATIVE_PHASE_CHANGED, {
            "initiative_id": state["initiative_id"],
            "phase": "architect",
        })

        return {
            "prd": prd,
            "north_star_metric": metrics.get("north_star"),
            "local_metrics": metrics.get("local_metrics", []),
            "success_threshold": metrics.get("success_threshold"),
            "evaluation_window_days": metrics.get("evaluation_window_days", 7),
            "current_phase": "architect",
            "decisions": [{
                "agent": "pm_agent",
                "phase": "pm_spec",
                "decision": result.get("decision", ""),
                "confidence": result.get("confidence", 0.0),
                "assumptions": result.get("assumptions", []),
            }],
            "messages": [_msg("pm_agent", "prd", prd)],
        }

    # ------------------------------------------------------------------
    # architect: Chief Architect creates technical design
    # ------------------------------------------------------------------

    async def architect(self, state: InitiativeState) -> dict:
        logger.info("Chief Architect: creating design for initiative")

        agent_def = self.registry.get("chief_architect")
        runtime = create_executor(agent_def, self.audit)

        extra = {
            "initiative_id": state["initiative_id"],
            "title": state["title"],
            "goal": state["goal"],
            "prd": state.get("prd"),
        }
        context = await self.ctx.build_for_initiative(
            initiative_title=state["title"],
            initiative_goal=state["goal"],
            agent_role="architect",
            initiative_id=state["initiative_id"],
            workspace_path=state.get("workspace_path", ""),
            extra=extra,
        )

        result = await runtime.execute(context)
        design_doc = json.dumps(result.get("design_document", result), indent=2)

        await self.ledger.record(
            category="architecture",
            agent_id="chief_architect",
            decision=result.get("decision", "Architecture designed"),
            reasoning=design_doc[:500],
            assumptions=result.get("assumptions", []),
            risks=result.get("risks", []),
            confidence=result.get("confidence", 0.0),
            initiative_id=uuid.UUID(state["initiative_id"]),
        )
        await event_bus.emit(INITIATIVE_DECISION_RECORDED, {
            "initiative_id": state["initiative_id"],
            "agent_id": "chief_architect",
            "phase": "architect",
            "decision": result.get("decision", "Architecture designed"),
        })
        await event_bus.emit(INITIATIVE_PHASE_CHANGED, {
            "initiative_id": state["initiative_id"],
            "phase": "security_review",
        })

        return {
            "design_document": design_doc,
            "current_phase": "security_review",
            "decisions": [{
                "agent": "chief_architect",
                "phase": "architect",
                "decision": result.get("decision", ""),
                "confidence": result.get("confidence", 0.0),
            }],
            "messages": [_msg("chief_architect", "design_document", result)],
        }

    # ------------------------------------------------------------------
    # security_review: Security Reviewer assesses the design
    # ------------------------------------------------------------------

    async def security_review(self, state: InitiativeState) -> dict:
        """Security Reviewer assesses the architecture for vulnerabilities."""
        logger.info("Security Reviewer: assessing design")

        if not self.registry.has("security_reviewer"):
            logger.info("No security_reviewer agent registered; skipping review")
            await event_bus.emit(INITIATIVE_PHASE_CHANGED, {
                "initiative_id": state["initiative_id"],
                "phase": "task_planning",
            })
            return {
                "security_review": {"risk_level": "low", "cleared": True, "findings": [], "skipped": True},
                "current_phase": "task_planning",
                "messages": [_msg("system", "status", "Security review skipped (no agent registered)")],
            }

        agent_def = self.registry.get("security_reviewer")
        runtime = create_executor(agent_def, self.audit)

        extra = {
            "initiative_id": state["initiative_id"],
            "title": state["title"],
            "goal": state["goal"],
            "design_document": state.get("design_document"),
            "prd": state.get("prd"),
        }
        context = await self.ctx.build_for_initiative(
            initiative_title=state["title"],
            initiative_goal=state["goal"],
            agent_role="security",
            initiative_id=state["initiative_id"],
            workspace_path=state.get("workspace_path", ""),
            extra=extra,
        )

        result = await runtime.execute(context)
        review = result.get("security_review", {})
        risk_level = review.get("risk_level", "low")
        cleared = review.get("cleared", True)

        await self.ledger.record(
            category="architecture",
            agent_id="security_reviewer",
            decision=result.get("decision", f"Security review: {risk_level} risk"),
            reasoning=json.dumps(review.get("findings", []))[:500],
            assumptions=result.get("assumptions", []),
            risks=result.get("risks", []),
            confidence=result.get("confidence", 0.0),
            initiative_id=uuid.UUID(state["initiative_id"]),
        )
        await event_bus.emit(INITIATIVE_SECURITY_REVIEWED, {
            "initiative_id": state["initiative_id"],
            "risk_level": risk_level,
            "cleared": cleared,
            "findings_count": len(review.get("findings", [])),
        })
        await event_bus.emit(INITIATIVE_DECISION_RECORDED, {
            "initiative_id": state["initiative_id"],
            "agent_id": "security_reviewer",
            "phase": "security_review",
            "decision": result.get("decision", f"Security: {risk_level}"),
        })

        # Critical + not cleared → kill the initiative
        next_phase = "task_planning"
        if risk_level == "critical" and not cleared:
            next_phase = "closed"
            logger.warning(
                f"Initiative '{state['title']}' killed: critical security risk"
            )

        await event_bus.emit(INITIATIVE_PHASE_CHANGED, {
            "initiative_id": state["initiative_id"],
            "phase": next_phase,
        })

        return {
            "security_review": review,
            "current_phase": next_phase,
            "verdict": "kill" if next_phase == "closed" else None,
            "decisions": [{
                "agent": "security_reviewer",
                "phase": "security_review",
                "risk_level": risk_level,
                "cleared": cleared,
                "decision": result.get("decision", ""),
                "confidence": result.get("confidence", 0.0),
            }],
            "messages": [_msg("security_reviewer", "security_review", review)],
        }

    # ------------------------------------------------------------------
    # task_planning: Task Planner breaks spec into task graph
    # ------------------------------------------------------------------

    async def task_planning(self, state: InitiativeState) -> dict:
        logger.info("Task Planner: creating task graph")

        agent_def = self.registry.get("task_planner")
        runtime = create_executor(agent_def, self.audit)

        extra = {
            "initiative_id": state["initiative_id"],
            "title": state["title"],
            "prd": state.get("prd"),
            "design_document": state.get("design_document"),
            "budget_remaining": state.get("budget_remaining", 0.0),
        }
        context = await self.ctx.build_for_initiative(
            initiative_title=state["title"],
            initiative_goal=state["goal"],
            agent_role="task_planner",
            initiative_id=state["initiative_id"],
            workspace_path=state.get("workspace_path", ""),
            extra=extra,
        )

        result = await runtime.execute(context)
        task_graph = result.get("task_graph", [])

        await self.ledger.record(
            category="initiative",
            agent_id="task_planner",
            decision=result.get("decision", f"Planned {len(task_graph)} tasks"),
            reasoning=json.dumps(result.get("execution_order", []))[:500],
            assumptions=result.get("assumptions", []),
            risks=result.get("risks", []),
            confidence=result.get("confidence", 0.0),
            initiative_id=uuid.UUID(state["initiative_id"]),
        )
        await event_bus.emit(INITIATIVE_DECISION_RECORDED, {
            "initiative_id": state["initiative_id"],
            "agent_id": "task_planner",
            "phase": "task_planning",
            "decision": result.get("decision", f"Planned {len(task_graph)} tasks"),
        })
        await event_bus.emit(INITIATIVE_PHASE_CHANGED, {
            "initiative_id": state["initiative_id"],
            "phase": "executing",
            "task_count": len(task_graph),
        })

        return {
            "task_graph": task_graph,
            "current_phase": "executing",
            "decisions": [{
                "agent": "task_planner",
                "phase": "task_planning",
                "decision": result.get("decision", ""),
                "task_count": len(task_graph),
            }],
            "messages": [_msg("task_planner", "task_graph", {"task_count": len(task_graph), "tasks": task_graph})],
        }

    # ------------------------------------------------------------------
    # execute_tasks: run each task in the task graph through agents
    # ------------------------------------------------------------------

    async def execute_tasks(self, state: InitiativeState) -> dict:
        """Execute tasks from the task graph sequentially through appropriate agents."""
        logger.info("Executing task graph")

        task_graph = state.get("task_graph", [])
        if not task_graph:
            return {
                "current_phase": "evaluating",
                "messages": [_msg("system", "status", "No tasks to execute")],
            }

        results = []
        workspace_path = state.get("workspace_path", "")

        for task in task_graph:
            agent_id = task.get("assigned_agent", "backend_engineer")
            task_title = task.get("title", "Untitled task")
            task_desc = task.get("description", "")

            if not self.registry.has(agent_id):
                logger.warning(f"Agent {agent_id} not found, falling back to backend_engineer")
                agent_id = "backend_engineer"

            # Team delegation: if assigned to a team lead, delegate to specialist
            delegated_from = None
            if self.registry.is_team_lead(agent_id):
                delegated_from = agent_id
                specialist_id = await self._delegate_to_specialist(
                    agent_id, task_title, task_desc, task.get("specialist_hint", "")
                )
                if specialist_id and self.registry.has(specialist_id):
                    logger.info(f"Team delegation: {agent_id} → {specialist_id} for '{task_title}'")
                    results.append({
                        "task_id": task.get("task_id", ""),
                        "title": f"[delegation] {task_title}",
                        "agent_id": agent_id,
                        "status": "delegated",
                        "output": {"delegate_to": specialist_id, "original_agent": agent_id},
                    })
                    agent_id = specialist_id
                else:
                    # Fallback: use first team member
                    members = self.registry.get(delegated_from).team_members or []
                    if members and self.registry.has(members[0]):
                        agent_id = members[0]
                        logger.info(f"Team fallback: {delegated_from} → {agent_id}")

            agent_def = self.registry.get(agent_id)
            runtime = create_executor(agent_def, self.audit)

            context = {
                "initiative_id": state["initiative_id"],
                "task_title": task_title,
                "task_description": task_desc,
                "design_document": state.get("design_document"),
                "prd": state.get("prd"),
                "acceptance_criteria": task.get("acceptance_criteria", []),
                "workspace_path": workspace_path,
                "project_context": state.get("project_context"),
            }

            timeout_seconds = getattr(
                settings, "initiative_task_timeout_seconds", 600
            )
            await event_bus.emit(INITIATIVE_TASK_STARTED, {
                "initiative_id": state["initiative_id"],
                "task_title": task_title,
                "agent_id": agent_id,
            })
            try:
                result = await asyncio.wait_for(
                    runtime.execute(context),
                    timeout=timeout_seconds,
                )
                results.append({
                    "task_id": task.get("task_id", ""),
                    "title": task_title,
                    "agent_id": agent_id,
                    "status": "completed",
                    "output": result,
                })
                await event_bus.emit(INITIATIVE_TASK_COMPLETED, {
                    "initiative_id": state["initiative_id"],
                    "task_title": task_title,
                    "agent_id": agent_id,
                    "status": "completed",
                })
                logger.info(f"Task '{task_title}' completed by {agent_id}")
            except asyncio.TimeoutError:
                logger.warning(
                    f"Task '{task_title}' timed out after {timeout_seconds}s"
                )
                results.append({
                    "task_id": task.get("task_id", ""),
                    "title": task_title,
                    "agent_id": agent_id,
                    "status": "failed",
                    "error": f"Task timed out after {timeout_seconds}s",
                })
            except Exception as e:
                logger.error(f"Task '{task_title}' failed: {e}")
                results.append({
                    "task_id": task.get("task_id", ""),
                    "title": task_title,
                    "agent_id": agent_id,
                    "status": "failed",
                    "error": str(e),
                })

        completed = sum(1 for r in results if r["status"] == "completed")
        failed = sum(1 for r in results if r["status"] == "failed")

        return {
            "execution_results": results,
            "current_phase": "evaluating",
            "iteration_count": state.get("iteration_count", 0) + 1,
            "messages": [_msg("system", "execution_complete", {
                "total": len(results),
                "completed": completed,
                "failed": failed,
            })],
        }

    # ------------------------------------------------------------------
    # evaluate: assess outcomes and decide scale / iterate / kill
    # ------------------------------------------------------------------

    async def evaluate(self, state: InitiativeState) -> dict:
        """Evaluator assesses the initiative and decides verdict."""
        logger.info("Evaluating initiative outcomes")

        agent_def = self.registry.get("agent_evaluator")
        runtime = create_executor(agent_def, self.audit)

        execution_results = state.get("execution_results", [])
        completed = sum(1 for r in execution_results if r.get("status") == "completed")
        failed = sum(1 for r in execution_results if r.get("status") == "failed")

        context = {
            "initiative_id": state["initiative_id"],
            "title": state["title"],
            "goal": state["goal"],
            "hypothesis": state["hypothesis"],
            "prd": state.get("prd"),
            "north_star_metric": state.get("north_star_metric"),
            "success_threshold": state.get("success_threshold"),
            "execution_summary": {
                "total_tasks": len(execution_results),
                "completed": completed,
                "failed": failed,
            },
            "execution_results": execution_results[-10:],
            "decisions_made": state.get("decisions", []),
            "iteration_count": state.get("iteration_count", 0),
            "max_iterations": state.get("max_iterations", 3),
            "budget_spent": state.get("budget_spent", 0.0),
            "budget_remaining": state.get("budget_remaining", 0.0),
        }

        result = await runtime.execute(context)

        verdict = result.get("verdict", "iterate")
        if verdict not in ("scale", "iterate", "kill"):
            verdict = "iterate"

        # If iterate and we haven't hit max iterations, loop back
        can_iterate = (
            verdict == "iterate"
            and state.get("iteration_count", 0) < state.get("max_iterations", 3)
        )

        next_phase = "task_planning" if can_iterate else "closed"

        await self.ledger.record(
            category="evaluation",
            agent_id="agent_evaluator",
            decision=f"Verdict: {verdict}",
            reasoning=result.get("reasoning", ""),
            assumptions=result.get("assumptions", []),
            risks=result.get("risks", []),
            confidence=result.get("confidence", 0.0),
            initiative_id=uuid.UUID(state["initiative_id"]),
        )
        await event_bus.emit(INITIATIVE_DECISION_RECORDED, {
            "initiative_id": state["initiative_id"],
            "agent_id": "agent_evaluator",
            "phase": "evaluate",
            "verdict": verdict,
            "next_phase": next_phase,
        })
        await event_bus.emit(INITIATIVE_PHASE_CHANGED, {
            "initiative_id": state["initiative_id"],
            "phase": next_phase,
            "verdict": verdict,
        })

        return {
            "evaluation": result,
            "verdict": verdict if not can_iterate else None,
            "current_phase": next_phase,
            "decisions": [{
                "agent": "agent_evaluator",
                "phase": "evaluate",
                "verdict": verdict,
                "reasoning": result.get("reasoning", ""),
                "confidence": result.get("confidence", 0.0),
            }],
            "messages": [_msg("agent_evaluator", "evaluation", {
                "verdict": verdict,
                "reasoning": result.get("reasoning", ""),
                "next_phase": next_phase,
            })],
        }

    # ------------------------------------------------------------------
    # close: finalize the initiative
    # ------------------------------------------------------------------

    async def close(self, state: InitiativeState) -> dict:
        verdict = state.get("verdict", "kill")
        logger.info(f"Initiative closed with verdict: {verdict}")

        messages = [_msg("system", "initiative_closed", {
            "verdict": verdict,
            "iterations": state.get("iteration_count", 0),
            "budget_spent": state.get("budget_spent", 0.0),
            "tasks_executed": len(state.get("execution_results", [])),
        })]

        # Run postmortem writer for kill/iterate verdicts
        if verdict in ("kill", "iterate") and self.registry.has("postmortem_writer"):
            try:
                agent_def = self.registry.get("postmortem_writer")
                runtime = create_executor(agent_def, self.audit)
                context = {
                    "initiative_id": state["initiative_id"],
                    "title": state["title"],
                    "goal": state["goal"],
                    "hypothesis": state["hypothesis"],
                    "prd": state.get("prd"),
                    "verdict": verdict,
                    "decisions_made": state.get("decisions", []),
                    "execution_results": state.get("execution_results", [])[-10:],
                    "evaluation": state.get("evaluation"),
                    "budget_spent": state.get("budget_spent", 0.0),
                    "iteration_count": state.get("iteration_count", 0),
                }
                result = await runtime.execute(context)
                postmortem = result.get("postmortem", result)

                # Record postmortem decision
                await self.ledger.record(
                    category="evaluation",
                    agent_id="postmortem_writer",
                    decision=f"Postmortem: {postmortem.get('initiative_summary', verdict)}",
                    reasoning=json.dumps(postmortem.get("lessons_learned", []))[:500],
                    assumptions=postmortem.get("what_went_wrong", []),
                    risks=postmortem.get("process_recommendations", []),
                    confidence=result.get("confidence", 0.0),
                    initiative_id=uuid.UUID(state["initiative_id"]),
                )

                # Update decision ledger entries with outcomes if provided
                for update in result.get("decision_updates", []):
                    decision_id = update.get("decision_id")
                    if decision_id:
                        try:
                            await self.ledger.record_outcome(
                                decision_id=uuid.UUID(decision_id),
                                outcome=update.get("outcome", ""),
                                lessons_learned=update.get("lessons_learned", ""),
                            )
                        except Exception as e:
                            logger.warning(f"Failed to update decision {decision_id}: {e}")

                messages.append(_msg("postmortem_writer", "postmortem", postmortem))
                logger.info(f"Postmortem written for initiative {state['initiative_id']}")
            except Exception as e:
                logger.warning(f"Postmortem writer failed: {e}")

        await event_bus.emit(INITIATIVE_CLOSED, {
            "initiative_id": state["initiative_id"],
            "verdict": verdict,
            "iterations": state.get("iteration_count", 0),
            "budget_spent": state.get("budget_spent", 0.0),
        })

        return {
            "current_phase": "closed",
            "verdict": verdict,
            "messages": messages,
        }
