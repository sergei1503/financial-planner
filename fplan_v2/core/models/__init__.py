"""
FPlan v2 Core Models Package.

This package contains the core financial modeling classes for assets, loans,
and revenue streams. All classes have been ported from v1 with preserved
calculation logic and added database serialization support.

Modules:
    asset: Asset classes (Asset, CashAsset, RealEstateAsset, StockAsset, PensionAsset)
    loan: Loan classes (LoanFixed, LoanVariable, LoanPrimePegged, LoanCPIPegged)
    revenue_stream: Revenue stream classes (SalaryRevenueStream, RentRevenueStream, etc.)
"""

from fplan_v2.core.models.asset import (
    Asset,
    CashAsset,
    RealEstateAsset,
    StockAsset,
    PensionAsset,
)

from fplan_v2.core.models.loan import (
    LoanFixed,
    LoanVariable,
    LoanPrimePegged,
    LoanCPIPegged,
)

from fplan_v2.core.models.revenue_stream import (
    RevenueStream,
    SalaryRevenueStream,
    RentRevenueStream,
    DividendRevenueStream,
    PensionRevenueStream,
)

__all__ = [
    # Asset classes
    "Asset",
    "CashAsset",
    "RealEstateAsset",
    "StockAsset",
    "PensionAsset",
    # Loan classes
    "LoanFixed",
    "LoanVariable",
    "LoanPrimePegged",
    "LoanCPIPegged",
    # Revenue stream classes
    "RevenueStream",
    "SalaryRevenueStream",
    "RentRevenueStream",
    "DividendRevenueStream",
    "PensionRevenueStream",
]

__version__ = "2.0.0"
__author__ = "FPlan Development Team"
