"""
Cash flow repository for database operations on cash_flows table.
"""

from typing import List, Optional

from fplan_v2.db.repositories.base import BaseRepository
from fplan_v2.db.models import CashFlow


class CashFlowRepository(BaseRepository[CashFlow]):
    """Repository for CashFlow CRUD operations."""

    def __init__(self, session):
        super().__init__(CashFlow, session)

    def get_by_asset(self, user_id: int, asset_id: int, portfolio_id: Optional[int] = None) -> List[CashFlow]:
        """Get all cash flows targeting a specific asset, optionally scoped to a portfolio."""
        query = self.session.query(CashFlow).filter(
            CashFlow.user_id == user_id, CashFlow.target_asset_id == asset_id
        )
        if portfolio_id is not None:
            query = query.filter(CashFlow.portfolio_id == portfolio_id)
        return query.all()

    def get_by_user(self, user_id: int, portfolio_id: Optional[int] = None) -> List[CashFlow]:
        """Get all cash flows for a user, optionally scoped to a portfolio."""
        query = self.session.query(CashFlow).filter(CashFlow.user_id == user_id)
        if portfolio_id is not None:
            query = query.filter(CashFlow.portfolio_id == portfolio_id)
        return query.all()
