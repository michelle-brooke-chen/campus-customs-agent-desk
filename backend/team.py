"""Shared wiring for the agent team: model, MCP tools, teammate consultation, limits.

Every agent is built with `build_agent`, which gives it:
  * the gpt-6-luna model through the Portkey gateway,
  * its system prompt from backend/prompts/<role>.md,
  * an allowlisted, read-only view of the Campus Customs MCP server's tools
    (every call is appended to output/audit_trail.json), and
  * a `consult_teammate` tool that can reach any other agent (full connectivity).

Shop facts only ever come through the MCP server; no agent touches the
database directly, and no agent is given an action (write) tool.
"""

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastmcp.client.transports import PythonStdioTransport
from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelRetry, RunContext, UsageLimits
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from . import audit
from .models import Consultation, Role, TeamDeps

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"

load_dotenv(PROJECT_ROOT / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

PORTKEY_BASE_URL = os.environ.get("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")
PORTKEY_MODEL = os.environ.get("PORTKEY_MODEL", "gpt-6-luna")
DB_PATH = os.environ.get("CAMPUS_CUSTOMS_DB", str(PROJECT_ROOT / "data" / "campus_customs_new.db"))

# --- Token / cost limits -----------------------------------------------------
# Usage is shared across the whole consultation tree for a ticket, so these cap
# the Boss plus every teammate it (transitively) consults.
TOKENS_PER_TICKET = int(os.environ.get("TEAM_TOKENS_PER_TICKET", 120_000))
REQUESTS_PER_TICKET = int(os.environ.get("TEAM_REQUESTS_PER_TICKET", 40))
TOOL_CALLS_PER_TICKET = int(os.environ.get("TEAM_TOOL_CALLS_PER_TICKET", 60))
TOKENS_PER_RUN = int(os.environ.get("TEAM_TOKENS_PER_RUN", 360_000))
MAX_OUTPUT_TOKENS = int(os.environ.get("TEAM_MAX_OUTPUT_TOKENS", 8_000))
MAX_CONSULT_DEPTH = int(os.environ.get("TEAM_MAX_CONSULT_DEPTH", 2))


def ticket_usage_limits() -> UsageLimits:
    return UsageLimits(
        total_tokens_limit=TOKENS_PER_TICKET,
        request_limit=REQUESTS_PER_TICKET,
        tool_calls_limit=TOOL_CALLS_PER_TICKET,
    )


# --- MCP tools ---------------------------------------------------------------
# Action tools change the books. They exist on the MCP server but no agent may
# hold them: the runner calls them only after a human approves.
ACTION_TOOLS = {
    "pay_invoice",
    "pay_rent",
    "place_vendor_order",
    "approve_price_override",
    "send_customer_message",
    "update_ticket_status",
    "reset_database",
}


# Every agent holds these (plus consult_teammate) and lists them in its prompt.
SHARED_MCP_TOOLS = {"get_ticket"}

# Read tools on the MCP server. A prompt may only name the ones its agent holds.
READ_TOOLS = {
    "list_tickets",
    "list_payments",  # runner only: feeds the desk board's cash panel
    "list_open_tickets",
    "get_ticket",
    "get_product_details",
    "check_stock",
    "list_vendors",
    "check_vendor_can_ship",
    "get_invoice",
    "get_cash_position",
    "preview_payment",
    "check_rent_affordability",
    "quote_bulk_order",
    "get_lease",
}


async def _audit_tool_call(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict[str, Any]):
    result = await call_tool(name, args)
    audit.record(
        "mcp_tool_call",
        actor=ctx.agent.name if ctx.agent else "unknown",
        ticket_id=ctx.deps.ticket_id if ctx.deps else None,
        tool=name,
        arguments=args,
        result=result,
    )
    return result


# One MCP connection (stdio subprocess) shared by every agent and the runner.
mcp_toolset = MCPToolset(
    PythonStdioTransport(
        PROJECT_ROOT / "mcp_server" / "server.py",
        env={**os.environ, "CAMPUS_CUSTOMS_DB": DB_PATH},
        cwd=str(PROJECT_ROOT),
    ),
    process_tool_call=_audit_tool_call,
)


# --- Model -------------------------------------------------------------------


def build_model() -> OpenAIResponsesModel:
    api_key = os.environ.get("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("Set PORTKEY_API_KEY in the environment or a .env file before running.")
    # Responses API: Azure-hosted gpt-6-luna only allows function tools with
    # reasoning on /v1/responses, not /v1/chat/completions.
    return OpenAIResponsesModel(
        PORTKEY_MODEL,
        provider=OpenAIProvider(
            openai_client=AsyncOpenAI(
                api_key=api_key,
                base_url=PORTKEY_BASE_URL,
                default_headers={"x-portkey-api-key": api_key},
            )
        ),
    )


# --- Team --------------------------------------------------------------------

TEAM: dict[Role, Agent[TeamDeps, Any]] = {}

ROLE_SUMMARIES = {
    Role.BOSS: "triages tickets, delegates, and assembles the final plan for human approval",
    Role.INVENTORY: "stock levels, product details (type, color, design, price), vendors, whether a vendor can ship, lead times",
    Role.ACCOUNTING: "cash, invoices, payment previews, payments, purchase orders, quotes, discounts, and margins",
    Role.FACILITIES: "the physical shop: leases, rent, landlord, and space issues",
    Role.CUSTOMER_SERVICE: "drafts every customer-facing message in a professional, respectful tone",
}


def load_prompt(role: Role) -> str:
    return (PROMPTS_DIR / f"{role.value}.md").read_text(encoding="utf-8")


def _roster(me: Role) -> str:
    lines = [f"- {r.value}: {s}" for r, s in ROLE_SUMMARIES.items() if r != me]
    return "Your teammates (reachable with `consult_teammate`):\n" + "\n".join(lines)


def build_agent(role: Role, output_type: type, mcp_tools: set[str]) -> Agent[TeamDeps, Any]:
    if forbidden := mcp_tools & ACTION_TOOLS:
        raise ValueError(f"{role.value} may not hold action tools: {sorted(forbidden)}")
    if missing := SHARED_MCP_TOOLS - mcp_tools:
        raise ValueError(f"{role.value} must hold the shared tools: {sorted(missing)}")
    prompt = load_prompt(role)
    if unlisted := [t for t in sorted(mcp_tools | {"consult_teammate"}) if f"`{t}" not in prompt]:
        raise ValueError(f"prompts/{role.value}.md must list every tool it holds; missing {unlisted}")
    if not_held := [t for t in sorted(READ_TOOLS - mcp_tools) if f"`{t}" in prompt]:
        raise ValueError(f"prompts/{role.value}.md names read tools it doesn't hold: {not_held}")

    agent = Agent(
        build_model(),
        name=role.value,
        deps_type=TeamDeps,
        output_type=output_type,
        instructions=[prompt, _roster(role)],
        toolsets=[mcp_toolset.filtered(lambda ctx, tool: tool.name in mcp_tools)],
        model_settings={"max_tokens": MAX_OUTPUT_TOKENS},
        retries=2,
    )

    @agent.tool
    async def consult_teammate(ctx: RunContext[TeamDeps], teammate: Role, request: str) -> str:
        """Ask another agent on the team for help and get their report back.

        Args:
            teammate: Which agent to ask (any role except yourself).
            request: A specific, self-contained question or task, including
                the ticket id and any facts they need.
        """
        if teammate == role:
            raise ModelRetry("You cannot consult yourself; pick a different teammate.")
        if ctx.deps.depth >= ctx.deps.max_depth:
            audit.record("consultation_blocked", role.value, ctx.deps.ticket_id, to=teammate.value, request=request)
            return (
                "Consultation limit reached for this chain. Answer with the facts you "
                "already have and list anything missing as a clarifying question."
            )
        record = Consultation(role, teammate, request, ctx.deps.depth + 1)
        ctx.deps.consultations.append(record)
        audit.record("consultation_request", role.value, ctx.deps.ticket_id, to=teammate.value, depth=record.depth, request=request)
        result = await TEAM[teammate].run(
            f"Request from {role.value}: {request}",
            deps=ctx.deps.child(),
            usage=ctx.usage,
            usage_limits=ctx.usage_limits,
        )
        report = result.output.model_dump(mode="json")
        record.answer = report.get("answer")
        audit.record("consultation_report", teammate.value, ctx.deps.ticket_id, to=role.value,
                     answer=report.get("answer"), report=report)
        return json.dumps(report)

    TEAM[role] = agent
    return agent
