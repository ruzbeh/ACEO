# AECO — Working Process & Company Structure

## 1. Task-level workflow

How a single task moves from trigger to done:

```mermaid
flowchart TB
    subgraph triggers["Triggers"]
        API["POST /api/tasks\n(create task)"]
        Webhook["ClickUp webhook\n(taskCreated)"]
        Initiative["Initiative workflow\n(execute_tasks node)"]
        API --> Trigger
        Webhook --> Trigger
        Initiative --> Trigger
        Trigger["trigger_workflow_for_task()"]
    end

    subgraph workflow["LangGraph task workflow"]
        START([Start])
        START --> Intake
        Intake["intake\n- Create ClickUp task if needed\n- Set workspace"]
        Intake --> Route

        Route["route\n- COO Orchestrator decides\n- next_action + reasoning"]

        Route -->|all_done or max_iterations| Publish
        Route -->|needs_design, needs_implementation,\nneeds_frontend, needs_qa| BudgetCheck

        BudgetCheck["budget_check\n- Estimate cost\n- Approval tier check\n- Anomaly detection\n- Optimization hints"]
        BudgetCheck -->|approved| Architect
        BudgetCheck -->|approved| Engineer
        BudgetCheck -->|approved| Frontend
        BudgetCheck -->|approved| QA
        BudgetCheck -->|denied| Publish

        Architect["architect\n- Chief Architect\n- Design document\n- Ingest to vector memory"]
        Engineer["engineer\n- Backend Engineer\n- Code artifacts -> file_write\n- Ingest to memory"]
        Frontend["frontend\n- Frontend Engineer\n- UI code -> file_write\n- Ingest to memory"]
        QA["qa\n- QA Engineer\n- Review + test_results\n- approved -> all_done\n- else -> needs_implementation"]

        Architect --> Route
        Engineer --> Route
        Frontend --> Route
        QA --> Route

        Publish["publish\n- Post summary + budget to ClickUp\n- Mark task done"]
        Publish --> END([End])
    end

    Trigger --> START
```

**Flow in short:**
Trigger (API, ClickUp webhook, or initiative workflow) -> **intake** -> **route** (COO decides) -> **budget_check** (approved -> agent, denied -> publish) -> one of **architect / engineer / frontend / qa** -> back to **route** (loop until `all_done` or `max_iterations`) -> **publish** -> end.

---

## 2. Initiative-level workflow

How a product initiative flows from idea to verdict:

```mermaid
flowchart TB
    subgraph initiative["LangGraph initiative workflow"]
        START([Start])
        START --> Intake
        Intake["intake\n- Initialize initiative"]
        Intake --> PM

        PM["pm_spec\n- PM Agent\n- PRD + metrics\n- Decision ledger entry"]
        PM --> Arch

        Arch["architect\n- Chief Architect\n- Technical design\n- Decision ledger entry"]
        Arch --> Plan

        Plan["task_planning\n- Task Planner\n- Task graph with deps\n- Decision ledger entry"]
        Plan --> Exec

        Exec["execute_tasks\n- Run each task through\n  assigned agent\n- Sequential execution"]
        Exec --> Eval

        Eval["evaluate\n- Agent Evaluator\n- Assess outcomes\n- Decision: scale/iterate/kill"]

        Eval -->|iterate & under max| Plan
        Eval -->|scale or kill or max reached| Close

        Close["close\n- Record verdict\n- Update initiative status"]
        Close --> END([End])
    end
```

**Flow in short:**
`POST /api/initiatives/run` -> **intake** -> **pm_spec** (PRD + metrics) -> **architect** (design) -> **task_planning** (task graph) -> **execute_tasks** (run agents) -> **evaluate** (scale/iterate/kill) -> loop back to task_planning if iterating, else **close**.

---

## 3. Company structure (agents & roles)

All 12 agents and their status:

