"""
Database repository layer.

Provides data access patterns using the Repository Pattern.
"""

from fplan_v2.db.repositories.base import BaseRepository
from fplan_v2.db.repositories.asset_repository import AssetRepository
from fplan_v2.db.repositories.loan_repository import LoanRepository
from fplan_v2.db.repositories.revenue_stream_repository import RevenueStreamRepository
from fplan_v2.db.repositories.historical_measurement_repository import HistoricalMeasurementRepository
from fplan_v2.db.repositories.cash_flow_repository import CashFlowRepository

__all__ = [
    "BaseRepository",
    "AssetRepository",
    "LoanRepository",
    "RevenueStreamRepository",
    "HistoricalMeasurementRepository",
    "CashFlowRepository",
]
