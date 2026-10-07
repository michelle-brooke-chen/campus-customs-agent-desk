"""Campus Customs backend: FastAPI routes for the desk board, plus a CLI runner.

Serve the API (the board talks to this), from the hw5 folder:

    uvicorn main:app --reload --port 8000

(hw5/main.py just imports `app` from here.)

Routes:
    GET  /tickets                      all tickets, open or resolved, plus each one's run state
    POST /tickets/{ticket_id}/run      start the agent team on one ticket (runs in the background)
    GET  /tickets/{ticket_id}/run      that run's status, plan, and proposed actions
    GET  /events?since=&ticket_id=     recent agent events (who said what, which tools) for refresh
    GET  /actions?status=pending       proposed actions waiting for a human
    POST /actions/{action_id}/approve  a human approves; the action runs through the MCP server
    POST /actions/{action_id}/reject   a human declines; nothing runs
    POST /tickets/{ticket_id}/resolve  a human closes a ticket whose run needs their OK to resolve
    GET  /cash                         checking balance, the balance at the last reset, and payments since
    POST /reset                        restore the database to the original values

Or run from the terminal (with the venv active), approving each action on stdin:

    python -m backend.main                       # full run: reset DB, then every open ticket
    python -m backend.main 101 103               # just these tickets (no reset unless --reset)
    python -m backend.main --approve none        # plan only; approve nothing

Every shop fact and every change goes through the MCP server, and every step is
appended to output/audit_trail.json.
"""

import argparse
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, StringConstraints
from pydantic_ai import UsageLimitExceeded
from pydantic_ai.usage import RunUsage

from . import audit, boss_agent, mcp_toolset
from .models import ProposedAction, TeamDeps, TicketPlan
from .team import MAX_CONSULT_DEPTH, PROJECT_ROOT, TOKENS_PER_RUN, ticket_usage_limits

RUN_OUTPUT = PROJECT_ROOT / "output" / "team_run.json"
CASH_ACCOUNT = "checking"


# =============================================================================
# Shared helpers (API and CLI)
# =============================================================================


async def call_mcp(name: str, args: dict | None = None) -> Any:
    """Every shop fact and change goes through the MCP server, never the DB directly."""
    result = await mcp_toolset.direct_call_tool(name, args or {})
    # FastMCP wraps list results as {"result": [...]}.
    if isinstance(result, dict) and set(result) == {"result"}:
        return result["result"]
    return result


async def run_ticket(ticket_id: int) -> dict:
    deps = TeamDeps(ticket_id=ticket_id, max_depth=MAX_CONSULT_DEPTH)
    run_usage = RunUsage()  # kept outside the run so tokens spent before a limit stop still count
    audit.record("ticket_started", "boss", ticket_id)
    try:
        result = await boss_agent.run(
            f"Handle ticket #{ticket_id}. Look it up, delegate to the right teammates, "
            "and return a plan for human approval.",
            deps=deps,
            usage=run_usage,
            usage_limits=ticket_usage_limits(),
        )
    except UsageLimitExceeded as e:
        usage = {"requests": run_usage.requests, "total_tokens": run_usage.total_tokens}
        audit.record("usage_limit_exceeded", "runner", ticket_id, error=str(e), usage=usage)
        return {"status": "stopped_usage_limit", "error": str(e), "total_tokens": usage["total_tokens"],
                "usage": usage, "consultations": [asdict(c) for c in deps.consultations]}
    usage = {"requests": run_usage.requests, "total_tokens": run_usage.total_tokens}
    plan = result.output
    audit.record("plan_ready", "boss", ticket_id, summary=plan.summary, plan=plan.model_dump(mode="json"), usage=usage)
    return {
        "status": plan.status,
        "plan": plan,
        "consultations": [asdict(c) for c in deps.consultations],
        "total_tokens": usage["total_tokens"],
        "usage": usage,
    }


def action_arguments(action: ProposedAction, plan: TicketPlan) -> dict:
    args = dict(action.arguments)
    if action.tool == "send_customer_message" and plan.customer_message_draft:
        draft = plan.customer_message_draft
        args.setdefault("ticket_id", plan.ticket_id)
        args.setdefault("to", draft.to)
        args.setdefault("subject", draft.subject)
        args.setdefault("body", draft.body)
    return args


