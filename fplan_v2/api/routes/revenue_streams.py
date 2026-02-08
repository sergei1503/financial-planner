"""
Revenue Stream CRUD API endpoints.

Provides REST API for managing user revenue streams.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from fplan_v2.api.schemas import RevenueStreamCreate, RevenueStreamUpdate, RevenueStreamResponse
from fplan_v2.api.auth import get_current_user
from fplan_v2.db.connection import get_db_session
from fplan_v2.db.models import User
from fplan_v2.db.repositories import RevenueStreamRepository


router = APIRouter()


@router.post("/", response_model=RevenueStreamResponse, status_code=status.HTTP_201_CREATED)
def create_revenue_stream(
    stream: RevenueStreamCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repo = RevenueStreamRepository(db)

    try:
        new_stream = repo.create(user_id=current_user.id, **stream.model_dump())
        db.commit()
        db.refresh(new_stream)
        return new_stream
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create revenue stream: {str(e)}",
        )


@router.get("/{stream_id}", response_model=RevenueStreamResponse)
def get_revenue_stream(
    stream_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repo = RevenueStreamRepository(db)
    stream = repo.get_by_id(stream_id)

    if not stream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Revenue stream {stream_id} not found",
        )

    if stream.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this revenue stream",
        )

    return stream


@router.get("/", response_model=List[RevenueStreamResponse])
def list_revenue_streams(
    stream_type: str = None,
    asset_id: int = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repo = RevenueStreamRepository(db)

    if stream_type:
        streams = repo.get_by_type(current_user.id, stream_type)
    elif asset_id:
        streams = repo.get_by_asset(asset_id)
    else:
        streams = repo.get_all(user_id=current_user.id, limit=limit, offset=offset)

    return streams


@router.put("/{stream_id}", response_model=RevenueStreamResponse)
def update_revenue_stream(
    stream_id: int,
    stream_update: RevenueStreamUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repo = RevenueStreamRepository(db)

    existing = repo.get_by_id(stream_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Revenue stream {stream_id} not found",
        )
    if existing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this revenue stream",
        )

    try:
        update_data = {k: v for k, v in stream_update.model_dump().items() if v is not None}
        updated_stream = repo.update(stream_id, **update_data)
        db.commit()
        db.refresh(updated_stream)
        return updated_stream
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update revenue stream: {str(e)}",
        )


@router.delete("/{stream_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_revenue_stream(
    stream_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repo = RevenueStreamRepository(db)

    existing = repo.get_by_id(stream_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Revenue stream {stream_id} not found",
        )
    if existing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this revenue stream",
        )

    try:
        repo.delete(stream_id)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete revenue stream: {str(e)}",
        )
