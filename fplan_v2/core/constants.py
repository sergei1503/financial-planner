"""
Core constants and enumerations for FPlan v2.

This module defines all constant values, enumerations, and configuration
parameters used throughout the financial planning system.
"""

from enum import Enum

# Projection constants
CASH_FLOW = "cash_flow"
VALUE = "value"
PROJECTION_IN_MONTH = 30 * 12  # 30 years


class EScenario:
    """Legacy scenario type IDs (maintained for backward compatibility)"""
    new_loan = 0
    new_asset = 1
    repay_loan = 2
    transform_asset = 3
    param_change = 4
    withdraw_from_asset = 5
    deposit_to_asset = 6
    market_crash = 7
    add_revenue_stream = 8


class ActionType(Enum):
    """
    Scenario action types for v2.

    These map to the EScenario constants but provide better type safety
    and NLP integration support.
    """
    NEW_LOAN = "new_loan"
    NEW_ASSET = "new_asset"
    REPAY_LOAN = "repay_loan"
    TRANSFORM_ASSET = "transform_asset"
    PARAM_CHANGE = "param_change"
    WITHDRAW_FROM_ASSET = "withdraw_from_asset"
    DEPOSIT_TO_ASSET = "deposit_to_asset"
    MARKET_CRASH = "market_crash"
    ADD_REVENUE_STREAM = "add_revenue_stream"

    @classmethod
    def from_legacy_id(cls, legacy_id: int) -> 'ActionType':
        """Convert legacy EScenario ID to ActionType enum."""
        mapping = {
            EScenario.new_loan: cls.NEW_LOAN,
            EScenario.new_asset: cls.NEW_ASSET,
            EScenario.repay_loan: cls.REPAY_LOAN,
            EScenario.transform_asset: cls.TRANSFORM_ASSET,
            EScenario.param_change: cls.PARAM_CHANGE,
            EScenario.withdraw_from_asset: cls.WITHDRAW_FROM_ASSET,
            EScenario.deposit_to_asset: cls.DEPOSIT_TO_ASSET,
            EScenario.market_crash: cls.MARKET_CRASH,
            EScenario.add_revenue_stream: cls.ADD_REVENUE_STREAM,
        }
        return mapping.get(legacy_id)

    def to_legacy_id(self) -> int:
        """Convert ActionType enum to legacy EScenario ID."""
        mapping = {
            self.NEW_LOAN: EScenario.new_loan,
            self.NEW_ASSET: EScenario.new_asset,
            self.REPAY_LOAN: EScenario.repay_loan,
            self.TRANSFORM_ASSET: EScenario.transform_asset,
            self.PARAM_CHANGE: EScenario.param_change,
            self.WITHDRAW_FROM_ASSET: EScenario.withdraw_from_asset,
            self.DEPOSIT_TO_ASSET: EScenario.deposit_to_asset,
            self.MARKET_CRASH: EScenario.market_crash,
            self.ADD_REVENUE_STREAM: EScenario.add_revenue_stream,
        }
        return mapping.get(self)


class EPeriod:
    """Payment/withdrawal period types"""
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"


class ECurrency:
    """Supported currencies"""
    ILS = "ILS"
    USD = "USD"


class EItemType:
    """Financial item types"""
    REAL_ESTATE = "Real Estate"
    STOCK = "Stock"
    CRYPTO = "Crypto"  # Fixed typo from v1
    PENSION = "Pension"
    CASH = "Cash"
    LOAN = "Loan"
    REVENUE_STREAM = "Revenue Stream"
    WITHDRAWAL = "Withdrawal"


class EIndexType:
    """Index types for variable-rate loans"""
    UNSPECIFIED = "unspecified"
    PRIME = "prime"
    CPI = "consumer_price_index"


class ELoanType:
    """Loan interest rate types"""
    FIXED_LOAN = "fixed_interest"
    ATTACHED_TO_INDEX = "attached_to_index"


# Financial constants
PENSION_EXTRACTION_FEE = 0.35


# Module metadata
__version__ = "2.0.0"
__author__ = "FPlan Development Team"
__description__ = "Core constants and enumerations for FPlan v2"
