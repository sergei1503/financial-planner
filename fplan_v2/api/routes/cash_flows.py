"""
Cash flow CRUD API endpoints.

Provides REST API for managing user cash flows (deposits/withdrawals).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from fplan_v2.api.schemas import CashFlowCreate, CashFlowUpdate, CashFlowResponse
from fplan_v2.api.auth import get_current_user
from fplan_v2.db.connection import get_db_session
from fplan_v2.db.models import User
from fplan_v2.db.repositories import CashFlowRepository


router = APIRouter()


@router.post("/", response_model=CashFlowResponse, status_code=status.HTTP_201_CREATED)
def create_cash_flow(
    cash_flow: CashFlowCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Create a new cash flow (deposit or withdrawal)."""
    repo = CashFlowRepository(db)

    try:
        new_cf = repo.create(user_id=current_user.id, **cash_flow.model_dump())
        db.commit()
        db.refresh(new_cf)
        return new_cf
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create cash flow: {str(e)}",
        )


@router.get("/", response_model=List[CashFlowResponse])
def list_cash_flows(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """List all cash flows for the current user."""
    repo = CashFlowRepository(db)
    return repo.get_by_user(current_user.id)


@router.get("/asset/{asset_id}", response_model=List[CashFlowResponse])
def get_cash_flows_by_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get cash flows for a specific asset."""
    repo = CashFlowRepository(db)
    return repo.get_by_asset(current_user.id, asset_id)


@router.get("/{cash_flow_id}", response_model=CashFlowResponse)
def get_cash_flow(
    cash_flow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get a single cash flow by ID."""
    repo = CashFlowRepository(db)
    cf = repo.get_by_id(cash_flow_id)

    if not cf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cash flow {cash_flow_id} not found",
        )

    if cf.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this cash flow",
        )

    return cf


@router.put("/{cash_flow_id}", response_model=CashFlowResponse)
def update_cash_flow(
    cash_flow_id: int,
    cash_flow_update: CashFlowUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update an existing cash flow."""
    repo = CashFlowRepository(db)

    existing = repo.get_by_id(cash_flow_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cash flow {cash_flow_id} not found",
        )
    if existing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this cash flow",
        )

    try:
        update_data = {k: v for k, v in cash_flow_update.model_dump().items() if v is not None}
        updated_cf = repo.update(cash_flow_id, **update_data)
        db.commit()
        db.refresh(updated_cf)
        return updated_cf
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update cash flow: {str(e)}",
        )


@router.delete("/{cash_flow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cash_flow(
    cash_flow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Delete a cash flow."""
    repo = CashFlowRepository(db)

    existing = repo.get_by_id(cash_flow_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cash flow {cash_flow_id} not found",
        )
    if existing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this cash flow",
        )

    try:
        repo.delete(cash_flow_id)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete cash flow: {str(e)}",
        )
