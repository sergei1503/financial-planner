"""
Clerk JWT authentication for FastAPI.

Supports three modes:
1. Clerk mode: Verifies JWT tokens from Clerk (when CLERK_SECRET_KEY is set)
2. Demo mode: When Clerk IS configured but no token provided, returns demo user
3. Single-user mode: Falls back to user_id=1 for self-hosted open-source usage
"""

import os
from typing import Optional

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from fplan_v2.db.connection import get_db_session
from fplan_v2.db.models import User


# Clerk configuration from environment
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")
CLERK_ISSUER = os.getenv("CLERK_ISSUER")  # e.g., https://clerk.your-domain.com
CLERK_JWKS_URL = f"{CLERK_ISSUER}/.well-known/jwks.json" if CLERK_ISSUER else None

# Demo user convention: clerk_id="demo"
DEMO_CLERK_ID = "demo"

# Security scheme - optional so it doesn't fail when no auth is configured
security = HTTPBearer(auto_error=False)

# Cache JWKS client
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    """Get or create cached JWKS client."""
    global _jwks_client
    if _jwks_client is None and CLERK_JWKS_URL:
        _jwks_client = PyJWKClient(CLERK_JWKS_URL)
    return _jwks_client


def _verify_clerk_token(token: str) -> dict:
    """
    Verify a Clerk JWT token and return the decoded payload.

    Raises:
        HTTPException: If token is invalid or expired
    """
    jwks_client = _get_jwks_client()
    if not jwks_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Clerk JWKS not configured",
        )

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=CLERK_ISSUER,
            options={"verify_aud": False},  # Clerk doesn't always set audience
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )


def _get_or_create_user(db: Session, clerk_id: str, email: Optional[str] = None) -> User:
    """
    Get existing user by clerk_id or create a new one.

    Args:
        db: Database session
        clerk_id: Clerk user ID (from JWT 'sub' claim)
        email: Optional email from JWT

    Returns:
        User instance
    """
    user = db.query(User).filter_by(clerk_id=clerk_id).first()
    if user:
        return user

    # Auto-create user on first authentication
    user = User(
        name=email or f"user_{clerk_id[:8]}",
        email=email,
        clerk_id=clerk_id,
        auth_provider="clerk",
    )
    db.add(user)
    db.flush()  # Get the ID without committing
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db_session),
) -> User:
    """
    FastAPI dependency that returns the current authenticated user.

    In Clerk mode (CLERK_SECRET_KEY set):
        - Verifies JWT from Authorization header
        - Returns user mapped to Clerk ID (auto-creates on first auth)

    In single-user mode (no CLERK_SECRET_KEY):
        - Returns user with id=1 (default for self-hosted)
        - No authentication required
    """
    # Single-user mode: no Clerk configured
    if not CLERK_SECRET_KEY:
        user = db.query(User).filter_by(id=1).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Default user (id=1) not found. Run database initialization first.",
            )
        return user

    # Clerk mode: verify JWT — or fall back to demo user if no token
    if not credentials:
        # No token provided: return demo user instead of 401
        demo_user = db.query(User).filter_by(clerk_id=DEMO_CLERK_ID).first()
        if demo_user:
            return demo_user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _verify_clerk_token(credentials.credentials)
    clerk_id = payload.get("sub")
    if not clerk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
        )

    email = payload.get("email")
    user = _get_or_create_user(db, clerk_id, email)
    return user


def is_demo_user(user: User) -> bool:
    """Check if the given user is the demo user."""
    return user.clerk_id == DEMO_CLERK_ID
