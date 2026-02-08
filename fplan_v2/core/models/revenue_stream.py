"""
Revenue stream models for FPlan v2.

This module contains revenue stream classes for financial planning, ported from v1
with database serialization support. All financial calculation logic is preserved
exactly as-is to maintain golden master compatibility.

Classes:
    RevenueStream: Base class for revenue streams
    SalaryRevenueStream: Salary income with growth
    RentRevenueStream: Rental income with periodic payments
    DividendRevenueStream: Stock dividend income
    PensionRevenueStream: Pension payout stream
"""

from typing import Dict, Any, Optional, Union
import numpy as np
import numpy_financial as npf
import pandas as pd
from dateutil.relativedelta import relativedelta
from datetime import datetime

# V2 imports
from fplan_v2.core.constants import EPeriod, CASH_FLOW, PROJECTION_IN_MONTH
from fplan_v2.utils.date_utils import parse_date, normalize_date_to_month_start
from fplan_v2.utils.error_utils import error_handler


class RevenueStream:
    """
    Base class for all revenue streams.

    A revenue stream represents regular income from various sources.

    Attributes:
        id: Unique identifier for the revenue stream
        start_date: Date when revenue stream begins
    """

    def __init__(self, id: str, start_date: Union[str, datetime, pd.Timestamp]):
        self.id = id
        self.start_date = parse_date(start_date, normalize_to_month_start=True)

    def init_start_date(self, start_date: Union[str, datetime, pd.Timestamp]) -> pd.Timestamp:
        """DEPRECATED: Use parse_date directly in constructor"""
        return parse_date(start_date, normalize_to_month_start=True)

    def get_cash_flow(self) -> pd.DataFrame:
        """
        Get cash flow projection for this revenue stream.

        Must be implemented by subclasses.

        Returns:
            DataFrame with columns: id, date, cash_flow
        """
        return pd.DataFrame(columns=["id", "date", CASH_FLOW])

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """Serialize revenue stream to dictionary."""
        return {
            "id": self.id,
            "type": "base",
            "start_date": self.start_date.strftime("%Y-%m-%d"),
        }

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any]) -> 'RevenueStream':
        """Deserialize revenue stream from dictionary."""
        return cls(
            id=data["id"],
            start_date=data["start_date"],
        )


