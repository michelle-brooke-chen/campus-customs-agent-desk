"""Customer Service agent: drafts every customer-facing message (never sends)."""

from .models import CustomerServiceReport, Role
from .team import build_agent

customer_service_agent = build_agent(
    Role.CUSTOMER_SERVICE,
    output_type=CustomerServiceReport,
    mcp_tools={"get_ticket", "get_product_details"},
)
