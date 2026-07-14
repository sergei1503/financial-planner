"""
Asset CRUD API endpoints.

Provides REST API for managing user assets.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from fplan_v2.api.schemas import AssetCreate, AssetUpdate, AssetResponse
from fplan_v2.api.auth import get_current_user, get_current_portfolio
from fplan_v2.db.connection import get_db_session
from fplan_v2.db.models import Portfolio, User
from fplan_v2.db.repositories import AssetRepository


router = APIRouter()


@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(
    asset: AssetCreate,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    repo = AssetRepository(db)

    # Check if external_id already exists in this portfolio (external_id is unique per portfolio)
    existing = repo.get_by_external_id(current_user.id, asset.external_id, portfolio_id=current_portfolio.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Asset with external_id '{asset.external_id}' already exists in this portfolio",
        )

    try:
        new_asset = repo.create(user_id=current_user.id, portfolio_id=current_portfolio.id, **asset.model_dump())
        db.commit()
        db.refresh(new_asset)
        return new_asset
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create asset: {str(e)}",
        )


@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    repo = AssetRepository(db)
    asset = repo.get_by_id(asset_id)

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found",
        )

    if asset.user_id != current_user.id or asset.portfolio_id != current_portfolio.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this asset",
        )

    return asset


@router.get("/", response_model=List[AssetResponse])
def list_assets(
    asset_type: str = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    repo = AssetRepository(db)

    if asset_type:
        assets = repo.get_by_type(current_user.id, asset_type, portfolio_id=current_portfolio.id)
    else:
        assets = repo.get_all(user_id=current_user.id, portfolio_id=current_portfolio.id, limit=limit, offset=offset)

    return assets


@router.put("/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: int,
    asset_update: AssetUpdate,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    repo = AssetRepository(db)

    # Verify ownership
    existing = repo.get_by_id(asset_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found",
        )
    if existing.user_id != current_user.id or existing.portfolio_id != current_portfolio.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this asset",
        )

    try:
        update_data = asset_update.model_dump(exclude_unset=True)
        updated_asset = repo.update(asset_id, **update_data)
        db.commit()
        db.refresh(updated_asset)
        return updated_asset
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update asset: {str(e)}",
        )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    repo = AssetRepository(db)

    # Verify ownership
    existing = repo.get_by_id(asset_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found",
        )
    if existing.user_id != current_user.id or existing.portfolio_id != current_portfolio.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this asset",
        )

    try:
        repo.delete(asset_id)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete asset: {str(e)}",
        )
