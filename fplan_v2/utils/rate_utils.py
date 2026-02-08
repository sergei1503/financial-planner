"""
Rate conversion utilities for financial calculations.

This module provides standardized functions for converting between different
rate formats used throughout the financial planning system.

Conventions:
- All user inputs are annual rates as percentages (e.g., 5.0 = 5%)
- All calculations use decimal rates (e.g., 0.05 = 5%)
- Monthly rates are derived from annual rates: annual_decimal / 12
- Variable naming: *_rate_annual_pct, *_rate_monthly_decimal, etc.
"""

from typing import Union
from fplan_v2.utils.error_utils import error_handler


@error_handler
def annual_pct_to_decimal(rate_pct: Union[float, str]) -> float:
    """
    Convert annual percentage rate to decimal format.

    Args:
        rate_pct: Annual rate as percentage (e.g., 5.0 for 5%)

    Returns:
        Annual rate as decimal (e.g., 0.05 for 5%)

    Examples:
        >>> annual_pct_to_decimal(5.0)
        0.05
        >>> annual_pct_to_decimal("7.5")
        0.075
    """
    return float(rate_pct) / 100.0


@error_handler
def decimal_to_annual_pct(rate_decimal: float) -> float:
    """
    Convert decimal rate to annual percentage format.

    Args:
        rate_decimal: Annual rate as decimal (e.g., 0.05 for 5%)

    Returns:
        Annual rate as percentage (e.g., 5.0 for 5%)

    Examples:
        >>> decimal_to_annual_pct(0.05)
        5.0
        >>> decimal_to_annual_pct(0.075)
        7.5
    """
    return float(rate_decimal) * 100.0


@error_handler
def annual_decimal_to_monthly_decimal(annual_rate_decimal: float) -> float:
    """
    Convert annual decimal rate to monthly decimal rate.

    Args:
        annual_rate_decimal: Annual rate as decimal (e.g., 0.05 for 5% annually)

    Returns:
        Monthly rate as decimal (e.g., 0.004167 for ~5% annually)

    Examples:
        >>> annual_decimal_to_monthly_decimal(0.06)
        0.005
        >>> round(annual_decimal_to_monthly_decimal(0.05), 6)
        0.004167
    """
    return annual_rate_decimal / 12.0


@error_handler
def monthly_decimal_to_annual_decimal(monthly_rate_decimal: float) -> float:
    """
    Convert monthly decimal rate to annual decimal rate.

    Args:
        monthly_rate_decimal: Monthly rate as decimal

    Returns:
        Annual rate as decimal

    Examples:
        >>> monthly_decimal_to_annual_decimal(0.005)
        0.06
        >>> round(monthly_decimal_to_annual_decimal(0.004167), 6)
        0.050004
    """
    return monthly_rate_decimal * 12.0


@error_handler
def annual_pct_to_monthly_decimal(rate_pct: Union[float, str]) -> float:
    """
    Convert annual percentage rate directly to monthly decimal rate.

    This is a convenience function that combines annual_pct_to_decimal
    and annual_decimal_to_monthly_decimal.

    Args:
        rate_pct: Annual rate as percentage (e.g., 5.0 for 5%)

    Returns:
        Monthly rate as decimal (e.g., 0.004167 for ~5% annually)

    Examples:
        >>> round(annual_pct_to_monthly_decimal(6.0), 6)
        0.005
        >>> round(annual_pct_to_monthly_decimal("5.0"), 6)
        0.004167
    """
    annual_decimal = annual_pct_to_decimal(rate_pct)
    return annual_decimal_to_monthly_decimal(annual_decimal)


@error_handler
def monthly_decimal_to_annual_pct(monthly_rate_decimal: float) -> float:
    """
    Convert monthly decimal rate directly to annual percentage rate.

    This is a convenience function that combines monthly_decimal_to_annual_decimal
    and decimal_to_annual_pct.

    Args:
        monthly_rate_decimal: Monthly rate as decimal

    Returns:
        Annual rate as percentage

    Examples:
        >>> monthly_decimal_to_annual_pct(0.005)
        6.0
        >>> round(monthly_decimal_to_annual_pct(0.004167), 2)
        5.0
    """
    annual_decimal = monthly_decimal_to_annual_decimal(monthly_rate_decimal)
    return decimal_to_annual_pct(annual_decimal)


@error_handler
def convert_duration_years_to_months(years: Union[float, int]) -> int:
    """
    Convert duration from years to months.

    Args:
        years: Duration in years

    Returns:
        Duration in months (rounded to nearest integer)

    Examples:
        >>> convert_duration_years_to_months(2.5)
        30
        >>> convert_duration_years_to_months(10)
        120
    """
    return round(float(years) * 12)


@error_handler
def convert_duration_months_to_years(months: int) -> float:
    """
    Convert duration from months to years.

    Args:
        months: Duration in months

    Returns:
        Duration in years

    Examples:
        >>> convert_duration_months_to_years(24)
        2.0
        >>> convert_duration_months_to_years(30)
        2.5
    """
    return float(months) / 12.0


@error_handler
def validate_rate_range(rate_pct: float, min_pct: float = -50.0, max_pct: float = 100.0) -> bool:
    """
    Validate that a percentage rate is within reasonable bounds.

    Args:
        rate_pct: Rate as percentage to validate
        min_pct: Minimum allowed percentage (default -50%)
        max_pct: Maximum allowed percentage (default 100%)

    Returns:
        True if rate is valid, False otherwise

    Examples:
        >>> validate_rate_range(5.0)
        True
        >>> validate_rate_range(150.0)
        False
        >>> validate_rate_range(-30.0)
        True
        >>> validate_rate_range(-60.0)
        False
    """
    return min_pct <= rate_pct <= max_pct


@error_handler
def normalize_rate_input(rate_input: Union[str, float, int]) -> float:
    """
    Normalize rate input from various formats to a standard float percentage.

    Handles string inputs, removes percentage signs, and validates ranges.

    Args:
        rate_input: Rate input in various formats

    Returns:
        Normalized rate as percentage float

    Raises:
        ValueError: If rate cannot be converted or is out of range

    Examples:
        >>> normalize_rate_input("5.5%")
        5.5
        >>> normalize_rate_input("6")
        6.0
        >>> normalize_rate_input(7.25)
        7.25
    """
    # Handle string inputs
    if isinstance(rate_input, str):
        # Remove percentage sign if present
        cleaned = rate_input.strip().rstrip('%')
        try:
            rate_float = float(cleaned)
        except ValueError:
            raise ValueError(f"Cannot convert rate input '{rate_input}' to number")
    else:
        rate_float = float(rate_input)

    # Validate range
    if not validate_rate_range(rate_float):
        raise ValueError(f"Rate {rate_float}% is outside valid range (-50% to 100%)")

    return rate_float


# Convenience constants for common conversions
MONTHS_PER_YEAR = 12
PERCENTAGE_TO_DECIMAL = 100.0


# Module metadata
__version__ = "2.0.0"
__author__ = "FPlan Development Team"
__description__ = "Rate conversion utilities for FPlan v2"
