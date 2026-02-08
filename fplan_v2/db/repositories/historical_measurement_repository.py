"""
Historical measurement repository for database operations.

Provides CRUD operations and queries specific to HistoricalMeasurement entities.
"""

from typing import List, Optional
from datetime import date

from sqlalchemy.orm import Session

from fplan_v2.db.models import HistoricalMeasurement
from fplan_v2.db.repositories.base import BaseRepository


class HistoricalMeasurementRepository(BaseRepository[HistoricalMeasurement]):
    """Repository for HistoricalMeasurement database operations."""

    def __init__(self, session: Session):
        """Initialize historical measurement repository."""
        super().__init__(HistoricalMeasurement, session)

    def get_by_entity(
        self,
        user_id: int,
        entity_type: str,
        entity_id: int,
    ) -> List[HistoricalMeasurement]:
        """
        Get all measurements for a specific entity, ordered by date.

        Args:
            user_id: User ID
            entity_type: 'asset' or 'loan'
            entity_id: ID of the asset or loan

        Returns:
            List of HistoricalMeasurement instances ordered by measurement_date
        """
        return (
            self.session.query(HistoricalMeasurement)
            .filter(
                HistoricalMeasurement.user_id == user_id,
                HistoricalMeasurement.entity_type == entity_type,
                HistoricalMeasurement.entity_id == entity_id,
            )
            .order_by(HistoricalMeasurement.measurement_date)
            .all()
        )

    def get_by_date_range(
        self,
        user_id: int,
        entity_type: str,
        entity_id: int,
        start_date: date,
        end_date: date,
    ) -> List[HistoricalMeasurement]:
        """
        Get measurements for an entity within a date range.

        Args:
            user_id: User ID
            entity_type: 'asset' or 'loan'
            entity_id: ID of the asset or loan
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of HistoricalMeasurement instances
        """
        return (
            self.session.query(HistoricalMeasurement)
            .filter(
                HistoricalMeasurement.user_id == user_id,
                HistoricalMeasurement.entity_type == entity_type,
                HistoricalMeasurement.entity_id == entity_id,
                HistoricalMeasurement.measurement_date >= start_date,
                HistoricalMeasurement.measurement_date <= end_date,
            )
            .order_by(HistoricalMeasurement.measurement_date)
            .all()
        )
