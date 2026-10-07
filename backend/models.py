"""Data types shared by the Campus Customs agent team."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Role(str, Enum):
    BOSS = "boss"
    INVENTORY = "inventory"
    ACCOUNTING = "accounting"
    FACILITIES = "facilities"
    CUSTOMER_SERVICE = "customer_service"


# --- Run-time dependencies ---------------------------------------------------


@dataclass
class Consultation:
    """One agent-to-agent request, kept for the audit trail."""

    from_role: Role
    to_role: Role
    request: str
    depth: int
    answer: str | None = None


@dataclass
class TeamDeps:
    """Passed to every agent run. Shared log + depth guard for teammate calls."""

    ticket_id: int | None = None
    depth: int = 0
    max_depth: int = 2
    consultations: list[Consultation] = field(default_factory=list)

    def child(self) -> "TeamDeps":
        return TeamDeps(
            ticket_id=self.ticket_id,
            depth=self.depth + 1,
            max_depth=self.max_depth,
            consultations=self.consultations,
        )


# --- Agent outputs -----------------------------------------------------------


class Fact(BaseModel):
    """A fact an agent relies on, with where it came from."""

    statement: str
    source: str = Field(description="Tool or teammate it came from, e.g. 'check_stock' or 'accounting'")


ActionTool = Literal[
    "pay_invoice",
    "pay_rent",
    "place_vendor_order",
    "approve_price_override",
    "send_customer_message",
    "update_ticket_status",
]


class ProposedAction(BaseModel):
    """Something that would change the books. Never executed without a human.

    If a human approves, the runner calls `tool` on the MCP server with
    `arguments` plus the approver's name. The server re-checks every shop rule.
    """

    owner: Role
    kind: Literal[
        "payment",
        "purchase_order",
        "restock_request",
        "price_override",
        "customer_message",
        "ticket_update",
        "other",
    ]
    description: str
    tool: ActionTool | None = Field(
        default=None, description="MCP action tool to run if a human approves; null if not executable"
    )
    arguments: dict[str, str | int | float] = Field(
        default_factory=dict, description="Arguments for `tool`, excluding approved_by"
    )
    amount: float | None = Field(default=None, description="Dollars leaving cash, if any")
    rationale: str
    requires_human_approval: Literal[True] = True


class CustomerMessageDraft(BaseModel):
    to: str
    subject: str
    body: str
    status: Literal["draft_awaiting_approval"] = "draft_awaiting_approval"


class SpecialistReport(BaseModel):
    """What Inventory, Accounting, and Facilities hand back."""

    role: Role
    answer: str = Field(description="Direct answer to the request, grounded in facts")
    facts: list[Fact] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(
        default_factory=list, description="Anything the agent needs a human or teammate to clarify"
    )
    proposed_actions: list[ProposedAction] = Field(default_factory=list)


class CustomerServiceReport(SpecialistReport):
    """Customer Service also returns a draft message (never sent)."""

    message_draft: CustomerMessageDraft | None = None


class Delegation(BaseModel):
    role: Role
    request: str
    finding: str


class TicketPlan(BaseModel):
    """The Boss's recommendation for one ticket, held for human approval."""

    ticket_id: int
    summary: str
    delegations: list[Delegation]
    facts: list[Fact]
    cash_check: str = Field(
        description="Cash before and after every proposed payment, in execution order; must never go negative"
    )
    proposed_actions: list[ProposedAction] = Field(description="In the order they must execute")
    customer_message_draft: CustomerMessageDraft | None = None
    open_questions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    status: Literal["awaiting_human_approval"] = "awaiting_human_approval"
