"""
Loan CRUD API endpoints.

Provides REST API for managing user loans.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from fplan_v2.api.schemas import LoanCreate, LoanUpdate, LoanResponse
from fplan_v2.api.auth import get_current_user
from fplan_v2.db.connection import get_db_session
from fplan_v2.db.models import User
from fplan_v2.db.repositories import LoanRepository


router = APIRouter()


@router.post("/", response_model=LoanResponse, status_code=status.HTTP_201_CREATED)
def create_loan(
    loan: LoanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repo = LoanRepository(db)

    existing = repo.get_by_external_id(current_user.id, loan.external_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Loan with external_id '{loan.external_id}' already exists for this user",
        )

    try:
        new_loan = repo.create(user_id=current_user.id, **loan.model_dump())
        db.commit()
        db.refresh(new_loan)
        return new_loan
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create loan: {str(e)}",
        )


@router.get("/{loan_id}", response_model=LoanResponse)
def get_loan(
    loan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repo = LoanRepository(db)
    loan = repo.get_by_id(loan_id)

    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Loan {loan_id} not found",
        )

    if loan.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this loan",
        )

    return loan


@router.get("/", response_model=List[LoanResponse])
def list_loans(
    loan_type: str = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repo = LoanRepository(db)

    if loan_type:
        loans = repo.get_by_type(current_user.id, loan_type)
    else:
        loans = repo.get_all(user_id=current_user.id, limit=limit, offset=offset)

    return loans


@router.put("/{loan_id}", response_model=LoanResponse)
def update_loan(
    loan_id: int,
    loan_update: LoanUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repo = LoanRepository(db)

    existing = repo.get_by_id(loan_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Loan {loan_id} not found",
        )
    if existing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this loan",
        )

    try:
        update_data = {k: v for k, v in loan_update.model_dump().items() if v is not None}
        updated_loan = repo.update(loan_id, **update_data)
        db.commit()
        db.refresh(updated_loan)
        return updated_loan
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update loan: {str(e)}",
        )


@router.delete("/{loan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loan(
    loan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repo = LoanRepository(db)

    existing = repo.get_by_id(loan_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Loan {loan_id} not found",
        )
    if existing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this loan",
        )

    try:
        repo.delete(loan_id)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete loan: {str(e)}",
        )
