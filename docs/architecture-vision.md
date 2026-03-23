# AECO Architecture Vision: AI-Native Product Company Simulator

This doc captures the target architecture: **product company simulator**, not just an agent workflow or execution engine. Current system is task-centric and execution-heavy; the goal is to own all five loops and to prioritize **governance and truth** before maximum autonomy.

---

## 1. Core principle: five loops

A system that **builds and evolves products** must own:

| Loop | What | Current AECO |
|------|------|--------------|
| 1. **Opportunity discovery** | What should be built | ✅ CEO / Portfolio Director + Product Strategist (portfolio workflow) |
| 2. **Planning** | Why this is the right move | ✅ PM Agent + Task Planner + Context Builder |
| 3. **Execution** | Design, code, test, ship | ✅ Strong (task + initiative + portfolio graphs) |
| 4. **Measurement** | Did it work | ✅ Evaluator + metrics_read + agent_logs_read + Stripe/Facebook analytics |
| 5. **Adaptation** | What changes next | ✅ scale/iterate/kill + postmortem writer + decision ledger |

All five loops are now structurally in place. The portfolio workflow (CEO + Product Strategist) closes loop 1.

---

## 2. Org chart (5 departments + executive layer)

### Executive layer (direction)
- **CEO / Portfolio Director**: company goals, portfolio bets, initiative selection
- **Product Strategist**: goals → product opportunities

### Engineering department (10 agents + team lead)
- **Engineering Lead** (team lead) → manages all engineering specialists
- **Chief Architect**: system design, contracts
- **Backend Engineer**, **Frontend Engineer**, **Fullstack Engineer**: implementation
- **Database Engineer**, **API Engineer**: data & interface layer
- **Infrastructure Engineer**, **DevOps Engineer**: deployment & infra
- **QA Engineer**: review & tests
- **Release Manager**: merge, rollout, rollback

### Product department (5 agents + team lead)
- **Product Lead** (team lead)
- **PM Agent**: PRDs, success metrics
- **Task Planner**: task graphs, dependencies
- **UX Researcher**, **Data Analyst**, **Product Designer**: research & design

### Marketing department (6 agents + team lead)
- **Marketing Lead** (team lead)
- **Growth Marketing Agent**, **Content Creator**
- **Facebook Ads Specialist**, **Email Marketer**, **SEO Specialist**, **Landing Page Designer**

### Revenue & Customer department (5 agents + team lead)
- **Revenue Lead** (team lead)
- **Customer Success Agent**, **Revenue Analyst**
- **Pricing Analyst**, **Retention Specialist**, **Onboarding Specialist**

### Operations department (7 agents + team lead)
- **Operations Lead** (team lead)
- **COO Orchestrator**: routes every task step
- **Budget Controller**: spend approval, anomaly detection
- **Analytics Agent**, **Evaluator**, **Security Reviewer**
- **Postmortem Writer**, **Incident Investigator**, **Experiment Agent**
- **Compliance Reviewer**, **Cost Optimizer**

**Total: 48 specialists + 5 team leads + 2 executives = 55 agents**

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

### Phase 2 — Governance hardening (DONE)
- ✅ Security Reviewer agent
- ✅ Incident Investigator
- ✅ Experiment Agent (A/B testing, funnels)
- ✅ Compliance Reviewer + Cost Optimizer
- ✅ Real-time monitoring dashboard (WebSocket)

### Phase 3 — Portfolio autonomy (DONE)
- ✅ CEO / Portfolio Director, Product Strategist
- ✅ Multi-initiative prioritization, resource allocation
- ✅ Portfolio workflow graph (`POST /api/portfolio/run`)
- ✅ Approval workflow for founder-gated decisions
- ✅ Persistent portfolio state + Dockerization

### Phase 4 — Agent Teams & Departments (DONE)
- ✅ 5 departments with team leads (Engineering, Product, Marketing, Revenue, Operations)
- ✅ 21 new specialist agents (48 total specialists)
- ✅ Team lead delegation pattern
- ✅ Standardized JSON output across all 23+ agent prompts

### Phase 5 — Revenue & Growth (DONE)
- ✅ Marketing department: Facebook Ads, email, SEO, content, landing pages
- ✅ Revenue department: customer success, pricing, retention, onboarding
- ✅ Stripe integration (MRR, revenue, churn, customers)
- ✅ Facebook/Meta Ads integration (campaigns, insights)
- ✅ WhatsApp notifications for founder alerts

