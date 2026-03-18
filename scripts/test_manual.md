# Manual testing: tasks, workflows, initiatives, and budget

## Prerequisites

- Server running: `uv run uvicorn aeco.main:app --reload` (from project root)
- Database and env set (e.g. `.env` with `DATABASE_URL`, optional `CLICKUP_API_TOKEN`)

---

## 1. Create a task (workflow auto-starts)

```bash
curl -s -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Add login page", "description": "Implement auth UI"}' | jq .
```

- You should get a task with `id`, `status: "todo"`.
- A workflow run should start in the background (task moves to `in_progress`). Check logs or:

```bash
# List workflows (use a workflow_id from logs or from task.workflow_run_id)
curl -s http://localhost:8000/api/workflows/<workflow_id> | jq .
```

---

## 2. Run workflow for an existing task

```bash
# Replace TASK_ID with an actual task UUID from GET /api/tasks
curl -s -X POST http://localhost:8000/api/workflows/run \
  -H "Content-Type: application/json" \
  -d '{"task_id": "TASK_ID"}' | jq .
```

---

## 3. Initiatives (initiative-level workflow)

### Create an initiative

```bash
curl -s -X POST http://localhost:8000/api/initiatives \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Add user onboarding flow",
    "goal": "Increase signup conversion by 20%",
    "hypothesis": "A guided 3-step onboarding reduces drop-off"
  }' | jq .
```

### List initiatives

```bash
curl -s http://localhost:8000/api/initiatives | jq .
```

### Run the initiative workflow

This triggers PM -> Architect -> Task Planner -> Execute -> Evaluate:

```bash
curl -s -X POST http://localhost:8000/api/initiatives/run \
  -H "Content-Type: application/json" \
  -d '{"initiative_id": "INITIATIVE_ID"}' | jq .
```

### View decisions made during an initiative

```bash
curl -s http://localhost:8000/api/initiatives/INITIATIVE_ID/decisions | jq .
```

---

## 4. Budget management

### Create a budget period

```bash
curl -s -X POST http://localhost:8000/api/budget/periods \
  -H "Content-Type: application/json" \
  -d '{
    "name": "March 2026 Sprint",
    "total_budget": 500.00,
    "period_start": "2026-03-01T00:00:00Z",
    "period_end": "2026-03-31T23:59:59Z"
  }' | jq .
```

### Get active budget

```bash
curl -s http://localhost:8000/api/budget/active | jq .
```

### Submit a spend request

```bash
curl -s -X POST http://localhost:8000/api/budget/spend \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "backend_engineer",
    "amount": 0.05,
    "category": "llm_tokens",
    "description": "Code generation call",
    "tokens_used": 15000,
    "llm_model": "anthropic/claude-sonnet-4"
  }' | jq .
```

### Get budget summary

```bash
curl -s http://localhost:8000/api/budget/periods/BUDGET_ID/summary | jq .
```

### Get optimization report

```bash
curl -s http://localhost:8000/api/budget/periods/BUDGET_ID/optimize | jq .
```

### Get workflow cost breakdown

```bash
curl -s http://localhost:8000/api/budget/workflows/WORKFLOW_RUN_ID/cost | jq .
```

---

## 5. ClickUp webhooks (simulate)

**taskCreated** (creates AECO task and starts workflow):

```bash
curl -s -X POST http://localhost:8000/api/webhooks/clickup \
  -H "Content-Type: application/json" \
  -d '{"event": "taskCreated", "task_id": "YOUR_CLICKUP_TASK_ID"}' | jq .
```

**taskUpdated** (syncs AECO task from ClickUp):

```bash
curl -s -X POST http://localhost:8000/api/webhooks/clickup \
  -H "Content-Type: application/json" \
  -d '{"event": "taskUpdated", "task_id": "CLICKUP_TASK_ID"}' | jq .
```

**taskCommentPosted** (stores last comment on AECO task):

```bash
curl -s -X POST http://localhost:8000/api/webhooks/clickup \
  -H "Content-Type: application/json" \
  -d '{"event": "taskCommentPosted", "task_id": "CLICKUP_TASK_ID", "comment": {"comment_text": "Use OAuth2"}}' | jq .
```

---

## 6. Other endpoints

```bash
# List agents
curl -s http://localhost:8000/api/agents | jq .

# Get agent details
curl -s http://localhost:8000/api/agents/pm_agent | jq .

# List projects
curl -s http://localhost:8000/api/projects | jq .

# Health check
curl -s http://localhost:8000/health | jq .
```

---

## 7. API docs

- Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/health
