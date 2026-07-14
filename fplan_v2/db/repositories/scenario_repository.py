"""
Scenario repository for database operations.

Provides CRUD operations and queries specific to Scenario entities.
Note: Scenario operations do NOT bump portfolio_version since scenarios
don't modify the real portfolio.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from fplan_v2.db.models import Scenario
from fplan_v2.db.repositories.base import BaseRepository


class ScenarioRepository(BaseRepository[Scenario]):
    """Repository for Scenario database operations."""

    def __init__(self, session: Session):
        """Initialize scenario repository."""
        super().__init__(Scenario, session)

    def create(self, **kwargs) -> Scenario:
        """Create a new scenario without bumping portfolio_version."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        self.session.flush()
        return instance

    def update(self, id: int, **kwargs) -> Optional[Scenario]:
        """Update a scenario without bumping portfolio_version."""
        instance = self.get_by_id(id)
        if not instance:
            return None

        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        self.session.flush()
        return instance

    def get_by_user(self, user_id: int, portfolio_id: Optional[int] = None) -> List[Scenario]:
        """
        Get all scenarios for a user, optionally scoped to a portfolio.

        Args:
            user_id: User ID
            portfolio_id: If provided, scope to this portfolio

        Returns:
            List of Scenario instances
        """
        query = self.session.query(Scenario).filter(Scenario.user_id == user_id)
        if portfolio_id is not None:
            query = query.filter(Scenario.portfolio_id == portfolio_id)
        return query.order_by(Scenario.updated_at.desc()).all()

    def get_active(self, user_id: int) -> Optional[Scenario]:
        """
        Get the currently active scenario for a user.

        Args:
            user_id: User ID

        Returns:
            Active Scenario instance or None
        """
        return (
            self.session.query(Scenario)
            .filter(Scenario.user_id == user_id, Scenario.is_active == True)
            .first()
        )
