"""
Central date utilities for FPlan v2 financial planning application.

This module provides unified date handling to resolve the date format inconsistencies
throughout the codebase. It standardizes on ISO format (YYYY-MM-DD) while maintaining
backward compatibility with existing DD/MM/YYYY data.

Key Features:
- Universal date parsing with format detection
- Month-start normalization (required for financial calculations)
- Backward compatibility with existing data formats
- Comprehensive error handling and validation
"""

from datetime import datetime, date
import pandas as pd
from typing import Union, Optional
import re
from fplan_v2.utils.error_utils import error_handler


@error_handler
def parse_date(
    date_input: Union[str, datetime, date, pd.Timestamp],
    normalize_to_month_start: bool = True,
    default_format: str = "iso",
) -> pd.Timestamp:
    """
    Universal date parser for FPlan application.

    Accepts multiple date formats and normalizes to pandas Timestamp.
    Automatically detects common date formats and handles conversion.

    Args:
        date_input: Date in various formats (str, datetime, date, pd.Timestamp)
        normalize_to_month_start: If True, sets day to 1 (required for financial calcs)
        default_format: Default format assumption for ambiguous strings ("iso" or "day_first")

    Returns:
        pd.Timestamp: Normalized timestamp object

    Raises:
        ValueError: If date format cannot be determined or parsed
        TypeError: If input type is not supported

    Examples:
        >>> parse_date("2024-01-15")  # ISO format
        Timestamp('2024-01-01 00:00:00')

        >>> parse_date("15/01/2024")  # Day-first format
        Timestamp('2024-01-01 00:00:00')

        >>> parse_date(datetime.now())  # datetime object
        Timestamp('2024-01-01 00:00:00')
    """
    if date_input is None:
        raise ValueError("Date input cannot be None")

    # Handle pandas Timestamp
    if isinstance(date_input, pd.Timestamp):
        result = date_input

    # Handle datetime objects
    elif isinstance(date_input, (datetime, date)):
        result = pd.Timestamp(date_input)

    # Handle string inputs with format detection
    elif isinstance(date_input, str):
        result = _parse_date_string(date_input.strip(), default_format)

    else:
        raise TypeError(f"Unsupported date input type: {type(date_input)}")

    # Normalize to month start if requested (critical for financial calculations)
    if normalize_to_month_start:
        result = result.replace(day=1)

    return result


def _parse_date_string(date_str: str, default_format: str = "iso") -> pd.Timestamp:
    """
    Parse date string with automatic format detection.

    Supports:
    - ISO format: YYYY-MM-DD, YYYY/MM/DD
    - Day-first format: DD/MM/YYYY, DD-MM-YYYY
    - US format: MM/DD/YYYY, MM-DD-YYYY
    - Various separators: -, /, space

    Args:
        date_str: String representation of date
        default_format: Fallback format for ambiguous cases

    Returns:
        pd.Timestamp: Parsed date

    Raises:
        ValueError: If no format can successfully parse the string
    """
    if not date_str:
        raise ValueError("Date string cannot be empty")

    # Define format patterns in order of preference
    format_patterns = [
        # ISO formats (preferred)
        ("%Y-%m-%d", "iso"),
        ("%Y/%m/%d", "iso"),
        ("%Y %m %d", "iso"),
        # Day-first formats (existing backend preference)
        ("%d/%m/%Y", "day_first"),
        ("%d-%m-%Y", "day_first"),
        ("%d %m %Y", "day_first"),
        # US formats (less common but supported)
        ("%m/%d/%Y", "us"),
        ("%m-%d/%Y", "us"),
        ("%m %d %Y", "us"),
        # Short year formats
        ("%Y-%m-%d", "iso_short"),
        ("%d/%m/%y", "day_first_short"),
        ("%m/%d/%y", "us_short"),
    ]

    # Try each format pattern
    for format_str, format_type in format_patterns:
        try:
            parsed_date = datetime.strptime(date_str, format_str)
            return pd.Timestamp(parsed_date)
        except ValueError:
            continue

    # Try pandas intelligent parsing as fallback
    try:
        if default_format == "day_first":
            return pd.to_datetime(date_str, dayfirst=True)
        else:
            return pd.to_datetime(date_str)
    except (ValueError, TypeError):
        pass

    # If all else fails, raise descriptive error
    raise ValueError(
        f"Unable to parse date string '{date_str}'. " f"Supported formats include: YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY"
    )


@error_handler
def detect_date_format(date_str: str) -> str:
    """
    Detect the likely format of a date string.

    Args:
        date_str: Date string to analyze

    Returns:
        str: Detected format ("iso", "day_first", "us", or "unknown")
    """
    if not isinstance(date_str, str):
        return "unknown"

    # Remove whitespace
    date_str = date_str.strip()

    # Common patterns for format detection
    iso_pattern = r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$"
    day_first_pattern = r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}$"

    if re.match(iso_pattern, date_str):
        return "iso"
    elif re.match(day_first_pattern, date_str):
        # Could be day_first or us format - need more context
        parts = re.split(r"[-/]", date_str)
        if len(parts) == 3:
            first, second, third = parts
            if int(first) > 12:  # First part > 12, must be day
                return "day_first"
            elif int(second) > 12:  # Second part > 12, first must be month
                return "us"
            else:
                return "ambiguous"  # Could be either format

    return "unknown"


