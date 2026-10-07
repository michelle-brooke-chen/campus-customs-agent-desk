"""Campus Customs agent team. Importing the package registers all five agents."""

from .accounting import accounting_agent
from .boss import boss_agent
from .customer_service import customer_service_agent
from .facilities import facilities_agent
from .inventory import inventory_agent
from .team import TEAM, mcp_toolset

__all__ = [
    "TEAM",
    "accounting_agent",
    "boss_agent",
    "customer_service_agent",
    "facilities_agent",
    "inventory_agent",
    "mcp_toolset",
]
