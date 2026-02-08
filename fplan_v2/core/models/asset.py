"""
Asset models for FPlan v2.

This module contains the core asset classes for financial planning, ported from v1
with database serialization support. All financial calculation logic is preserved
exactly as-is to maintain golden master compatibility.

Classes:
    Asset: Base class for all financial assets
    CashAsset: Cash/bank account assets
    RealEstateAsset: Real estate properties with revenue streams
    StockAsset: Stock/investment portfolios with dividends
    PensionAsset: Pension/retirement accounts
"""

from typing import List, Dict, Any, Optional, Union
import numpy as np
from numpy_financial import fv
from dateutil.relativedelta import relativedelta
import pandas as pd
from datetime import datetime

# V2 imports
from fplan_v2.core.constants import EItemType, EPeriod, CASH_FLOW, VALUE
from fplan_v2.utils.date_utils import parse_date, normalize_date_to_month_start
from fplan_v2.utils.rate_utils import annual_pct_to_monthly_decimal, normalize_rate_input
from fplan_v2.utils.error_utils import error_handler


class Asset:
    """
    Base class for all financial assets.

    Handles core asset functionality including appreciation, fees, deposits/withdrawals,
    and projection calculations. All dates are normalized to month-start for consistent
    monthly projections.

    Attributes:
        id: Unique identifier for the asset
        type: Asset type (set by subclasses)
        original_value: Initial asset value
        value: Current asset value
        appreciation_rate_annual_pct: Annual appreciation rate as percentage
        yearly_fee_pct: Annual fee as percentage
        revenue_stream: Optional revenue stream attached to asset
        start_date: Asset start date (normalized to month start)
        deposits: List of deposit schedules
        withdrawals: List of withdrawal schedules
        extraction_date: Date when asset is sold/extracted
        history: Historical value entries for tracking actual performance
        loan_ids: IDs of loans attached to this asset
        sell_tax: Capital gains tax on sale
    """

    @error_handler
    def __init__(
        self,
        id: str,
        start_date: Union[str, datetime, pd.Timestamp],
        original_value: float,
        appreciation_rate_annual_pct: float,
        yearly_fee_pct: float,
        revenue_stream: Optional[Any],
        deposits: List[Dict],
        withdrawals: List[Dict],
        pmt: float = 0,
        history: Optional[List] = None,
    ):
        self.id = id
        self.type = None
        self.original_value = float(original_value)
        self.value = float(original_value)

        # Standardize rate storage: normalize input and store as annual percentage
        self.appreciation_rate_annual_pct = normalize_rate_input(appreciation_rate_annual_pct)
        self.yearly_fee_pct = normalize_rate_input(yearly_fee_pct) if yearly_fee_pct else 0.0

        # For backward compatibility, keep old attribute names pointing to new ones
        self.appreciation_rate = self.appreciation_rate_annual_pct
        self.yearly_fee = self.yearly_fee_pct

        self.revenue_stream = revenue_stream

        # Use centralized date parsing with month-start normalization
        self.start_date = parse_date(start_date, normalize_to_month_start=True)

        self.deposits = deposits
        self.withdrawals = withdrawals
        self.df = pd.DataFrame
        self.extraction_date = pd.Timestamp("2100-01-01").normalize()
        self.events = []
        self.pmt = pmt
        self.yearly_fee = self.yearly_fee_pct  # Use the new standardized field
        # Historical tracking: list of {"date": "YYYY-MM-DD", "value": float, "appreciation_rate": float, "notes": str}
        self.history = history or []
        self.loan_ids = []
        self.sell_tax = 0

        # Only initialize history with start date if no historical data provided
        if not self.history:
            self.history = [(self.start_date, float(original_value))]

    @error_handler
    def attach_loans(self, loan_ids: Union[List[str], str]):
        """Attach one or more loan IDs to this asset."""
        if isinstance(loan_ids, list):
            self.loan_ids.extend(loan_ids)
        else:
            self.loan_ids.append(loan_ids)

    @error_handler
    def get_type(self) -> str:
        """Get the asset type."""
        return self.type

    @error_handler
    def add_deposit(self, deposit: Dict):
        """Add a deposit schedule to this asset."""
        self.deposits.append(deposit)

    @error_handler
    def add_withdrawal(self, withdrawal: Dict):
        """Add a withdrawal schedule to this asset."""
        self.withdrawals.append(withdrawal)

    @error_handler
    def add_revenue_stream(self, revenue_stream):
        """Attach a revenue stream to this asset."""
        self.revenue_stream = revenue_stream

    @error_handler
    def get_projection(self, months_to_project: int = 30 * 12) -> pd.DataFrame:
        """
        Calculate future value projection.

        Must be implemented by subclasses.

        Args:
            months_to_project: Number of months to project forward

        Returns:
            DataFrame with columns: id, date, value, cash_flow
        """
        raise NotImplementedError("Subclasses must implement get_projection()")

    @error_handler
    def get_cash_flow(self) -> pd.DataFrame:
        """Get positive cash flows from this asset."""
        df = self.get_projection()[["date", CASH_FLOW]]
        df["id"] = self.id
        df = df[df[CASH_FLOW] > 0]
        return df

    @error_handler
    def value_on_date(self, date: Union[str, datetime, pd.Timestamp]) -> float:
        """
        Get asset value on a specific date.

        Args:
            date: Target date

        Returns:
            Asset value on that date
        """
        projection = self.get_projection()
        projection["date"] = pd.to_datetime(projection["date"])  # ensure dtype
        target_date = pd.to_datetime(date)
        subset = projection[projection["date"] <= target_date]
        if subset.empty:
            return self.original_value
        vals = subset[VALUE].values
        # If last value is zero (legacy extraction zeroing) keep prior value when available
        if len(vals) >= 2 and vals[-1] == 0:
            return vals[-2]
        return vals[-1]

    @error_handler
    def set_extraction_date(self, date: Union[str, datetime, pd.Timestamp]):
        """Set the asset extraction/sale date using centralized date parsing."""
        self.extraction_date = parse_date(date, normalize_to_month_start=True)

    @error_handler
    def set_attribute(self, k: str, v: Any):
        """Set an attribute dynamically."""
        setattr(self, k, v)

    @error_handler
    def add_market_crash_info(self, info: Dict):
        """Add a market crash event to this asset."""
        self.events.append(info)

    @error_handler
    def set_history(self, history: List):
        """Set the historical value entries for this asset."""
        # Ensure history includes the initial value
        self.history = sorted(
            set([(pd.to_datetime(self.start_date), float(self.value))] + history),
            key=lambda x: x[0],
        )

    @error_handler
    def get_value_at_date(self, date: Union[str, datetime, pd.Timestamp]) -> float:
        """
        Get projected value at a specific date based on historical data.

        Args:
            date: Target date

        Returns:
            Projected value at that date
        """
        date = pd.to_datetime(date)
        # Find the closest historical value before the given date
        past_values = [(d, v) for d, v in self.history if d <= date]
        if not past_values:
            return self.value

        last_known_date, last_known_value = max(past_values, key=lambda x: x[0])
        if date == last_known_date:
            return last_known_value

        # Calculate appreciation from last known value
        years_diff = (date - last_known_date).days / 365.25
        appreciation_rate_decimal = self.appreciation_rate_annual_pct / 100.0
        return last_known_value * (1 + appreciation_rate_decimal) ** years_diff

    @error_handler
    def add_historical_entry(self, date: Union[str, datetime, pd.Timestamp], value: float,
                           appreciation_rate: Optional[float] = None, notes: str = ""):
        """Add a historical entry for this asset."""
        date = normalize_date_to_month_start(date)

        # Update current appreciation rate if provided
        if appreciation_rate is not None:
            self.appreciation_rate_annual_pct = normalize_rate_input(appreciation_rate)
            self.appreciation_rate = self.appreciation_rate_annual_pct  # Backward compatibility

        # Create historical entry
        entry = {
            "date": date.strftime("%Y-%m-%d"),
            "value": float(value),
            "appreciation_rate": float(appreciation_rate or self.appreciation_rate_annual_pct),
            "notes": notes,
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Add to history, avoiding duplicates by date
        # Handle both tuple and dict format in history
        filtered_history = []
        for h in self.history:
            if isinstance(h, dict):
                if h.get("date") != entry["date"]:
                    filtered_history.append(h)
            elif isinstance(h, (list, tuple)) and len(h) >= 2:
                # Skip tuple entries - they'll be replaced by the new dict entry
                h_date = pd.to_datetime(h[0]).strftime("%Y-%m-%d")
                if h_date != entry["date"]:
                    filtered_history.append(h)

        self.history = filtered_history
        self.history.append(entry)
        self.history.sort(key=lambda x: x["date"] if isinstance(x, dict) else pd.to_datetime(x[0]).strftime("%Y-%m-%d"))

        # Update current value if this is the most recent entry
        history_dates = []
        for h in self.history:
            if isinstance(h, dict):
                history_dates.append(pd.to_datetime(h["date"]))
            elif isinstance(h, (list, tuple)) and len(h) >= 2:
                history_dates.append(pd.to_datetime(h[0]))

        latest_date = max(history_dates + [self.start_date]) if history_dates else self.start_date
        if date >= latest_date:
            self.value = value

    @error_handler
    def get_historical_performance(self) -> pd.DataFrame:
        """Get a DataFrame with historical performance vs predictions."""
        if not self.history:
            return pd.DataFrame()

        data = []
        for entry in self.history:
            # Handle both dict format and tuple format for history
            if isinstance(entry, dict):
                # Dict format from JSON
                data.append(
                    {
                        "date": pd.to_datetime(entry["date"]),
                        "actual_value": entry["value"],
                        "appreciation_rate": entry.get("appreciation_rate", 0),
                        "notes": entry.get("notes", ""),
                        "timestamp": entry.get("timestamp", ""),
                    }
                )
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                # Tuple format (timestamp, value)
                data.append(
                    {
                        "date": pd.to_datetime(entry[0]),
                        "actual_value": float(entry[1]),
                        "appreciation_rate": 0,  # Default for tuple format
                        "notes": "",
                        "timestamp": "",
                    }
                )

        df = pd.DataFrame(data)
        df = df.sort_values("date")

        # Calculate what the projected value would have been
        for i, row in df.iterrows():
            if i == 0:
                df.loc[i, "projected_value"] = self.original_value
            else:
                prev_date = df.iloc[i - 1]["date"]
                prev_value = df.iloc[i - 1]["actual_value"]
                years_diff = (row["date"] - prev_date).days / 365.25
                appreciation_rate_decimal = self.appreciation_rate_annual_pct / 100.0
                df.loc[i, "projected_value"] = prev_value * (1 + appreciation_rate_decimal) ** years_diff

        # Calculate performance vs prediction
        df["performance_diff"] = df["actual_value"] - df["projected_value"]
        df["performance_pct"] = (df["performance_diff"] / df["projected_value"]) * 100

        return df

    @error_handler
    def get_projection_with_history(self, months_to_project: int = 30 * 12) -> pd.DataFrame:
        """Get projection that incorporates historical data."""
        if not self.history:
            return self.get_projection(months_to_project)

        # Get historical data and find the last historical entry
        historical_entries = []

        # Always add the original start point as the first "historical" entry
        historical_entries.append((self.start_date, self.original_value))

        for entry in self.history:
            if isinstance(entry, dict):
                entry_date = pd.to_datetime(entry["date"])
                entry_value = float(entry["value"])
                historical_entries.append((entry_date, entry_value))
            elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                entry_date = pd.to_datetime(entry[0])
                entry_value = float(entry[1])
                historical_entries.append((entry_date, entry_value))

        if len(historical_entries) <= 1:  # Only the start point, no additional history
            return self.get_projection(months_to_project)

        # Sort historical entries by date
        historical_entries.sort(key=lambda x: x[0])
        last_historical_date, last_historical_value = historical_entries[-1]

        # Start with projection from asset start_date
        projection_df = self.get_projection(months_to_project)

        # Add historical data points
        for i, (entry_date, entry_value) in enumerate(historical_entries):
            matching_rows = projection_df[projection_df["date"] == entry_date]
            if not matching_rows.empty:
                idx = matching_rows.index[0]
                projection_df.loc[idx, "actual_value"] = entry_value
                # Mark first entry (start point) differently from logged history
                if i == 0:  # This is the original start point
                    projection_df.loc[idx, "is_historical"] = "start_point"
                else:  # This is logged historical data
                    projection_df.loc[idx, "is_historical"] = True
                projection_df.loc[idx, "value"] = entry_value
            else:
                # Add new row for historical data
                new_row = {
                    "date": entry_date,
                    "value": entry_value,
                    "actual_value": entry_value,
                    "is_historical": True if i > 0 else "start_point",
                    "id": self.id,
                    "cash_flow": 0,
                }
                projection_df = pd.concat([projection_df, pd.DataFrame([new_row])], ignore_index=True)

        # Sort by date
        projection_df = projection_df.sort_values("date").reset_index(drop=True)
        projection_df["is_historical"] = projection_df["is_historical"].fillna(False)

        # Now recalculate future projections starting from the last historical value
        last_historical_idx = projection_df[projection_df["date"] == last_historical_date].index
        if len(last_historical_idx) > 0:
            last_idx = last_historical_idx[0]

            # Recalculate all values after the last historical date
            current_value = last_historical_value
            current_date = last_historical_date

            for i in range(last_idx + 1, len(projection_df)):
                row_date = projection_df.loc[i, "date"]

                # Skip if this is also a historical entry
                if projection_df.loc[i, "is_historical"]:
                    current_value = projection_df.loc[i, "value"]
                    current_date = row_date
                    continue

                # Calculate months elapsed since last update
                months_elapsed = (row_date.year - current_date.year) * 12 + (row_date.month - current_date.month)

                # Apply appreciation for each month
                monthly_rate_decimal = annual_pct_to_monthly_decimal(self.appreciation_rate_annual_pct)
                yearly_fee_decimal = self.yearly_fee_pct / 100.0

                for month in range(months_elapsed):
                    next_month_date = current_date + relativedelta(months=month + 1)
                    if next_month_date.month == 1:
                        current_value *= 1 - yearly_fee_decimal
                    current_value *= 1 + monthly_rate_decimal

                # Update the projection
                projection_df.loc[i, "value"] = current_value
                current_date = row_date

        return projection_df

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize asset to dictionary for database storage.

        Returns:
            Dictionary representation of the asset
        """
        return {
            "id": self.id,
            "type": self.type,
            "original_value": self.original_value,
            "value": self.value,
            "appreciation_rate_annual_pct": self.appreciation_rate_annual_pct,
            "yearly_fee_pct": self.yearly_fee_pct,
            "start_date": self.start_date.strftime("%Y-%m-%d"),
            "extraction_date": self.extraction_date.strftime("%Y-%m-%d") if self.extraction_date else None,
            "deposits": self.deposits,
            "withdrawals": self.withdrawals,
            "pmt": self.pmt,
            "history": self.history,
            "loan_ids": self.loan_ids,
            "sell_tax": self.sell_tax,
            "events": self.events,
            # Revenue stream handled by subclasses if needed
        }

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any]) -> 'Asset':
        """
        Deserialize asset from dictionary.

        Args:
            data: Dictionary representation of the asset

        Returns:
            Asset instance
        """
        # Note: This is the base class from_dict
        # Subclasses should override to add their specific fields
        asset = cls(
            id=data["id"],
            start_date=data["start_date"],
            original_value=data["original_value"],
            appreciation_rate_annual_pct=data["appreciation_rate_annual_pct"],
            yearly_fee_pct=data.get("yearly_fee_pct", 0),
            revenue_stream=None,  # Handled by subclasses
            deposits=data.get("deposits", []),
            withdrawals=data.get("withdrawals", []),
            pmt=data.get("pmt", 0),
            history=data.get("history", []),
        )

        # Restore additional fields
        if "extraction_date" in data and data["extraction_date"]:
            asset.set_extraction_date(data["extraction_date"])

        asset.loan_ids = data.get("loan_ids", [])
        asset.sell_tax = data.get("sell_tax", 0)
        asset.events = data.get("events", [])
        asset.value = data.get("value", data["original_value"])

        return asset


class CashAsset(Asset):
    """
    Cash/bank account asset.

    Simple asset with no appreciation, just deposits and withdrawals.
    """

    def __init__(self, id: str, start_date: Union[str, datetime, pd.Timestamp], original_value: float):
        super().__init__(id, start_date, original_value, 0, 0, None, [], [])
        self.type = EItemType.CASH
        self.id = "cash"

    def get_projection(self, months_to_project: int = 30 * 12) -> pd.DataFrame:
        """Calculate cash projection with deposits and withdrawals."""
        value = self.value
        date = self.start_date
        list_projection = []

        for i in range(months_to_project):
            monthly_cash_flow = 0
            if date.month == 1:
                value *= 1 - self.yearly_fee

            for deposit in self.deposits:
                from_date = deposit["from"]
                to_date = deposit["to"]
                if isinstance(from_date, str):
                    from_date = pd.to_datetime(from_date)
                if isinstance(to_date, str):
                    to_date = pd.to_datetime(to_date)

                if from_date <= date <= to_date:
                    value += deposit["amount"]
                    monthly_cash_flow -= deposit["amount"]
            for withdrawal in self.withdrawals:
                w_from = withdrawal["from"]
                w_to = withdrawal["to"]
                if isinstance(w_from, str):
                    w_from = pd.to_datetime(w_from)
                if isinstance(w_to, str):
                    w_to = pd.to_datetime(w_to)
                if w_from <= date <= w_to:
                    value -= withdrawal["amount"]
                    monthly_cash_flow += withdrawal["amount"]

            list_projection.append([self.id, date, value, monthly_cash_flow])
            date += relativedelta(months=1)

        projection_df = pd.DataFrame(
            list_projection,
            columns=["id", "date", VALUE, CASH_FLOW],
        )
        projection_df["date"] = pd.to_datetime(projection_df["date"])
        projection_df = projection_df.loc[projection_df["date"] <= self.extraction_date]
        return projection_df

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """Serialize CashAsset to dictionary."""
        base_dict = super().to_dict()
        return base_dict

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any]) -> 'CashAsset':
        """Deserialize CashAsset from dictionary."""
        asset = cls(
            id=data.get("id", "cash"),
            start_date=data["start_date"],
            original_value=data["original_value"],
        )

        # Restore additional fields
        if "extraction_date" in data and data["extraction_date"]:
            asset.set_extraction_date(data["extraction_date"])

        asset.deposits = data.get("deposits", [])
        asset.withdrawals = data.get("withdrawals", [])
        asset.value = data.get("value", data["original_value"])

        return asset


class RealEstateAsset(Asset):
    """
    Real estate property asset.

    Can have appreciation, fees, and revenue streams (e.g., rental income).
    """

    def __init__(
        self,
        id: str,
        start_date: Union[str, datetime, pd.Timestamp],
        original_value: float,
        appreciation_rate_annual_pct: float,
        yearly_fee_pct: float,
        revenue_stream: Optional[Any],
    ):
        super().__init__(
            id,
            start_date,
            original_value,
            appreciation_rate_annual_pct,
            yearly_fee_pct,
            revenue_stream,
            [],
            [],
        )
        self.type = EItemType.REAL_ESTATE

    def set_sell_tax(self, sell_tax: float):
        """Set the capital gains tax rate for sale."""
        self.sell_tax = sell_tax

    def get_projection(self, months_to_project: int = 30 * 12) -> pd.DataFrame:
        """Calculate real estate value projection with revenue stream."""
        periods = range(1, months_to_project + 1)
        # Apply monthly appreciation using standardized rate conversion
        monthly_rate_decimal = annual_pct_to_monthly_decimal(self.appreciation_rate_annual_pct)
        projected_values = fv(
            monthly_rate_decimal,
            periods,
            pmt=self.pmt,
            pv=-float(self.value),
            when="end",
        )
        date_list = [self.start_date + x * relativedelta(months=1) for x in range(months_to_project)]

        value_projection_dict = {
            "id": self.id,
            "date": date_list,
            VALUE: projected_values,
            CASH_FLOW: 0,
        }

        value_projection_df = pd.DataFrame.from_dict(value_projection_dict)
        value_projection_df.date = pd.to_datetime(value_projection_df["date"])

        if self.revenue_stream:
            revenue_stream_df = self.revenue_stream.get_cash_flow()
            revenue_stream_df["date"] = pd.to_datetime(revenue_stream_df["date"])
            # set 'date' as index
            value_projection_df.set_index("date", inplace=True)
            revenue_stream_df.set_index("date", inplace=True)

            # replace cash_flow values in value_projection_df by those of revenue_stream_df
            value_projection_df[CASH_FLOW] = revenue_stream_df[CASH_FLOW].combine_first(
                value_projection_df[CASH_FLOW]
            )

            # reset index
            value_projection_df.reset_index(inplace=True)

        value_projection_df["date"] = pd.to_datetime(value_projection_df["date"])
        value_projection_df = value_projection_df.loc[value_projection_df["date"] <= self.extraction_date]
        return value_projection_df

    def get_cash_flow(self) -> pd.DataFrame:
        """Get cash flow from revenue stream or parent method."""
        if self.revenue_stream:
            return self.revenue_stream.get_cash_flow()
        else:
            return super().get_cash_flow()

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """Serialize RealEstateAsset to dictionary."""
        base_dict = super().to_dict()
        if self.revenue_stream:
            base_dict["revenue_stream"] = self.revenue_stream.to_dict() if hasattr(self.revenue_stream, 'to_dict') else None
        return base_dict

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any]) -> 'RealEstateAsset':
        """Deserialize RealEstateAsset from dictionary."""
        # Note: Revenue stream deserialization needs to be handled separately
        # as it requires importing revenue_stream module
        asset = cls(
            id=data["id"],
            start_date=data["start_date"],
            original_value=data["original_value"],
            appreciation_rate_annual_pct=data["appreciation_rate_annual_pct"],
            yearly_fee_pct=data.get("yearly_fee_pct", 0),
            revenue_stream=None,  # Will be restored separately
        )

        # Restore additional fields
        if "extraction_date" in data and data["extraction_date"]:
            asset.set_extraction_date(data["extraction_date"])

        asset.loan_ids = data.get("loan_ids", [])
        asset.sell_tax = data.get("sell_tax", 0)
        asset.events = data.get("events", [])
        asset.value = data.get("value", data["original_value"])
        asset.history = data.get("history", [])

        return asset


class StockAsset(Asset):
    """
    Stock/investment portfolio asset.

    Supports appreciation, fees, deposits, withdrawals, and dividend revenue streams.
    """

    def __init__(
        self,
        id: str,
        start_date: Union[str, datetime, pd.Timestamp],
        original_value: float,
        appreciation_rate_annual_pct: float,
        yearly_fee_pct: float,
        revenue_stream: Optional[Any],
        deposits: List[Dict],
        withdrawals: List[Dict],
    ):
        super().__init__(
            id,
            start_date,
            original_value,
            appreciation_rate_annual_pct,
            yearly_fee_pct,
            None,
            deposits,
            withdrawals,
        )
        self.type = EItemType.STOCK
        self.revenue_stream = revenue_stream

    def get_projection(self, months_to_project: int = 30 * 12) -> pd.DataFrame:
        """Calculate stock asset projection with dividends and deposits."""
        # Determine starting value and date based on historical data
        if self.history:
            # Convert history to proper format if needed
            historical_dates_values = []
            for h in self.history:
                if isinstance(h, dict):
                    # New format: {"date": "YYYY-MM-DD", "value": float}
                    historical_dates_values.append((pd.to_datetime(h["date"]), float(h["value"])))
                elif isinstance(h, (list, tuple)) and len(h) == 2:
                    # Old format: (date, value)
                    historical_dates_values.append((pd.to_datetime(h[0]), float(h[1])))

            if historical_dates_values:
                # Sort by date and get the latest entry
                historical_dates_values.sort(key=lambda x: x[0])
                latest_date, latest_value = historical_dates_values[-1]

                # Start projection from the latest historical date/value
                value = latest_value
                date = latest_date
            else:
                # Fallback to original values
                value = self.value
                date = self.start_date
        else:
            # No history, use original values
            value = self.value
            date = self.start_date

        list_projection = []

        # Track if we're starting from historical data to avoid double-applying deposits/growth
        starting_from_history = False
        if self.history:
            historical_dates_values = []
            for h in self.history:
                if isinstance(h, dict):
                    historical_dates_values.append((pd.to_datetime(h["date"]), float(h["value"])))
                elif isinstance(h, (list, tuple)) and len(h) == 2:
                    historical_dates_values.append((pd.to_datetime(h[0]), float(h[1])))

            if historical_dates_values:
                historical_dates_values.sort(key=lambda x: x[0])
                latest_date, _ = historical_dates_values[-1]
                starting_from_history = date == latest_date

        for i in range(months_to_project):
            monthly_dividend_cash_flow = 0
            monthly_cash_flow = 0  # Initialize monthly cash flow

            # Skip applying growth and fees for the first month if starting from historical data
            if not (i == 0 and starting_from_history):
                # Apply yearly fee in January using standardized rate conversion
                yearly_fee_decimal = self.yearly_fee_pct / 100.0
                if date.month == 1:
                    value *= 1 - yearly_fee_decimal
                # Apply monthly appreciation using standardized rate conversion
                monthly_rate_decimal = annual_pct_to_monthly_decimal(self.appreciation_rate_annual_pct)
                value *= 1 + monthly_rate_decimal

            # Handle deposits (process every month for cash flow tracking, even on month 0)
            # When starting from historical data, assume past deposits are in the value already
            for deposit in self.deposits:
                from_date = deposit["from"]
                to_date = deposit["to"]
                if isinstance(from_date, str):
                    from_date = pd.to_datetime(from_date)
                if isinstance(to_date, str):
                    to_date = pd.to_datetime(to_date)

                if from_date <= date <= to_date:
                    # Only update value if: (not starting from history) OR (not first month)
                    should_apply_to_value = not starting_from_history or i > 0
                    if should_apply_to_value:
                        value += float(deposit["amount"])

                    # ALWAYS track cash flow for breakdown (needed for cash flow breakdown UI)
                    if deposit.get("deposit_from_own_capital", False):
                        monthly_cash_flow -= float(deposit["amount"])  # Own capital = expense
                    else:
                        monthly_cash_flow += float(deposit["amount"])  # External deposit = income

            # Handle withdrawals
            for withdrawal in self.withdrawals:
                w_from = withdrawal["from"]
                w_to = withdrawal["to"]
                if isinstance(w_from, str):
                    w_from = pd.to_datetime(w_from)
                if isinstance(w_to, str):
                    w_to = pd.to_datetime(w_to)
                if w_from <= date <= w_to:
                    # Only update value if: (not starting from history) OR (not first month)
                    should_apply_to_value = not starting_from_history or i > 0
                    if should_apply_to_value:
                        value -= float(withdrawal["amount"])

                    # ALWAYS track cash flow for breakdown
                    monthly_cash_flow += float(withdrawal["amount"])

            for event in self.events:
                if event["date"] == date:
                    value *= 1 - event["percent"]
            if self.revenue_stream:
                # Handle different dividend frequency formats - only if it's a DividendRevenueStream
                if hasattr(self.revenue_stream, "dividend_payout_frequency"):
                    frequency = self.revenue_stream.dividend_payout_frequency

                    # Convert numeric frequency to string constants for consistency
                    if frequency == "12" or frequency == 12 or frequency == EPeriod.monthly:
                        monthly_dividend_cash_flow = (
                            value
                            * (float(self.revenue_stream.dividend_yield) / 100 / 12)
                            * (1 - float(self.revenue_stream.tax) / 100)
                        )
                        # Debug extreme dividend values and validate reasonable ranges
                        if monthly_dividend_cash_flow > 50000:  # Flag unusually high monthly dividends
                            print(f"WARNING: High monthly dividend for {self.id}: ${monthly_dividend_cash_flow:,.0f}")
                            print(
                                f"  Asset value: ${value:,.0f}, Yield: {float(self.revenue_stream.dividend_yield):.1f}%, Tax: {float(self.revenue_stream.tax):.1f}%"
                            )
                        if monthly_dividend_cash_flow < 0:  # Flag negative dividends (calculation error)
                            print(f"ERROR: Negative dividend for {self.id}: ${monthly_dividend_cash_flow:,.0f}")
                            print(f"  This indicates a tax calculation error - tax rate likely > 100%")
                            monthly_dividend_cash_flow = 0  # Prevent negative feedback loop
                    elif frequency == "4" or frequency == 4 or frequency == EPeriod.quarterly:
                        if i % 3 == 0:
                            monthly_dividend_cash_flow = (
                                value
                                * (float(self.revenue_stream.dividend_yield) / 100 / 4)
                                * (1 - float(self.revenue_stream.tax) / 100)
                            )
                        else:
                            monthly_dividend_cash_flow = 0
                    elif frequency == "1" or frequency == 1 or frequency == EPeriod.yearly:
                        if i % 12 == 0:
                            monthly_dividend_cash_flow = (
                                value
                                * (float(self.revenue_stream.dividend_yield) / 100)
                                * (1 - float(self.revenue_stream.tax) / 100)
                            )
                        else:
                            monthly_dividend_cash_flow = 0
                    else:
                        # Default to monthly if unknown
                        monthly_dividend_cash_flow = (
                            value
                            * (float(self.revenue_stream.dividend_yield) / 100 / 12)
                            * (1 - float(self.revenue_stream.tax) / 100)
                        )

                    # Handle dividend reinvestment vs withdrawal transition
                    withdraw_date = pd.to_datetime(self.revenue_stream.start_dividend_withdraw_date)
                    current_date = pd.Timestamp(date)

                    # Debug logging for dividend calculations
                    if self.id == "ibi" and current_date.year >= 2044:
                        print(
                            f"🔍 IBI DEBUG [{current_date.strftime('%Y-%m-%d')}]: Asset value=${value:,.0f}, Dividend=${monthly_dividend_cash_flow:,.0f}, Before/After withdraw={current_date < withdraw_date}"
                        )

                    if current_date < withdraw_date:
                        # Before withdrawal date: reinvest dividends (add to asset value)
                        value += monthly_dividend_cash_flow
                        monthly_dividend_cash_flow = 0
                        if self.id == "ibi" and current_date.year >= 2044:
                            print(f"   REINVEST: New asset value=${value:,.0f}, Cash flow=0")
                    else:
                        # After withdrawal date: provide dividends as cash flow
                        # The dividend cash flow is already calculated above and will be added to monthly_cash_flow
                        if self.id == "ibi" and current_date.year >= 2044:
                            print(
                                f"   WITHDRAW: Asset value=${value:,.0f}, Cash flow=${monthly_dividend_cash_flow:,.0f}"
                            )
                        pass
                else:
                    # For non-dividend revenue streams, get cash flow differently
                    monthly_dividend_cash_flow = 0

            monthly_cash_flow += monthly_dividend_cash_flow
            list_projection.append([self.id, date, value, monthly_cash_flow])
            date += relativedelta(months=1)

        projection_df = pd.DataFrame(
            list_projection,
            columns=["id", "date", VALUE, CASH_FLOW],
        )
        projection_df["date"] = pd.to_datetime(projection_df["date"])
        projection_df = projection_df.loc[projection_df["date"] <= self.extraction_date]
        # Only set final value to 0 if the extraction date is reached within the projection period
        if len(projection_df) > 0 and projection_df.iloc[-1]["date"] >= self.extraction_date:
            projection_df.loc[projection_df.index[-1], VALUE] = 0
        return projection_df

    def get_cash_flow(self) -> pd.DataFrame:
        """Get positive cash flows from this stock asset."""
        df = self.get_projection()[["date", CASH_FLOW]]
        df["id"] = self.id
        df = df[df[CASH_FLOW] > 0]
        return df

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """Serialize StockAsset to dictionary."""
        base_dict = super().to_dict()
        if self.revenue_stream:
            base_dict["revenue_stream"] = self.revenue_stream.to_dict() if hasattr(self.revenue_stream, 'to_dict') else None
        return base_dict

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any]) -> 'StockAsset':
        """Deserialize StockAsset from dictionary."""
        asset = cls(
            id=data["id"],
            start_date=data["start_date"],
            original_value=data["original_value"],
            appreciation_rate_annual_pct=data["appreciation_rate_annual_pct"],
            yearly_fee_pct=data.get("yearly_fee_pct", 0),
            revenue_stream=None,  # Will be restored separately
            deposits=data.get("deposits", []),
            withdrawals=data.get("withdrawals", []),
        )

        # Restore additional fields
        if "extraction_date" in data and data["extraction_date"]:
            asset.set_extraction_date(data["extraction_date"])

        asset.loan_ids = data.get("loan_ids", [])
        asset.sell_tax = data.get("sell_tax", 0)
        asset.events = data.get("events", [])
        asset.value = data.get("value", data["original_value"])
        asset.history = data.get("history", [])

        return asset


class PensionAsset(StockAsset):
    """
    Pension/retirement account asset.

    Similar to StockAsset but with pension-specific revenue stream and end date.
    """

    def __init__(
        self,
        id: str,
        start_date: Union[str, datetime, pd.Timestamp],
        original_value: float,
        appreciation_rate_annual_pct: float,
        yearly_fee_pct: float,
        revenue_stream: Any,  # PensionRevenueStream
        deposits: List[Dict],
        end_date: Union[str, datetime, pd.Timestamp],
        conversion_date: Union[str, datetime, pd.Timestamp, None] = None,
        conversion_coefficient: float = 200,
    ):
        super().__init__(
            id,
            start_date,
            original_value,
            appreciation_rate_annual_pct,
            yearly_fee_pct,
            revenue_stream,
            deposits,
            [],
        )
        self.type = EItemType.STOCK
        self.end_date = parse_date(end_date, normalize_to_month_start=True)
        self.revenue_stream = revenue_stream
        self.conversion_date = parse_date(conversion_date, normalize_to_month_start=True) if conversion_date else None
        self.conversion_coefficient = conversion_coefficient

    def get_projection(self, months_to_project: int = 30 * 12) -> pd.DataFrame:
        """Calculate pension asset projection with optional conversion to annuity."""
        value = self.value
        date = self.start_date
        list_projection = []
        converted = False
        monthly_payout = 0.0

        for i in range(months_to_project):
            monthly_cash_flow = 0  # Track deposits/withdrawals for breakdown

            # Check if we've reached the conversion date
            if self.conversion_date and not converted and date >= self.conversion_date:
                # Convert accumulated value to monthly payout
                monthly_payout = value / self.conversion_coefficient
                converted = True
                value = 0  # Annuity - asset value goes to 0

            if not converted:
                # Accumulation phase: deposits + growth
                for deposit in self.deposits:
                    d_from = deposit["from"]
                    d_to = deposit["to"]
                    if isinstance(d_from, str):
                        d_from = pd.to_datetime(d_from)
                    if isinstance(d_to, str):
                        d_to = pd.to_datetime(d_to)
                    if d_from <= date <= d_to:
                        value += deposit["amount"]

                        # Track cash flow for breakdown — only own-capital deposits affect user cash flow
                        if deposit.get("deposit_from_own_capital", False):
                            monthly_cash_flow -= deposit["amount"]  # Own capital = expense
                        # Employer deposits don't pass through user's bank account, no cash flow impact

                # Apply yearly fee (at the beginning of each year)
                yearly_fee_decimal = self.yearly_fee_pct / 100.0
                if date.month == 1:
                    value *= 1 - yearly_fee_decimal

                # Apply monthly appreciation
                monthly_rate_decimal = annual_pct_to_monthly_decimal(self.appreciation_rate_annual_pct)
                value *= 1 + monthly_rate_decimal

                # Calculate cash flow from pension payouts (legacy revenue_stream path)
                if self.revenue_stream and date > self.revenue_stream.start_date:
                    cash_flow = self.revenue_stream.monthly_payout
                else:
                    cash_flow = 0

                cash_flow += monthly_cash_flow
            else:
                # Payout phase: fixed monthly income, no growth
                cash_flow = monthly_payout

            # Append the result for this month
            list_projection.append([self.id, date, value, cash_flow])

            # Move to next month
            date += relativedelta(months=1)

        projection_df = pd.DataFrame(
            list_projection,
            columns=["id", "date", VALUE, CASH_FLOW],
        )

        # Add is_historical column for consistency with historical projections
        projection_df["is_historical"] = False
        projection_df["actual_value"] = None

        # Stop projection at end_date (no forced zeroing). Sale/cash realization handled separately.
        projection_df = projection_df.loc[projection_df["date"] <= self.end_date]
        projection_df = projection_df.loc[projection_df["date"] <= self.extraction_date]
        return projection_df

    def get_projection_with_history(self, months_to_project: int = 30 * 12) -> pd.DataFrame:
        """Get projection that incorporates historical data for pension assets."""
        # Check if we have actual historical data (more than just the default start point)
        meaningful_history = []
        for entry in self.history:
            if isinstance(entry, dict):
                meaningful_history.append(entry)
            elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                # Only count as meaningful if it's not the default start date entry
                entry_date = pd.to_datetime(entry[0])
                if entry_date != self.start_date or float(entry[1]) != self.original_value:
                    meaningful_history.append(entry)

        if not meaningful_history:
            return self.get_projection(months_to_project)

        # Get historical data and find the last historical entry
        historical_entries = []

        for entry in meaningful_history:
            if isinstance(entry, dict):
                entry_date = pd.to_datetime(entry["date"])
                entry_value = float(entry["value"])
                historical_entries.append((entry_date, entry_value))
            elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                entry_date = pd.to_datetime(entry[0])
                entry_value = float(entry[1])
                historical_entries.append((entry_date, entry_value))

        if not historical_entries:  # No valid historical data
            return self.get_projection(months_to_project)

        # Sort historical entries by date and get the last one
        historical_entries.sort(key=lambda x: x[0])
        last_historical_date, last_historical_value = historical_entries[-1]

        # Create projection starting from the last historical date
        current_value = last_historical_value
        current_date = last_historical_date
        list_projection = []

        # Add the historical point as the starting point
        list_projection.append([self.id, current_date, current_value, 0])

        # Project forward from the historical date
        for i in range(months_to_project):
            # Move to next month
            current_date = current_date + relativedelta(months=1)

            # Add deposits for this month
            for deposit in self.deposits:
                d_from = deposit["from"]
                d_to = deposit["to"]
                if isinstance(d_from, str):
                    d_from = pd.to_datetime(d_from)
                if isinstance(d_to, str):
                    d_to = pd.to_datetime(d_to)
                if d_from <= current_date <= d_to:
                    current_value += deposit["amount"]

            # Apply yearly fee (at the beginning of each year) using standardized rate conversion
            yearly_fee_decimal = self.yearly_fee_pct / 100.0
            if current_date.month == 1:
                current_value *= 1 - yearly_fee_decimal

            # Apply monthly appreciation using standardized rate conversion
            monthly_rate_decimal = annual_pct_to_monthly_decimal(self.appreciation_rate_annual_pct)
            current_value *= 1 + monthly_rate_decimal

            # Calculate cash flow
            if current_date > self.revenue_stream.start_date:
                cash_flow = self.revenue_stream.monthly_payout
            else:
                cash_flow = 0

            # Append the result for this month
            list_projection.append([self.id, current_date, current_value, cash_flow])

        # Create DataFrame
        projection_df = pd.DataFrame(
            list_projection,
            columns=["id", "date", VALUE, CASH_FLOW],
        )

        # Mark the first entry as historical, rest as projected
        projection_df["is_historical"] = False
        projection_df["actual_value"] = None
        projection_df.loc[0, "is_historical"] = True
        projection_df.loc[0, "actual_value"] = last_historical_value

        # Apply end date restriction without zeroing values
        projection_df = projection_df.loc[projection_df["date"] <= self.end_date]
        projection_df = projection_df.loc[projection_df["date"] <= self.extraction_date]

        return projection_df

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """Serialize PensionAsset to dictionary."""
        base_dict = super().to_dict()
        base_dict["end_date"] = self.end_date.strftime("%Y-%m-%d")
        return base_dict

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any]) -> 'PensionAsset':
        """Deserialize PensionAsset from dictionary."""
        asset = cls(
            id=data["id"],
            start_date=data["start_date"],
            original_value=data["original_value"],
            appreciation_rate_annual_pct=data["appreciation_rate_annual_pct"],
            yearly_fee_pct=data.get("yearly_fee_pct", 0),
            revenue_stream=None,  # Will be restored separately
            deposits=data.get("deposits", []),
            end_date=data["end_date"],
        )

        # Restore additional fields
        if "extraction_date" in data and data["extraction_date"]:
            asset.set_extraction_date(data["extraction_date"])

        asset.loan_ids = data.get("loan_ids", [])
        asset.sell_tax = data.get("sell_tax", 0)
        asset.events = data.get("events", [])
        asset.value = data.get("value", data["original_value"])
        asset.history = data.get("history", [])

        return asset


# Module metadata
__version__ = "2.0.0"
__author__ = "FPlan Development Team"
__description__ = "Asset models for FPlan v2 with database serialization support"
