"""Node functions for the portfolio-level LangGraph workflow.

Flow: opportunity_scan → portfolio_review → execute_portfolio → portfolio_evaluate → rebalance → (loop or close)
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
    PORTFOLIO_CLOSED,
    PORTFOLIO_CYCLE_STARTED,
    PORTFOLIO_DECISIONS_MADE,
    PORTFOLIO_EVALUATED,
    PORTFOLIO_EXECUTION_COMPLETED,
    PORTFOLIO_EXECUTION_STARTED,
    PORTFOLIO_OPPORTUNITIES_DISCOVERED,
    PORTFOLIO_REBALANCED,
    event_bus,
)
from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.orchestrator.portfolio_state import PortfolioState

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


class PortfolioNodes:
    """Node functions for portfolio-level orchestration."""

    def __init__(
        self,
        registry: AgentRegistry,
        audit_logger: AuditLogger,
        context_builder: ContextBuilder,
        decision_ledger: DecisionLedgerStore,
        budget_engine: "BudgetEngine | None" = None,
        initiative_graph: Any = None,
    ) -> None:
        self.registry = registry
        self.audit = audit_logger
        self.ctx = context_builder
        self.ledger = decision_ledger
        self.budget = budget_engine
        self.initiative_graph = initiative_graph

    # ------------------------------------------------------------------
    # opportunity_scan: Product Strategist discovers opportunities
    # ------------------------------------------------------------------

    async def opportunity_scan(self, state: PortfolioState) -> dict:
        cycle = state.get("cycle_count", 0)
        logger.info(f"Portfolio cycle {cycle}: scanning for opportunities")

        await event_bus.emit(PORTFOLIO_CYCLE_STARTED, {
            "portfolio_id": state["portfolio_id"],
            "cycle": cycle,
        })

        agent_def = self.registry.get("product_strategist")
        runtime = create_executor(agent_def, self.audit)

        # Gather context for the strategist
        recent_outcomes = []
        for init in state.get("active_initiatives", []):
            if init.get("verdict"):
                recent_outcomes.append({
                    "title": init.get("title"),
                    "verdict": init.get("verdict"),
                    "budget_spent": init.get("budget_spent", 0),
                })

        context = {
            "company_goals": state.get("company_goals", []),
            "recent_outcomes": recent_outcomes,
            "active_initiatives": state.get("active_initiatives", []),
            "budget_remaining": state.get("budget_remaining", 0),
            "cycle_count": cycle,
            "past_opportunities": state.get("opportunities", [])[-10:],
        }

        result = await runtime.execute(context)

        opportunities = result.get("opportunities", [])
        logger.info(f"Product Strategist discovered {len(opportunities)} opportunities")

        await self.ledger.record(
            category="portfolio",
            agent_id="product_strategist",
            decision=result.get("decision", f"Discovered {len(opportunities)} opportunities"),
            reasoning=json.dumps([o.get("title") for o in opportunities])[:500],
            assumptions=result.get("assumptions", []),
            risks=result.get("risks", []),
            confidence=result.get("confidence", 0.0),
        )

        await event_bus.emit(PORTFOLIO_OPPORTUNITIES_DISCOVERED, {
            "portfolio_id": state["portfolio_id"],
            "count": len(opportunities),
            "titles": [o.get("title", "") for o in opportunities],
        })

        return {
            "opportunities": opportunities,
            "current_phase": "portfolio_review",
            "decisions": [{
                "agent": "product_strategist",
                "phase": "opportunity_scan",
                "decision": result.get("decision", ""),
                "opportunity_count": len(opportunities),
            }],
            "messages": [_msg("product_strategist", "opportunities", {
                "count": len(opportunities),
                "opportunities": opportunities,
            })],
        }

    # ------------------------------------------------------------------
    # portfolio_review: CEO reviews and makes funding/kill decisions
    # ------------------------------------------------------------------

    async def portfolio_review(self, state: PortfolioState) -> dict:
        logger.info("CEO: reviewing portfolio and opportunities")

        agent_def = self.registry.get("ceo_director")
        runtime = create_executor(agent_def, self.audit)

        context = {
            "company_goals": state.get("company_goals", []),
            "active_initiatives": state.get("active_initiatives", []),
            "opportunities": state.get("opportunities", [])[-10:],
            "budget_state": {
                "total": state.get("total_budget", 0),
                "spent": state.get("budget_spent", 0),
                "remaining": state.get("budget_remaining", 0),
            },
            "past_decisions": state.get("portfolio_decisions", [])[-5:],
            "cycle_count": state.get("cycle_count", 0),
        }

        result = await runtime.execute(context)

        funded = result.get("fund", [])
        killed = result.get("kill", [])
        scaled = result.get("scale", [])

        logger.info(
            f"CEO decisions: fund {len(funded)}, kill {len(killed)}, scale {len(scaled)}"
        )

        await self.ledger.record(
            category="portfolio",
            agent_id="ceo_director",
            decision=result.get("decision", f"Fund {len(funded)}, kill {len(killed)}"),
            reasoning=result.get("reasoning", ""),
            assumptions=result.get("assumptions", []),
            risks=result.get("risks", []),
            confidence=result.get("confidence", 0.0),
        )

        await event_bus.emit(PORTFOLIO_DECISIONS_MADE, {
            "portfolio_id": state["portfolio_id"],
            "funded": len(funded),
            "killed": len(killed),
            "scaled": len(scaled),
        })

        return {
            "funded_initiatives": funded,
            "killed_initiatives": killed,
            "current_phase": "executing",
            "portfolio_decisions": [{
                "agent": "ceo_director",
                "phase": "portfolio_review",
                "funded": [f.get("title") for f in funded],
                "killed": killed,
                "scaled": scaled,
                "reasoning": result.get("reasoning", ""),
            }],
            "messages": [_msg("ceo_director", "portfolio_decision", result)],
        }

    # ------------------------------------------------------------------
    # execute_portfolio: run funded initiatives via existing initiative graph
    # ------------------------------------------------------------------

    async def execute_portfolio(self, state: PortfolioState) -> dict:
        """Create and run initiatives sequentially using the existing initiative graph."""
        funded = state.get("funded_initiatives", [])
        killed = state.get("killed_initiatives", [])
        workspace_path = state.get("workspace_path", settings.workspace_path)

        logger.info(f"Executing portfolio: {len(funded)} to fund, {len(killed)} to kill")

        await event_bus.emit(PORTFOLIO_EXECUTION_STARTED, {
            "portfolio_id": state["portfolio_id"],
            "initiatives_to_run": len(funded),
            "initiatives_to_kill": len(killed),
        })

        results = []

        # Kill marked initiatives
        for init_id in killed:
            try:
                from aeco.db.session import async_session_factory
                from aeco.models.initiative import Initiative, InitiativeStatus, InitiativeVerdict
                async with async_session_factory() as session:
                    initiative = await session.get(Initiative, uuid.UUID(init_id))
                    if initiative and initiative.status != InitiativeStatus.CLOSED.value:
                        initiative.status = InitiativeStatus.CLOSED.value
                        initiative.verdict = InitiativeVerdict.KILL.value
                        await session.commit()
                        logger.info(f"Killed initiative: {initiative.title}")
                        results.append({
                            "title": initiative.title,
                            "action": "killed",
                            "initiative_id": init_id,
                        })
            except Exception as e:
                logger.warning(f"Failed to kill initiative {init_id}: {e}")

        # Run funded initiatives
        for funded_init in funded:
            title = funded_init.get("title", "Untitled")
            goal = funded_init.get("goal", "")
            hypothesis = funded_init.get("hypothesis", "")
            allocated = funded_init.get("allocated_budget", 0)

            if not self.initiative_graph:
                logger.warning("No initiative graph available; skipping execution")
                results.append({
                    "title": title,
                    "action": "skipped",
                    "reason": "No initiative graph",
                })
                continue

            # Create initiative in DB
            try:
                from aeco.db.session import async_session_factory
                from aeco.models.initiative import Initiative
                async with async_session_factory() as session:
                    initiative = Initiative(
                        title=title,
                        goal=goal,
                        hypothesis=hypothesis,
                    )
                    session.add(initiative)
                    await session.commit()
                    await session.refresh(initiative)
                    init_id = str(initiative.id)
            except Exception as e:
                logger.error(f"Failed to create initiative '{title}': {e}")
                results.append({"title": title, "action": "failed", "error": str(e)})
                continue

            # Build initial state for initiative graph
            from aeco.orchestrator.initiative_state import InitiativeState
            init_state: InitiativeState = {
                "initiative_id": init_id,
                "title": title,
                "goal": goal,
                "hypothesis": hypothesis,
                "workspace_path": workspace_path,
                "project_context": None,
                "prd": None,
                "design_document": None,
                "security_review": None,
                "task_graph": [],
                "execution_results": [],
                "evaluation": None,
                "north_star_metric": None,
                "local_metrics": [],
                "success_threshold": None,
                "evaluation_window_days": 7,
                "decisions": [],
                "current_phase": "intake",
                "verdict": None,
                "iteration_count": 0,
                "max_iterations": 2,
                "messages": [],
                "errors": [],
                "budget_spent": 0.0,
                "budget_remaining": allocated,
            }

            timeout = getattr(settings, "initiative_task_timeout_seconds", 600) * 3

            try:
                logger.info(f"Running initiative: {title}")
                final_state = await asyncio.wait_for(
                    self.initiative_graph.ainvoke(init_state),
                    timeout=timeout,
                )

                verdict = final_state.get("verdict", "kill")
                budget_used = final_state.get("budget_spent", 0)

                # Update DB
                from aeco.models.initiative import Initiative, InitiativeStatus
                async with async_session_factory() as session:
                    db_init = await session.get(Initiative, uuid.UUID(init_id))
                    if db_init and db_init.status != InitiativeStatus.CLOSED.value:
                        db_init.status = InitiativeStatus.CLOSED.value
                        db_init.verdict = verdict
                        db_init.north_star_metric = final_state.get("north_star_metric")
                        await session.commit()

                results.append({
                    "title": title,
                    "initiative_id": init_id,
                    "action": "completed",
                    "verdict": verdict,
                    "budget_spent": budget_used,
                    "tasks_executed": len(final_state.get("execution_results", [])),
                })
                logger.info(f"Initiative '{title}' completed: verdict={verdict}")

            except asyncio.TimeoutError:
                logger.warning(f"Initiative '{title}' timed out")
                results.append({
                    "title": title,
                    "initiative_id": init_id,
                    "action": "timeout",
                })
            except Exception as e:
                logger.error(f"Initiative '{title}' failed: {e}")
                results.append({
                    "title": title,
                    "initiative_id": init_id,
                    "action": "failed",
                    "error": str(e),
                })

        total_spent = sum(r.get("budget_spent", 0) for r in results)

        await event_bus.emit(PORTFOLIO_EXECUTION_COMPLETED, {
            "portfolio_id": state["portfolio_id"],
            "results_count": len(results),
            "total_spent": total_spent,
        })

        return {
            "execution_results": results,
            "budget_spent": state.get("budget_spent", 0) + total_spent,
            "budget_remaining": state.get("budget_remaining", 0) - total_spent,
            "current_phase": "evaluating",
            "messages": [_msg("system", "execution_complete", {
                "results": len(results),
                "budget_spent": total_spent,
            })],
        }

    # ------------------------------------------------------------------
    # portfolio_evaluate: aggregate outcomes across initiatives
    # ------------------------------------------------------------------

    async def portfolio_evaluate(self, state: PortfolioState) -> dict:
        logger.info("Evaluating portfolio outcomes")

        results = state.get("execution_results", [])
        completed = [r for r in results if r.get("action") == "completed"]
        scaled = [r for r in completed if r.get("verdict") == "scale"]
        killed_results = [r for r in completed if r.get("verdict") == "kill"]
        iterated = [r for r in completed if r.get("verdict") == "iterate"]

        summary = {
            "total_executed": len(results),
            "completed": len(completed),
            "scaled": len(scaled),
            "killed": len(killed_results),
            "iterated": len(iterated),
            "failed": len([r for r in results if r.get("action") in ("failed", "timeout")]),
            "total_budget_spent": state.get("budget_spent", 0),
            "budget_remaining": state.get("budget_remaining", 0),
            "success_rate": len(scaled) / max(len(completed), 1),
        }

        await self.ledger.record(
            category="portfolio",
            agent_id="system",
            decision=f"Portfolio evaluation: {summary['scaled']} scaled, {summary['killed']} killed",
            reasoning=json.dumps(summary),
            assumptions=[],
            risks=[],
            confidence=1.0,
        )

        await event_bus.emit(PORTFOLIO_EVALUATED, {
            "portfolio_id": state["portfolio_id"],
            **summary,
        })

        return {
            "current_phase": "rebalancing",
            "decisions": [{
                "agent": "system",
                "phase": "portfolio_evaluate",
                "summary": summary,
            }],
            "messages": [_msg("system", "portfolio_evaluation", summary)],
        }

    # ------------------------------------------------------------------
    # rebalance: decide whether to continue the portfolio loop
    # ------------------------------------------------------------------

    async def rebalance(self, state: PortfolioState) -> dict:
        cycle = state.get("cycle_count", 0) + 1
        max_cycles = state.get("max_cycles", 3)
        budget_remaining = state.get("budget_remaining", 0)

        should_continue = cycle < max_cycles and budget_remaining > 0

        next_phase = "opportunity_scan" if should_continue else "closed"
        logger.info(
            f"Rebalance: cycle {cycle}/{max_cycles}, "
            f"budget remaining ${budget_remaining:.2f}, "
            f"next={next_phase}"
        )

        # Refresh active initiatives from DB for next cycle
        active = []
        if should_continue:
            try:
                from aeco.db.session import async_session_factory
                from aeco.models.initiative import Initiative, InitiativeStatus
                from sqlalchemy import select
                async with async_session_factory() as session:
                    result = await session.execute(
                        select(Initiative).where(
                            Initiative.status != InitiativeStatus.CLOSED.value
                        )
                    )
                    for init in result.scalars():
                        active.append({
                            "id": str(init.id),
                            "title": init.title,
                            "status": init.status,
                            "verdict": init.verdict,
                        })
            except Exception as e:
                logger.warning(f"Failed to refresh active initiatives: {e}")

        await event_bus.emit(PORTFOLIO_REBALANCED, {
            "portfolio_id": state["portfolio_id"],
            "cycle": cycle,
            "next_phase": next_phase,
            "budget_remaining": budget_remaining,
        })

        return {
            "cycle_count": cycle,
            "current_phase": next_phase,
            "active_initiatives": active if active else state.get("active_initiatives", []),
            "funded_initiatives": [],
            "killed_initiatives": [],
            "messages": [_msg("system", "rebalance", {
                "cycle": cycle,
                "max_cycles": max_cycles,
                "next": next_phase,
                "budget_remaining": budget_remaining,
            })],
        }

    # ------------------------------------------------------------------
    # close: finalize the portfolio cycle
    # ------------------------------------------------------------------

    async def close(self, state: PortfolioState) -> dict:
        cycles = state.get("cycle_count", 0)
        spent = state.get("budget_spent", 0)
        results = state.get("execution_results", [])

        logger.info(
            f"Portfolio closed: {cycles} cycles, ${spent:.2f} spent, "
            f"{len(results)} initiative results"
        )

        await event_bus.emit(PORTFOLIO_CLOSED, {
            "portfolio_id": state["portfolio_id"],
            "cycles": cycles,
            "budget_spent": spent,
            "results_count": len(results),
        })

        return {
            "current_phase": "closed",
            "messages": [_msg("system", "portfolio_closed", {
                "cycles": cycles,
                "budget_spent": spent,
                "results": len(results),
            })],
        }
