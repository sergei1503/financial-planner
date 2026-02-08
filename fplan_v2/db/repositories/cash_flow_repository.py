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

    def get_by_asset(self, user_id: int, asset_id: int) -> List[CashFlow]:
        """Get all cash flows targeting a specific asset."""
        return (
            self.session.query(CashFlow)
            .filter(CashFlow.user_id == user_id, CashFlow.target_asset_id == asset_id)
            .all()
        )

    def get_by_user(self, user_id: int) -> List[CashFlow]:
        """Get all cash flows for a user."""
        return (
            self.session.query(CashFlow)
            .filter(CashFlow.user_id == user_id)
            .all()
        )