```mermaid
flowchart TB
    subgraph initiative_pipeline["Initiative pipeline"]
        PM["Product Manager\n(product_manager)\n- PRD, metrics, specs"]
        TP["Task Planner\n(planner)\n- Task graphs, deps"]
        EV["Agent Evaluator\n(evaluator)\n- scale/iterate/kill"]
    end

    subgraph task_pipeline["Task pipeline"]
        COO["COO Orchestrator\n(orchestrator)\n- Routes every step"]
        CA["Chief Architect\n(architect)\n- Design docs"]
        BE["Backend Engineer\n(engineer)\n- Implementation"]
        FE["Frontend Engineer\n(engineer)\n- UI implementation"]
        QA["QA Engineer\n(qa)\n- Review & tests"]
    end

    subgraph governance["Governance & support"]
        BC["Budget Controller\n(finance)\n- Spend approval\n- Anomaly detection\n- Optimization hints"]
        PGM["Program Manager\n(planner)\n- ClickUp coordination"]
        DevOps["DevOps Engineer\n(infrastructure)\n- Deployment scripts"]
        Analytics["Analytics Agent\n(analytics)\n- Metrics & insights"]
    end

    PM --> CA
    CA --> TP
    TP --> COO
    COO --> CA
    COO --> BE
    COO --> FE
    COO --> QA
    BC -.->|budget gate| COO
    EV -.->|verdict| TP
```

**Roles:**

| Role             | In workflow     | Agents |
|------------------|-----------------|--------|
| Product Manager  | Initiative      | PM Agent |
| Task Planner     | Initiative      | Task Planner |
| Evaluator        | Initiative      | Agent Evaluator |
| Orchestrator     | Task            | COO Orchestrator |
| Architect        | Both            | Chief Architect |
| Engineer         | Task            | Backend Engineer, Frontend Engineer |
| QA               | Task            | QA Engineer |
| Finance          | Task (gate)     | Budget Controller |
| Planner          | Available       | Program Manager |
| Infrastructure   | Available       | DevOps Engineer |
| Analytics        | Available       | Analytics Agent |

---

## 4. Budget approval flow

```mermaid
flowchart LR
    Request["Spend Request"]
    Request --> Check{"Amount?"}
    Check -->|< $20| Auto["Auto-approved"]
    Check -->|$20-$200| Agent["Budget Controller\napproves/denies"]
    Check -->|$200-$1000| Notify["Approved +\nfounder notification"]
    Check -->|> $1000| Escalate["Escalated to\nfounder"]

    Agent --> Record["Record spend\n+ anomaly check\n+ optimization hints"]
    Auto --> Record
    Notify --> Record
```

---

## 5. Decision Ledger flow

Every major decision gets recorded with explicit assumptions:

```mermaid
sequenceDiagram
    participant Agent
    participant Ledger as Decision Ledger
    participant Evaluator

    Agent->>Ledger: Record decision + assumptions + confidence
    Note over Ledger: Stored with evidence_refs, risks, alternatives

    Evaluator->>Ledger: Query decisions for initiative
    Evaluator->>Evaluator: Validate assumptions against outcomes
    Evaluator->>Ledger: Record outcome + lessons_learned
```

---

## 6. End-to-end process (initiative level)

```mermaid
sequenceDiagram
    participant User
    participant API
    participant PM as PM Agent
    participant Arch as Architect
    participant Planner as Task Planner
    participant COO
    participant Agents as Execution Agents
    participant Budget as Budget Engine
    participant Eval as Evaluator

    User->>API: POST /api/initiatives (title, goal, hypothesis)
    User->>API: POST /api/initiatives/run

    API->>PM: Write PRD + define metrics
    PM->>Arch: Design architecture
    Arch->>Planner: Create task graph

    loop For each task in graph
        Planner->>COO: Assign task to agent
        COO->>Budget: Check budget
        Budget-->>COO: Approved/Denied
        COO->>Agents: Execute (engineer/frontend/qa)
        Agents-->>COO: Artifacts + results
    end

    COO->>Eval: Evaluate outcomes
    alt iterate
        Eval->>Planner: Refine task graph
        Note over Planner,Eval: Loop (max 3 iterations)
    else scale or kill
        Eval->>API: Close initiative with verdict
    end
```

---

*Generated from the AECO codebase. 12 agents, 2 workflow graphs (task + initiative), budget engine, decision ledger.*