def other_ticket_for(ticket_id: int, tool: str | None, args: dict, tickets: list[dict]) -> int | None:
    """The other ticket an action really belongs to, if any (e.g. #101 proposing #102's rent)."""
    for t in tickets:
        if t["id"] == ticket_id:
            continue
        if args.get("ticket_id") == t["id"]:
            return t["id"]
        if tool == "pay_rent" and t["lease_id"] is not None and args.get("lease_id") == t["lease_id"]:
            return t["id"]
        if tool == "pay_invoice" and t["invoice_id"] is not None and args.get("invoice_id") == t["invoice_id"]:
            return t["id"]
    return None


def other_ticket_refusal(other_id: int) -> dict:
    return {"ok": False, "error": f"This belongs to ticket #{other_id}. Approve it on that ticket instead."}


async def execute_action(tool: str, args: dict, approver: str, ticket_id: int, description: str) -> Any:
    """Run an approved action through the MCP server, which re-checks every shop rule."""
    result = await call_mcp(tool, {**args, "approved_by": approver})
    audit.record("human_decision", approver, ticket_id, action=description, tool=tool,
                 arguments=args, decision="approved", approved_by=approver, result=result)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# =============================================================================
# FastAPI app
# =============================================================================

# In-memory state for this server process. The audit trail is the durable record.
RUNS: dict[int, dict] = {}       # ticket_id -> latest run
TASKS: dict[int, asyncio.Task] = {}  # ticket_id -> background agent run
ACTIONS: dict[str, dict] = {}    # action_id -> proposed action + decision
STATE = {"tokens_used": 0}        # tokens spent since startup or the last reset


def _new_action(action_id: str, ticket_id: int, action: ProposedAction, args: dict, other_id: int | None) -> dict:
    return {
        "id": action_id,
        "ticket_id": ticket_id,
        "owner": action.owner.value,
        "kind": action.kind,
        "description": action.description,
        "amount": action.amount,
        "rationale": action.rationale,
        "tool": action.tool,
        "arguments": args,
        "status": "not_executable" if not action.tool
        else "blocked_other_ticket" if other_id is not None else "pending",
        "decided_by": None,
        "decided_at": None,
        "result": other_ticket_refusal(other_id) if other_id is not None else None,
    }


def _ok(result: Any) -> bool:
    return isinstance(result, dict) and bool(result.get("ok"))


