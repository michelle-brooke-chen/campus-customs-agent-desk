"""Inventory agent: stock levels, product details, vendors and restock lead times."""

from .models import Role, SpecialistReport
from .team import build_agent

inventory_agent = build_agent(
    Role.INVENTORY,
    output_type=SpecialistReport,
    mcp_tools={"get_ticket", "check_stock", "get_product_details", "list_vendors", "check_vendor_can_ship"},
)
