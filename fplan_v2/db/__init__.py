"""
Database layer for FPlan v2.

Provides PostgreSQL schema, ORM models, and connection management
optimized for Neon serverless deployment.
"""

from .connection import db_session, get_db_manager, init_database, check_connection
from fplan_v2.db import models  # noqa: F401 — re-export models module for `from fplan_v2.db import models`
from .models import (
    User,
    Asset,
    Loan,
    RevenueStream,
    CashFlow,
    HistoricalMeasurement,
    OperationLog,
    IndexData,
    IndexNotification,
    Scenario,
    ScenarioResult,
)

__all__ = [
    # Connection utilities
    "db_session",
    "get_db_manager",
    "init_database",
    "check_connection",
    # Models
    "User",
    "Asset",
    "Loan",
    "RevenueStream",
    "CashFlow",
    "HistoricalMeasurement",
    "OperationLog",
    "IndexData",
    "IndexNotification",
    "Scenario",
    "ScenarioResult",
]
