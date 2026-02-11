"""
Database connection management for Neon PostgreSQL.

Handles:
- Connection pooling for serverless functions
- Environment-based configuration
- Context managers for transactions
- Connection lifecycle management
"""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

# Load environment variables from .env file
load_dotenv()

# Import models to ensure they're registered with Base
from .models import Base


class DatabaseConfig:
    """Database configuration from environment variables."""

    def __init__(self):
        self.database_url = os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError(
                "Database URL not configured. Set NEON_DATABASE_URL or DATABASE_URL environment variable."
            )

        # Log masked URL for debugging (hide password)
        if '@' in self.database_url:
            masked_url = self.database_url.split('@')[1]
            print(f"Database: Connecting to {masked_url}")
        else:
            print("Database: Connection configured")

        # Connection pooling settings
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))  # 1 hour

        # Vercel serverless optimization: use connection pooler
        # Neon provides built-in PgBouncer at -pooler.neon.tech endpoint
        if "-pooler" not in self.database_url and os.getenv("USE_POOLER", "true").lower() == "true":
            # Suggest using pooler endpoint
            print("Warning: Consider using Neon pooler endpoint (-pooler.neon.tech) for serverless deployments")


class DatabaseManager:
    """
    Singleton database manager for connection pooling.

    Usage:
        db_manager = DatabaseManager()
        with db_manager.session() as session:
            users = session.query(User).all()
    """

    _instance: Optional["DatabaseManager"] = None
    _engine: Optional[Engine] = None
    _session_factory: Optional[sessionmaker] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._engine is None:
            self._initialize_engine()

    def _initialize_engine(self):
        """Initialize SQLAlchemy engine with connection pooling."""
        config = DatabaseConfig()

        # Determine pooling strategy
        is_serverless = bool(os.getenv("VERCEL"))

        if is_serverless:
            # Serverless: Use NullPool to avoid connection buildup
            # Each function invocation gets fresh connections
            self._engine = create_engine(
                config.database_url,
                poolclass=NullPool,
                echo=os.getenv("SQL_ECHO", "false").lower() == "true",
            )
            print("Database: Using NullPool (serverless mode)")
        else:
            # Traditional server: Use QueuePool with connection reuse
            self._engine = create_engine(
                config.database_url,
                pool_size=config.pool_size,
                max_overflow=config.max_overflow,
                pool_timeout=config.pool_timeout,
                pool_recycle=config.pool_recycle,
                poolclass=QueuePool,
                echo=os.getenv("SQL_ECHO", "false").lower() == "true",
            )
            print(f"Database: Using QueuePool (pool_size={config.pool_size}, max_overflow={config.max_overflow})")

        # Configure connection events
        self._configure_events()

        # Create session factory
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    def _configure_events(self):
        """Configure SQLAlchemy engine events."""

        @event.listens_for(self._engine, "connect")
        def set_search_path(dbapi_conn, connection_record):
            """Set search path on connection."""
            cursor = dbapi_conn.cursor()
            cursor.execute("SET search_path TO public")
            cursor.close()

        @event.listens_for(self._engine, "checkout")
        def check_connection(dbapi_conn, connection_record, connection_proxy):
            """Verify connection is alive on checkout with timing."""
            import time
            start = time.time()
            cursor = dbapi_conn.cursor()
            try:
                cursor.execute("SELECT 1")
                elapsed_ms = (time.time() - start) * 1000
                if elapsed_ms > 100:
                    print(f"[WARNING] Slow connection health check: {elapsed_ms:.2f}ms")
            except Exception as e:
                elapsed_ms = (time.time() - start) * 1000
                print(f"[ERROR] Connection health check failed after {elapsed_ms:.2f}ms: {e}")
                # Connection is stale, raise to trigger reconnection
                raise
            finally:
                cursor.close()

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions with automatic commit/rollback.

        Usage:
            with db_manager.session() as session:
                user = session.query(User).first()
                user.name = "New Name"
                # Automatically commits on success, rolls back on exception
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def transaction(self) -> Generator[Session, None, None]:
        """
        Context manager for explicit transactions (alias for session()).

        Usage:
            with db_manager.transaction() as session:
                # Multiple operations in one transaction
                session.add(asset)
                session.add(loan)
        """
        with self.session() as session:
            yield session

    def get_session(self) -> Session:
        """
        Get a new session without context manager.

        Warning: Caller is responsible for closing the session.
        Prefer using session() context manager instead.
        """
        return self._session_factory()

    def create_all(self):
        """Create all tables in the database."""
        Base.metadata.create_all(self._engine)
        print("Database: All tables created")

    def drop_all(self):
        """Drop all tables in the database. USE WITH CAUTION."""
        Base.metadata.drop_all(self._engine)
        print("Database: All tables dropped")

    def dispose(self):
        """Dispose of the connection pool."""
        if self._engine:
            self._engine.dispose()
            print("Database: Connection pool disposed")


# Convenience functions

def get_db_manager() -> DatabaseManager:
    """Get or create the database manager singleton."""
    return DatabaseManager()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Convenience context manager for database sessions.

    Usage:
        from fplan_v2.db.connection import db_session

        with db_session() as session:
            users = session.query(User).all()
    """
    db_manager = get_db_manager()
    with db_manager.session() as session:
        yield session


def init_database():
    """
    Initialize database schema.

    Call this once during deployment to create all tables.
    """
    db_manager = get_db_manager()
    db_manager.create_all()


def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency for getting database sessions.

    Usage in FastAPI routes:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db_session)):
            return db.query(User).all()
    """
    db_manager = get_db_manager()
    session = db_manager.get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine() -> Engine:
    """
    Get the SQLAlchemy engine instance.

    Returns:
        Engine instance
    """
    db_manager = get_db_manager()
    return db_manager._engine


def init_db():
    """
    Initialize database (alias for init_database).

    Used by FastAPI lifespan for consistency.
    """
    init_database()


# Connection health check for Vercel health endpoints
def check_connection() -> bool:
    """
    Check if database connection is healthy.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        with db_session() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection check failed: {e}")
        return False
