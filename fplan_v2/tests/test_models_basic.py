"""
Basic tests for FPlan v2 models.

Tests instantiation and serialization of asset, loan, and revenue stream classes.
Full golden master validation will be performed in Task #4.
"""

import pytest
import pandas as pd
from datetime import datetime

from fplan_v2.core.models import (
    Asset,
    CashAsset,
    RealEstateAsset,
    StockAsset,
    PensionAsset,
    LoanFixed,
    LoanVariable,
    SalaryRevenueStream,
    RentRevenueStream,
    DividendRevenueStream,
    PensionRevenueStream,
)


class TestAssetInstantiation:
    """Test basic asset creation and serialization."""

    def test_cash_asset_creation(self):
        """Test CashAsset instantiation."""
        asset = CashAsset(
            id="test_cash",
            start_date="2024-01-01",
            original_value=10000.0,
        )

        assert asset.id == "cash"  # CashAsset overrides id to "cash"
        assert asset.value == 10000.0
        assert asset.appreciation_rate_annual_pct == 0
        assert asset.start_date == pd.Timestamp("2024-01-01")

    def test_cash_asset_serialization(self):
        """Test CashAsset to_dict and from_dict."""
        asset = CashAsset(
            id="test_cash",
            start_date="2024-01-01",
            original_value=10000.0,
        )

        # Serialize
        asset_dict = asset.to_dict()
        assert asset_dict["id"] == "cash"
        assert asset_dict["original_value"] == 10000.0

        # Deserialize
        restored = CashAsset.from_dict(asset_dict)
        assert restored.id == "cash"
        assert restored.value == 10000.0
        assert restored.start_date == pd.Timestamp("2024-01-01")

    def test_real_estate_asset_creation(self):
        """Test RealEstateAsset instantiation."""
        asset = RealEstateAsset(
            id="test_property",
            start_date="2024-01-01",
            original_value=500000.0,
            appreciation_rate_annual_pct=3.0,
            yearly_fee_pct=0.5,
            revenue_stream=None,
        )

        assert asset.id == "test_property"
        assert asset.value == 500000.0
        assert asset.appreciation_rate_annual_pct == 3.0
        assert asset.yearly_fee_pct == 0.5

    def test_stock_asset_creation(self):
        """Test StockAsset instantiation."""
        asset = StockAsset(
            id="test_stock",
            start_date="2024-01-01",
            original_value=100000.0,
            appreciation_rate_annual_pct=7.0,
            yearly_fee_pct=0.2,
            revenue_stream=None,
            deposits=[],
            withdrawals=[],
        )

        assert asset.id == "test_stock"
        assert asset.value == 100000.0
        assert asset.appreciation_rate_annual_pct == 7.0

    def test_pension_asset_creation(self):
        """Test PensionAsset instantiation."""
        pension_stream = PensionRevenueStream(
            id="pension_stream",
            start_date="2060-01-01",
            monthly_payout=5000.0,
        )

        asset = PensionAsset(
            id="test_pension",
            start_date="2024-01-01",
            original_value=50000.0,
            appreciation_rate_annual_pct=5.0,
            yearly_fee_pct=1.0,
            revenue_stream=pension_stream,
            deposits=[],
            end_date="2070-01-01",
        )

        assert asset.id == "test_pension"
        assert asset.value == 50000.0
        assert asset.end_date == pd.Timestamp("2070-01-01")


class TestLoanInstantiation:
    """Test basic loan creation and serialization."""

    def test_fixed_loan_creation(self):
        """Test LoanFixed instantiation."""
        loan = LoanFixed(
            id="test_loan",
            value=200000.0,
            interest_rate_annual_pct=4.5,
            duration_months=360,
            start_date="2024-01-01",
        )

        assert loan.id == "test_loan"
        assert loan.value == -200000.0  # Stored as negative
        assert loan.interest_rate_annual_pct == 4.5
        assert loan.duration_months == 360

    def test_fixed_loan_serialization(self):
        """Test LoanFixed to_dict and from_dict."""
        loan = LoanFixed(
            id="test_loan",
            value=200000.0,
            interest_rate_annual_pct=4.5,
            duration_months=360,
            start_date="2024-01-01",
        )

        # Serialize
        loan_dict = loan.to_dict()
        assert loan_dict["id"] == "test_loan"
        assert loan_dict["value"] == 200000.0  # Positive in dict
        assert loan_dict["type"] == "fixed"

        # Deserialize
        restored = LoanFixed.from_dict(loan_dict)
        assert restored.id == "test_loan"
        assert restored.value == -200000.0  # Negative internally
        assert restored.interest_rate_annual_pct == 4.5

    def test_variable_loan_creation(self):
        """Test LoanVariable instantiation."""
        loan = LoanVariable(
            id="test_var_loan",
            value=150000.0,
            base_rate_annual_pct=3.0,
            margin_pct=1.5,
            duration_months=240,
            start_date="2024-01-01",
            inflation_rate_annual_pct=2.0,
        )

        assert loan.id == "test_var_loan"
        assert loan.base_rate_annual_pct == 3.0
        assert loan.margin_pct == 1.5
        assert loan.inflation_rate_annual_pct == 2.0


