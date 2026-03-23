# M3 Plan: Make Initiatives Actually Complete + Headshot AI

## Root Cause Analysis (from logs)

**Every initiative ever run has FAILED.** Here's why:

### March 18 runs (LangChain executor):
- Agents call `file_read("workspace")` → gets `[Errno 21] Is a directory`
- Agents burn all tool rounds retrying this, never write code
- **Fix**: file_read now returns directory listing instead of error (DONE)

### March 21 runs (Claude Code executor):
- PM agent (LangChain) works fine, writes good PRDs
- `chief_architect` (Claude Code) → binary "claude" not in PATH → exit code 1 in <700ms
- Every initiative dies at architect node, never reaches task_planning
- **Fix**: Binary path updated to full macOS app path (DONE)

### Both dates:
- No initiative has EVER reached task_planning, execute_tasks, or evaluate
- Zero code has ever been written by the engineering agents

## What's Already Fixed (this session)

1. **Claude Code binary path** → now points to `/Users/ruzbeh.i/Library/Application Support/Claude/claude-code/2.1.78/claude.app/Contents/MacOS/claude`
2. **file_read directory handling** → now returns file listing instead of error, so agents can navigate the workspace
3. **M2 closed loops** → QA retry, concurrent tasks, verdict actions, parse resilience

## What Still Needs To Happen (M3 implementation)

### Step 1: Verify Claude Code CLI actually works with the full path
- Run a simple test: create a subprocess with the binary, pass a trivial prompt, check output
- If it fails (auth, permissions, etc), switch all `claude_code` agents to `langchain` so they stop crashing

### Step 2: Add workspace_path to config pointing to headshot-studio
- Set `workspace_path` to `/Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio`
- This is the REAL project we want to improve

### Step 3: Run a REAL initiative end-to-end
- Launch the server, send a POST to `/api/initiative` with a simple Headshot AI improvement
- Watch the logs to see if it gets past architect → task_planning → execute_tasks → evaluate
- Fix whatever breaks in real-time

### Step 4: If Claude Code still fails, switch all engineers to LangChain
- Change `executor: claude_code` to `executor: langchain` for all 10 engineering agents
- They'll use file_read/file_write tools through LangChain (which works)
- This is the pragmatic path — LangChain with tools actually works, Claude Code CLI has been broken for 5 days

### Step 5: Headshot quality analysis
- Point AECO at the headshot-studio codebase
- Run an initiative: "Improve headshot generation quality and conversion rate"
- This tests the full pipeline with a real business goal

## Recommendation

**Switch all agents to LangChain first** (Step 4). The Claude Code CLI has been broken since day one. Get something shipping, THEN optimize the executor later. The LangChain path with file_read/file_write/git tools already works (PM agent, security reviewer, etc. all complete successfully).
