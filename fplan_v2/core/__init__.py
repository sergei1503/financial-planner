"""
Core modules for FPlan v2.

This package contains the core domain models, constants, and financial
calculation engines.
"""

from fplan_v2.core.constants import (
    ActionType,
    EScenario,
    EPeriod,
    ECurrency,
    EItemType,
    EIndexType,
    ELoanType,
    PENSION_EXTRACTION_FEE,
    PROJECTION_IN_MONTH,
    CASH_FLOW,
    VALUE,
)

__all__ = [
    "ActionType",
    "EScenario",
    "EPeriod",
    "ECurrency",
    "EItemType",
    "EIndexType",
    "ELoanType",
    "PENSION_EXTRACTION_FEE",
    "PROJECTION_IN_MONTH",
    "CASH_FLOW",
    "VALUE",
]

__version__ = "2.0.0"