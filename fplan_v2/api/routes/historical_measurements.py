"""
Historical Measurement CRUD API endpoints.

Provides REST API for logging and querying actual values of assets and loans over time.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from fplan_v2.api.schemas import (
    HistoricalMeasurementCreate,
    HistoricalMeasurementUpdate,
    HistoricalMeasurementResponse,
)
from fplan_v2.api.auth import get_current_user, get_current_portfolio
from fplan_v2.db.connection import get_db_session
from fplan_v2.db.models import Portfolio, User
from fplan_v2.db.repositories import (
    HistoricalMeasurementRepository,
    AssetRepository,
    LoanRepository,
)


router = APIRouter()


def _sync_entity_value(db: Session, user_id: int, entity_type: str, entity_id: int, portfolio_id: int = None) -> None:
    """
    Sync the entity's current value to its latest-by-date measurement.

    The displayed current_value/current_balance must always reflect the most
    recent measurement_date, not the most recently inserted row — backfilled
    older measurements must not clobber a newer value. If the entity has no
    measurements left, the entity value is left unchanged.
    """
    repo = HistoricalMeasurementRepository(db)
    measurements = repo.get_by_entity(user_id, entity_type, entity_id, portfolio_id=portfolio_id)
    if not measurements:
        return

    latest = max(measurements, key=lambda m: (m.measurement_date, m.id))
    if entity_type == "asset":
        AssetRepository(db).update(entity_id, current_value=latest.actual_value)
    elif entity_type == "loan":
        LoanRepository(db).update(entity_id, current_balance=latest.actual_value)


@router.post("/", response_model=HistoricalMeasurementResponse, status_code=status.HTTP_201_CREATED)
def create_measurement(
    measurement: HistoricalMeasurementCreate,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    repo = HistoricalMeasurementRepository(db)

    try:
        new_measurement = repo.create(
            user_id=current_user.id,
            portfolio_id=current_portfolio.id,
            **measurement.model_dump(),
        )

        # Sync the entity's current_value/current_balance to the latest-by-date measurement
        _sync_entity_value(db, current_user.id, measurement.entity_type, measurement.entity_id, portfolio_id=current_portfolio.id)

        db.commit()
        db.refresh(new_measurement)
        return new_measurement
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create measurement: {str(e)}",
        )


@router.get("/", response_model=List[HistoricalMeasurementResponse])
def list_all_measurements(
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    repo = HistoricalMeasurementRepository(db)
    return repo.get_all(user_id=current_user.id, portfolio_id=current_portfolio.id)


@router.get("/{measurement_id}", response_model=HistoricalMeasurementResponse)
def get_measurement(
    measurement_id: int,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    repo = HistoricalMeasurementRepository(db)
    measurement = repo.get_by_id(measurement_id)

    if not measurement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Measurement {measurement_id} not found",
        )
    if measurement.user_id != current_user.id or measurement.portfolio_id != current_portfolio.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this measurement",
        )

    return measurement


@router.get("/entity/{entity_type}/{entity_id}", response_model=List[HistoricalMeasurementResponse])
def list_measurements(
    entity_type: str,
    entity_id: int,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    if entity_type not in ("asset", "loan"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entity_type must be 'asset' or 'loan'",
        )

    repo = HistoricalMeasurementRepository(db)
    measurements = repo.get_by_entity(current_user.id, entity_type, entity_id, portfolio_id=current_portfolio.id)
    return measurements


@router.put("/{measurement_id}", response_model=HistoricalMeasurementResponse)
def update_measurement(
    measurement_id: int,
    measurement_update: HistoricalMeasurementUpdate,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    repo = HistoricalMeasurementRepository(db)

    existing = repo.get_by_id(measurement_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Measurement {measurement_id} not found",
        )
    if existing.user_id != current_user.id or existing.portfolio_id != current_portfolio.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this measurement",
        )

    try:
        update_data = {k: v for k, v in measurement_update.model_dump().items() if v is not None}
        updated = repo.update(measurement_id, **update_data)
        _sync_entity_value(db, current_user.id, updated.entity_type, updated.entity_id, portfolio_id=current_portfolio.id)
        db.commit()
        db.refresh(updated)
        return updated
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update measurement: {str(e)}",
        )


@router.delete("/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_measurement(
    measurement_id: int,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    repo = HistoricalMeasurementRepository(db)

    existing = repo.get_by_id(measurement_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Measurement {measurement_id} not found",
        )
    if existing.user_id != current_user.id or existing.portfolio_id != current_portfolio.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this measurement",
        )

    try:
        entity_type, entity_id = existing.entity_type, existing.entity_id
        repo.delete(measurement_id)
        _sync_entity_value(db, current_user.id, entity_type, entity_id, portfolio_id=current_portfolio.id)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete measurement: {str(e)}",
        )
