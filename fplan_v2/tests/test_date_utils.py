"""
Test suite for date utilities in FPlan v2.
"""

import sys
import os
import pytest
from datetime import datetime, date
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def test_parse_date_iso_format():
    """Test parsing ISO format dates."""
    result = parse_date("2024-01-15")
    expected = pd.Timestamp("2024-01-01")
    assert result == expected


def test_parse_date_day_first_format():
    """Test parsing day-first format dates."""
    result = parse_date("15/01/2024")
    expected = pd.Timestamp("2024-01-01")
    assert result == expected


def test_parse_date_datetime_object():
    """Test parsing datetime objects."""
    dt = datetime(2024, 1, 15)
    result = parse_date(dt)
    expected = pd.Timestamp("2024-01-01")
    assert result == expected


def test_parse_date_timestamp_object():
    """Test parsing pandas Timestamp objects."""
    ts = pd.Timestamp("2024-01-15")
    result = parse_date(ts)
    expected = pd.Timestamp("2024-01-01")
    assert result == expected


def test_parse_date_no_normalization():
    """Test parsing without month-start normalization."""
    result = parse_date("2024-01-15", normalize_to_month_start=False)
    expected = pd.Timestamp("2024-01-15")
    assert result == expected


def test_detect_date_format():
    """Test date format detection."""
    assert detect_date_format("2024-01-15") == "iso"
    assert detect_date_format("31/01/2024") == "day_first"
    assert detect_date_format("01/13/2024") == "us"
    assert detect_date_format("01/02/2024") == "ambiguous"
    assert detect_date_format("invalid") == "unknown"


def test_format_date_for_display():
    """Test formatting dates for display."""
    test_date = "15/01/2024"
    result = format_date_for_display(test_date)
    assert result == "2024-01-15"


def test_format_date_for_storage():
    """Test formatting dates for storage."""
    test_date = "15/01/2024"
    result = format_date_for_storage(test_date)
    assert result == "2024-01-15"


def test_format_date_for_backend():
    """Test formatting dates for backend (deprecated)."""
    test_date = "2024-01-15"
    result = format_date_for_backend(test_date)
    assert result == "15/01/2024"


def test_normalize_date_to_month_start():
    """Test normalizing dates to month start."""
    result = normalize_date_to_month_start("2024-01-15")
    expected = pd.Timestamp("2024-01-01")
    assert result == expected


def test_validate_date_range_valid():
    """Test valid date range validation."""
    assert validate_date_range("2024-01-01", "2024-12-31") is True
    assert validate_date_range("2024-01-01", "2024-01-01", allow_equal=True) is True


def test_validate_date_range_invalid():
    """Test invalid date range validation."""
    with pytest.raises(Exception):  # FinancialPlannerError wraps ValueError
        validate_date_range("2024-12-31", "2024-01-01")

    with pytest.raises(Exception):
        validate_date_range("2024-01-01", "2024-01-01", allow_equal=False)


def test_convert_legacy_config_dates():
    """Test converting legacy configuration dates."""
    legacy_config = {
        "asset_list": {
            "house": {
                "start_date": "15/01/2024",
                "name": "My House"
            }
        }
    }

    converted = convert_legacy_config_dates(legacy_config)
    result_date = converted["asset_list"]["house"]["start_date"]
    assert result_date == "2024-01-15"
    assert converted["asset_list"]["house"]["name"] == "My House"


def test_convert_legacy_config_dates_nested():
    """Test converting nested date structures."""
    legacy_config = {
        "assets": [
            {"start_date": "01/03/2024", "name": "Asset 1"},
            {"start_date": "15/06/2024", "name": "Asset 2"}
        ]
    }

    converted = convert_legacy_config_dates(legacy_config)
    assert converted["assets"][0]["start_date"] == "2024-03-01"
    assert converted["assets"][1]["start_date"] == "2024-06-15"


def test_parse_date_none_input():
    """Test parsing None input raises error."""
    with pytest.raises(Exception):  # FinancialPlannerError wraps ValueError
        parse_date(None)


def test_parse_date_empty_string():
    """Test parsing empty string raises error."""
    with pytest.raises(Exception):  # FinancialPlannerError wraps ValueError
        parse_date("")


def test_parse_date_invalid_format():
    """Test parsing invalid format raises error."""
    with pytest.raises(Exception):  # FinancialPlannerError wraps ValueError
        parse_date("invalid-date-format")


if __name__ == "__main__":
    # Run tests with pytest if available
    try:
        pytest.main([__file__, "-v"])
    except SystemExit:
        pass
