"""
Demo mode endpoints for FPlan v2.

Provides reset and status endpoints for the demo user showcase.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from fplan_v2.api.auth import get_current_user, is_demo_user
from fplan_v2.db.connection import get_db_session
from fplan_v2.db.models import User
from fplan_v2.scripts.seed_demo_data import delete_demo_data, seed_demo_data

router = APIRouter()


@router.get("/status")
async def demo_status(user: User = Depends(get_current_user)):
    """Return whether the current session is in demo mode."""
    return {"is_demo": is_demo_user(user)}


@router.post("/reset")
async def reset_demo(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Delete all demo user data and re-seed. Only works for the demo user."""
    if not is_demo_user(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reset is only available for the demo user.",
        )

    delete_demo_data(db)
    seed_demo_data(db)
    return {"status": "ok", "message": "Demo data has been reset."}
