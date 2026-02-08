"""
Index Tracker for FPlan v2.

Tracks historical changes in financial indices (Prime interest rate, CPI)
for use with variable-rate loans. Ported from v1 with preserved calculation logic.

Classes:
    IndexTracker: Main tracker class for loading and processing index histories
"""

from typing import Dict
import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta

from fplan_v2.core.constants import EIndexType
from fplan_v2.utils.error_utils import error_handler


class IndexTracker:
    """
    Tracks historical changes in financial indices (Prime rate, CPI).

    Used by LoanPrimePegged and LoanCPIPegged to calculate payment schedules
    based on historical index changes.

    Attributes:
        start_date: Start date for index tracking
        duration: Duration in months to track
        indices: Dictionary mapping index types to raw DataFrames
        index_history: Prepared index history data for each index type
    """

    def __init__(self, start_date: pd.Timestamp = None, duration: int = 0):
        """
        Initialize IndexTracker.

        Args:
            start_date: Start date for tracking (normalized to month start)
            duration: Duration in months
        """
        self.start_date = start_date
        self.duration = duration
        self.indices: Dict[str, pd.DataFrame] = {}
        self.index_history: Dict[str, pd.DataFrame] = {}

    @error_handler
    def add_index_file(self, index_type: str, df: pd.DataFrame):
        """
        Add index data from a DataFrame.

        Args:
            index_type: Type of index (EIndexType.PRIME or EIndexType.CPI)
            df: DataFrame with index data
        """
        self.indices[index_type] = df

    @error_handler
    def prepare_index_histories(self):
        """Prepare index histories for all loaded indices."""
        for index_type in self.indices.keys():
            if index_type == EIndexType.PRIME:
                self.index_history[index_type] = self.prepare_prime_index_history(
                    index_type, self.start_date, self.duration
                )
            elif index_type == EIndexType.CPI:
                self.index_history[index_type] = self.prepare_cpi_history(self.start_date, self.duration)

    @error_handler
    def drop_consecutive_duplicate_rates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove consecutive rows with duplicate rates.

        Args:
            df: DataFrame with 'rate' column

        Returns:
            DataFrame with consecutive duplicates removed
        """
        cols = ["rate"]
        de_dup = df.loc[(df[cols].shift() != df[cols]).any(axis=1)]
        return de_dup

    @error_handler
    def get_index_change_history(self, index_type: str) -> pd.DataFrame:
        """
        Get the prepared index change history for a given index type.

        Args:
            index_type: Type of index (EIndexType.PRIME or EIndexType.CPI)

        Returns:
            DataFrame with prepared index history
        """
        return self.index_history[index_type]

    @error_handler
    def prepare_cpi_history(self, start_date: pd.Timestamp, duration: int) -> pd.DataFrame:
        """
        Prepare CPI history data.

        Args:
            start_date: Loan start date
            duration: Loan duration in months

        Returns:
            DataFrame with CPI history prepared for loan calculations
        """
        df = self.indices[EIndexType.CPI].copy()

        # CPI data format is MM/YY - convert to proper datetime
        # Convert MM/YY to 01/MM/YYYY format for month start dates
        df['date'] = df['date'].apply(lambda x: f"01/{x}")
        try:
            df['date'] = pd.to_datetime(df['date'], format="%d/%m/%y")
        except ValueError:
            # Fallback for different date formats
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            if df['date'].isna().any():
                print(f"Warning: Some CPI dates could not be parsed. Missing data may affect calculations.")
                df = df.dropna(subset=['date'])

        if df.empty:
            raise RuntimeError("No valid CPI data available after date parsing")

        start_date = pd.to_datetime(start_date, format="%d/%m/%Y")
        df = df[df.date >= start_date]

        if df.empty:
            print(f"Warning: No CPI data available from start date {start_date}. Using available data from earliest date.")
            df = self.indices[EIndexType.CPI].copy()
            df['date'] = df['date'].apply(lambda x: f"01/{x}")
            df['date'] = pd.to_datetime(df['date'], format="%d/%m/%y", errors='coerce')
            df = df.dropna(subset=['date'])

        df = df.sort_values("date")

        loan_end_date = start_date + duration * relativedelta(months=1)
        df["duration_till_end_of_loan"] = (loan_end_date - df["date"]).dt.days / 30.44  # Convert to approximate months
        df["duration_till_end_of_loan"] = df["duration_till_end_of_loan"].astype(float)
        df["duration_till_end_of_loan"] = df["duration_till_end_of_loan"].round().astype(int)

        df = df.reset_index(drop=True)
        return df

    @error_handler
    def prepare_prime_index_history(self, index_type: str, start_date: pd.Timestamp, duration: int) -> pd.DataFrame:
        """
        Prepare prime rate index history.

        Args:
            index_type: Should be EIndexType.PRIME
            start_date: Loan start date
            duration: Loan duration in months

        Returns:
            DataFrame with prime rate history prepared for loan calculations
        """
        # for prime
        df = self.drop_consecutive_duplicate_rates(self.indices[index_type]).copy()

        df["start"] = pd.to_datetime(df["start"], dayfirst=True)
        df = df.sort_values("start")

        start_date_rate_index = df.start.searchsorted(start_date) - 1
        start_date_rate = df.iloc[start_date_rate_index]["rate"]
        df = df[df.start > start_date]

        # insert start of loan date
        start_date = pd.to_datetime(start_date, format="%d/%m/%Y")
        df = df.sort_values("start")

        loan_end_date = start_date + duration * relativedelta(months=1)
        df["duration_till_end_of_loan"] = (loan_end_date - df["start"]).dt.days / 30.44  # Convert to approximate months
        df["duration_till_end_of_loan"] = df["duration_till_end_of_loan"].astype(float)
        df["duration_till_end_of_loan"] = df["duration_till_end_of_loan"].round().astype(int)
        df = df.reset_index(drop=True)

        df["rate_change"] = df["rate"].diff()
        df["rate_change"] = df["rate_change"].fillna(0)

        return df


# Module metadata
__version__ = "2.0.0"
__author__ = "FPlan Development Team"
__description__ = "Stub index tracker for FPlan v2 (DB-backed version coming)"
