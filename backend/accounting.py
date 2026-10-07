"""Accounting agent: cash, invoices, payments, purchase orders, quotes and margins."""

from .models import Role, SpecialistReport
from .team import build_agent

accounting_agent = build_agent(
    Role.ACCOUNTING,
    output_type=SpecialistReport,
    mcp_tools={
        "get_ticket",
        "get_invoice",
        "get_cash_position",
        "preview_payment",
        "check_rent_affordability",
        "quote_bulk_order",
        "check_vendor_can_ship",
    },
)
