"""
Test API structure and endpoint definitions.

These tests verify the API is properly configured without requiring
database connections or backend business logic.
"""

import pytest
from fastapi.testclient import TestClient


def test_api_can_import():
    """Test that API modules can be imported."""
    from fplan_v2.api import main
    from fplan_v2.api import schemas
    from fplan_v2.api.routes import assets, loans, revenue_streams, projections

    assert main.app is not None
    assert hasattr(schemas, "AssetCreate")
    assert hasattr(assets, "router")
    assert hasattr(loans, "router")
    assert hasattr(revenue_streams, "router")
    assert hasattr(projections, "router")


def test_schemas_defined():
    """Test that all required Pydantic schemas are defined."""
    from fplan_v2.api.schemas import (
        AssetCreate,
        AssetUpdate,
        AssetResponse,
        LoanCreate,
        LoanUpdate,
        LoanResponse,
        RevenueStreamCreate,
        RevenueStreamUpdate,
        RevenueStreamResponse,
        ProjectionRequest,
        ProjectionResponse,
        PortfolioSummary,
    )

    # Verify schemas can be instantiated (will fail on import errors)
    assert AssetCreate is not None
    assert LoanCreate is not None
    assert RevenueStreamCreate is not None
    assert ProjectionRequest is not None


def test_repositories_defined():
    """Test that all repository classes are defined."""
    from fplan_v2.db.repositories import (
        AssetRepository,
        LoanRepository,
        RevenueStreamRepository,
    )

    assert AssetRepository is not None
    assert LoanRepository is not None
    assert RevenueStreamRepository is not None


def test_app_metadata():
    """Test FastAPI app metadata is correctly configured."""
    from fplan_v2.api.main import app

    assert app.title == "FPlan v2 API"
    assert app.version == "2.0.0"
    assert app.docs_url == "/api/docs"
    assert app.redoc_url == "/api/redoc"


def test_routes_registered():
    """Test that all routes are registered with the app."""
    from fplan_v2.api.main import app

    # Get all route paths
    routes = [route.path for route in app.routes]

    # Check key routes exist
    assert "/health" in routes
    assert "/" in routes
    assert "/api/docs" in routes
    assert "/api/redoc" in routes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
