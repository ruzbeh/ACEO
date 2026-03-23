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
from aeco.logging.company_logger import log_initiative_node
from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.orchestrator.initiative_state import InitiativeState
from aeco.tools.postmortem_tools import git_workspace_snapshot

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


def _execution_timeline_text(state: InitiativeState) -> str:
    """Human-readable timeline from decisions + task execution results."""
    lines: list[str] = []
    for i, d in enumerate(state.get("decisions") or [], 1):
        agent = d.get("agent") or d.get("agent_id") or "?"
        phase = d.get("phase") or "?"
        dec = str(d.get("decision", ""))[:500]
        lines.append(f"{i}. [{phase}] {agent}: {dec}")
    for j, ex in enumerate(state.get("execution_results") or [], 1):
        title = ex.get("title", "task")
        ag = ex.get("agent_id", "?")
        st = ex.get("status", "?")
        err = ex.get("error")
        tail = f" — error: {err[:200]}" if err else ""
        lines.append(f"   Execution {j}: {title} | agent={ag} | status={st}{tail}")
    return "\n".join(lines) if lines else "(no structured execution steps recorded)"


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
        log_initiative_node(
            "intake",
            "Starting initiative workflow",
            initiative_id=state["initiative_id"],
        )
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
        log_initiative_node("pm_spec", "PM writing PRD and metrics", initiative_id=state["initiative_id"])

        agent_def = self.registry.get("pm_agent")
        runtime = create_executor(agent_def, self.audit)

        extra = {
            "initiative_id": state["initiative_id"],
            "title": state["title"],
            "goal": state["goal"],
            "hypothesis": state["hypothesis"],
            "project_context": state.get("project_context"),
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
        log_initiative_node("architect", "Chief Architect — technical design", initiative_id=state["initiative_id"])
        logger.info("Chief Architect: creating design for initiative")

        agent_def = self.registry.get("chief_architect")
        runtime = create_executor(agent_def, self.audit)

        extra = {
            "initiative_id": state["initiative_id"],
            "title": state["title"],
            "goal": state["goal"],
            "prd": state.get("prd"),
            "project_context": state.get("project_context"),
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
        log_initiative_node("security_review", "Security review of architecture", initiative_id=state["initiative_id"])

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
        log_initiative_node("task_planning", "Task Planner building task graph", initiative_id=state["initiative_id"])

        agent_def = self.registry.get("task_planner")
        runtime = create_executor(agent_def, self.audit)

        extra = {
            "initiative_id": state["initiative_id"],
            "title": state["title"],
            "prd": state.get("prd"),
            "design_document": state.get("design_document"),
            "budget_remaining": state.get("budget_remaining", 0.0),
        }

        # On iterate: inject evaluation feedback so task planner can adapt
        if state.get("evaluation") and state.get("iteration_count", 0) > 0:
            prev_eval = state["evaluation"]
            extra["iteration_feedback"] = {
                "previous_verdict": prev_eval.get("verdict", "iterate"),
                "previous_reasoning": prev_eval.get("reasoning", ""),
                "what_to_improve": prev_eval.get("what_to_improve", prev_eval.get("improvements", "")),
                "previous_execution_results": [
                    {"title": r.get("title"), "status": r.get("status"), "error": r.get("error")}
                    for r in (state.get("execution_results") or [])[-5:]
                ],
            }
            extra["instructions_addendum"] = (
                "This is an ITERATION. The evaluator reviewed the previous execution and requested changes. "
                "Review the iteration_feedback carefully and create a new task graph that addresses the feedback. "
                "Focus on fixing what went wrong, not re-doing what already succeeded."
            )

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

    # ------------------------------------------------------------------
    # _resolve_agent: resolve agent_id with fallback + team delegation
    # ------------------------------------------------------------------

    async def _resolve_agent(
        self, agent_id: str, task_title: str, task_desc: str, specialist_hint: str = ""
    ) -> tuple[str, list[dict]]:
        """Resolve the final agent_id for a task, handling team delegation.

        Returns (resolved_agent_id, delegation_results).
        """
        delegation_results: list[dict] = []

        if not self.registry.has(agent_id):
            logger.warning(f"Agent {agent_id} not found, falling back to backend_engineer")
            agent_id = "backend_engineer"

        if self.registry.is_team_lead(agent_id):
            delegated_from = agent_id
            specialist_id = await self._delegate_to_specialist(
                agent_id, task_title, task_desc, specialist_hint
            )
            if specialist_id and self.registry.has(specialist_id):
                logger.info(f"Team delegation: {agent_id} → {specialist_id} for '{task_title}'")
                delegation_results.append({
                    "task_id": "",
                    "title": f"[delegation] {task_title}",
                    "agent_id": agent_id,
                    "status": "delegated",
                    "output": {"delegate_to": specialist_id, "original_agent": agent_id},
                })
                agent_id = specialist_id
            else:
                members = self.registry.get(delegated_from).team_members or []
                if members and self.registry.has(members[0]):
                    agent_id = members[0]
                    logger.info(f"Team fallback: {delegated_from} → {agent_id}")

        return agent_id, delegation_results

    # ------------------------------------------------------------------
    # _execute_single_task: run one task with QA retry loop
    # ------------------------------------------------------------------

    MAX_QA_RETRIES = 2

    async def _execute_single_task(
        self,
        task: dict,
        state: InitiativeState,
        workspace_path: str,
    ) -> list[dict]:
        """Execute a single task, including optional QA retry loop.

        Returns a list of result dicts (may include delegation + QA entries).
        """
        results: list[dict] = []
        task_title = task.get("title", "Untitled task")
        task_desc = task.get("description", "")
        task_id = task.get("task_id", "")

        agent_id, delegation_results = await self._resolve_agent(
            task.get("assigned_agent", "backend_engineer"),
            task_title, task_desc, task.get("specialist_hint", ""),
        )
        results.extend(delegation_results)

        timeout_seconds = getattr(settings, "initiative_task_timeout_seconds", 600)
        qa_feedback: str | None = None

        for attempt in range(1 + self.MAX_QA_RETRIES):
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
            # Inject QA feedback on retries
            if qa_feedback:
                context["qa_feedback"] = qa_feedback
                context["qa_retry_attempt"] = attempt
                context["instructions_addendum"] = (
                    f"IMPORTANT: QA rejected your previous implementation. Fix these issues:\n{qa_feedback}"
                )

            await event_bus.emit(INITIATIVE_TASK_STARTED, {
                "initiative_id": state["initiative_id"],
                "task_title": task_title,
                "agent_id": agent_id,
                "attempt": attempt + 1,
            })

            try:
                result = await asyncio.wait_for(
                    runtime.execute(context), timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning(f"Task '{task_title}' timed out after {timeout_seconds}s")
                results.append({
                    "task_id": task_id, "title": task_title,
                    "agent_id": agent_id, "status": "failed",
                    "error": f"Task timed out after {timeout_seconds}s",
                })
                break
            except Exception as e:
                logger.error(f"Task '{task_title}' failed: {e}")
                results.append({
                    "task_id": task_id, "title": task_title,
                    "agent_id": agent_id, "status": "failed",
                    "error": str(e),
                })
                break

            # --- QA check (only if qa_engineer exists and task has acceptance criteria) ---
            acceptance = task.get("acceptance_criteria", [])
            if acceptance and self.registry.has("qa_engineer") and attempt < self.MAX_QA_RETRIES:
                qa_result = await self._run_qa_check(
                    state, task_title, task_desc, acceptance, result, workspace_path,
                )
                if qa_result and not qa_result.get("approved", True):
                    # QA rejected — retry with feedback
                    qa_feedback = qa_result.get("summary", "") + "\n" + "\n".join(
                        issue.get("description", str(issue)) if isinstance(issue, dict) else str(issue)
                        for issue in qa_result.get("issues", [])
                    )
                    logger.info(
                        f"QA rejected '{task_title}' (attempt {attempt + 1}/{1 + self.MAX_QA_RETRIES}). Retrying..."
                    )
                    results.append({
                        "task_id": task_id,
                        "title": f"[QA rejection] {task_title} (attempt {attempt + 1})",
                        "agent_id": "qa_engineer",
                        "status": "qa_rejected",
                        "output": qa_result,
                    })
                    continue  # Retry with QA feedback

            # Task passed (or no QA check)
            results.append({
                "task_id": task_id, "title": task_title,
                "agent_id": agent_id, "status": "completed",
                "output": result,
            })
            await event_bus.emit(INITIATIVE_TASK_COMPLETED, {
                "initiative_id": state["initiative_id"],
                "task_title": task_title,
                "agent_id": agent_id,
                "status": "completed",
            })
            logger.info(f"Task '{task_title}' completed by {agent_id}")
            break

        return results

    async def _run_qa_check(
        self,
        state: InitiativeState,
        task_title: str,
        task_desc: str,
        acceptance_criteria: list,
        engineer_output: dict,
        workspace_path: str,
    ) -> dict | None:
        """Run QA engineer to check task output. Returns QA result or None on failure."""
        try:
            qa_def = self.registry.get("qa_engineer")
            qa_runtime = create_executor(qa_def, self.audit)
            qa_context = {
                "action": "review_task",
                "initiative_id": state["initiative_id"],
                "task_title": task_title,
                "task_description": task_desc,
                "acceptance_criteria": acceptance_criteria,
                "engineer_output": {
                    k: v for k, v in engineer_output.items()
                    if k in ("decision", "code_artifacts", "files_modified", "files_changed")
                },
                "workspace_path": workspace_path,
            }
            qa_result = await asyncio.wait_for(qa_runtime.execute(qa_context), timeout=120)
            review = qa_result.get("review", qa_result)
            return review
        except Exception as e:
            logger.warning(f"QA check failed for '{task_title}': {e}")
            return None

    async def _git_auto_branch(self, workspace_path: str, initiative_id: str) -> str | None:
        """Create a feature branch for this initiative if not already on one."""
        if not workspace_path:
            return None
        branch_name = f"aeco/initiative-{initiative_id[:8]}"
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--abbrev-ref", "HEAD",
                cwd=workspace_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            current = stdout.decode().strip()
            if current == branch_name:
                return branch_name  # Already on the right branch

            # Create and checkout the branch
            proc = await asyncio.create_subprocess_exec(
                "git", "checkout", "-B", branch_name,
                cwd=workspace_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode == 0:
                logger.info(f"Git: created branch {branch_name} in {workspace_path}")
                return branch_name
            else:
                logger.warning(f"Git: failed to create branch {branch_name}")
                return None
        except Exception as e:
            logger.warning(f"Git auto-branch failed: {e}")
            return None

    async def _git_auto_commit(self, workspace_path: str, initiative_id: str, message: str) -> bool:
        """Stage all changes and commit with the given message."""
        if not workspace_path:
            return False
        try:
            # Check if there are any changes to commit
            proc = await asyncio.create_subprocess_exec(
                "git", "status", "--porcelain",
                cwd=workspace_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if not stdout.decode().strip():
                logger.info("Git: no changes to commit")
                return False

            # Stage all changes
            proc = await asyncio.create_subprocess_exec(
                "git", "add", "-A",
                cwd=workspace_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            # Commit
            full_msg = f"[AECO] {message}\n\nInitiative: {initiative_id}\nAutomated commit by AECO engineering agents"
            proc = await asyncio.create_subprocess_exec(
                "git", "commit", "-m", full_msg,
                cwd=workspace_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env={**__import__("os").environ, "GIT_AUTHOR_NAME": "AECO", "GIT_AUTHOR_EMAIL": "aeco@automated.dev",
                     "GIT_COMMITTER_NAME": "AECO", "GIT_COMMITTER_EMAIL": "aeco@automated.dev"},
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                logger.info(f"Git: committed changes — {message}")
                return True
            else:
                logger.warning(f"Git commit failed: {stderr.decode()[:200]}")
                return False
        except Exception as e:
            logger.warning(f"Git auto-commit failed: {e}")
            return False

    async def execute_tasks(self, state: InitiativeState) -> dict:
        """Execute tasks from the task graph with QA retry and concurrent execution."""
        logger.info("Executing task graph")
        task_graph = state.get("task_graph", [])
        log_initiative_node(
            "execute_tasks",
            f"Executing {len(task_graph)} task(s)",
            initiative_id=state["initiative_id"],
        )

        if not task_graph:
            return {
                "current_phase": "evaluating",
                "messages": [_msg("system", "status", "No tasks to execute")],
            }

        workspace_path = state.get("workspace_path", "")

        # Auto-create feature branch before executing tasks
        branch = await self._git_auto_branch(workspace_path, state["initiative_id"])
        max_concurrent = 3  # Max parallel tasks

        # Separate tasks into dependency groups
        # Tasks with depends_on execute after their deps; others can run in parallel
        dependent_tasks = []
        independent_tasks = []
        for task in task_graph:
            if task.get("depends_on"):
                dependent_tasks.append(task)
            else:
                independent_tasks.append(task)

        all_results: list[dict] = []

        # Run independent tasks concurrently (in batches of max_concurrent)
        if independent_tasks:
            for batch_start in range(0, len(independent_tasks), max_concurrent):
                batch = independent_tasks[batch_start : batch_start + max_concurrent]
                coros = [
                    self._execute_single_task(task, state, workspace_path)
                    for task in batch
                ]
                batch_results = await asyncio.gather(*coros, return_exceptions=True)
                for br in batch_results:
                    if isinstance(br, Exception):
                        all_results.append({
                            "task_id": "", "title": "batch_error",
                            "agent_id": "unknown", "status": "failed",
                            "error": str(br),
                        })
                    else:
                        all_results.extend(br)

        # Run dependent tasks sequentially
        for task in dependent_tasks:
            task_results = await self._execute_single_task(task, state, workspace_path)
            all_results.extend(task_results)

        completed = sum(1 for r in all_results if r.get("status") == "completed")
        failed = sum(1 for r in all_results if r.get("status") == "failed")
        qa_rejected = sum(1 for r in all_results if r.get("status") == "qa_rejected")

        # Auto-commit all changes after task execution
        iteration = state.get("iteration_count", 0) + 1
        if completed > 0:
            task_titles = [r.get("title", "") for r in all_results if r.get("status") == "completed"]
            commit_msg = f"{state.get('title', 'Initiative')} (iteration {iteration}): {', '.join(task_titles[:3])}"
            if len(task_titles) > 3:
                commit_msg += f" (+{len(task_titles) - 3} more)"
            committed = await self._git_auto_commit(workspace_path, state["initiative_id"], commit_msg)
        else:
            committed = False

        return {
            "execution_results": all_results,
            "current_phase": "evaluating",
            "iteration_count": iteration,
            "messages": [_msg("system", "execution_complete", {
                "total": len(all_results),
                "completed": completed,
                "failed": failed,
                "qa_rejected": qa_rejected,
                "git_committed": committed,
            })],
        }

    # ------------------------------------------------------------------
    # evaluate: assess outcomes and decide scale / iterate / kill
    # ------------------------------------------------------------------

    async def _fetch_live_metrics(self) -> dict:
        """Auto-pull live metrics from Stripe, Facebook, and telemetry for evaluation context."""
        live_metrics: dict = {}
        try:
            from aeco.tools.stripe_tools import stripe_get_mrr, stripe_get_revenue, stripe_get_churn
            mrr_data = await stripe_get_mrr()
            if mrr_data.get("mrr"):
                live_metrics["stripe_mrr"] = mrr_data["mrr"]
            revenue_data = await stripe_get_revenue()
            if revenue_data.get("total_revenue"):
                live_metrics["stripe_revenue"] = revenue_data["total_revenue"]
            churn_data = await stripe_get_churn()
            if churn_data.get("churn_rate"):
                live_metrics["stripe_churn_rate"] = churn_data["churn_rate"]
        except Exception as e:
            logger.debug(f"Stripe metrics fetch skipped: {e}")

        try:
            from aeco.tools.facebook_tools import facebook_get_insights
            fb_data = await facebook_get_insights()
            if fb_data.get("spend"):
                live_metrics["facebook_spend"] = fb_data["spend"]
                live_metrics["facebook_impressions"] = fb_data.get("impressions", 0)
                live_metrics["facebook_conversions"] = fb_data.get("conversions", 0)
                if fb_data.get("spend", 0) > 0:
                    live_metrics["facebook_roas"] = round(
                        fb_data.get("revenue", 0) / fb_data["spend"], 2
                    )
        except Exception as e:
            logger.debug(f"Facebook metrics fetch skipped: {e}")

        try:
            from aeco.tools.telemetry_tools import telemetry_query
            # Try to fetch the north star metric if one was defined
            # This is a best-effort query
        except Exception:
            pass

        return live_metrics

    async def evaluate(self, state: InitiativeState) -> dict:
        """Evaluator assesses the initiative and decides verdict."""
        logger.info("Evaluating initiative outcomes")
        log_initiative_node("evaluate", "Agent evaluator — scale / iterate / kill", initiative_id=state["initiative_id"])

        agent_def = self.registry.get("agent_evaluator")
        runtime = create_executor(agent_def, self.audit)

        execution_results = state.get("execution_results", [])
        completed = sum(1 for r in execution_results if r.get("status") == "completed")
        failed = sum(1 for r in execution_results if r.get("status") == "failed")

        # Auto-inject live metrics from Stripe, Facebook, telemetry
        live_metrics = await self._fetch_live_metrics()

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
            "live_metrics": live_metrics,
        }

        # On iterate: inject previous evaluation feedback into context
        if state.get("evaluation") and state.get("iteration_count", 0) > 0:
            prev_eval = state["evaluation"]
            context["iteration_feedback"] = {
                "previous_verdict": prev_eval.get("verdict", "iterate"),
                "previous_reasoning": prev_eval.get("reasoning", ""),
                "what_to_improve": prev_eval.get("what_to_improve", prev_eval.get("improvements", "")),
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

        if can_iterate:
            next_phase = "task_planning"
        elif verdict == "scale":
            next_phase = "acceptance_testing"  # Route to acceptance test gate
        else:
            next_phase = "closed"  # kill or max iterations

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
    # acceptance_test: run the app and verify it actually works
    # ------------------------------------------------------------------

    async def acceptance_test(self, state: InitiativeState) -> dict:
        """Run acceptance tests — start the app, browse it, verify acceptance criteria."""
        logger.info("Running acceptance tests on built app")
        log_initiative_node(
            "acceptance_test",
            "Acceptance tester — start app, browse, verify",
            initiative_id=state["initiative_id"],
        )

        if not self.registry.has("acceptance_tester"):
            logger.warning("acceptance_tester agent not found, skipping acceptance test")
            return {
                "current_phase": "closed",
                "messages": [_msg("system", "status", "Acceptance tester not available, skipping")],
            }

        agent_def = self.registry.get("acceptance_tester")
        runtime = create_executor(agent_def, self.audit)

        # Gather acceptance criteria from all tasks
        all_criteria = []
        for task in state.get("task_graph", []):
            for c in task.get("acceptance_criteria", []):
                all_criteria.append(f"[{task.get('title', 'task')}] {c}")

        context = {
            "initiative_id": state["initiative_id"],
            "title": state["title"],
            "goal": state["goal"],
            "workspace_path": state.get("workspace_path", ""),
            "acceptance_criteria": all_criteria,
            "prd": state.get("prd"),
            "execution_results": [
                {"title": r.get("title"), "status": r.get("status")}
                for r in (state.get("execution_results") or [])
                if r.get("status") == "completed"
            ],
        }

        try:
            result = await asyncio.wait_for(
                runtime.execute(context),
                timeout=getattr(settings, "acceptance_test_timeout_seconds", 300),
            )
        except Exception as e:
            logger.error(f"Acceptance test failed with error: {e}")
            result = {"approved": False, "summary": f"Acceptance test crashed: {e}", "issues": []}

        approved = result.get("approved", False)

        await self.ledger.record(
            category="acceptance_test",
            agent_id="acceptance_tester",
            decision=f"Acceptance: {'APPROVED' if approved else 'REJECTED'}",
            reasoning=result.get("summary", ""),
            assumptions=[],
            risks=[
                issue.get("description", str(issue)) if isinstance(issue, dict) else str(issue)
                for issue in result.get("issues", [])
            ],
            confidence=result.get("confidence", 0.0),
            initiative_id=uuid.UUID(state["initiative_id"]),
        )

        await event_bus.emit(INITIATIVE_DECISION_RECORDED, {
            "initiative_id": state["initiative_id"],
            "agent_id": "acceptance_tester",
            "phase": "acceptance_test",
            "approved": approved,
        })

        if approved:
            # Passed — proceed to close (merge + deploy)
            next_phase = "closed"
            logger.info("Acceptance test PASSED — proceeding to close")
        else:
            # Failed — can we iterate?
            iteration = state.get("iteration_count", 0)
            max_iter = state.get("max_iterations", 3)
            if iteration < max_iter:
                next_phase = "task_planning"
                logger.info(
                    f"Acceptance test FAILED — sending back to task_planning "
                    f"(iteration {iteration}/{max_iter})"
                )
            else:
                next_phase = "closed"
                logger.warning("Acceptance test FAILED and max iterations reached — closing with kill")

        return {
            "acceptance_result": result,
            "current_phase": next_phase,
            # Override verdict if acceptance failed at max iterations
            **({"verdict": "kill"} if not approved and next_phase == "closed" else {}),
            # Feed rejection details back for iterate
            **({"evaluation": {
                "verdict": "iterate",
                "reasoning": f"Acceptance test failed: {result.get('summary', '')}",
                "what_to_improve": "\n".join(
                    issue.get("description", str(issue)) if isinstance(issue, dict) else str(issue)
                    for issue in result.get("issues", [])
                ),
            }} if not approved and next_phase == "task_planning" else {}),
            "messages": [_msg("acceptance_tester", "acceptance_test", {
                "approved": approved,
                "summary": result.get("summary", ""),
                "screenshots": result.get("screenshots", []),
                "issues": result.get("issues", []),
            })],
        }

    # ------------------------------------------------------------------
    # close: finalize the initiative
    # ------------------------------------------------------------------

    async def _git_merge_to_main(self, workspace: str, initiative_id: str) -> tuple[bool, str]:
        """Merge feature branch into main and push. Returns (success, message)."""
        if not workspace:
            return False, "No workspace path"
        branch_name = f"aeco/initiative-{initiative_id[:8]}"
        try:
            import os
            env = {**os.environ, "GIT_AUTHOR_NAME": "AECO", "GIT_AUTHOR_EMAIL": "aeco@automated.dev",
                   "GIT_COMMITTER_NAME": "AECO", "GIT_COMMITTER_EMAIL": "aeco@automated.dev"}

            # Ensure everything is committed first
            await self._git_auto_commit(workspace, initiative_id, "Final changes before merge")

            # Switch to main
            proc = await asyncio.create_subprocess_exec(
                "git", "checkout", "main",
                cwd=workspace, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                return False, f"Failed to checkout main: {stderr.decode()[:200]}"

            # Merge feature branch
            proc = await asyncio.create_subprocess_exec(
                "git", "merge", branch_name, "--no-ff",
                "-m", f"[AECO] Merge {branch_name}: initiative {initiative_id[:8]} (verdict: scale)",
                cwd=workspace, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                # Abort merge on conflict
                await (await asyncio.create_subprocess_exec(
                    "git", "merge", "--abort", cwd=workspace,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )).communicate()
                return False, f"Merge conflict — aborted: {stderr.decode()[:200]}"

            logger.info(f"Git: merged {branch_name} into main")

            # Push to remote
            proc = await asyncio.create_subprocess_exec(
                "git", "push", "origin", "main",
                cwd=workspace, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                logger.info("Git: pushed main to origin")
                return True, f"Merged {branch_name} → main and pushed to origin"
            else:
                logger.warning(f"Git push failed: {stderr.decode()[:200]}")
                return True, f"Merged {branch_name} → main (push failed: {stderr.decode()[:100]})"

        except Exception as e:
            logger.warning(f"Git merge failed: {e}")
            return False, str(e)

    async def _execute_verdict_actions(self, state: InitiativeState, verdict: str) -> list[dict]:
        """Execute automated actions based on evaluator verdict.

        scale: commit → merge to main → push → deploy
        kill:  checkout main → delete feature branch → rollback deploy
        """
        action_messages: list[dict] = []
        workspace = state.get("workspace_path")

        if verdict == "scale":
            # Step 1: Merge feature branch to main and push
            merged, merge_msg = await self._git_merge_to_main(workspace, state["initiative_id"])
            if merged:
                action_messages.append(_msg("system", "verdict_action", f"Scale: {merge_msg}"))
            else:
                action_messages.append(_msg("system", "verdict_action_error", f"Scale merge failed: {merge_msg}"))

            # Step 2: Deploy to production
            try:
                from aeco.tools.deploy_tools import deploy_production
                deploy_result = await deploy_production(workspace)
                if deploy_result.get("status") == "ok":
                    url = deploy_result.get("production_url", "")
                    action_messages.append(
                        _msg("system", "verdict_action", f"Scale: deployed to production at {url}")
                    )
                    logger.info(f"Scale verdict: deployed to {url}")
                else:
                    action_messages.append(
                        _msg("system", "verdict_action_error", f"Scale deploy failed: {deploy_result.get('error')}")
                    )
            except Exception as e:
                logger.warning(f"Scale deploy action failed: {e}")
                action_messages.append(_msg("system", "verdict_action_error", f"Deploy failed: {e}"))

        elif verdict == "kill":
            # Step 1: Switch to main
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "checkout", "main",
                    cwd=workspace, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
            except Exception:
                pass

            # Step 2: Delete feature branch
            branch_name = f"aeco/initiative-{state['initiative_id'][:8]}"
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "branch", "-D", branch_name,
                    cwd=workspace, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode == 0:
                    action_messages.append(_msg("system", "verdict_action", f"Kill: deleted branch {branch_name}"))
                    logger.info(f"Kill: deleted branch {branch_name}")
            except Exception as e:
                logger.debug(f"Kill branch cleanup skipped: {e}")

            # Step 3: Rollback deployment
            try:
                from aeco.tools.deploy_tools import deploy_rollback
                rollback_result = await deploy_rollback(workspace)
                if rollback_result.get("status") == "ok":
                    action_messages.append(_msg("system", "verdict_action", "Kill: rolled back deployment"))
            except Exception as e:
                logger.debug(f"Kill rollback skipped: {e}")

        return action_messages

    async def close(self, state: InitiativeState) -> dict:
        verdict = state.get("verdict", "kill")
        logger.info(f"Initiative closed with verdict: {verdict}")
        log_initiative_node("close", f"Closing initiative (verdict={verdict})", initiative_id=state["initiative_id"])

        messages = [_msg("system", "initiative_closed", {
            "verdict": verdict,
            "iterations": state.get("iteration_count", 0),
            "budget_spent": state.get("budget_spent", 0.0),
            "tasks_executed": len(state.get("execution_results", [])),
        })]

        # Execute verdict actions (deploy on scale, rollback on kill)
        verdict_messages = await self._execute_verdict_actions(state, verdict)
        messages.extend(verdict_messages)

        # Run postmortem writer for kill/iterate verdicts
        if verdict in ("kill", "iterate") and self.registry.has("postmortem_writer"):
            try:
                agent_def = self.registry.get("postmortem_writer")
                runtime = create_executor(agent_def, self.audit)
                pre_git = await git_workspace_snapshot(
                    state.get("workspace_path"),
                    max_diff_chars=20000,
                )
                context = {
                    "initiative_id": state["initiative_id"],
                    "title": state["title"],
                    "goal": state["goal"],
                    "hypothesis": state["hypothesis"],
                    "workspace_path": state.get("workspace_path"),
                    "prd": state.get("prd"),
                    "verdict": verdict,
                    "decisions_made": state.get("decisions", []),
                    "execution_results": state.get("execution_results", [])[-10:],
                    "execution_timeline_text": _execution_timeline_text(state),
                    "git_evidence_precomputed": pre_git,
                    "dashboard_base_url": settings.postmortem_dashboard_base_url or "",
                    "evaluation": state.get("evaluation"),
                    "budget_spent": state.get("budget_spent", 0.0),
                    "iteration_count": state.get("iteration_count", 0),
                    "postmortem_deliverables": (
                        "Produce a full markdown report with file_write at "
                        f"postmortems/{state['initiative_id']}/POSTMORTEM.md (create directory implicitly). "
                        "Use tools: git_workspace_snapshot for live diff, capture_page_screenshot for "
                        "dashboard_base_url or deployed URLs. Final JSON must list report path and screenshots."
                    ),
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

                doc_meta = result.get("documentation") or {}
                messages.append(
                    _msg(
                        "postmortem_writer",
                        "postmortem",
                        {
                            "postmortem": postmortem,
                            "documentation": doc_meta,
                            "report_markdown_path": doc_meta.get("report_markdown_path"),
                            "screenshots": doc_meta.get("screenshots", []),
                        },
                    )
                )
                rpath = doc_meta.get("report_markdown_path")
                if rpath:
                    logger.info(
                        "Postmortem markdown report for initiative %s: %s",
                        state["initiative_id"],
                        rpath,
                    )
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
