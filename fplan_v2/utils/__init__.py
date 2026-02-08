"""
Utility modules for FPlan v2.

This package contains reusable utility functions for date handling,
rate conversions, and error handling throughout the application.
"""

from fplan_v2.utils.date_utils import (
    parse_date,
    detect_date_format,
    format_date_for_display,
    format_date_for_storage,
    format_date_for_backend,
    normalize_date_to_month_start,
    validate_date_range,
    convert_legacy_config_dates,
)

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
    MONTHS_PER_YEAR,
    PERCENTAGE_TO_DECIMAL,
)

from fplan_v2.utils.error_utils import (
    FinancialPlannerError,
    error_handler,
    logger,
)

__all__ = [
    # Date utilities
    "parse_date",
    "detect_date_format",
    "format_date_for_display",
    "format_date_for_storage",
    "format_date_for_backend",
    "normalize_date_to_month_start",
    "validate_date_range",
    "convert_legacy_config_dates",
    # Rate utilities
    "annual_pct_to_decimal",
    "decimal_to_annual_pct",
    "annual_decimal_to_monthly_decimal",
    "monthly_decimal_to_annual_decimal",
    "annual_pct_to_monthly_decimal",
    "monthly_decimal_to_annual_pct",
    "convert_duration_years_to_months",
    "convert_duration_months_to_years",
    "validate_rate_range",
    "normalize_rate_input",
    "MONTHS_PER_YEAR",
    "PERCENTAGE_TO_DECIMAL",
    # Error handling
    "FinancialPlannerError",
    "error_handler",
    "logger",
]

__version__ = "2.0.0"