# AECO Architecture Vision: AI-Native Product Company Simulator

This doc captures the target architecture: **product company simulator**, not just an agent workflow or execution engine. Current system is task-centric and execution-heavy; the goal is to own all five loops and to prioritize **governance and truth** before maximum autonomy.

---

## 1. Core principle: five loops

A system that **builds and evolves products** must own:

| Loop | What | Current AECO |
|------|------|--------------|
| 1. **Opportunity discovery** | What should be built | ❌ Missing |
| 2. **Planning** | Why this is the right move | ✅ PM Agent + Task Planner + Context Builder |
| 3. **Execution** | Design, code, test, ship | ✅ Strong (task + initiative graphs) |
| 4. **Measurement** | Did it work | ✅ Evaluator + metrics_read + agent_logs_read |
| 5. **Adaptation** | What changes next | ✅ scale/iterate/kill + postmortem writer + decision ledger |

Loop 1 remains the main gap. Loops 2-5 are now structurally in place via the initiative workflow.

---

## 2. Org chart (four layers)

### Executive layer (direction)
- **CEO / Portfolio Director**: company goals, portfolio bets
- **Product Strategist**: goals → product opportunities
- **Finance / Budget Controller**: spend caps, ROI gates
- **Program Manager**: initiatives → operating cadence

### Product management layer (what & why)
- **PM Agent**: problem statements, PRDs, success metrics
- **Research Agent**: docs, tickets, logs, analytics, feedback
- **Growth / Experiment Agent**: experiments, funnels, A/B

### Technical management layer (how)
- **Tech Lead Agent**: implementation plan, sequencing
- **Chief Architect**: system design, contracts, long-horizon
- **Task Planner**: work → executable units
- **Release Manager**: merge, rollout, rollback

### Execution + oversight layer (do & judge)
- Backend / Frontend / DevOps / QA / Security Reviewer
- **Evaluator / Critic**
- **Analytics Agent**
- **Incident Investigator**

---

## 3. Operating loop (target)

Not: `task → route → agent → done`

But:

```
company goals
→ opportunity scan
→ initiative selection
→ product spec
→ technical design
→ task graph creation
→ parallel implementation
→ review / QA / security
→ staged rollout
→ metrics read
→ evaluation
→ follow-up tasks / rollback / next iteration
```

This loop should run **continuously**. If the system waits for humans to hand it tasks, it is not autonomous.

---

## 4. Three sources of truth

### A. Product truth
- Company goals, active hypotheses, PRDs
- User journeys, success metrics, experiments
- Constraints and non-goals

### B. Technical truth
- Architecture docs, service contracts
- Code ownership, deployment state
- Test coverage, known incidents, tech debt

### C. Market/user truth
- Customer feedback, support tickets
- Funnel analytics, session insights
- Feature adoption, churn, competitor moves

Without these, agents optimize nonsense.

---

## 5. Unit of autonomy: initiative-level task graph

Top-level unit of work = **initiative**, not task.

- **Initiative** = goal + hypothesis + metrics + constraints + task graph + rollout plan + evaluation window + verdict (scale / iterate / kill).
- Execution = dynamic **task graph** (PM → Research → Growth → Architect → Task Planner → parallel FE/BE/Analytics/QA → Release Manager → Evaluator → PM).

Single-task routing is insufficient for a product company.

---

## 6. Structured agent output (required)

Every agent must emit a **structured packet**, not just “work”:

```json
{
  "artifact_refs": [],
  "decision": "",
  "assumptions": [],
  "risks": [],
  "confidence": 0.0,
  "requested_followups": [],
  "blocking_dependencies": [],
  "success_criteria": []
}
```

- **assumptions** → expose hallucination
- **risks** → expose fragility
- **confidence** → helps routing
- **blocking_dependencies** → help planning
- **success_criteria** → make evaluation possible

---

## 7. Control loops (non-negotiable)

| Loop | Purpose |
|------|--------|
| **Critic** | Every major artifact challenged by a separate reviewer (no self-approval) |
| **Metrics** | Every shipped change maps to measurable outcomes; no “done” without instrumentation |
| **Rollback** | If metrics worsen or incidents rise → rollback (auto or gated) |
| **Postmortem** | Failed initiatives → training data (assumptions, routing, context, evaluation, spec, code) |

---

## 8. Context assembly

A **Context Builder** sits between memory and agent execution. For each run it assembles:

- Relevant goal, PRD, architecture slice
- Exact code files touched, related tickets
- Recent experiment outcomes, guardrails

Without this, models drown in irrelevant context.

---

## 9. Layered memory (not just vector dump)

| Layer | Content |
|-------|--------|
| 1. Raw artifacts | Docs, code, logs, tickets, tests |
| 2. Canonical summaries | Living summaries of product, architecture, incidents, experiments |
| 3. Decision ledger | Why decisions were made, by whom, on what assumptions |
| 4. Performance memory | Which agents, prompts, plans, rollouts worked historically |

---

## 10. Governance

Approval policies must be explicit, e.g.:

- Blast radius &lt; X: auto-merge if tests + critic + security pass
- Blast radius ≥ X: executive or human gate
- Production schema: always staged
- Model cost above threshold: budget approval
- User-visible copy in regulated areas: policy review

Autonomy without governance = automated outage generator.

---

## 11. Definition of “done” (company level)

A product initiative is done only when:

