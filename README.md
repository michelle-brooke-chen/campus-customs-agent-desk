# Campus Customs Agent Desk (Homework 5)

A team of five AI agents (Boss, Inventory, Accounting, Facilities, Customer Service) that works the help-desk tickets of Campus Customs, a Yale apparel shop. Every shop fact comes from a SQLite database through an MCP server, nothing that moves money happens without a named human's approval, and a React desk board lets you watch the team work and approve its proposals.

```
desk board (frontend/, :5173) → FastAPI (backend/main.py, :8000) → agent team (backend/, gpt-6-luna via Portkey)
                                                                  → MCP server (mcp_server/server.py) → data/campus_customs_new.db
```

## What's in the repo

| Path | What it is |
|---|---|
| `mcp_server/` | FastMCP server with 21 tools over the shop database ([README](mcp_server/README.md)) |
| `backend/` | The five PydanticAI agents, their prompts (`backend/prompts/`), and the FastAPI routes |
| `frontend/` | The desk board (React + Vite + TypeScript) |
| `data/` | `campus_customs.db` (original, never changed) and `campus_customs_new.db` (the working copy) |
| `output/` | Deliverables: [harness.md](output/harness.md), [design.md](output/design.md), `desk_tickets.html`, `resolved_board.html`, `resolved_tickets.json`, the audit trail, and test evidence |
| `AI_prompts.md` | Every prompt used to build this, organized by problem |

The two HTML pages in `output/` open by double-clicking; they don't need the servers.

## Setup

You need **Python 3.10+** (built with 3.14), **Node.js 20.19+ or 22.12+** (what Vite 8 requires; built with 24), and a **Portkey API key** with access to `gpt-6-luna`.

`.venv/` and `frontend/node_modules/` are specific to the computer they were installed on, so they aren't in the repo. Install them fresh on each machine, including when you switch between a Mac and a Windows PC.

### 1. Python environment

macOS / Linux:

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
python -m pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -m venv .venv
```

```powershell
.venv\Scripts\Activate.ps1
```

```powershell
python -m pip install -r requirements.txt
```

If PowerShell blocks the activation script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use Command Prompt with `.venv\Scripts\activate.bat`.

### 2. Frontend packages

```bash
npm --prefix frontend install
```

### 3. API key

Copy `.env.example` to `.env` and fill in `PORTKEY_API_KEY`. The model is already set to `gpt-6-luna`. `.env` is ignored by Git, so your key never leaves your computer.

macOS / Linux:

```bash
cp .env.example .env
```

Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

## Run the desk board

Start the API and the board in two terminals, both from this folder, with the virtual environment active in the first:

```bash
uvicorn main:app --reload --port 8000
```

```bash
npm run dev
```

Then open <http://localhost:5173> (or <http://localhost:5173/?ticket=102> to open on a specific ticket). The API's interactive docs are at <http://localhost:8000/docs>. The board only talks to the API at `http://localhost:8000`, and the API only accepts the board from `http://localhost:5173`.

On the board: type your name in **Approving as**, pick a ticket, click **Start agent team**, then approve or decline the team's proposals. **Reset shop** restores the original database.

## Run from the terminal instead

With the virtual environment active:

```bash
python -m backend.main --approve none
```

This resets the database, runs every open ticket, and approves nothing (drop `--approve none` to approve each action at a `y/N` prompt). Results go to `output/team_run.json` and `output/audit_trail.json`.

## Mac vs. Windows: the two config files to adjust

Two config files point at the virtual environment's Python, and that path differs by operating system. They're committed with the macOS path:

| File | macOS / Linux (as committed) | Windows |
|---|---|---|
| `.mcp.json` (connects the MCP server to Claude Code) | `"command": ".venv/bin/python"` | `"command": ".venv\\Scripts\\python.exe"` |
| `.claude/launch.json` (starts the servers from Claude Code's preview) | `"runtimeExecutable": ".venv/bin/python"` | `"runtimeExecutable": ".venv\\Scripts\\python.exe"` |

Nothing else depends on the operating system. The backend starts the MCP server with whatever Python is running it, and `npm run dev` works the same everywhere.

## Safety in one paragraph

Agents only hold read tools. Anything that changes the shop (payments, orders, price overrides, messages, ticket status) is proposed, shown on the board, and run only after a named human approves it, and the MCP server re-checks every rule when it does. Cash never goes up (no revenue is modeled) and never goes below $0, vendors with unpaid invoices can't ship, and prices never drop below cost. Every tool call, consultation, plan, and decision is appended to `output/audit_trail.json`. Token use is capped per ticket and per run. Details are in [output/harness.md](output/harness.md).
