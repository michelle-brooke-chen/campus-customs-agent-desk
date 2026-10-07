"""Boss agent: triages tickets, delegates to the team, returns a plan for human approval."""

from .models import Role, TicketPlan
from .team import build_agent

boss_agent = build_agent(
    Role.BOSS,
    output_type=TicketPlan,
    mcp_tools={"list_open_tickets", "get_ticket", "get_cash_position"},
)
