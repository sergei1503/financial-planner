"""
Loan repository for database operations.

Provides CRUD operations and queries specific to Loan entities.
"""

from typing import List, Optional
from datetime import date

from sqlalchemy.orm import Session

from fplan_v2.db.models import Loan
from fplan_v2.db.repositories.base import BaseRepository


class LoanRepository(BaseRepository[Loan]):
    """Repository for Loan database operations."""

    def __init__(self, session: Session):
        """Initialize loan repository."""
        super().__init__(Loan, session)

    def get_by_external_id(self, user_id: int, external_id: str) -> Optional[Loan]:
        """
        Get loan by user_id and external_id.

        Args:
            user_id: User ID
            external_id: External identifier

        Returns:
            Loan instance or None if not found
        """
        return (
            self.session.query(Loan)
            .filter(Loan.user_id == user_id, Loan.external_id == external_id)
            .first()
        )

    def get_by_type(self, user_id: int, loan_type: str) -> List[Loan]:
        """
        Get all loans of a specific type for a user.

        Args:
            user_id: User ID
            loan_type: Loan type ('fixed', 'prime_pegged', 'cpi_pegged', 'variable')

        Returns:
            List of Loan instances
        """
        return (
            self.session.query(Loan)
            .filter(Loan.user_id == user_id, Loan.loan_type == loan_type)
            .all()
        )

    def get_active_loans(self, user_id: int, as_of_date: date) -> List[Loan]:
        """
        Get all active loans as of a specific date.

        A loan is active if:
        - start_date <= as_of_date
        - start_date + duration_months > as_of_date

        Args:
            user_id: User ID
            as_of_date: Reference date

        Returns:
            List of active Loan instances
        """
        from sqlalchemy import func, extract

        # Calculate end date as start_date + duration_months
        return (
            self.session.query(Loan)
            .filter(
                Loan.user_id == user_id,
                Loan.start_date <= as_of_date,
                func.date(
                    Loan.start_date
                    + func.make_interval(0, Loan.duration_months)
                ) > as_of_date,
            )
            .all()
        )

    def get_by_collateral(self, asset_id: int) -> List[Loan]:
        """
        Get all loans using a specific asset as collateral.

        Args:
            asset_id: Asset ID used as collateral

        Returns:
            List of Loan instances
        """
        return (
            self.session.query(Loan)
            .filter(Loan.collateral_asset_id == asset_id)
            .all()
        )

    def calculate_total_balance(self, user_id: int) -> float:
        """
        Calculate total current balance of all loans for a user.

        Args:
            user_id: User ID

        Returns:
            Total loan balance (sum of current_balance or original_value)
        """
        from sqlalchemy import func, case

        result = (
            self.session.query(
                func.sum(
                    case(
                        (Loan.current_balance.isnot(None), Loan.current_balance),
                        else_=Loan.original_value,
                    )
                )
            )
            .filter(Loan.user_id == user_id)
            .scalar()
        )

        return float(result) if result else 0.0

    def calculate_monthly_payments(self, user_id: int) -> float:
        """
        Calculate estimated total monthly loan payments for a user.

        Uses simple amortization formula:
        M = P * [r(1+r)^n] / [(1+r)^n - 1]

        Where:
        - M = monthly payment
        - P = principal (current_balance or original_value)
        - r = monthly interest rate (annual_pct / 12 / 100)
        - n = number of remaining months

        Args:
            user_id: User ID

        Returns:
            Estimated total monthly payment amount
        """
        loans = self.get_all(user_id=user_id)
        total_payment = 0.0

        for loan in loans:
            principal = float(loan.current_balance if loan.current_balance else loan.original_value)
            annual_rate = float(loan.interest_rate_annual_pct)
            monthly_rate = annual_rate / 12 / 100

            if monthly_rate == 0:
                # No interest, just divide principal by months
                payment = principal / loan.duration_months
            else:
                # Amortization formula
                numerator = monthly_rate * ((1 + monthly_rate) ** loan.duration_months)
                denominator = ((1 + monthly_rate) ** loan.duration_months) - 1
                payment = principal * (numerator / denominator)

            total_payment += payment

        return total_payment
