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

## Start from a clean database

The agents only ever work on `data/campus_customs_new.db`. `data/campus_customs.db` is the original and is never changed. Approvals change the working copy (payments, orders, ticket statuses, notes), so before a fresh run, copy the original over it. There are three ways, and all give the same result:

1. **From the board:** click **Reset shop** and confirm. This is the usual way.
2. **From the API** (with the backend running):

   macOS / Linux:

   ```bash
   curl -X POST http://localhost:8000/reset
   ```

   Windows (PowerShell):

   ```powershell
   Invoke-RestMethod -Method Post http://localhost:8000/reset
   ```

3. **By copying the file yourself.** Stop the backend first, so nothing is using the database.

   macOS / Linux:

   ```bash
   cp data/campus_customs.db data/campus_customs_new.db
   ```

   Windows (PowerShell):

   ```powershell
   Copy-Item data\campus_customs.db data\campus_customs_new.db -Force
   ```

The first two go through the MCP server's `reset_database` tool. They also clear the board's runs and approvals and start a fresh `output/audit_trail.json`, moving the old one to `output/audit_archive/`. A manual copy only replaces the database, so use the board or the API when you also want a clean audit trail. The command-line runner below resets on its own before a full run.

After a reset, checking is $3,400.00 and tickets #101, #102, and #103 are open.

## Start the pieces

Run every command from this folder, with the virtual environment active in each Python terminal (`source .venv/bin/activate` on macOS / Linux, `.venv\Scripts\Activate.ps1` on Windows).

**1. MCP server.** You don't need to start it for the board or the command-line runner: the backend launches it automatically with its own Python. To run it on its own, for example to try its tools from Claude Code (registered in `.mcp.json`) or another MCP client:

```bash
python mcp_server/server.py
```

It talks over stdio, so it waits silently for a client; stop it with Ctrl+C. It uses `data/campus_customs_new.db` unless the `CAMPUS_CUSTOMS_DB` environment variable points elsewhere. The tools are listed in [mcp_server/README.md](mcp_server/README.md).

**2. FastAPI backend** (first terminal):

```bash
uvicorn main:app --reload --port 8000
```

It reads your key from `.env`, starts the MCP server, and rebuilds any earlier runs from the audit trail. The interactive docs are at <http://localhost:8000/docs>.

**3. React board** (second terminal):

```bash
npm run dev
```

Then open <http://localhost:5173>, or <http://localhost:5173/?ticket=102> to open on a specific ticket. The board only talks to the API at `http://localhost:8000`, and the API only accepts the board from `http://localhost:5173`.

## A full run of the three tickets

1. Start the backend and the board (above).
2. Type your name in **Approving as**. Every approval is recorded with it.
3. Click **Reset shop** and confirm. The green banner should show checking back at $3,400.00.
4. Select **#101**, click **Start agent team**, and watch the bulldogs work. When the plan is ready, read it and approve or decline each proposed action in the Approvals panel. Approve a vendor's unpaid invoice before any order from that vendor, or the server will refuse the order.
5. Repeat for **#102** and **#103**. A ticket resolves once you approve all of its actions. If you decline something, click **Mark ticket resolved** when you're satisfied.
6. Check the result in the Checking balance panel and in `output/audit_trail.json`.

### Or from the terminal

With the virtual environment active:

```bash
python -m backend.main --approve none
```

This resets the database, runs all three open tickets, and approves nothing (drop `--approve none` to approve each action at a `y/N` prompt). Results go to `output/team_run.json` and `output/audit_trail.json`.

## Mac vs. Windows: the two config files to adjust

Two config files point at the virtual environment's Python, and that path differs by operating system. They're committed with the macOS path:

| File | macOS / Linux (as committed) | Windows |
|---|---|---|
| `.mcp.json` (connects the MCP server to Claude Code) | `"command": ".venv/bin/python"` | `"command": ".venv\\Scripts\\python.exe"` |
| `.claude/launch.json` (starts the servers from Claude Code's preview) | `"runtimeExecutable": ".venv/bin/python"` | `"runtimeExecutable": ".venv\\Scripts\\python.exe"` |

Nothing else depends on the operating system. The backend starts the MCP server with whatever Python is running it, and `npm run dev` works the same everywhere.

## Safety in one paragraph

Agents only hold read tools. Anything that changes the shop (payments, orders, price overrides, messages, ticket status) is proposed, shown on the board, and run only after a named human approves it, and the MCP server re-checks every rule when it does. Cash never goes up (no revenue is modeled) and never goes below $0, vendors with unpaid invoices can't ship, and prices never drop below cost. Every tool call, consultation, plan, and decision is appended to `output/audit_trail.json`. Token use is capped per ticket and per run. Details are in [output/harness.md](output/harness.md).
