"""
Asset repository for database operations.

Provides CRUD operations and queries specific to Asset entities.
"""

from typing import List, Optional
from datetime import date

from sqlalchemy.orm import Session

from fplan_v2.db.models import Asset
from fplan_v2.db.repositories.base import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    """Repository for Asset database operations."""

    def __init__(self, session: Session):
        """Initialize asset repository."""
        super().__init__(Asset, session)

    def get_by_external_id(self, user_id: int, external_id: str, portfolio_id: Optional[int] = None) -> Optional[Asset]:
        """
        Get asset by user_id and external_id, optionally scoped to a portfolio.

        Args:
            user_id: User ID
            external_id: External identifier
            portfolio_id: If provided, scope the lookup to this portfolio
                (external_id is unique per portfolio, not per user)

        Returns:
            Asset instance or None if not found
        """
        query = self.session.query(Asset).filter(
            Asset.user_id == user_id, Asset.external_id == external_id
        )
        if portfolio_id is not None:
            query = query.filter(Asset.portfolio_id == portfolio_id)
        return query.first()

    def get_by_type(self, user_id: int, asset_type: str, portfolio_id: Optional[int] = None) -> List[Asset]:
        """
        Get all assets of a specific type for a user, optionally scoped to a portfolio.

        Args:
            user_id: User ID
            asset_type: Asset type ('real_estate', 'stock', 'pension', 'cash')
            portfolio_id: If provided, scope to this portfolio

        Returns:
            List of Asset instances
        """
        query = self.session.query(Asset).filter(
            Asset.user_id == user_id, Asset.asset_type == asset_type
        )
        if portfolio_id is not None:
            query = query.filter(Asset.portfolio_id == portfolio_id)
        return query.all()

    def get_active_assets(self, user_id: int, as_of_date: date) -> List[Asset]:
        """
        Get all active assets as of a specific date.

        An asset is active if:
        - start_date <= as_of_date
        - sell_date is NULL or sell_date > as_of_date

        Args:
            user_id: User ID
            as_of_date: Reference date

        Returns:
            List of active Asset instances
        """
        return (
            self.session.query(Asset)
            .filter(
                Asset.user_id == user_id,
                Asset.start_date <= as_of_date,
                (Asset.sell_date.is_(None)) | (Asset.sell_date > as_of_date),
            )
            .all()
        )

    def get_with_loans(self, user_id: int) -> List[Asset]:
        """
        Get all assets that have associated loans (collateral).

        Args:
            user_id: User ID

        Returns:
            List of Asset instances with loans
        """
        from fplan_v2.db.models import Loan

        return (
            self.session.query(Asset)
            .join(Loan, Loan.collateral_asset_id == Asset.id)
            .filter(Asset.user_id == user_id)
            .distinct()
            .all()
        )

    def calculate_total_value(self, user_id: int) -> float:
        """
        Calculate total current value of all assets for a user.

        Args:
            user_id: User ID

        Returns:
            Total asset value (sum of current_value or original_value)
        """
        from sqlalchemy import func, case

        result = (
            self.session.query(
                func.sum(
                    case(
                        (Asset.current_value.isnot(None), Asset.current_value),
                        else_=Asset.original_value,
                    )
                )
            )
            .filter(Asset.user_id == user_id)
            .scalar()
        )

        return float(result) if result else 0.0
