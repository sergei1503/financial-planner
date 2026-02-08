"""
Revenue Stream repository for database operations.

Provides CRUD operations and queries specific to RevenueStream entities.
"""

from typing import List, Optional
from datetime import date

from sqlalchemy.orm import Session

from fplan_v2.db.models import RevenueStream
from fplan_v2.db.repositories.base import BaseRepository


class RevenueStreamRepository(BaseRepository[RevenueStream]):
    """Repository for RevenueStream database operations."""

    def __init__(self, session: Session):
        """Initialize revenue stream repository."""
        super().__init__(RevenueStream, session)

    def get_by_type(self, user_id: int, stream_type: str) -> List[RevenueStream]:
        """
        Get all revenue streams of a specific type for a user.

        Args:
            user_id: User ID
            stream_type: Stream type ('rent', 'dividend', 'pension', 'salary')

        Returns:
            List of RevenueStream instances
        """
        return (
            self.session.query(RevenueStream)
            .filter(RevenueStream.user_id == user_id, RevenueStream.stream_type == stream_type)
            .all()
        )

    def get_by_asset(self, asset_id: int) -> List[RevenueStream]:
        """
        Get all revenue streams associated with a specific asset.

        Args:
            asset_id: Asset ID

        Returns:
            List of RevenueStream instances
        """
        return (
            self.session.query(RevenueStream)
            .filter(RevenueStream.asset_id == asset_id)
            .all()
        )

    def get_standalone(self, user_id: int) -> List[RevenueStream]:
        """
        Get all revenue streams not attached to any asset (asset_id IS NULL).

        Args:
            user_id: User ID

        Returns:
            List of standalone RevenueStream instances (e.g., salary)
        """
        return (
            self.session.query(RevenueStream)
            .filter(RevenueStream.user_id == user_id, RevenueStream.asset_id.is_(None))
            .all()
        )

    def get_active_streams(self, user_id: int, as_of_date: date) -> List[RevenueStream]:
        """
        Get all active revenue streams as of a specific date.

        A stream is active if:
        - start_date <= as_of_date
        - end_date is NULL or end_date >= as_of_date

        Args:
            user_id: User ID
            as_of_date: Reference date

        Returns:
            List of active RevenueStream instances
        """
        return (
            self.session.query(RevenueStream)
            .filter(
                RevenueStream.user_id == user_id,
                RevenueStream.start_date <= as_of_date,
                (RevenueStream.end_date.is_(None)) | (RevenueStream.end_date >= as_of_date),
            )
            .all()
        )

    def calculate_monthly_revenue(self, user_id: int, as_of_date: Optional[date] = None) -> float:
        """
        Calculate total monthly revenue for a user.

        Converts all revenue streams to monthly equivalent:
        - Monthly: as-is
        - Quarterly: amount / 3
        - Yearly: amount / 12

        Args:
            user_id: User ID
            as_of_date: Reference date (defaults to today)

        Returns:
            Total monthly revenue amount
        """
        if as_of_date is None:
            as_of_date = date.today()

        streams = self.get_active_streams(user_id, as_of_date)
        total_monthly = 0.0

        for stream in streams:
            amount = float(stream.amount)

            # Convert to monthly based on period
            if stream.period == "monthly":
                monthly_amount = amount
            elif stream.period == "quarterly":
                monthly_amount = amount / 3
            elif stream.period == "yearly":
                monthly_amount = amount / 12
            else:
                monthly_amount = amount  # Default to monthly

            # Apply tax
            tax_rate = float(stream.tax_rate) / 100
            after_tax = monthly_amount * (1 - tax_rate)

            total_monthly += after_tax

        return total_monthly
