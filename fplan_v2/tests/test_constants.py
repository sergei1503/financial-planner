"""
Test suite for constants in FPlan v2.
"""

import sys
import os
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
)


def test_action_type_enum():
    """Test ActionType enum values."""
    assert ActionType.NEW_LOAN.value == "new_loan"
    assert ActionType.NEW_ASSET.value == "new_asset"
    assert ActionType.REPAY_LOAN.value == "repay_loan"
    assert ActionType.TRANSFORM_ASSET.value == "transform_asset"
    assert ActionType.PARAM_CHANGE.value == "param_change"
    assert ActionType.WITHDRAW_FROM_ASSET.value == "withdraw_from_asset"
    assert ActionType.DEPOSIT_TO_ASSET.value == "deposit_to_asset"
    assert ActionType.MARKET_CRASH.value == "market_crash"
    assert ActionType.ADD_REVENUE_STREAM.value == "add_revenue_stream"


def test_action_type_from_legacy_id():
    """Test converting legacy EScenario IDs to ActionType."""
    assert ActionType.from_legacy_id(EScenario.new_loan) == ActionType.NEW_LOAN
    assert ActionType.from_legacy_id(EScenario.new_asset) == ActionType.NEW_ASSET
    assert ActionType.from_legacy_id(EScenario.repay_loan) == ActionType.REPAY_LOAN
    assert ActionType.from_legacy_id(EScenario.market_crash) == ActionType.MARKET_CRASH


def test_action_type_to_legacy_id():
    """Test converting ActionType to legacy EScenario IDs."""
    assert ActionType.NEW_LOAN.to_legacy_id() == EScenario.new_loan
    assert ActionType.NEW_ASSET.to_legacy_id() == EScenario.new_asset
    assert ActionType.REPAY_LOAN.to_legacy_id() == EScenario.repay_loan
    assert ActionType.MARKET_CRASH.to_legacy_id() == EScenario.market_crash


def test_action_type_round_trip():
    """Test round-trip conversion between ActionType and legacy IDs."""
    for action_type in ActionType:
        legacy_id = action_type.to_legacy_id()
        converted_back = ActionType.from_legacy_id(legacy_id)
        assert converted_back == action_type


def test_escenario_legacy_ids():
    """Test legacy EScenario integer IDs."""
    assert EScenario.new_loan == 0
    assert EScenario.new_asset == 1
    assert EScenario.repay_loan == 2
    assert EScenario.transform_asset == 3
    assert EScenario.param_change == 4
    assert EScenario.withdraw_from_asset == 5
    assert EScenario.deposit_to_asset == 6
    assert EScenario.market_crash == 7
    assert EScenario.add_revenue_stream == 8


def test_period_constants():
    """Test period type constants."""
    assert EPeriod.monthly == "monthly"
    assert EPeriod.quarterly == "quarterly"
    assert EPeriod.yearly == "yearly"


def test_currency_constants():
    """Test currency constants."""
    assert ECurrency.ILS == "ILS"
    assert ECurrency.USD == "USD"


def test_item_type_constants():
    """Test item type constants."""
    assert EItemType.REAL_ESTATE == "Real Estate"
    assert EItemType.STOCK == "Stock"
    assert EItemType.CRYPTO == "Crypto"
    assert EItemType.PENSION == "Pension"
    assert EItemType.CASH == "Cash"
    assert EItemType.LOAN == "Loan"
    assert EItemType.REVENUE_STREAM == "Revenue Stream"
    assert EItemType.WITHDRAWAL == "Withdrawal"


def test_index_type_constants():
    """Test index type constants."""
    assert EIndexType.UNSPECIFIED == "unspecified"
    assert EIndexType.PRIME == "prime"
    assert EIndexType.CPI == "consumer_price_index"


def test_loan_type_constants():
    """Test loan type constants."""
    assert ELoanType.FIXED_LOAN == "fixed_interest"
    assert ELoanType.ATTACHED_TO_INDEX == "attached_to_index"


def test_financial_constants():
    """Test financial calculation constants."""
    assert PENSION_EXTRACTION_FEE == 0.35
    assert PROJECTION_IN_MONTH == 360  # 30 years * 12 months


if __name__ == "__main__":
    # Run tests with pytest if available
    try:
        pytest.main([__file__, "-v"])
    except SystemExit:
        pass
