"""
Portfolio management API endpoints.

A user owns one or more portfolios; every asset, loan, revenue stream, cash flow,
historical measurement and scenario belongs to one. These endpoints let the UI list,
create, rename, delete and switch the default portfolio, plus export a portfolio to a
self-contained JSON document and import one back as a fresh portfolio (the transport
for moving data between environments, e.g. local -> Neon).

Invariant: each user has exactly one default portfolio at all times.
"""

import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from fplan_v2.api.auth import get_current_user
from fplan_v2.api.schemas import PortfolioCreate, PortfolioUpdate, PortfolioResponse
from fplan_v2.db.connection import get_db_session
from fplan_v2.db.models import Portfolio, User
from fplan_v2.scripts.portfolio_io import export_portfolio, import_portfolio


router = APIRouter()


def _get_owned_portfolio(db: Session, user: User, portfolio_id: int) -> Portfolio:
    """Fetch a portfolio, 404-ing if it doesn't exist or isn't owned by the user."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
        .first()
    )
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio {portfolio_id} not found",
        )
    return portfolio


@router.get("", response_model=List[PortfolioResponse])
def list_portfolios(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """List the user's portfolios, default first."""
    return (
        db.query(Portfolio)
        .filter(Portfolio.user_id == current_user.id)
        .order_by(Portfolio.is_default.desc(), Portfolio.id)
        .all()
    )


@router.post("", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    payload: PortfolioCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Create a new (empty) portfolio. Becomes the default if it's the user's first."""
    is_first = (
        db.query(Portfolio).filter(Portfolio.user_id == current_user.id).count() == 0
    )
    portfolio = Portfolio(user_id=current_user.id, name=payload.name, is_default=is_first)
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


@router.put("/{portfolio_id}", response_model=PortfolioResponse)
def rename_portfolio(
    portfolio_id: int,
    payload: PortfolioUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Rename a portfolio."""
    portfolio = _get_owned_portfolio(db, current_user, portfolio_id)
    if payload.name is not None:
        portfolio.name = payload.name
    db.commit()
    db.refresh(portfolio)
    return portfolio


@router.post("/{portfolio_id}/set-default", response_model=PortfolioResponse)
def set_default_portfolio(
    portfolio_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Make a portfolio the user's default, clearing the flag on the others."""
    portfolio = _get_owned_portfolio(db, current_user, portfolio_id)
    db.query(Portfolio).filter(
        Portfolio.user_id == current_user.id, Portfolio.id != portfolio.id
    ).update({"is_default": False})
    portfolio.is_default = True
    db.commit()
    db.refresh(portfolio)
    return portfolio


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(
    portfolio_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Delete a portfolio (cascades to its entities). Refuses to delete the user's last
    portfolio; if the deleted one was the default, promotes the next portfolio to default.
    """
    portfolio = _get_owned_portfolio(db, current_user, portfolio_id)

    remaining = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == current_user.id, Portfolio.id != portfolio.id)
        .order_by(Portfolio.id)
        .all()
    )
    if not remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your only portfolio",
        )

    was_default = portfolio.is_default
    db.delete(portfolio)
    if was_default:
        # Promote the lowest-id remaining portfolio to default.
        remaining[0].is_default = True
    db.commit()


@router.get("/{portfolio_id}/export")
def export_portfolio_endpoint(
    portfolio_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Export a portfolio as a self-contained JSON document (for download)."""
    # Ownership check (export_portfolio itself doesn't scope by user).
    _get_owned_portfolio(db, current_user, portfolio_id)
    doc = export_portfolio(portfolio_id)
    return doc


@router.post("/import", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
async def import_portfolio_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Import a portfolio-export JSON as a new portfolio owned by the current user."""
    raw = await file.read()
    try:
        doc = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not valid JSON",
        )

    try:
        new_id = import_portfolio(doc, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    portfolio = db.query(Portfolio).filter(Portfolio.id == new_id).first()
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Import completed but the new portfolio could not be loaded",
        )
    return portfolio
