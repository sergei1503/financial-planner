"""
Base repository pattern for database operations.

Provides common CRUD operations with SQLAlchemy ORM.
"""

from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from fplan_v2.db.models import Base, User


ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository with common CRUD operations.

    Generic repository pattern that can be extended for specific models.
    Provides type-safe database operations.
    """

    def __init__(self, model: Type[ModelType], session: Session):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Database session
        """
        self.model = model
        self.session = session

    def _bump_portfolio_version(self, user_id: int) -> None:
        """Increment user's portfolio_version to invalidate projection cache."""
        self.session.query(User).filter_by(id=user_id).update(
            {"portfolio_version": User.portfolio_version + 1}
        )

    def create(self, **kwargs) -> ModelType:
        """
        Create a new record.

        Args:
            **kwargs: Field values for the new record

        Returns:
            Created model instance

        Raises:
            IntegrityError: If unique constraint violation or foreign key error
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        self.session.flush()  # Flush to get ID without committing
        if hasattr(instance, "user_id") and instance.user_id:
            self._bump_portfolio_version(instance.user_id)
        return instance

    def get_by_id(self, id: int) -> Optional[ModelType]:
        """
        Get record by primary key ID.

        Args:
            id: Primary key ID

        Returns:
            Model instance or None if not found
        """
        return self.session.query(self.model).filter(self.model.id == id).first()

    def get_all(self, user_id: Optional[int] = None, limit: int = 100, offset: int = 0, eager_load: Optional[List[Any]] = None) -> List[ModelType]:
        """
        Get all records with optional user filtering, pagination, and eager loading.

        Args:
            user_id: Filter by user_id if provided
            limit: Maximum number of records to return
            offset: Number of records to skip
            eager_load: List of relationships to eager load with joinedload (e.g., [Model.relationship])

        Returns:
            List of model instances
        """
        query = self.session.query(self.model)

        if user_id is not None and hasattr(self.model, "user_id"):
            query = query.filter(self.model.user_id == user_id)

        if eager_load:
            for relationship in eager_load:
                query = query.options(joinedload(relationship))

        return query.limit(limit).offset(offset).all()

    def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """
        Update record by ID.

        Args:
            id: Primary key ID
            **kwargs: Fields to update

        Returns:
            Updated model instance or None if not found
        """
        instance = self.get_by_id(id)
        if not instance:
            return None

        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        self.session.flush()
        if hasattr(instance, "user_id") and instance.user_id:
            self._bump_portfolio_version(instance.user_id)
        return instance

    def delete(self, id: int) -> bool:
        """
        Delete record by ID.

        Args:
            id: Primary key ID

        Returns:
            True if deleted, False if not found
        """
        instance = self.get_by_id(id)
        if not instance:
            return False

        user_id = getattr(instance, "user_id", None)
        self.session.delete(instance)
        self.session.flush()
        if user_id:
            self._bump_portfolio_version(user_id)
        return True

    def exists(self, **filters) -> bool:
        """
        Check if record exists matching filters.

        Args:
            **filters: Field filters

        Returns:
            True if exists, False otherwise
        """
        query = self.session.query(self.model)
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)

        return query.first() is not None

    def count(self, user_id: Optional[int] = None) -> int:
        """
        Count records.

        Args:
            user_id: Filter by user_id if provided

        Returns:
            Number of records
        """
        query = self.session.query(self.model)

        if user_id is not None and hasattr(self.model, "user_id"):
            query = query.filter(self.model.user_id == user_id)

        return query.count()

    def get_portfolio_summary_optimized(self, user_id: int) -> Dict[str, Any]:
        """
        Get complete portfolio summary in a single optimized SQL query.

        Uses CTEs to calculate all portfolio metrics with one database round-trip:
        - Total assets value
        - Total liabilities balance
        - Monthly revenue (with tax and period conversion)
        - Monthly loan payments (with amortization formula)
        - Counts for assets, loans, and revenue streams

        Args:
            user_id: User ID

        Returns:
            Dictionary with all portfolio metrics
        """
        from sqlalchemy import text
        from datetime import date

        query = text("""
            WITH asset_summary AS (
                SELECT
                    COUNT(*) as asset_count,
                    COALESCE(SUM(
                        CASE
                            WHEN current_value IS NOT NULL THEN current_value
                            ELSE original_value
                        END
                    ), 0) as total_assets
                FROM assets
                WHERE user_id = :user_id
            ),
            loan_summary AS (
                SELECT
                    COUNT(*) as loan_count,
                    COALESCE(SUM(
                        CASE
                            WHEN current_balance IS NOT NULL THEN current_balance
                            ELSE original_value
                        END
                    ), 0) as total_liabilities,
                    COALESCE(SUM(
                        CASE
                            WHEN interest_rate_annual_pct = 0 THEN
                                -- No interest: principal / duration
                                COALESCE(current_balance, original_value) / duration_months
                            ELSE
                                -- Amortization formula: P * [r(1+r)^n] / [(1+r)^n - 1]
                                COALESCE(current_balance, original_value) *
                                (
                                    (interest_rate_annual_pct / 12 / 100) *
                                    POWER(1 + (interest_rate_annual_pct / 12 / 100), duration_months)
                                ) /
                                (
                                    POWER(1 + (interest_rate_annual_pct / 12 / 100), duration_months) - 1
                                )
                        END
                    ), 0) as monthly_payments
                FROM loans
                WHERE user_id = :user_id
            ),
            revenue_summary AS (
                SELECT
                    COUNT(*) as stream_count,
                    COALESCE(SUM(
                        CASE
                            WHEN period = 'monthly' THEN amount * (1 - tax_rate / 100)
                            WHEN period = 'quarterly' THEN (amount / 3) * (1 - tax_rate / 100)
                            WHEN period = 'yearly' THEN (amount / 12) * (1 - tax_rate / 100)
                            ELSE amount * (1 - tax_rate / 100)
                        END
                    ), 0) as monthly_revenue
                FROM revenue_streams
                WHERE user_id = :user_id
                  AND start_date <= :as_of_date
                  AND (end_date IS NULL OR end_date >= :as_of_date)
            )
            SELECT
                a.asset_count,
                a.total_assets,
                l.loan_count,
                l.total_liabilities,
                l.monthly_payments,
                r.stream_count,
                r.monthly_revenue
            FROM asset_summary a
            CROSS JOIN loan_summary l
            CROSS JOIN revenue_summary r;
        """)

        result = self.session.execute(
            query,
            {"user_id": user_id, "as_of_date": date.today()}
        ).fetchone()

        if not result:
            return {
                "asset_count": 0,
                "total_assets": 0.0,
                "loan_count": 0,
                "total_liabilities": 0.0,
                "monthly_payments": 0.0,
                "stream_count": 0,
                "monthly_revenue": 0.0,
            }

        return {
            "asset_count": int(result[0]),
            "total_assets": float(result[1]),
            "loan_count": int(result[2]),
            "total_liabilities": float(result[3]),
            "monthly_payments": float(result[4]),
            "stream_count": int(result[5]),
            "monthly_revenue": float(result[6]),
        }