- Feature is shipped
- Telemetry is live
- Metrics are collected
- Outcome is evaluated
- Learnings are written back
- Next action is chosen: **expand**, **iterate**, or **kill**

The **kill** branch is essential.

---

## 12. Build order (phased)

### Phase 1a — Foundation (DONE)
- ✅ Context Builder (`aeco/context/builder.py`)
- ✅ Decision Ledger (`aeco/models/decision_ledger.py`, `aeco/memory/decision_ledger.py`)
- ✅ PM Agent (`aeco/agents/prompts/pm_agent.md`)
- ✅ Task Planner (`aeco/agents/prompts/task_planner.md`)
- ✅ Initiative model + orchestrator (`aeco/orchestrator/initiative_graph.py`)
- ✅ Structured agent output (`aeco/models/agent_output.py`)
- ✅ Evaluator with scale/iterate/kill verdict
- ✅ Budget Engine with 4-tier approval + anomaly detection + optimization
- ✅ Budget check gate in task workflow (route → budget_check → agent)
- ✅ Initiative API routes (`POST /api/initiatives`, `POST /api/initiatives/run`)
- ✅ Tasks linked to initiatives (`initiative_id` FK)

### Phase 1b — Reliability (DONE)
- ✅ Release Manager agent (`aeco/agents/prompts/release_manager.md`)
- ✅ Metrics tooling: `metrics_read` + `agent_logs_read` (`aeco/tools/metrics_tools.py`)
- ✅ Postmortem Writer agent — auto-runs on kill/iterate, writes learnings to decision ledger
- ✅ Evaluator prompt upgraded for initiative verdicts (scale/iterate/kill + assumption validation)
- ✅ Alembic migration 003 for budget, decision_ledger, projects, initiative_id FK
- ✅ Integration tests for both orchestrator graphs (graph compilation, edge routing, agent/tool completeness)
- Security Reviewer agent (deferred to Phase 2)

### Phase 2 — Governance hardening (NEXT)
- Security Reviewer agent
- Incident Investigator
- Experiment Agent (A/B testing, funnels)
- Blast-radius-based approval policies
- Real-time monitoring dashboard (WebSocket)

### Phase 3 — Portfolio autonomy
- CEO / Portfolio Director, Product Strategist
- Multi-initiative prioritization, resource allocation
- Opportunity discovery loop (loop 1)
- Initiative kill/continue scaling logic
**Goal:** System chooses among multiple bets.

---

## 13. Ordered next steps (immediate)

1. ~~Redefine top-level object from **task** to **initiative**.~~ DONE — `Initiative` model + `InitiativeState` + initiative graph
2. ~~Add **PM Agent** and **Analytics Agent** before more engineers.~~ DONE — PM Agent + Task Planner registered
3. ~~Create **Decision Ledger** and canonical product/architecture summaries.~~ DONE — `DecisionRecord` model + `DecisionLedgerStore`
4. ~~Replace simple route loop with **initiative task graph** orchestration.~~ DONE — `build_initiative_graph()` with PM → Architect → TaskPlanner → Execute → Evaluate loop
5. ~~Add **Release Manager** + staged rollout + rollback logic.~~ DONE — Release Manager + Postmortem Writer registered
6. ~~Add **Evaluator** that decides scale / iterate / kill.~~ DONE — evaluate node with verdict + iteration loop
7. Only then add executive autonomy for portfolio selection.

**Do not add more builder agents before evaluation and governance.**

---

## 14. Forced-choice answer

**Chosen: B — Tighter governance.**

Rationale: Maximum autonomy without governance produces more bad decisions and unrecoverable failure. The gap is evaluation and truth (metrics, decision ledger, critic loop). Optimize for governance first (initiative unit, structured output, Decision Ledger, Evaluator, rollout/rollback); relax gates later once the system proves it learns.

---

## 15. Failure modes to watch

| Failure mode | Mitigation |
|--------------|------------|
| Fake progress | Tie every initiative to one north-star + one local metric |
| Hallucinated certainty | Explicit evidence refs + confidence in agent output |
| Endless loops | Max retries + escalation to Tech Lead / Architect / Human |
| Local optimization | Primary metric + guardrail metrics |
| Context rot | Canonical summaries + decision ledger, not raw vector spam |

---

*This document is the single source of truth for “what we’re building toward.”*

**Key implementation files:**
- Initiative model: `aeco/models/initiative.py`
- Structured agent output: `aeco/models/agent_output.py`
- Decision ledger: `aeco/models/decision_ledger.py`, `aeco/memory/decision_ledger.py`
- Context builder: `aeco/context/builder.py`
- Initiative orchestrator: `aeco/orchestrator/initiative_graph.py`, `initiative_nodes.py`, `initiative_state.py`
- Budget engine: `aeco/budget/engine.py`
- Metrics tools: `aeco/tools/metrics_tools.py`
- PM Agent: `aeco/agents/prompts/pm_agent.md`
- Task Planner: `aeco/agents/prompts/task_planner.md`
- Release Manager: `aeco/agents/prompts/release_manager.md`
- Postmortem Writer: `aeco/agents/prompts/postmortem_writer.md`
- Initiative API: `aeco/api/routes_initiatives.py`
- Budget API: `aeco/api/routes_budget.py`
- Migrations: `alembic/versions/003_add_budget_decision_ledger_initiative_fk.py`
