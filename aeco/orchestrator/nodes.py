"""Node functions for the AECO LangGraph workflow."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from aeco.agents.executor_factory import create_executor
from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.logging.company_logger import log_node_enter, log_node_exit
from aeco.orchestrator.state import AECOState
from aeco.budget.engine import BudgetEngine, SpendRequest, estimate_cost
from aeco.models.budget import SpendCategory
from aeco.tools.clickup_tools import clickup_create_comment, clickup_create_task
from aeco.tools.file_tools import file_write

if TYPE_CHECKING:
    from aeco.memory.vector import VectorMemory

logger = logging.getLogger(__name__)


def _make_message(sender: str, msg_type: str, content: Any) -> dict:
    return {
        "sender": sender,
        "type": msg_type,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class WorkflowNodes:
    """Container for all node functions, with shared dependencies."""

    def __init__(
        self,
        registry: AgentRegistry,
        audit_logger: AuditLogger,
        vector_memory: "VectorMemory | None" = None,
        budget_engine: "BudgetEngine | None" = None,
    ) -> None:
        self.registry = registry
        self.audit_logger = audit_logger
        self.vector_memory = vector_memory
        self.budget_engine = budget_engine

    def _relevant_past(self, state: AECOState, n: int = 5) -> list[dict]:
        """Retrieve semantically relevant past artifacts for context."""
        if not self.vector_memory:
            return []
        query = f"{state.get('task_title', '')} {state.get('task_description', '')}".strip()
        if not query:
            return []
        try:
            return self.vector_memory.search(query, n_results=n)
        except Exception as e:
            logger.warning(f"Vector memory search failed: {e}")
            return []

    def _ingest_artifact(
        self, content: str, task_id: str, artifact_type: str, agent_id: str
    ) -> None:
        """Store an artifact in vector memory for future retrieval."""
        if not self.vector_memory:
            return
        try:
            self.vector_memory.add(
                content[:50000],  # cap size for embedding
                metadata={
                    "task_id": task_id,
                    "type": artifact_type,
                    "agent_id": agent_id,
                },
            )
        except Exception as e:
            logger.warning(f"Vector memory ingest failed: {e}")

    async def intake(self, state: AECOState) -> dict:
        """Initialize the workflow. Create ClickUp task if needed."""
        run_id = state.get("workflow_run_id")
        task_id = state.get("task_id")
        task_title = state.get("task_title", "")
        log_node_enter("intake", run_id=run_id, task_id=task_id, task_title=task_title)

        logger.info(f"Intake: processing task '{state['task_title']}'")

        clickup_task_id = state.get("clickup_task_id")

        # Create ClickUp task if we don't have one
        if not clickup_task_id:
            try:
                result = await clickup_create_task(
                    name=state["task_title"],
                    description=state["task_description"],
                )
                clickup_task_id = result["id"]
                logger.info(f"Created ClickUp task: {clickup_task_id}")
            except Exception as e:
                logger.warning(f"Failed to create ClickUp task: {e}")

        workspace_path = state.get("workspace_path", "")
        logger.info(f"Intake: workspace_path={workspace_path}")

        log_node_exit("intake", run_id=run_id, task_id=task_id, next_action=None)
        return {
            "clickup_task_id": clickup_task_id,
            "status": "intake",
            "current_agent": "coo_orchestrator",
            "messages": [
                _make_message(
                    "system",
                    "status_update",
                    f"Workflow started for: {state['task_title']}",
                )
            ],
        }

    async def route(self, state: AECOState) -> dict:
        """COO Orchestrator decides what happens next."""
        run_id = state.get("workflow_run_id")
        task_id = state.get("task_id")
        task_title = state.get("task_title", "")
        iteration = state.get("iteration_count", 0)
        log_node_enter("route", run_id=run_id, task_id=task_id, task_title=task_title, iteration=iteration)

        logger.info(f"Route: iteration {state['iteration_count']}")

        agent_def = self.registry.get("coo_orchestrator")
        runtime = create_executor(agent_def, self.audit_logger)

        context = {
            "workflow_run_id": run_id,
            "task_id": task_id,
            "task_title": state["task_title"],
            "task_description": state["task_description"],
            "current_status": state["status"],
            "iteration_count": state["iteration_count"],
            "max_iterations": state["max_iterations"],
            "has_design": state.get("design_document") is not None,
            "has_code": len(state.get("code_artifacts", [])) > 0,
            "has_test_results": state.get("test_results") is not None,
            "review_feedback": state.get("review_feedback"),
            "recent_messages": state.get("messages", [])[-5:],
            "relevant_past_work": self._relevant_past(state),
            "workspace_path": state.get("workspace_path", ""),
            "project_context": state.get("project_context"),
        }

        result = await runtime.execute(context)

        next_action = result.get("next_action", "needs_design")
        reasoning = result.get("reasoning", "")
        log_node_exit("route", run_id=run_id, task_id=task_id, next_action=next_action, reasoning=reasoning)

        logger.info(f"Route decision: {next_action} — {reasoning}")

        return {
            "next_action": next_action,
            "current_agent": "coo_orchestrator",
            "iteration_count": state["iteration_count"] + 1,
            "messages": [
                _make_message(
                    "coo_orchestrator",
                    "status_update",
                    {"decision": next_action, "reasoning": reasoning},
                )
            ],
        }

    async def architect(self, state: AECOState) -> dict:
        """Chief Architect produces a design document."""
        run_id = state.get("workflow_run_id")
        task_id = state.get("task_id")
        task_title = state.get("task_title", "")
        log_node_enter("architect", run_id=run_id, task_id=task_id, task_title=task_title)

        logger.info("Architect: creating design document")

        agent_def = self.registry.get("chief_architect")
        runtime = create_executor(agent_def, self.audit_logger)

        context = {
            "workflow_run_id": run_id,
            "task_id": task_id,
            "task_title": state["task_title"],
            "task_description": state["task_description"],
            "existing_messages": state.get("messages", [])[-10:],
            "relevant_past_work": self._relevant_past(state),
            "workspace_path": state.get("workspace_path", ""),
            "project_context": state.get("project_context"),
        }

        result = await runtime.execute(context)
        design_doc = json.dumps(result.get("design_document", result), indent=2)

        self._ingest_artifact(
            design_doc, state["task_id"], "design", "chief_architect"
        )

        # Post design to ClickUp
        if state.get("clickup_task_id"):
            try:
                await clickup_create_comment(
                    state["clickup_task_id"],
                    f"**Architecture Design**\n\n```json\n{design_doc[:3000]}\n```",
                )
            except Exception as e:
                logger.warning(f"Failed to post design to ClickUp: {e}")

        log_node_exit("architect", run_id=run_id, task_id=task_id, next_action="needs_implementation")
        return {
            "design_document": design_doc,
            "status": "architect_design",
            "current_agent": "chief_architect",
            "next_action": "needs_implementation",
            "messages": [
                _make_message("chief_architect", "design_document", result)
            ],
        }

    async def engineer(self, state: AECOState) -> dict:
        """Backend Engineer writes code based on the design."""
        run_id = state.get("workflow_run_id")
        task_id = state.get("task_id")
        task_title = state.get("task_title", "")
        log_node_enter("engineer", run_id=run_id, task_id=task_id, task_title=task_title)

        logger.info("Engineer: implementing code")

        agent_def = self.registry.get("backend_engineer")
        runtime = create_executor(agent_def, self.audit_logger)

        workspace_path = state.get("workspace_path", "")

        context = {
            "workflow_run_id": run_id,
            "task_id": task_id,
            "task_title": state["task_title"],
            "task_description": state["task_description"],
            "design_document": state.get("design_document"),
            "review_feedback": state.get("review_feedback"),
            "existing_code": state.get("code_artifacts", []),
            "recent_messages": state.get("messages", [])[-10:],
            "relevant_past_work": self._relevant_past(state),
            "workspace_path": workspace_path,
            "project_context": state.get("project_context"),
        }

        result = await runtime.execute(context)
        code_artifacts = result.get("code_artifacts", [])

        # Write code artifacts to the workspace
        for artifact in code_artifacts:
            artifact_path = artifact.get("path")
            artifact_content = artifact.get("content")
            if artifact_path and artifact_content:
                try:
                    await file_write(artifact_path, artifact_content, workspace_path=workspace_path or None)
                    logger.info(f"Wrote file: {artifact_path}")
                except Exception as e:
                    logger.error(f"Failed to write {artifact_path}: {e}")

        code_summary = json.dumps(
            [{"path": a.get("path"), "summary": a.get("content", "")[:500]} for a in code_artifacts],
            indent=2,
        )
        self._ingest_artifact(
            code_summary, state["task_id"], "code", "backend_engineer"
        )

        # Post summary to ClickUp
        if state.get("clickup_task_id"):
            files = [a.get("path", "unknown") for a in code_artifacts]
            try:
                await clickup_create_comment(
                    state["clickup_task_id"],
                    f"**Implementation Complete**\nFiles: {', '.join(files)}",
                )
            except Exception as e:
                logger.warning(f"Failed to post to ClickUp: {e}")

        log_node_exit("engineer", run_id=run_id, task_id=task_id, next_action="needs_qa", files_written=len(code_artifacts))
        return {
            "status": "engineering",
            "current_agent": "backend_engineer",
            "next_action": "needs_qa",
            "review_feedback": None,  # Clear previous feedback
            "code_artifacts": code_artifacts,
            "messages": [_make_message("backend_engineer", "code_artifact", result)],
        }

    async def frontend(self, state: AECOState) -> dict:
        """Frontend Engineer implements UI based on the design."""
        logger.info("Frontend: implementing UI")

        agent_def = self.registry.get("frontend_engineer")
        runtime = create_executor(agent_def, self.audit_logger)

        context = {
            "task_title": state["task_title"],
            "task_description": state["task_description"],
            "design_document": state.get("design_document"),
            "review_feedback": state.get("review_feedback"),
            "existing_code": state.get("code_artifacts", []),
            "recent_messages": state.get("messages", [])[-10:],
            "relevant_past_work": self._relevant_past(state),
        }

        result = await runtime.execute(context)
        code_artifacts = result.get("code_artifacts", [])
        code_summary = json.dumps(
            [
                {"path": a.get("path"), "summary": (a.get("content", "") or "")[:500]}
                for a in code_artifacts
            ],
            indent=2,
        )
        self._ingest_artifact(
            code_summary, state["task_id"], "code", "frontend_engineer"
        )

        if state.get("clickup_task_id"):
            files = [a.get("path", "unknown") for a in code_artifacts]
            try:
                await clickup_create_comment(
                    state["clickup_task_id"],
                    f"**Frontend Implementation**\nFiles: {', '.join(files)}",
                )
            except Exception as e:
                logger.warning(f"Failed to post to ClickUp: {e}")

        return {
            "status": "engineering",
            "current_agent": "frontend_engineer",
            "next_action": "needs_qa",
            "review_feedback": None,
            "code_artifacts": code_artifacts,
            "messages": [_make_message("frontend_engineer", "code_artifact", result)],
        }

    async def qa(self, state: AECOState) -> dict:
        """QA Engineer reviews code and runs tests."""
        run_id = state.get("workflow_run_id")
        task_id = state.get("task_id")
        task_title = state.get("task_title", "")
        log_node_enter("qa", run_id=run_id, task_id=task_id, task_title=task_title)

        logger.info("QA: reviewing and testing")

        agent_def = self.registry.get("qa_engineer")
        runtime = create_executor(agent_def, self.audit_logger)

        context = {
            "workflow_run_id": run_id,
            "task_id": task_id,
            "task_title": state["task_title"],
            "task_description": state["task_description"],
            "design_document": state.get("design_document"),
            "code_artifacts": state.get("code_artifacts", []),
            "recent_messages": state.get("messages", [])[-10:],
            "relevant_past_work": self._relevant_past(state),
            "workspace_path": state.get("workspace_path", ""),
            "project_context": state.get("project_context"),
        }

        result = await runtime.execute(context)
        review_summary = json.dumps(
            result.get("review", result.get("test_results", {})),
            indent=2,
        )
        self._ingest_artifact(review_summary, state["task_id"], "qa_review", "qa_engineer")

        review = result.get("review", {})
        approved = review.get("approved", False)
        feedback = review.get("summary", "")
        test_results = result.get("test_results", {})

        # Post review to ClickUp
        if state.get("clickup_task_id"):
            status_emoji = "approved" if approved else "needs changes"
            try:
                await clickup_create_comment(
                    state["clickup_task_id"],
                    f"**QA Review: {status_emoji}**\n{feedback}",
                )
            except Exception as e:
                logger.warning(f"Failed to post QA review to ClickUp: {e}")

        next_action = "all_done" if approved else "needs_implementation"
        log_node_exit("qa", run_id=run_id, task_id=task_id, next_action=next_action, approved=approved)

        return {
            "status": "qa_review",
            "current_agent": "qa_engineer",
            "next_action": next_action,
            "review_feedback": None if approved else feedback,
            "test_results": test_results,
            "messages": [_make_message("qa_engineer", "code_review", result)],
        }

    async def budget_check(self, state: AECOState) -> dict:
        """Budget Controller evaluates spend and provides optimization feedback.

        Runs after route decides the next agent, before that agent executes.
        Estimates the cost of the upcoming agent call and checks budget.
        If budget is exhausted, forces publish. Also injects optimization
        hints from past spend patterns back into the workflow state.
        """
        run_id = state.get("workflow_run_id")
        task_id = state.get("task_id")
        task_title = state.get("task_title", "")
        iteration = state.get("iteration_count", 0)
        log_node_enter("budget_check", run_id=run_id, task_id=task_id, task_title=task_title)

        if not self.budget_engine:
            log_node_exit("budget_check", run_id=run_id, task_id=task_id, next_action=None)
            return {
                "budget_approved": True,
                "messages": [
                    _make_message("system", "budget", "No budget engine configured; skipping check")
                ],
            }

        # Estimate cost for the upcoming agent call (~4K tokens avg)
        next_agent = state.get("current_agent", "unknown")
        estimated_tokens = 4000
        estimated_cost = estimate_cost(estimated_tokens, "anthropic/claude-sonnet-4")

        import uuid as _uuid

        request = SpendRequest(
            agent_id=next_agent,
            amount=estimated_cost,
            category=SpendCategory.LLM_TOKENS,
            description=f"Estimated cost for iteration {iteration} of workflow {run_id}",
            workflow_run_id=_uuid.UUID(run_id) if run_id else None,
            task_id=_uuid.UUID(task_id) if task_id else None,
            tokens_used=estimated_tokens,
            llm_model="anthropic/claude-sonnet-4",
        )

        decision = await self.budget_engine.request_spend(request, pre_approval_only=True)
        approved = decision.status.value in ("auto_approved", "approved")

        updates: dict = {
            "budget_approved": approved,
            "budget_spent": state.get("budget_spent", 0.0) + (estimated_cost if approved else 0.0),
            "budget_remaining": decision.remaining_budget,
            "budget_warnings": decision.warnings,
            "budget_optimization_hints": decision.optimization_hints,
            "messages": [
                _make_message(
                    "budget_controller",
                    "budget_decision",
                    {
                        "status": decision.status.value,
                        "reasoning": decision.reasoning,
                        "amount": decision.amount,
                        "remaining": decision.remaining_budget,
                        "utilization": decision.utilization_percent,
                        "warnings": decision.warnings,
                        "optimization_hints": decision.optimization_hints,
                    },
                )
            ],
        }

        if not approved:
            logger.warning(
                f"Budget denied for {next_agent}: {decision.reasoning}"
            )
            updates["next_action"] = "all_done"
            updates["errors"] = [
                f"Budget denied: {decision.reasoning}"
            ]

        # If there are optimization hints, also call the Budget Controller agent
        # to generate a richer feedback message for the workflow
        if decision.optimization_hints and self.registry.has("budget_controller"):
            try:
                agent_def = self.registry.get("budget_controller")
                runtime = create_executor(agent_def, self.audit_logger)
                context = {
                    "workflow_run_id": run_id,
                    "task_id": task_id,
                    "current_spend": state.get("budget_spent", 0.0),
                    "remaining_budget": decision.remaining_budget,
                    "utilization_percent": decision.utilization_percent,
                    "optimization_hints": decision.optimization_hints,
                    "warnings": decision.warnings,
                    "iteration_count": iteration,
                    "recent_messages": state.get("messages", [])[-5:],
                }
                result = await runtime.execute(context)
                if result.get("warnings"):
                    updates["budget_warnings"] = updates.get("budget_warnings", []) + result["warnings"]
            except Exception as e:
                logger.warning(f"Budget Controller agent call failed: {e}")

        log_node_exit("budget_check", run_id=run_id, task_id=task_id, approved=approved)
        return updates

    async def publish(self, state: AECOState) -> dict:
        """Finalize: update ClickUp task status and post summary."""
        run_id = state.get("workflow_run_id")
        task_id = state.get("task_id")
        log_node_enter("publish", run_id=run_id, task_id=task_id, task_title=state.get("task_title", ""))

        logger.info("Publish: finalizing workflow")

        # Update ClickUp task to done
        budget_summary = ""
        if state.get("budget_spent", 0) > 0:
            budget_summary = (
                f"\nBudget: ${state.get('budget_spent', 0):.4f} spent, "
                f"${state.get('budget_remaining', 0):.4f} remaining"
            )
            hints = state.get("budget_optimization_hints", [])
            if hints:
                budget_summary += f"\nOptimization hints: {'; '.join(hints[:3])}"

        if state.get("clickup_task_id"):
            try:
                await clickup_create_comment(
                    state["clickup_task_id"],
                    f"**Workflow Complete**\n"
                    f"Iterations: {state['iteration_count']}\n"
                    f"Files created: {len(state.get('code_artifacts', []))}"
                    f"{budget_summary}",
                )
            except Exception as e:
                logger.warning(f"Failed to post completion to ClickUp: {e}")

        log_node_exit("publish", run_id=run_id, task_id=task_id, next_action=None)
        return {
            "status": "done",
            "current_agent": None,
            "next_action": None,
            "messages": [
                _make_message(
                    "system",
                    "status_update",
                    f"Workflow completed after {state['iteration_count']} iterations",
                )
            ],
        }