@error_handler
def format_date_for_display(date_input: Union[str, datetime, date, pd.Timestamp]) -> str:
    """
    Format date for user interface display.

    Args:
        date_input: Date in any supported format

    Returns:
        str: Formatted date string for display (YYYY-MM-DD)
    """
    parsed_date = parse_date(date_input, normalize_to_month_start=False)
    return parsed_date.strftime("%Y-%m-%d")


@error_handler
def format_date_for_storage(date_input: Union[str, datetime, date, pd.Timestamp]) -> str:
    """
    Format date for JSON storage (ISO format).

    Args:
        date_input: Date in any supported format

    Returns:
        str: ISO formatted date string (YYYY-MM-DD)
    """
    parsed_date = parse_date(date_input, normalize_to_month_start=False)
    return parsed_date.strftime("%Y-%m-%d")


@error_handler
def format_date_for_backend(date_input: Union[str, datetime, date, pd.Timestamp]) -> str:
    """
    Format date for backend processing (day-first format for backward compatibility).

    DEPRECATED: This function is provided for backward compatibility only.
    New code should use parse_date() and work with pandas Timestamps directly.

    Args:
        date_input: Date in any supported format

    Returns:
        str: Day-first formatted date string (DD/MM/YYYY)
    """
    parsed_date = parse_date(date_input, normalize_to_month_start=False)
    return parsed_date.strftime("%d/%m/%Y")


@error_handler
def normalize_date_to_month_start(date_input: Union[str, datetime, date, pd.Timestamp]) -> pd.Timestamp:
    """
    Normalize any date to the first day of its month.

    This is critical for financial calculations in FPlan as all projections
    work on monthly boundaries.

    Args:
        date_input: Date in any supported format

    Returns:
        pd.Timestamp: Date normalized to first day of month
    """
    return parse_date(date_input, normalize_to_month_start=True)


@error_handler
def validate_date_range(start_date, end_date, allow_equal=True) -> bool:
    """
    Validate that start_date is before or equal to end_date.

    Args:
        start_date: Starting date in any supported format
        end_date: Ending date in any supported format
        allow_equal: Whether start and end dates can be equal

    Returns:
        bool: True if date range is valid

    Raises:
        ValueError: If date range is invalid
    """
    start = parse_date(start_date, normalize_to_month_start=False)
    end = parse_date(end_date, normalize_to_month_start=False)

    if allow_equal:
        is_valid = start <= end
    else:
        is_valid = start < end

    if not is_valid:
        raise ValueError(f"Invalid date range: start ({start}) must be before end ({end})")

    return True


@error_handler
def convert_legacy_config_dates(config_dict: dict) -> dict:
    """
    Convert dates in legacy configuration dictionaries to ISO format.

    This function provides backward compatibility by detecting and converting
    dates from the old DD/MM/YYYY format to the new ISO format.

    Args:
        config_dict: Configuration dictionary that may contain legacy dates

    Returns:
        dict: Configuration with dates converted to ISO format
    """

    def _convert_date_fields(obj):
        if isinstance(obj, dict):
            converted = {}
            for key, value in obj.items():
                if _is_date_field(key) and isinstance(value, str):
                    try:
                        # Try to parse and convert to ISO format (without month normalization)
                        parsed_date = parse_date(value, normalize_to_month_start=False)
                        converted[key] = format_date_for_storage(parsed_date)
                    except (ValueError, TypeError, Exception):
                        # If parsing fails, keep original value
                        converted[key] = value
                elif isinstance(value, (dict, list)):
                    converted[key] = _convert_date_fields(value)
                else:
                    converted[key] = value
            return converted
        elif isinstance(obj, list):
            return [_convert_date_fields(item) for item in obj]
        else:
            return obj

    return _convert_date_fields(config_dict)


def _is_date_field(field_name: str) -> bool:
    """Check if a field name likely contains a date."""
    date_field_patterns = [
        "date",
        "start_date",
        "end_date",
        "from",
        "to",
        "rent_start_date",
        "start_dividend_withdraw_date",
        "sell_date",
        "extraction_date",
    ]
    return any(pattern in field_name.lower() for pattern in date_field_patterns)


# Backward compatibility aliases
def convert_date_format(date_str: str) -> str:
    """
    DEPRECATED: Legacy function for backward compatibility.
    Use parse_date() instead.
    """
    if isinstance(date_str, str) and "-" in date_str:
        # Assume YYYY-MM-DD, convert to DD/MM/YYYY
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            pass
    return date_str


# Module metadata
__version__ = "2.0.0"
__author__ = "FPlan Development Team"
__description__ = "Central date utilities for FPlan v2 financial planning application"