class TestRevenueStreamInstantiation:
    """Test basic revenue stream creation and serialization."""

    def test_salary_stream_creation(self):
        """Test SalaryRevenueStream instantiation."""
        stream = SalaryRevenueStream(
            id="test_salary",
            start_date="2024-01-01",
            end_date="2050-01-01",
            amount=100000.0,
            growth_rate=3.0,
        )

        assert stream.id == "test_salary"
        assert stream.amount == 100000.0
        assert stream.growth_rate == 3.0

    def test_salary_stream_serialization(self):
        """Test SalaryRevenueStream to_dict and from_dict."""
        stream = SalaryRevenueStream(
            id="test_salary",
            start_date="2024-01-01",
            end_date="2050-01-01",
            amount=100000.0,
            growth_rate=3.0,
        )

        # Serialize
        stream_dict = stream.to_dict()
        assert stream_dict["id"] == "test_salary"
        assert stream_dict["type"] == "salary"

        # Deserialize
        restored = SalaryRevenueStream.from_dict(stream_dict)
        assert restored.id == "test_salary"
        assert restored.amount == 100000.0

    def test_rent_stream_creation(self):
        """Test RentRevenueStream instantiation."""
        stream = RentRevenueStream(
            id="test_rent",
            start_date="2024-01-01",
            amount=2000.0,
            period="monthly",
            tax=10.0,
            growth_rate=2.0,
        )

        assert stream.id == "test_rent"
        assert stream.amount == 2000.0
        assert stream.period == "monthly"
        assert stream.tax == 10.0

    def test_dividend_stream_creation(self):
        """Test DividendRevenueStream instantiation."""
        stream = DividendRevenueStream(
            dividend_yield=3.5,
            dividend_payout_frequency="quarterly",
            tax=25.0,
            start_dividend_withdraw_date="2040-01-01",
        )

        assert stream.dividend_yield == 3.5
        assert stream.dividend_payout_frequency == "quarterly"
        assert stream.tax == 25.0

    def test_pension_stream_creation(self):
        """Test PensionRevenueStream instantiation."""
        stream = PensionRevenueStream(
            id="test_pension_stream",
            start_date="2060-01-01",
            monthly_payout=5000.0,
        )

        assert stream.id == "test_pension_stream"
        assert stream.monthly_payout == 5000.0


class TestProjectionBasics:
    """Test basic projection functionality (not full golden master)."""

    def test_cash_asset_projection(self):
        """Test that CashAsset can generate a projection."""
        asset = CashAsset(
            id="test_cash",
            start_date="2024-01-01",
            original_value=10000.0,
        )

        projection = asset.get_projection(months_to_project=12)

        assert isinstance(projection, pd.DataFrame)
        assert len(projection) == 12
        assert "date" in projection.columns
        assert "value" in projection.columns
        assert "cash_flow" in projection.columns

    def test_fixed_loan_projection(self):
        """Test that LoanFixed can generate a projection."""
        loan = LoanFixed(
            id="test_loan",
            value=100000.0,
            interest_rate_annual_pct=4.0,
            duration_months=12,
            start_date="2024-01-01",
        )

        projection = loan.get_projection()

        assert isinstance(projection, pd.DataFrame)
        assert len(projection) == 12
        assert "date" in projection.columns
        assert "value" in projection.columns
        assert "interest_payment" in projection.columns
        assert "principal_payment" in projection.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
