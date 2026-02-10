"""
API route modules.

Contains FastAPI routers for different resource types.
"""

from fplan_v2.api.routes import assets, loans, revenue_streams, projections, historical_measurements, cash_flows, scenarios

__all__ = ["assets", "loans", "revenue_streams", "projections", "historical_measurements", "cash_flows", "scenarios"]