async def _restore_runs() -> None:
    """Rebuild each ticket's latest run from the audit trail, so a restart doesn't wipe the board.

    Only events since the last database reset count. The trail is the durable record:
    when the run started, the Boss's plan, token usage, every human decision, and the resolution.
    """
    entries = audit.read_all()
    resets = [i for i, e in enumerate(entries) if e["event"] == "database_reset"]
    entries = entries[resets[-1]:] if resets else entries
    db_status = {t["id"]: t["status"] for t in await call_mcp("list_tickets")}
    for ticket_id in db_status:
        events = [e for e in entries if e.get("ticket_id") == ticket_id]
        starts = [i for i, e in enumerate(events) if e["event"] == "ticket_started"]
        if not starts:
            continue
        run_no, events = len(starts), events[starts[-1]:]
        run: dict[str, Any] = {"ticket_id": ticket_id, "run_no": run_no, "started_at": events[0]["timestamp"],
                               "action_ids": [], "restored_from_audit": True}
        ended = next((e for e in events if e["event"] in {"plan_ready", "run_failed", "usage_limit_exceeded"}), None)
        if ended is None:  # the server stopped mid-run; nothing will finish it now
            run.update(status="error", error="The API restarted while this run was in progress. Run the team again.")
        elif ended["event"] == "run_failed":
            run.update(status="error", error=ended.get("error"), finished_at=ended["timestamp"])
        elif ended["event"] == "usage_limit_exceeded":
            run.update(status="stopped_usage_limit", error=ended.get("error"), usage=ended.get("usage"),
                       finished_at=ended["timestamp"])
        elif not isinstance(ended.get("plan"), dict):  # an older trail clipped the plan; can't rebuild it
            run.update(status="error", error="This run's plan wasn't stored in full. Run the team again.")
        else:
            plan = TicketPlan.model_validate(ended["plan"])
            run.update(plan=ended["plan"], usage=ended.get("usage"), finished_at=ended["timestamp"])
            blocked = [e for e in events if e["event"] == "action_blocked_other_ticket"]
            decisions = [e for e in events if e["event"] == "human_decision"]
            for i, action in enumerate(plan.proposed_actions, start=1):
                args = action_arguments(action, plan)
                b = next((e for e in blocked if e.get("tool") == action.tool and e.get("arguments") == args), None)
                a = _new_action(f"{ticket_id}-{run_no}-{i}", ticket_id, action, args, b and b["belongs_to"])
                d = next((e for e in decisions if e.get("tool") == action.tool and e.get("arguments") == args), None)
                if d is not None and a["status"] == "pending":
                    decisions.remove(d)
                    ok = _ok(d.get("result"))
                    a.update(status=("executed" if ok else "refused_by_server") if d.get("decision") == "approved"
                             else "rejected",
                             decided_by=d["actor"], decided_at=d["timestamp"], result=d.get("result"))
                ACTIONS[a["id"]] = a
                run["action_ids"].append(a["id"])
            statuses = [ACTIONS[i]["status"] for i in run["action_ids"]]
            # Only this run's own resolution counts; a resolved ticket can be run again. The run
            # resolved it either through the runner's ticket_resolved event or an approved
            # update_ticket_status(resolved) action.
            resolved = next((e for e in events if _ok(e.get("result")) and (
                e["event"] == "ticket_resolved"
                or (e["event"] == "human_decision" and e.get("tool") == "update_ticket_status"
                    and e.get("decision") == "approved" and (e.get("arguments") or {}).get("status") == "resolved")
            )), None)
            if resolved is not None and db_status[ticket_id] == "resolved":
                run.update(status="resolved", resolved_at=resolved["timestamp"])
            elif "pending" in statuses:
                run["status"] = "awaiting_approval"
            elif db_status[ticket_id] not in {"open", "resolved"}:
                run["status"] = f"finished_{db_status[ticket_id]}"
            else:
                run["status"] = "awaiting_resolution"
        RUNS[ticket_id] = run
    # Every run since the reset counts toward the token budget, not just each ticket's latest.
    STATE["tokens_used"] = sum((e.get("usage") or {}).get("total_tokens", 0) for e in entries
                               if e["event"] in {"plan_ready", "usage_limit_exceeded"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_toolset:  # one MCP connection for the server's lifetime
        try:
            await _restore_runs()
        except Exception as e:  # a bad trail must never keep the desk from starting
            RUNS.clear()
            ACTIONS.clear()
            audit.record("restore_failed", "runner", error=repr(e))
        yield


app = FastAPI(
    title="Campus Customs Desk API",
    description="Routes for the desk board. Shop data comes only from the MCP server.",
    lifespan=lifespan,
)
# Only the desk board's Vite page may call the API from a browser.
BOARD_ORIGINS = os.environ.get("BOARD_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=BOARD_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


# A name that is blank once trimmed is rejected with 422 before anything runs.
HumanName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ApproveBody(BaseModel):
    approved_by: HumanName = Field(description="Name of the human approving this action")


class RejectBody(BaseModel):
    rejected_by: HumanName
    reason: str = ""


def _public_action(a: dict) -> dict:
    return {k: v for k, v in a.items() if k != "_plan"}


def _run_view(ticket_id: int) -> dict:
    run = RUNS.get(ticket_id)
    if run is None:
        return {"status": "not_run"}
    actions = [_public_action(ACTIONS[i]) for i in run.get("action_ids", [])]
    return {**{k: v for k, v in run.items() if k != "action_ids"}, "actions": actions}


async def _ticket_ids() -> set[int]:
    return {t["id"] for t in await call_mcp("list_tickets")}


async def _background_run(ticket_id: int, run_no: int) -> None:
    run = RUNS[ticket_id]
    try:
        await _run_and_collect(ticket_id, run_no, run)
    except Exception as e:  # surface model/network errors to the board instead of staying "running" forever
        audit.record("run_failed", "runner", ticket_id, error=repr(e))
        run.update(status="error", error=repr(e), finished_at=_now())


async def _run_and_collect(ticket_id: int, run_no: int, run: dict) -> None:
    """Run the team, then turn the Boss's plan into actions waiting for a human."""
    result = await run_ticket(ticket_id)
    STATE["tokens_used"] += result["total_tokens"]
    plan = result.get("plan")
    if not isinstance(plan, TicketPlan):
        run.update(status=result["status"], error=result.get("error"), finished_at=_now())
        return
    tickets = await call_mcp("list_tickets")
    action_ids = []
    for i, action in enumerate(plan.proposed_actions, start=1):
        action_id = f"{ticket_id}-{run_no}-{i}"
        args = action_arguments(action, plan)
        other_id = other_ticket_for(ticket_id, action.tool, args, tickets) if action.tool else None
        if other_id is not None:
            audit.record("action_blocked_other_ticket", "runner", ticket_id, tool=action.tool,
                         arguments=args, belongs_to=other_id)
        ACTIONS[action_id] = _new_action(action_id, ticket_id, action, args, other_id)
        action_ids.append(action_id)
    has_pending = any(ACTIONS[i]["status"] == "pending" for i in action_ids)
    run.update(
        # With nothing to approve, a human still has to close the ticket; agents never resolve it.
        status="awaiting_approval" if has_pending else "awaiting_resolution",
        plan=plan.model_dump(mode="json"),
        consultations=result["consultations"],
        usage=result["usage"],
        action_ids=action_ids,
        finished_at=_now(),
    )


async def _resolve(ticket_id: int, approver: str, note: str) -> str:
    """Mark the ticket resolved through the MCP server (unless a human approved another status)."""
    run = RUNS[ticket_id]
    run["status"] = "resolving"  # claimed before any await, so a second click can't resolve twice
    try:
        status = next(t["status"] for t in await call_mcp("list_tickets") if t["id"] == ticket_id)
        result: dict = {}
        if status == "open":
            result = await call_mcp("update_ticket_status", {
                "ticket_id": ticket_id, "status": "resolved", "note": note, "approved_by": approver,
            })
            audit.record("ticket_resolved", approver, ticket_id, result=result)
            status = "resolved" if result.get("ok") else status
    except Exception:
        run["status"] = "awaiting_resolution"
        raise
    if status == "open":  # the MCP server refused; keep asking a human
        run.update(status="awaiting_resolution", error=str(result.get("error", "Resolving was refused")))
    else:
        run.update(status="resolved" if status == "resolved" else f"finished_{status}", resolved_at=_now())
    return status


async def _maybe_resolve(ticket_id: int, decided_by: str) -> None:
    """After a human's decision: once every action is decided, resolve the ticket.

    If anything was declined or refused, the ticket stays open and the board asks a
    human whether to close it anyway (POST /tickets/{id}/resolve) or run the team again.
    """
    run = RUNS.get(ticket_id)
    if run is None or run.get("status") != "awaiting_approval":
        return
    statuses = [ACTIONS[i]["status"] for i in run.get("action_ids", [])]
    if any(s in {"pending", "executing"} for s in statuses):
        return
    if any(s in {"rejected", "refused_by_server", "blocked_other_ticket"} for s in statuses):
        run.update(status="awaiting_resolution")
        return
    try:
        await _resolve(ticket_id, decided_by, "Agent run finished and every proposed action was approved on the desk board.")
    except Exception as e:  # the approval itself already ran; leave closing the ticket to a human
        audit.record("resolve_failed", "runner", ticket_id, error=repr(e))


@app.get("/tickets")
async def list_tickets():
    """All tickets, each marked open or resolved, plus the state of its latest agent run."""
    tickets = await call_mcp("list_tickets")
    return [
        {**t, "resolved": t["status"] == "resolved", "run": _run_view(t["id"])["status"]}
        for t in tickets
    ]


@app.post("/tickets/{ticket_id}/run", status_code=202)
async def run_team(ticket_id: int):
    """Start the agent team on one ticket. Poll /events or GET this route to follow it."""
    if ticket_id not in await _ticket_ids():
        raise HTTPException(404, f"No ticket {ticket_id}")
    if RUNS.get(ticket_id, {}).get("status") == "running":
        raise HTTPException(409, f"Ticket {ticket_id} is already running")
    if STATE["tokens_used"] >= TOKENS_PER_RUN:
        raise HTTPException(429, f"Token budget of {TOKENS_PER_RUN:,} used up; reset to start a fresh run")
    # Proposals from an earlier run of this ticket are replaced by the new plan.
    for a in ACTIONS.values():
        if a["ticket_id"] == ticket_id and a["status"] == "pending":
            a["status"] = "superseded"
    run_no = RUNS.get(ticket_id, {}).get("run_no", 0) + 1
    last_event = audit.recent(limit=1)
    RUNS[ticket_id] = {"ticket_id": ticket_id, "run_no": run_no, "status": "running", "started_at": _now()}
    TASKS[ticket_id] = asyncio.create_task(_background_run(ticket_id, run_no))
    return {
        "ticket_id": ticket_id,
        "run_no": run_no,
        "status": "running",
        "events_since": last_event[-1]["id"] if last_event else 0,
    }


@app.get("/tickets/{ticket_id}/run")
async def get_run(ticket_id: int):
    """The latest run for a ticket: status, the Boss's plan, and its proposed actions."""
    return _run_view(ticket_id)


@app.post("/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: int, body: ApproveBody):
    """A human closes a ticket whose run finished with nothing left to approve."""
    run = RUNS.get(ticket_id)
    if run is None or run.get("status") not in {"awaiting_approval", "awaiting_resolution"}:
        raise HTTPException(409, f"Ticket {ticket_id} has no finished run waiting to be resolved")
    if any(ACTIONS[i]["status"] in {"pending", "executing"} for i in run.get("action_ids", [])):
        raise HTTPException(409, f"Ticket {ticket_id} still has actions waiting for a decision")
    status = await _resolve(ticket_id, body.approved_by.strip(), "Closed on the desk board by a human.")
    return {"ticket_id": ticket_id, "status": status, "run": _run_view(ticket_id)["status"]}


def _summarize(e: dict) -> str:
    match e["event"]:
        case "mcp_tool_call":
            return f"{e['actor']} used {e['tool']}"
        case "consultation_request":
            return f"{e['actor']} asked {e['to']}: {e['request']}"
        case "consultation_report":
            return f"{e['actor']} answered {e['to']}: {e.get('answer', '')}"
        case "consultation_blocked":
            return f"{e['actor']} hit the consultation depth limit asking {e['to']}"
        case "plan_ready":
            return f"boss plan: {e.get('summary', '')}"
        case "ticket_resolved":
            return f"ticket resolved by {e['actor']}"
        case "action_blocked_other_ticket":
            return f"{e.get('tool')} blocked: it belongs to ticket #{e.get('belongs_to')}"
        case "human_decision":
            return f"{e['actor']} {e.get('decision')} {e.get('tool') or e.get('action')}"
        case _:
            return e["event"].replace("_", " ")


@app.get("/events")
async def events(since: int = 0, ticket_id: int | None = None, limit: int = 100):
    """Recent agent events after `since` (an event id), newest last, each with a one-line summary."""
    items = audit.recent(since_id=since, ticket_id=ticket_id, limit=min(limit, 500))
    return {
        "last_id": items[-1]["id"] if items else since,
        "events": [{**e, "summary": _summarize(e)} for e in items],
    }


@app.get("/actions")
async def list_actions(status: str | None = None, ticket_id: int | None = None):
    """Proposed actions, optionally filtered (e.g. status=pending for the approval queue)."""
    return [
        _public_action(a) for a in ACTIONS.values()
        if (status is None or a["status"] == status) and (ticket_id is None or a["ticket_id"] == ticket_id)
    ]


@app.post("/actions/{action_id}/approve")
async def approve_action(action_id: str, body: ApproveBody):
    """A human clicked Approve: run the action (payment, purchase, etc.) through the MCP server."""
    action = ACTIONS.get(action_id)
    if action is None:
        raise HTTPException(404, f"No action {action_id}")
    if action["status"] != "pending":
        raise HTTPException(409, f"Action {action_id} is {action['status']}, not pending")
    action["status"] = "executing"  # blocks a double-click from paying twice
    try:
        result = await execute_action(action["tool"], action["arguments"], body.approved_by.strip(),
                                      action["ticket_id"], action["description"])
    except Exception as e:
        action["status"] = "pending"
        raise HTTPException(502, f"MCP server error while executing {action['tool']}: {e!r}")
    ok = isinstance(result, dict) and result.get("ok", False)
    action.update(
        status="executed" if ok else "refused_by_server",
        decided_by=body.approved_by.strip(),
        decided_at=_now(),
        result=result,
    )
    await _maybe_resolve(action["ticket_id"], body.approved_by.strip())
    return _public_action(action)


@app.post("/actions/{action_id}/reject")
async def reject_action(action_id: str, body: RejectBody):
    """A human declined: nothing runs."""
    action = ACTIONS.get(action_id)
    if action is None:
        raise HTTPException(404, f"No action {action_id}")
    if action["status"] != "pending":
        raise HTTPException(409, f"Action {action_id} is {action['status']}, not pending")
    action.update(status="rejected", decided_by=body.rejected_by.strip(), decided_at=_now())
    audit.record("human_decision", body.rejected_by.strip(), action["ticket_id"], action=action["description"],
                 tool=action["tool"], arguments=action["arguments"], decision="not_approved", reason=body.reason)
    await _maybe_resolve(action["ticket_id"], body.rejected_by.strip())
    return _public_action(action)


@app.get("/cash")
async def cash():
    """Current checking balance from cash_accounts, plus every payment since the last reset (via MCP)."""
    position = await call_mcp("get_cash_position")
    payments = await call_mcp("list_payments")
    checking = next(a for a in position["accounts"] if a["name"] == CASH_ACCOUNT)
    return {
        "account": CASH_ACCOUNT,
        "balance": checking["balance"],
        # Cash only goes down through payments, so this is the balance right after the last reset.
        "starting_balance": checking["balance"] + sum(p["amount"] for p in payments),
        "payments": payments,
        "as_of": checking["date"],
        "total_committed": position["total_committed"],
        "cash_after_all_obligations": position["cash_after_all_obligations"],
    }


@app.post("/reset")
async def reset():
    """Restore the database to the original values for a fresh run. Clears runs and proposals."""
    if any(r.get("status") in {"running", "resolving"} for r in RUNS.values()):
        raise HTTPException(409, "A ticket is still running; wait for it to finish before resetting")
    if any(a["status"] == "executing" for a in ACTIONS.values()):
        raise HTTPException(409, "An approval is still being carried out; try again in a moment")
    result = await call_mcp("reset_database")
    # Runs and proposals start over; executed payments are undone by the restore, so drop them too.
    ACTIONS.clear()
    RUNS.clear()
    STATE["tokens_used"] = 0
    archived = audit.start_fresh()
    audit.record("database_reset", "runner", result=result,
                 previous_trail=archived.name if archived else None)
    return {**result, "archived_trail": archived.name if archived else None}


# =============================================================================
# CLI runner
# =============================================================================


def _ask(action: ProposedAction, args: dict, mode: str) -> bool:
    if mode == "none":
        return False
    print(f"\n  [{action.owner.value}] {action.kind}: {action.description}", file=sys.stderr)
    if action.amount is not None:
        print(f"  amount: ${action.amount:,.2f}", file=sys.stderr)
    print(f"  will call: {action.tool}({json.dumps(args)})", file=sys.stderr)
    print("  Approve? [y/N] ", end="", file=sys.stderr, flush=True)
    return sys.stdin.readline().strip().lower() in {"y", "yes"}


async def review_and_execute(plan: TicketPlan, approver: str, mode: str) -> list[dict]:
    """Human-in-the-loop: nothing executes unless a named human says yes."""
    decisions = []
    tickets = await call_mcp("list_tickets")
    for action in plan.proposed_actions:
        args = action_arguments(action, plan)
        other_id = other_ticket_for(plan.ticket_id, action.tool, args, tickets) if action.tool else None
        if other_id is not None:
            decision = {"action": action.description, "tool": action.tool, "arguments": args,
                        "decision": "blocked_other_ticket", "result": other_ticket_refusal(other_id)}
            audit.record("action_blocked_other_ticket", "runner", plan.ticket_id, tool=action.tool,
                         arguments=args, belongs_to=other_id)
        elif action.tool is None:
            decision = {"action": action.description, "decision": "noted_not_executable"}
            audit.record("human_decision", "human", plan.ticket_id, **decision)
        elif _ask(action, args, mode):
            result = await execute_action(action.tool, args, approver, plan.ticket_id, action.description)
            decision = {"action": action.description, "tool": action.tool, "arguments": args,
                        "decision": "approved", "approved_by": approver, "result": result}
            print(f"  -> {json.dumps(result)[:300]}", file=sys.stderr)
        else:
            decision = {"action": action.description, "tool": action.tool, "arguments": args,
                        "decision": "not_approved"}
            audit.record("human_decision", "human", plan.ticket_id, **decision)
        decisions.append(decision)
    return decisions


async def cli_main(ticket_ids: list[int], reset_db: bool, approver: str, mode: str) -> None:
    runs, tokens_used = [], 0
    if reset_db:
        audit.start_fresh()  # a full run gets its own clean audit trail
    async with mcp_toolset:
        audit.record("run_started", "runner", tickets=ticket_ids or "all_open", reset=reset_db,
                     approval_mode=mode, token_budget=TOKENS_PER_RUN)
        if reset_db:
            result = await call_mcp("reset_database")
            audit.record("database_reset", "runner", result=result)
            print(f"Database reset: {result}", file=sys.stderr)
        if not ticket_ids:
            ticket_ids = [t["id"] for t in await call_mcp("list_open_tickets")]

        for ticket_id in ticket_ids:
            if tokens_used >= TOKENS_PER_RUN:
                audit.record("ticket_skipped_run_budget", "runner", ticket_id, tokens_used=tokens_used)
                runs.append({"ticket_id": ticket_id, "status": "skipped_run_token_budget"})
                continue
            print(f"\n=== Ticket #{ticket_id} ===", file=sys.stderr)
            run = await run_ticket(ticket_id)
            tokens_used += run["total_tokens"]
            if isinstance(run.get("plan"), TicketPlan):
                plan = run["plan"]
                print(f"  {plan.summary}", file=sys.stderr)
                run["human_decisions"] = await review_and_execute(plan, approver, mode)
                run["plan"] = plan.model_dump(mode="json")
            runs.append({"ticket_id": ticket_id, **run})

        audit.record("run_finished", "runner", tokens_used=tokens_used)
    RUN_OUTPUT.write_text(json.dumps({"run_id": audit.RUN_ID, "tokens_used": tokens_used, "runs": runs},
                                     indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {RUN_OUTPUT.relative_to(PROJECT_ROOT)} ({tokens_used:,} tokens)", file=sys.stderr)


def cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ticket_ids", nargs="*", type=int)
    parser.add_argument("--reset", action=argparse.BooleanOptionalAction, default=None,
                        help="Restore the DB to the original first (default: on for a full run)")
    parser.add_argument("--approver", default=os.environ.get("USERNAME") or os.environ.get("USER") or "",
                        help="Name recorded as approved_by on every executed action")
    parser.add_argument("--approve", choices=["ask", "none"], default="ask",
                        help="ask: prompt for each action on stdin; none: approve nothing")
    a = parser.parse_args()
    if a.approve == "ask" and not a.approver.strip():
        parser.error("--approver is required to record who approved each action")
    asyncio.run(cli_main(a.ticket_ids, a.reset if a.reset is not None else not a.ticket_ids, a.approver, a.approve))


if __name__ == "__main__":
    cli()