### Phase 6 — Autonomous Operation (DONE)
- ✅ Async scheduler engine with cron parsing (`aeco/scheduler/engine.py`)
- ✅ Metric trigger system — auto-starts portfolio cycles on churn spikes, MRR drops, ad anomalies, error rate spikes (`aeco/scheduler/triggers.py`)
- ✅ Scheduler + trigger CRUD API routes (`/api/scheduler/jobs`, `/api/scheduler/triggers`)
- ✅ Telemetry pipeline: ingest + query product metrics with aggregations + trend analysis (`aeco/tools/telemetry_tools.py`)
- ✅ Telemetry API routes (`/api/telemetry/events`, `/api/telemetry/query`, `/api/telemetry/metrics`)
- ✅ Prompt Optimizer agent — reads postmortems + error data, proposes targeted prompt patches
- ✅ Prompt patcher runtime injection — approved patches injected into agent prompts without file edits (`aeco/agents/prompt_patcher.py`)
- ✅ Prompt patch management API (`/api/prompt-patches` with approve/reject workflow)
- ✅ `.aeco.yaml` project config support — goals, metrics, constraints auto-injected into agent context
- ✅ Workspace scanner reads `.aeco.yaml` for product-specific configuration
- ✅ Evaluator, data analyst, revenue analyst upgraded with telemetry_query access
- ✅ Alembic migration 004 for scheduler, triggers, patches, telemetry tables

### Phase 7 — Next
- Multi-product portfolio management (parallel product workspaces)
- Advanced experiment framework (feature flags + A/B testing with statistical significance)
- External trigger integrations (Stripe webhooks, Slack commands)
- Agent capability benchmarking (automated eval suites)

---

## 13. Completed milestones

1. ~~Redefine top-level object from **task** to **initiative**.~~ DONE
2. ~~Add **PM Agent** and **Analytics Agent** before more engineers.~~ DONE
3. ~~Create **Decision Ledger** and canonical product/architecture summaries.~~ DONE
4. ~~Replace simple route loop with **initiative task graph** orchestration.~~ DONE
5. ~~Add **Release Manager** + staged rollout + rollback logic.~~ DONE
6. ~~Add **Evaluator** that decides scale / iterate / kill.~~ DONE
7. ~~Add executive autonomy for portfolio selection.~~ DONE — CEO + Product Strategist + Portfolio workflow
8. ~~Scale to 5 departments with team leads.~~ DONE — 55 agents total
9. ~~Add revenue & growth integrations.~~ DONE — Stripe, Facebook Ads, WhatsApp
10. ~~Add autonomous scheduler + metric triggers.~~ DONE — cron scheduler, metric triggers, auto-portfolio-cycles
11. ~~Add self-improving agent prompts.~~ DONE — Prompt Optimizer agent, runtime patch injection, approve/reject workflow
12. ~~Add telemetry pipeline.~~ DONE — ingest, query, aggregation, trend analysis, Stripe/FB connectors
13. ~~Add `.aeco.yaml` project config.~~ DONE — goals, metrics, constraints auto-injected

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
- Agent definitions: `aeco/agents/definitions/v1_agents.yaml` (all 55 agents)
- Agent prompts: `aeco/agents/prompts/` (23+ prompt files)
- Initiative model: `aeco/models/initiative.py`
- Structured agent output: `aeco/models/agent_output.py`
- Decision ledger: `aeco/models/decision_ledger.py`, `aeco/memory/decision_ledger.py`
- Context builder: `aeco/context/builder.py`
- Orchestrators: `aeco/orchestrator/` (task, initiative, portfolio graphs)
- Budget engine: `aeco/budget/engine.py`
- Tools: `aeco/tools/` (file, code, clickup, budget, metrics, facebook, stripe, whatsapp)
- API routes: `aeco/api/` (tasks, workflows, agents, initiatives, portfolio, budget, projects, webhooks, ws)
- Dashboard: `dashboard/src/pages/` (9 pages: Tasks, Agents, Initiatives, Portfolio, Budget, Company)
- Scheduler: `aeco/scheduler/engine.py`, `aeco/scheduler/triggers.py`
- Telemetry: `aeco/tools/telemetry_tools.py`, `aeco/api/routes_telemetry.py`
- Prompt patches: `aeco/agents/prompt_patcher.py`, `aeco/api/routes_prompt_patches.py`
- Prompt optimizer: `aeco/agents/prompts/prompt_optimizer.md`
- Scheduler API: `aeco/api/routes_scheduler.py`
- Migrations: `alembic/versions/`
