"""
Loan models for FPlan v2.

This module contains loan classes for financial planning, ported from v1
with database serialization support. All financial calculation logic is preserved
exactly as-is to maintain golden master compatibility.

Classes:
    LoanFixed: Fixed-rate mortgage/loan
    LoanVariable: Variable-rate loan with inflation adjustment
    LoanPrimePegged: Loan pegged to prime interest rate index
    LoanCPIPegged: Loan pegged to Consumer Price Index (CPI)
"""

from typing import Dict, Any, Optional, Union, List
import numpy as np
import numpy_financial as npf
import pandas as pd
from dateutil.relativedelta import relativedelta
from datetime import datetime

# V2 imports
from fplan_v2.core.constants import EIndexType, CASH_FLOW, VALUE
from fplan_v2.utils.date_utils import parse_date, normalize_date_to_month_start
from fplan_v2.utils.rate_utils import annual_pct_to_monthly_decimal, normalize_rate_input
from fplan_v2.utils.error_utils import error_handler


class LoanFixed:
    """
    Fixed-rate loan with constant interest rate throughout the loan term.

    Attributes:
        id: Unique loan identifier
        value: Loan principal (stored as negative value)
        interest_rate_annual_pct: Annual interest rate as percentage
        duration_months: Loan duration in months
        start_date: Loan start date (normalized to month start)
        collateral_asset: Optional asset ID used as collateral
        history: Historical balance entries for tracking actual performance
        repayment_date: Optional early repayment date
    """

    @error_handler
    def __init__(
        self,
        id: str,
        value: float,
        interest_rate_annual_pct: float,
        duration_months: int,
        start_date: Union[str, datetime, pd.Timestamp],
        collateral_asset: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ):
        self.value = -value

        # Standardize rate storage: normalize input and store as annual percentage
        self.interest_rate_annual_pct = normalize_rate_input(interest_rate_annual_pct)
        self.duration_months = duration_months

        # For backward compatibility, keep old attribute names pointing to new ones
        self.yearly_interest_rate = (
            self.interest_rate_annual_pct / 100.0
        )  # Convert to decimal for backward compatibility
        self.duration = duration_months

        self.start_date = parse_date(start_date, normalize_to_month_start=True)
        self.id = id
        self.index_tracker = None
        self.repayment_date = None
        self.collateral_asset = collateral_asset
        # Historical tracking: list of {"date": "YYYY-MM-DD", "balance": float, "interest_rate": float, "notes": str}
        self.history = history or []

    @error_handler
    def init_start_date(self, start_date: Union[str, datetime, pd.Timestamp]) -> pd.Timestamp:
        """DEPRECATED: Use parse_date directly in constructor"""
        return parse_date(start_date, normalize_to_month_start=True)

    @error_handler
    def get_interest_paymnets(self) -> np.ndarray:
        """Calculate interest payments for each period."""
        periods = range(1, self.duration_months + 1)
        monthly_rate_decimal = annual_pct_to_monthly_decimal(self.interest_rate_annual_pct)
        interest_payment = npf.ipmt(rate=monthly_rate_decimal, per=periods, nper=self.duration_months, pv=-self.value)
        return interest_payment

    @error_handler
    def get_principal_payment(self) -> np.ndarray:
        """Calculate principal payments for each period."""
        periods = range(1, self.duration_months + 1)
        monthly_rate_decimal = annual_pct_to_monthly_decimal(self.interest_rate_annual_pct)
        principal_payment = npf.ppmt(rate=monthly_rate_decimal, per=periods, nper=self.duration_months, pv=-self.value)
        return principal_payment

    @error_handler
    def get_monthly_payment(self) -> float:
        """Calculate the fixed monthly payment amount."""
        monthly_rate_decimal = annual_pct_to_monthly_decimal(self.interest_rate_annual_pct)
        return npf.pmt(monthly_rate_decimal, self.duration_months, self.value)

    @error_handler
    def get_projection(self) -> pd.DataFrame:
        """
        Calculate loan amortization schedule projection.

        Returns:
            DataFrame with columns: id, date, interest_payment, principal_payment, cash_flow, value
        """
        date_list = [self.start_date + x * relativedelta(months=1) for x in range(self.duration_months)]

        interest_payments = self.get_interest_paymnets()
        principal_payment = self.get_principal_payment()

        d = {
            "id": self.id,
            "date": date_list,
            "interest_payment": interest_payments,
            "principal_payment": principal_payment,
        }

        df = pd.DataFrame.from_dict(d)

        df[CASH_FLOW] = df["interest_payment"] + df["principal_payment"]
        df[VALUE] = self.value - df["principal_payment"].cumsum()

        if self.repayment_date:
            df = df[df["date"] < self.repayment_date]
        return df

    @error_handler
    def repay_loan(self, date: Union[str, datetime, pd.Timestamp], amount: float) -> tuple:
        """
        Calculate remaining balance and duration after early repayment.

        Args:
            date: Repayment date
            amount: Repayment amount

        Returns:
            Tuple of (remaining_value, remaining_duration_months)
        """
        projection_df = self.get_projection()
        repay_date_df = projection_df[projection_df["date"] == date]
        remaining_value = repay_date_df[VALUE] + amount
        remaining_duration = (
            projection_df["date"].max() - repay_date_df.date
        ).dt.days / 30.44  # Convert to approximate months

        self.repayment_date = date
        return remaining_value.values[0], int(round(remaining_duration))

    @error_handler
    def add_historical_entry(self, date: Union[str, datetime, pd.Timestamp], balance: float,
                           interest_rate: Optional[float] = None, notes: str = ""):
        """Add a historical entry for this loan."""
        date = normalize_date_to_month_start(date)

        # Update current interest rate if provided
        if interest_rate is not None:
            self.interest_rate_annual_pct = normalize_rate_input(interest_rate)
            self.yearly_interest_rate = self.interest_rate_annual_pct / 100.0  # Backward compatibility

        # Create historical entry
        entry = {
            "date": date.strftime("%Y-%m-%d"),
            "balance": float(balance),
            "interest_rate": float(interest_rate or self.interest_rate_annual_pct),
            "notes": notes,
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Add to history, avoiding duplicates by date
        self.history = [h for h in self.history if h.get("date") != entry["date"]]
        self.history.append(entry)
        self.history.sort(key=lambda x: x["date"])

        # Update current value if this is the most recent entry
        latest_date = max([pd.to_datetime(h["date"]) for h in self.history] + [self.start_date])
        if date >= latest_date:
            self.value = -balance  # Negative because loans are liabilities

    @error_handler
    def get_historical_performance(self) -> pd.DataFrame:
        """Get a DataFrame with historical performance vs predictions."""
        if not self.history:
            return pd.DataFrame()

        data = []
        for entry in self.history:
            data.append(
                {
                    "date": pd.to_datetime(entry["date"]),
                    "actual_balance": entry["balance"],
                    "interest_rate": entry["interest_rate"],
                    "notes": entry.get("notes", ""),
                    "timestamp": entry.get("timestamp", ""),
                }
            )

        df = pd.DataFrame(data)
        df = df.sort_values("date")
        return df

    @error_handler
    def get_projection_with_history(self) -> pd.DataFrame:
        """Get projection that incorporates historical data."""
        # Get the standard projection
        projection_df = self.get_projection()

        if not self.history:
            return projection_df

        # Add historical actuals to the projection
        for entry in self.history:
            entry_date = pd.to_datetime(entry["date"])

            # Find the corresponding row in projection
            matching_rows = projection_df[projection_df["date"] == entry_date]
            if not matching_rows.empty:
                idx = matching_rows.index[0]
                projection_df.loc[idx, "actual_balance"] = entry["balance"]
                projection_df.loc[idx, "is_historical"] = True
            else:
                # Add new row for historical data
                new_row = {
                    "date": entry_date,
                    "value": -entry["balance"],  # Negative for loan balance
                    "actual_balance": entry["balance"],
                    "is_historical": True,
                    "id": self.id,
                }
                projection_df = pd.concat([projection_df, pd.DataFrame([new_row])], ignore_index=True)

        projection_df = projection_df.sort_values("date").reset_index(drop=True)
        projection_df["is_historical"] = projection_df["is_historical"].fillna(False)

        return projection_df

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize loan to dictionary for database storage.

        Returns:
            Dictionary representation of the loan
        """
        return {
            "id": self.id,
            "type": "fixed",
            "value": -self.value,  # Convert back to positive for storage
            "interest_rate_annual_pct": self.interest_rate_annual_pct,
            "duration_months": self.duration_months,
            "start_date": self.start_date.strftime("%Y-%m-%d"),
            "collateral_asset": self.collateral_asset,
            "history": self.history,
            "repayment_date": self.repayment_date.strftime("%Y-%m-%d") if self.repayment_date else None,
        }

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any]) -> 'LoanFixed':
        """
        Deserialize loan from dictionary.

        Args:
            data: Dictionary representation of the loan

        Returns:
            LoanFixed instance
        """
        loan = cls(
            id=data["id"],
            value=data["value"],
            interest_rate_annual_pct=data["interest_rate_annual_pct"],
            duration_months=data["duration_months"],
            start_date=data["start_date"],
            collateral_asset=data.get("collateral_asset"),
            history=data.get("history", []),
        )

        if data.get("repayment_date"):
            loan.repayment_date = parse_date(data["repayment_date"], normalize_to_month_start=True)

        return loan


class LoanVariable:
    """
    Variable-rate loan with annual inflation adjustment.

    The interest rate adjusts annually based on inflation rate.

    Attributes:
        id: Unique loan identifier
        value: Loan principal (stored as negative value)
        base_rate_annual_pct: Initial base interest rate as percentage
        margin_pct: Fixed margin added to base rate
        duration_months: Loan duration in months
        inflation_rate_annual_pct: Annual inflation rate for adjustments
        start_date: Loan start date (normalized to month start)
        collateral_asset: Optional asset ID used as collateral
    """

    @error_handler
    def __init__(
        self,
        id: str,
        value: float,
        base_rate_annual_pct: float,
        margin_pct: float,
        duration_months: int,
        start_date: Union[str, datetime, pd.Timestamp],
        inflation_rate_annual_pct: float,
        collateral_asset: Optional[str] = None,
    ):
        self.id = id
        self.value = -value

        # Standardize rate storage: normalize inputs and store as annual percentages
        self.base_rate_annual_pct = normalize_rate_input(base_rate_annual_pct)  # Initial base rate
        self.margin_pct = normalize_rate_input(margin_pct)  # Fixed margin above the base rate
        self.duration_months = duration_months
        self.inflation_rate_annual_pct = normalize_rate_input(inflation_rate_annual_pct)  # Annual inflation rate

        # For backward compatibility, keep old attribute names pointing to new ones
        self.base_rate = self.base_rate_annual_pct / 100.0
        self.margin = self.margin_pct / 100.0
        self.duration = duration_months
        self.inflation_rate = self.inflation_rate_annual_pct / 100.0

        self.start_date = parse_date(start_date, normalize_to_month_start=True)
        self.collateral_asset = collateral_asset
        self.repayment_date = None

        # Initialize with the current interest rate
        self.current_interest_rate = self.base_rate + self.margin

    @error_handler
    def init_start_date(self, start_date: Union[str, datetime, pd.Timestamp]) -> pd.Timestamp:
        """DEPRECATED: Use parse_date directly in constructor"""
        return parse_date(start_date, normalize_to_month_start=True)

    @error_handler
    def adjust_for_inflation(self):
        """Adjust the base rate annually for inflation."""
        self.base_rate *= 1 + self.inflation_rate

    @error_handler
    def get_interest_payments(self) -> List[float]:
        """Calculate interest payments for each period with inflation adjustments."""
        interest_payment = []
        for month in range(1, self.duration_months + 1):
            if month % 12 == 0:
                # Adjust the base rate at the end of each year
                self.adjust_for_inflation()

            self.current_interest_rate = self.base_rate + self.margin
            monthly_rate_decimal = self.current_interest_rate / 12.0
            payment = npf.ipmt(rate=monthly_rate_decimal, per=month, nper=self.duration_months, pv=-self.value)
            interest_payment.append(payment)
        return interest_payment

    @error_handler
    def get_principal_payment(self) -> List[float]:
        """Calculate principal payments for each period with inflation adjustments."""
        principal_payment = []
        for month in range(1, self.duration_months + 1):
            if month % 12 == 0:
                # Adjust the base rate at the end of each year
                self.adjust_for_inflation()

            self.current_interest_rate = self.base_rate + self.margin
            monthly_rate_decimal = self.current_interest_rate / 12.0
            payment = npf.ppmt(rate=monthly_rate_decimal, per=month, nper=self.duration_months, pv=-self.value)
            principal_payment.append(payment)
        return principal_payment

    @error_handler
    def get_monthly_payment(self) -> List[float]:
        """Calculate monthly payments for each period with inflation adjustments."""
        monthly_payment = []
        for month in range(1, self.duration_months + 1):
            if month % 12 == 0:
                # Adjust the base rate at the end of each year
                self.adjust_for_inflation()

            self.current_interest_rate = self.base_rate + self.margin
            monthly_rate_decimal = self.current_interest_rate / 12.0
            payment = npf.pmt(rate=monthly_rate_decimal, per=month, nper=self.duration_months, pv=-self.value)
            monthly_payment.append(payment)
        return monthly_payment

    @error_handler
    def get_projection(self) -> pd.DataFrame:
        """
        Calculate loan amortization schedule projection with variable rates.

        Returns:
            DataFrame with columns: id, date, interest_payment, principal_payment, cash_flow, value
        """
        date_list = [self.start_date + relativedelta(months=x) for x in range(self.duration_months)]

        interest_payments = self.get_interest_payments()
        principal_payments = self.get_principal_payment()

        d = {
            "id": self.id,
            "date": date_list,
            "interest_payment": interest_payments,
            "principal_payment": principal_payments,
        }

        df = pd.DataFrame.from_dict(d)

        df["cash_flow"] = df["interest_payment"] + df["principal_payment"]
        df["value"] = self.value - df["principal_payment"].cumsum()

        if self.repayment_date:
            df = df[df["date"] < self.repayment_date]
        return df

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """Serialize variable loan to dictionary."""
        return {
            "id": self.id,
            "type": "variable",
            "value": -self.value,
            "base_rate_annual_pct": self.base_rate_annual_pct,
            "margin_pct": self.margin_pct,
            "duration_months": self.duration_months,
            "inflation_rate_annual_pct": self.inflation_rate_annual_pct,
            "start_date": self.start_date.strftime("%Y-%m-%d"),
            "collateral_asset": self.collateral_asset,
            "repayment_date": self.repayment_date.strftime("%Y-%m-%d") if self.repayment_date else None,
        }

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any]) -> 'LoanVariable':
        """Deserialize variable loan from dictionary."""
        loan = cls(
            id=data["id"],
            value=data["value"],
            base_rate_annual_pct=data["base_rate_annual_pct"],
            margin_pct=data["margin_pct"],
            duration_months=data["duration_months"],
            start_date=data["start_date"],
            inflation_rate_annual_pct=data["inflation_rate_annual_pct"],
            collateral_asset=data.get("collateral_asset"),
        )

        if data.get("repayment_date"):
            loan.repayment_date = parse_date(data["repayment_date"], normalize_to_month_start=True)

        return loan


class LoanPrimePegged(LoanFixed):
    """
    Loan with interest rate pegged to prime rate index.

    Requires an IndexTracker instance to track historical prime rate changes.

    Attributes:
        index_tracker: IndexTracker instance with prime rate history
    """

    @error_handler
    def __init__(
        self,
        loan_id: str,
        value: float,
        base_interest_rate_annual_pct: float,
        duration_months: int,
        start_date: Union[str, datetime, pd.Timestamp],
        index_tracker: Any,  # IndexTracker type
    ):
        super().__init__(loan_id, value, base_interest_rate_annual_pct, duration_months, start_date)
        self.index_tracker = index_tracker

    @error_handler
    def get_projection(self) -> pd.DataFrame:
        """
        Calculate loan projection with prime rate adjustments.

        Returns:
            DataFrame with amortization schedule adjusted for prime rate changes
        """
        index_change_calendar_df = self.index_tracker.get_index_change_history(EIndexType.PRIME)
        projected_df_per_period = {}

        index_change_calendar_df = index_change_calendar_df.loc[index_change_calendar_df.start > self.start_date]
        index_change_calendar_df = pd.concat(
            [
                index_change_calendar_df,
                pd.DataFrame(
                    [[self.start_date, None, None, self.duration_months, 0]],
                    columns=["start", "end", "rate", "duration_till_end_of_loan", "rate_change"],
                ),
            ]
        )
        index_change_calendar_df = index_change_calendar_df.sort_values("start").reset_index(drop=True)

        if index_change_calendar_df["start"][0].month == index_change_calendar_df["start"][1].month:
            index_change_calendar_df.loc[1, "start"] = index_change_calendar_df["start"][0].replace(
                month=index_change_calendar_df["start"][0].month + 1, day=1
            )

        loan_end_date = self.start_date + self.duration_months * relativedelta(months=1)
        index_change_calendar_df["duration_till_end_of_loan"] = (
            loan_end_date - index_change_calendar_df["start"]
        ).dt.days / 30.44  # Convert to approximate months
        index_change_calendar_df["duration_till_end_of_loan"] = index_change_calendar_df[
            "duration_till_end_of_loan"
        ].astype(float)
        index_change_calendar_df["duration_till_end_of_loan"] = (
            index_change_calendar_df["duration_till_end_of_loan"].round().astype(int)
        )

        for row_i, row in index_change_calendar_df.iterrows():
            start_value = self.value
            if projected_df_per_period:
                i = projected_df_per_period[row_i - 1].date.searchsorted(row["start"]) - 1
                start_value = projected_df_per_period[row_i - 1].iloc[i, projected_df.columns.get_loc(VALUE)]

            periods = range(1, row["duration_till_end_of_loan"] + 1)
            rate_decimal = self.yearly_interest_rate + row["rate_change"] / 100
            duration = row["duration_till_end_of_loan"]

            date_list = [row["start"].replace(day=1) + x * relativedelta(months=1) for x in range(duration)]

            monthly_rate_decimal = rate_decimal / 12
            interest_payment = npf.ipmt(rate=monthly_rate_decimal, per=periods, nper=duration, pv=-start_value)

            principal_payment = npf.ppmt(rate=monthly_rate_decimal, per=periods, nper=duration, pv=-start_value)

            d = {
                "id": self.id,
                "date": date_list,
                "interest_payment": interest_payment,
                "principal_payment": principal_payment,
            }

            projected_df = pd.DataFrame.from_dict(d)

            projected_df[CASH_FLOW] = projected_df["interest_payment"] + projected_df["principal_payment"]
            projected_df[VALUE] = start_value - projected_df["principal_payment"].cumsum()
            projected_df_per_period[row_i] = projected_df

        complete_projected_df = pd.DataFrame
        period_ids = sorted(list(projected_df_per_period.keys()), reverse=True)
        for period in period_ids:
            df = projected_df_per_period[period]
            if complete_projected_df.empty:
                complete_projected_df = df
            else:
                min_date_so_far = complete_projected_df["date"].min()
                complete_projected_df = pd.concat([complete_projected_df, df.loc[df.date < min_date_so_far]])
        if self.repayment_date:
            complete_projected_df = complete_projected_df[complete_projected_df["date"] < self.repayment_date]
        return complete_projected_df

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """Serialize prime-pegged loan to dictionary."""
        base_dict = super().to_dict()
        base_dict["type"] = "prime_pegged"
        # Note: IndexTracker needs to be handled separately during deserialization
        return base_dict

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any], index_tracker: Any) -> 'LoanPrimePegged':
        """
        Deserialize prime-pegged loan from dictionary.

        Args:
            data: Dictionary representation
            index_tracker: IndexTracker instance (must be provided separately)

        Returns:
            LoanPrimePegged instance
        """
        loan = cls(
            loan_id=data["id"],
            value=data["value"],
            base_interest_rate_annual_pct=data["interest_rate_annual_pct"],
            duration_months=data["duration_months"],
            start_date=data["start_date"],
            index_tracker=index_tracker,
        )

        if data.get("repayment_date"):
            loan.repayment_date = parse_date(data["repayment_date"], normalize_to_month_start=True)

        loan.history = data.get("history", [])
        loan.collateral_asset = data.get("collateral_asset")

        return loan


class LoanCPIPegged(LoanFixed):
    """
    Loan with principal pegged to Consumer Price Index (CPI).

    The principal is adjusted monthly based on CPI changes, then standard
    amortization is applied to the adjusted principal.

    Attributes:
        index_tracker: IndexTracker instance with CPI history
        expected_cpi_increase_percent_yearly: Expected annual CPI increase for future projections
    """

    @error_handler
    def __init__(
        self,
        loan_id: str,
        value: float,
        base_interest_rate_annual_pct: float,
        duration_months: int,
        start_date: Union[str, datetime, pd.Timestamp],
        index_tracker: Any,  # IndexTracker type
        expected_cpi_increase_percent_yearly: float = 3,
    ):
        super().__init__(loan_id, value, base_interest_rate_annual_pct, duration_months, start_date)
        self.index_tracker = index_tracker
        self.expected_cpi_increase_percent_yearly = expected_cpi_increase_percent_yearly

    @error_handler
    def get_projection(self) -> pd.DataFrame:
        """
        Calculate loan projection with CPI-adjusted principal.

        Returns:
            DataFrame with amortization schedule adjusted for CPI changes
        """
        # Build full monthly CPI timeline from start_date for loan duration
        try:
            cpi_history = self.index_tracker.get_index_change_history(EIndexType.CPI).copy()
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve CPI history from IndexTracker: {e}")

        if cpi_history.empty:
            raise RuntimeError("No CPI data available from IndexTracker. Cannot calculate CPI-pegged loan projection.")

        # Validate required columns
        required_cols = ["date", "cpi"]
        missing_cols = [col for col in required_cols if col not in cpi_history.columns]
        if missing_cols:
            raise RuntimeError(f"CPI data missing required columns: {missing_cols}")

        # cpi_history has columns: date (month start), cpi, change, change_percent
        # Dates should already be properly formatted by IndexTracker
        start = self.start_date
        end = self.start_date + relativedelta(months=self.duration_months)
        monthly_idx = pd.date_range(start=start, end=end, freq="MS")

        # The date column should already be datetime from IndexTracker
        if not pd.api.types.is_datetime64_any_dtype(cpi_history["date"]):
            cpi_history["date"] = pd.to_datetime(cpi_history["date"], errors="coerce")

        cpi_history = cpi_history.dropna(subset=["date"]).drop_duplicates("date").set_index("date").sort_index()
        # Normalize to month start
        cpi_history.index = cpi_history.index.to_period("M").to_timestamp()
        # Generate baseline CPI series
        cpi_series = cpi_history["cpi"]
        # Fill forward and extend using expected yearly CPI increase for missing future months
        if cpi_series.empty:
            raise RuntimeError("CPI series empty after processing for CPI pegged loan projection")
        # Reindex
        cpi_series = cpi_series.reindex(monthly_idx, method="ffill")
        # For future beyond known CPI, project using expected annual increase evenly monthly
        monthly_inflation_factor = (1 + self.expected_cpi_increase_percent_yearly / 100) ** (1 / 12) - 1
        for d in monthly_idx:
            if pd.isna(cpi_series.loc[d]):
                prev = cpi_series.loc[cpi_series.index[cpi_series.index < d].max()]
                cpi_series.loc[d] = prev * (1 + monthly_inflation_factor)
        # Compute cumulative inflation factor relative to first month
        base_cpi = cpi_series.iloc[0]
        inflation_factor = cpi_series / base_cpi
        # Amortization with CPI-adjusted principal: assume principal is adjusted monthly before payment
        monthly_rate_decimal = annual_pct_to_monthly_decimal(self.interest_rate_annual_pct)
        # We create schedule iteratively
        remaining_principal = -self.value  # positive principal
        rows = []
        for i, current_date in enumerate(monthly_idx[: self.duration_months]):
            # Adjust principal for inflation relative to previous month
            if i > 0:
                infl_adj = inflation_factor.iloc[i] / inflation_factor.iloc[i - 1]
                remaining_principal *= infl_adj
            interest_payment = remaining_principal * monthly_rate_decimal
            # Compute annuity payment based on original schedule but applied to current adjusted principal balance
            annuity_payment = npf.pmt(monthly_rate_decimal, self.duration_months - i, -remaining_principal)
            principal_payment = annuity_payment - interest_payment
            remaining_principal -= principal_payment
            rows.append(
                {
                    "id": self.id,
                    "date": current_date,
                    "interest_payment": interest_payment,
                    "principal_payment": principal_payment,
                    CASH_FLOW: -annuity_payment,  # Negative because it's a payment (outgoing cash flow)
                    VALUE: -remaining_principal,  # store as negative liability value
                }
            )
            if remaining_principal <= 0:
                break
        df = pd.DataFrame(rows)
        if self.repayment_date:
            df = df[df["date"] < self.repayment_date]
        return df

    @error_handler
    def to_dict(self) -> Dict[str, Any]:
        """Serialize CPI-pegged loan to dictionary."""
        base_dict = super().to_dict()
        base_dict["type"] = "cpi_pegged"
        base_dict["expected_cpi_increase_percent_yearly"] = self.expected_cpi_increase_percent_yearly
        # Note: IndexTracker needs to be handled separately during deserialization
        return base_dict

    @classmethod
    @error_handler
    def from_dict(cls, data: Dict[str, Any], index_tracker: Any) -> 'LoanCPIPegged':
        """
        Deserialize CPI-pegged loan from dictionary.

        Args:
            data: Dictionary representation
            index_tracker: IndexTracker instance (must be provided separately)

        Returns:
            LoanCPIPegged instance
        """
        loan = cls(
            loan_id=data["id"],
            value=data["value"],
            base_interest_rate_annual_pct=data["interest_rate_annual_pct"],
            duration_months=data["duration_months"],
            start_date=data["start_date"],
            index_tracker=index_tracker,
            expected_cpi_increase_percent_yearly=data.get("expected_cpi_increase_percent_yearly", 3),
        )

        if data.get("repayment_date"):
            loan.repayment_date = parse_date(data["repayment_date"], normalize_to_month_start=True)

        loan.history = data.get("history", [])
        loan.collateral_asset = data.get("collateral_asset")

        return loan


# Module metadata
__version__ = "2.0.0"
__author__ = "FPlan Development Team"
__description__ = "Loan models for FPlan v2 with database serialization support"
