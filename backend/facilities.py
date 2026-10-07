"""Facilities agent: the physical shop -- leases, rent, landlord, and space."""

from .models import Role, SpecialistReport
from .team import build_agent

facilities_agent = build_agent(
    Role.FACILITIES,
    output_type=SpecialistReport,
    mcp_tools={"get_ticket", "get_lease", "check_rent_affordability", "preview_payment"},
)
