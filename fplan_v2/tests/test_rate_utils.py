"""
Test suite for rate utilities in FPlan v2.
"""

import sys
import os
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fplan_v2.utils.rate_utils import (
    annual_pct_to_decimal,
    decimal_to_annual_pct,
    annual_decimal_to_monthly_decimal,
    monthly_decimal_to_annual_decimal,
    annual_pct_to_monthly_decimal,
    monthly_decimal_to_annual_pct,
    convert_duration_years_to_months,
    convert_duration_months_to_years,
    validate_rate_range,
    normalize_rate_input,
)


def test_annual_pct_to_decimal():
    """Test percentage to decimal conversion."""
    assert annual_pct_to_decimal(5.0) == 0.05
    assert annual_pct_to_decimal("7.5") == 0.075
    assert annual_pct_to_decimal(0) == 0.0
    assert annual_pct_to_decimal(100) == 1.0


def test_decimal_to_annual_pct():
    """Test decimal to percentage conversion."""
    assert decimal_to_annual_pct(0.05) == 5.0
    assert decimal_to_annual_pct(0.075) == 7.5
    assert decimal_to_annual_pct(0.0) == 0.0
    assert decimal_to_annual_pct(1.0) == 100.0


def test_annual_decimal_to_monthly_decimal():
    """Test annual to monthly decimal conversion."""
    assert round(annual_decimal_to_monthly_decimal(0.06), 6) == 0.005
    assert round(annual_decimal_to_monthly_decimal(0.12), 6) == 0.01


def test_monthly_decimal_to_annual_decimal():
    """Test monthly to annual decimal conversion."""
    assert round(monthly_decimal_to_annual_decimal(0.005), 6) == 0.06
    assert round(monthly_decimal_to_annual_decimal(0.01), 6) == 0.12


def test_annual_pct_to_monthly_decimal():
    """Test convenience function for pct to monthly decimal."""
    assert round(annual_pct_to_monthly_decimal(6.0), 6) == 0.005
    assert round(annual_pct_to_monthly_decimal("5.0"), 6) == round(5.0 / 100.0 / 12.0, 6)


def test_monthly_decimal_to_annual_pct():
    """Test convenience function for monthly decimal to pct."""
    assert monthly_decimal_to_annual_pct(0.005) == 6.0
    assert round(monthly_decimal_to_annual_pct(0.004167), 2) == 5.0


def test_convert_duration_years_to_months():
    """Test years to months conversion."""
    assert convert_duration_years_to_months(2.5) == 30
    assert convert_duration_years_to_months(10) == 120
    assert convert_duration_years_to_months(1) == 12
    assert convert_duration_years_to_months(0) == 0


def test_convert_duration_months_to_years():
    """Test months to years conversion."""
    assert convert_duration_months_to_years(24) == 2.0
    assert convert_duration_months_to_years(30) == 2.5
    assert convert_duration_months_to_years(12) == 1.0
    assert convert_duration_months_to_years(0) == 0.0


def test_validate_rate_range():
    """Test rate validation."""
    assert validate_rate_range(5.0) is True
    assert validate_rate_range(0.0) is True
    assert validate_rate_range(-30.0) is True
    assert validate_rate_range(150.0) is False
    assert validate_rate_range(-60.0) is False


def test_validate_rate_range_custom_bounds():
    """Test rate validation with custom bounds."""
    assert validate_rate_range(5.0, min_pct=0.0, max_pct=10.0) is True
    assert validate_rate_range(15.0, min_pct=0.0, max_pct=10.0) is False
    assert validate_rate_range(-5.0, min_pct=0.0, max_pct=10.0) is False


def test_normalize_rate_input():
    """Test rate normalization."""
    assert normalize_rate_input("5.5%") == 5.5
    assert normalize_rate_input("6") == 6.0
    assert normalize_rate_input(7.25) == 7.25
    assert normalize_rate_input("  8.0  ") == 8.0


def test_normalize_rate_input_invalid():
    """Test rate normalization with invalid inputs."""
    with pytest.raises(Exception):  # FinancialPlannerError wraps ValueError
        normalize_rate_input("invalid")

    with pytest.raises(Exception):  # Out of range
        normalize_rate_input(150.0)


if __name__ == "__main__":
    # Run tests with pytest if available, otherwise run simple tests
    try:
        pytest.main([__file__, "-v"])
    except SystemExit:
        pass
