#!/usr/bin/env python3
"""Run an AECO portfolio cycle from the command line.

Usage:
    python scripts/run_portfolio.py --goals "Reduce CAC" "Increase MRR" --budget 500 --cycles 2
    python scripts/run_portfolio.py --goals "Improve conversion" --workspace /path/to/headshot-ai
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.budget.engine import BudgetEngine
from aeco.config import settings
from aeco.context.builder import ContextBuilder
from aeco.db.session import async_session_factory
from aeco.logging.company_logger import init_company_logging
from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.memory.store import MemoryStore
from aeco.memory.vector import VectorMemory
from aeco.orchestrator.initiative_graph import build_initiative_graph
from aeco.orchestrator.portfolio_graph import build_portfolio_graph
from aeco.orchestrator.portfolio_state import PortfolioState
from aeco.tools.gateway import tool_gateway
from aeco.tools.registry import register_all_tools


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main(args):
    setup_logging()
    logger = logging.getLogger("aeco.cli")

    init_company_logging(
        log_path=settings.company_log_path,
        console=settings.company_log_console,
    )

    # Initialize database tables
    from aeco.db.session import init_db
    await init_db()

    # Register tools and load agents
    register_all_tools(tool_gateway)
    registry = AgentRegistry()
    agents_yaml = Path("aeco/agents/definitions/v1_agents.yaml")
    if agents_yaml.exists():
        registry.load_from_yaml(agents_yaml)
        logger.info(f"Loaded {len(registry.list_agents())} agents")
    else:
        logger.error(f"Agent definitions not found at {agents_yaml}")
        sys.exit(1)

    # Create workspace
    workspace = args.workspace or settings.workspace_path
    Path(workspace).mkdir(parents=True, exist_ok=True)

    # Build dependencies
    vector_memory = VectorMemory(host=settings.chroma_host, port=settings.chroma_port)
    budget_engine = BudgetEngine(async_session_factory)
    audit_logger = AuditLogger(async_session_factory)
    memory_store = MemoryStore(async_session_factory)
    decision_ledger = DecisionLedgerStore(async_session_factory)
    context_builder = ContextBuilder(
        vector_memory=vector_memory,
        memory_store=memory_store,
        decision_ledger=decision_ledger,
    )

    # Build graphs
    initiative_graph = build_initiative_graph(
        registry=registry,
        audit_logger=audit_logger,
        context_builder=context_builder,
        decision_ledger=decision_ledger,
        budget_engine=budget_engine,
    )
    logger.info("Initiative workflow graph compiled")

    portfolio_graph = build_portfolio_graph(
        registry=registry,
        audit_logger=audit_logger,
        context_builder=context_builder,
        decision_ledger=decision_ledger,
        budget_engine=budget_engine,
        initiative_graph=initiative_graph,
    )
    logger.info("Portfolio workflow graph compiled")

    # Build initial state
    initial_state: PortfolioState = {
        "portfolio_id": str(uuid.uuid4()),
        "company_goals": args.goals,
        "opportunities": [],
        "active_initiatives": [],
        "portfolio_decisions": [],
        "funded_initiatives": [],
        "killed_initiatives": [],
        "execution_results": [],
        "total_budget": args.budget,
        "budget_spent": 0.0,
        "budget_remaining": args.budget,
        "current_phase": "opportunity_scan",
        "cycle_count": 0,
        "max_cycles": args.cycles,
        "workspace_path": str(Path(workspace).resolve()),
        "messages": [],
        "decisions": [],
        "errors": [],
    }

    logger.info(f"Starting portfolio run:")
    logger.info(f"  Goals: {args.goals}")
    logger.info(f"  Budget: ${args.budget}")
    logger.info(f"  Max cycles: {args.cycles}")
    logger.info(f"  Workspace: {workspace}")
    logger.info("")

    # Run it
    final_state = await portfolio_graph.ainvoke(initial_state)

    # Print results
    print("\n" + "=" * 70)
    print("  PORTFOLIO RUN COMPLETE")
    print("=" * 70)
    print(f"  Cycles:           {final_state.get('cycle_count', 0)}")
    print(f"  Budget spent:     ${final_state.get('budget_spent', 0):.2f}")
    print(f"  Budget remaining: ${final_state.get('budget_remaining', 0):.2f}")

    # Opportunities discovered
    opportunities = final_state.get("opportunities", [])
    print(f"\n  📊 Opportunities discovered: {len(opportunities)}")
    for i, opp in enumerate(opportunities):
        print(f"    {i+1}. {opp.get('title', '?')} [{opp.get('category', '?')}] "
              f"(confidence: {opp.get('confidence', 0):.0%})")
        if opp.get("goal"):
            print(f"       Goal: {opp['goal'][:100]}")

    # Initiatives executed
    results = final_state.get("execution_results", [])
    print(f"\n  🚀 Initiatives executed: {len(results)}")
    for r in results:
        status = r.get("action", "unknown")
        verdict = r.get("verdict", "")
        title = r.get("title", "Untitled")
        icon = {"completed": "✓", "failed": "✗", "timeout": "⏱", "killed": "☠", "skipped": "⊘"}.get(status, "?")
        verdict_str = f" → {verdict}" if verdict else ""
        print(f"    {icon} {title} ({status}{verdict_str})")
        if r.get("tasks_executed"):
            print(f"       Tasks: {r['tasks_executed']}, Budget: ${r.get('budget_spent', 0):.2f}")
        if r.get("prd"):
            prd = r["prd"]
            if isinstance(prd, dict):
                print(f"       PRD: {prd.get('problem_statement', '')[:120]}")
        if r.get("task_graph"):
            print(f"       Task graph: {len(r['task_graph'])} tasks")

    # Portfolio decisions
    decisions = final_state.get("portfolio_decisions", [])
    if decisions:
        print(f"\n  📋 Portfolio decisions: {len(decisions)}")
        for d in decisions[-5:]:
            agent = d.get("agent", "?")
            reasoning = d.get("reasoning", d.get("decision", ""))
            if isinstance(reasoning, dict):
                reasoning = json.dumps(reasoning)
            print(f"    - {agent}: {str(reasoning)[:120]}")

    # Errors
    errors = final_state.get("errors", [])
    if errors:
        print(f"\n  ⚠️  Errors: {len(errors)}")
        for e in errors:
            print(f"    ⚠ {e[:150]}")

    # Messages summary
    messages = final_state.get("messages", [])
    agent_calls = [m for m in messages if m.get("type") == "agent_call"]
    parse_errors = [m for m in messages if "parse_error" in m.get("type", "")]
    print(f"\n  📝 Message log: {len(messages)} messages, {len(agent_calls)} agent calls, {len(parse_errors)} parse errors")

    print("=" * 70)

    # Save full state to file for debugging
    output_path = Path("logs/last_portfolio_run.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(final_state, f, indent=2, default=str)
    print(f"\n  Full state saved to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run an AECO portfolio cycle")
    parser.add_argument(
        "--goals", nargs="+", required=True,
        help="Company goals (e.g. 'Reduce CAC below $15' 'Increase MRR')"
    )
    parser.add_argument("--budget", type=float, default=500.0, help="Total budget in USD")
    parser.add_argument("--cycles", type=int, default=2, help="Max portfolio cycles")
    parser.add_argument("--workspace", type=str, default=None, help="Workspace path (project root)")

    args = parser.parse_args()
    asyncio.run(main(args))
