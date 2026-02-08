"""
Base repository pattern for database operations.

Provides common CRUD operations with SQLAlchemy ORM.
"""

from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
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

    def get_all(self, user_id: Optional[int] = None, limit: int = 100, offset: int = 0) -> List[ModelType]:
        """
        Get all records with optional user filtering and pagination.

        Args:
            user_id: Filter by user_id if provided
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of model instances
        """
        query = self.session.query(self.model)

        if user_id is not None and hasattr(self.model, "user_id"):
            query = query.filter(self.model.user_id == user_id)

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