class SalaryRevenueStream(RevenueStream):
    """
    Salary revenue stream with annual growth.

    Attributes:
        amount: Annual salary amount
        end_date: Date when salary ends
        growth_rate: Annual salary growth rate as percentage
    """

    def __init__(
        self,
        id: str,
        start_date: Union[str, datetime, pd.Timestamp],
        end_date: Union[str, datetime, pd.Timestamp],
        amount: float,
        growth_rate: float = 0,
    ):
        super().__init__(id, start_date)
        self.amount = float(amount)
        self.end_date = parse_date(end_date, normalize_to_month_start=True)
        self.growth_rate = float(growth_rate)

    def get_cash_flow(self) -> pd.DataFrame:
        """Calculate salary cash flow with annual growth."""
        date_list = [
            self.start_date + x * relativedelta(months=12) for x in range(int(PROJECTION_IN_MONTH / 12))
        ]
        periods = range(1, int(PROJECTION_IN_MONTH / 12))

        months_diff = 0
        temp_date = self.start_date

        # Increment temp_date by one month until it exceeds or meets end_date
        while temp_date < self.end_date:
            months_diff += 1
            temp_date += relativedelta(months=1)

        # Convert growth rate from percentage to decimal for npf.fv (e.g., 3% -> 0.03)
        growth_rate_decimal = self.growth_rate / 100.0
        cash_flow = npf.fv(growth_rate_decimal, periods, 0, -self.amount)
        cash_flow = np.insert(cash_flow, 0, self.amount)
        d = {"id": self.id, "date": date_list, CASH_FLOW: cash_flow}

        df = pd.DataFrame.from_dict(d)
        df["date"] = pd.to_datetime(df["date"])

        # Normalize dates to month start for consistency with other components
        df["date"] = df["date"] + pd.offsets.MonthBegin(0)

        return df

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """Serialize salary revenue stream to dictionary."""
        return {
            "id": self.id,
            "type": "salary",
            "start_date": self.start_date.strftime("%Y-%m-%d"),
            "end_date": self.end_date.strftime("%Y-%m-%d") if isinstance(self.end_date, pd.Timestamp) else str(self.end_date),
            "amount": self.amount,
            "growth_rate": self.growth_rate,
        }

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any]) -> 'SalaryRevenueStream':
        """Deserialize salary revenue stream from dictionary."""
        return cls(
            id=data["id"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            amount=data["amount"],
            growth_rate=data.get("growth_rate", 0),
        )


class RentRevenueStream(RevenueStream):
    """
    Rental income revenue stream.

    Supports different payment periods (monthly, quarterly, yearly) and growth.

    Attributes:
        amount: Payment amount per period
        period: Payment period (monthly/quarterly/yearly)
        tax: Tax rate as percentage
        growth_rate: Annual growth rate as percentage
        end_date: Optional end date for rental period
    """

    def __init__(
        self,
        id: str,
        start_date: Union[str, datetime, pd.Timestamp],
        amount: float,
        period: str,
        tax: float,
        growth_rate: float = 0,
        end_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
    ):
        super().__init__(id, start_date)
        self.amount = float(amount)
        self.period = period
        self.tax = float(tax) if tax else 0
        self.growth_rate = float(growth_rate)
        self.end_date = parse_date(end_date, normalize_to_month_start=True) if end_date else None

    def get_cash_flow(self) -> pd.DataFrame:
        """Calculate rental income cash flow with periodic payments and growth."""
        # Define the period mapping
        period_mapping = {"monthly": 1, "quarterly": 3, "yearly": 12}

        # Convert the period to months
        period_months = period_mapping.get(self.period, 12)  # Default to 12 (yearly) if not found

        # Calculate maximum periods based on projection length or end date
        max_periods_from_projection = int(PROJECTION_IN_MONTH / period_months)

        if self.end_date:
            # Calculate months difference between start and end date
            months_diff = 0
            temp_date = self.start_date
            while temp_date <= self.end_date:
                months_diff += 1
                temp_date += relativedelta(months=1)

            # Calculate number of periods that fit within the rental duration
            max_periods_from_duration = int(months_diff / period_months)
            max_periods = min(max_periods_from_projection, max_periods_from_duration)
        else:
            max_periods = max_periods_from_projection

        # Generate the date list
        date_list = [
            self.start_date + x * relativedelta(months=period_months)
            for x in range(max_periods)
        ]

        # If no payments (date_list is empty), return empty DataFrame
        if not date_list:
            return pd.DataFrame(columns=["id", "date", CASH_FLOW])

        # Calculate cash flows with proper annual growth rate handling
        cash_flows = []
        growth_rate_decimal = self.growth_rate / 100.0  # Convert percentage to decimal

        for i, date in enumerate(date_list):
            # Calculate years from start date for proper annual compounding
            years_from_start = i * (period_months / 12.0)
            # Apply annual growth: amount * (1 + annual_rate)^years
            cash_flow_amount = self.amount * ((1 + growth_rate_decimal) ** years_from_start)
            cash_flows.append(cash_flow_amount)

        cash_flow = np.array(cash_flows)

        d = {"id": self.id, "date": date_list, CASH_FLOW: cash_flow}

        df = pd.DataFrame.from_dict(d)
        df["date"] = pd.to_datetime(df["date"])

        # Normalize dates to month start for consistency with other components
        df["date"] = df["date"] + pd.offsets.MonthBegin(0)

        return df

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """Serialize rent revenue stream to dictionary."""
        return {
            "id": self.id,
            "type": "rent",
            "start_date": self.start_date.strftime("%Y-%m-%d"),
            "amount": self.amount,
            "period": self.period,
            "tax": self.tax,
            "growth_rate": self.growth_rate,
            "end_date": self.end_date.strftime("%Y-%m-%d") if self.end_date else None,
        }

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any]) -> 'RentRevenueStream':
        """Deserialize rent revenue stream from dictionary."""
        return cls(
            id=data["id"],
            start_date=data["start_date"],
            amount=data["amount"],
            period=data["period"],
            tax=data["tax"],
            growth_rate=data.get("growth_rate", 0),
            end_date=data.get("end_date"),
        )


class DividendRevenueStream:
    """
    Stock dividend revenue stream.

    Dividends can be reinvested or withdrawn based on start_dividend_withdraw_date.

    Attributes:
        dividend_yield: Annual dividend yield as percentage
        dividend_payout_frequency: Payout frequency (monthly/quarterly/yearly)
        tax: Tax rate as percentage
        start_dividend_withdraw_date: Date to start withdrawing instead of reinvesting
    """

    def __init__(
        self,
        dividend_yield: float,
        dividend_payout_frequency: Union[str, int],
        tax: float,
        start_dividend_withdraw_date: Union[str, datetime, pd.Timestamp] = "01/01/2200",
    ):
        self.dividend_yield = dividend_yield
        self.dividend_payout_frequency = dividend_payout_frequency
        self.tax = tax
        self.start_dividend_withdraw_date = parse_date(start_dividend_withdraw_date, normalize_to_month_start=True)

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """Serialize dividend revenue stream to dictionary."""
        return {
            "type": "dividend",
            "dividend_yield": self.dividend_yield,
            "dividend_payout_frequency": self.dividend_payout_frequency,
            "tax": self.tax,
            "start_dividend_withdraw_date": self.start_dividend_withdraw_date.strftime("%Y-%m-%d"),
        }

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any]) -> 'DividendRevenueStream':
        """Deserialize dividend revenue stream from dictionary."""
        return cls(
            dividend_yield=data["dividend_yield"],
            dividend_payout_frequency=data["dividend_payout_frequency"],
            tax=data["tax"],
            start_dividend_withdraw_date=data.get("start_dividend_withdraw_date", "01/01/2200"),
        )


class PensionRevenueStream(RevenueStream):
    """
    Pension payout revenue stream.

    Fixed monthly payout from pension account.

    Attributes:
        monthly_payout: Fixed monthly payout amount
    """

    def __init__(self, id: str, start_date: Union[str, datetime, pd.Timestamp], monthly_payout: float):
        super().__init__(id, start_date)
        self.monthly_payout = monthly_payout

    def get_cash_flow(self) -> pd.DataFrame:
        """
        Get pension cash flow.

        Note: This method raises an error in v1 - maintained for compatibility.
        """
        raise RuntimeError("unsupported")
        date_list = [
            self.start_date + x * relativedelta(months=12) for x in range(int(PROJECTION_IN_MONTH / 12))
        ]
        d = {"id": self.id, "date": date_list, CASH_FLOW: self.monthly_payout}

        df = pd.DataFrame.from_dict(d)
        df["date"] = pd.to_datetime(df["date"])

        # Normalize dates to month start for consistency with other components
        df["date"] = df["date"] + pd.offsets.MonthBegin(0)

        return df

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """Serialize pension revenue stream to dictionary."""
        return {
            "id": self.id,
            "type": "pension",
            "start_date": self.start_date.strftime("%Y-%m-%d"),
            "monthly_payout": self.monthly_payout,
        }

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any]) -> 'PensionRevenueStream':
        """Deserialize pension revenue stream from dictionary."""
        return cls(
            id=data["id"],
            start_date=data["start_date"],
            monthly_payout=data["monthly_payout"],
        )


# Module metadata
__version__ = "2.0.0"
__author__ = "FPlan Development Team"
__description__ = "Revenue stream models for FPlan v2 with database serialization support"
