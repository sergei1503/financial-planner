"""
API integration tests using in-memory SQLite.

Tests CRUD operations for assets, loans, revenue streams,
and portfolio summary endpoints.

Run: python -m pytest fplan_v2/tests/test_api_integration.py -v
"""

import pytest
from datetime import date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, JSON
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fplan_v2.db.models import Base, User, Asset, Loan, RevenueStream
from fplan_v2.db.connection import get_db_session
from fplan_v2.api.main import app


# ---------------------------------------------------------------------------
# SQLite compatibility: swap JSONB -> JSON before table creation
# ---------------------------------------------------------------------------
# PostgreSQL JSONB columns don't work with SQLite. We intercept DDL to
# replace them with plain JSON (which SQLite treats as TEXT).

from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402


@event.listens_for(Base.metadata, "column_reflect")
def _reflect_col(inspector, table, column_info):
    if isinstance(column_info.get("type"), JSONB):
        column_info["type"] = JSON()


def _patch_jsonb_columns():
    """Replace JSONB columns with JSON for SQLite compatibility."""
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()


# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db_session():
    db = TestingSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


app.dependency_overrides[get_db_session] = override_get_db_session

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables and seed test user before each test, drop after."""
    _patch_jsonb_columns()

    # SQLite doesn't enforce CHECK constraints from PostgreSQL or GIN indexes,
    # so we can safely call create_all -- unsupported clauses are ignored.
    Base.metadata.create_all(bind=engine)

    # Seed test user
    db = TestingSessionLocal()
    try:
        user = User(id=1, name="Test User", email="test@fplan.local")
        db.add(user)
        db.commit()
    finally:
        db.close()

    yield

    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ASSET_PAYLOAD = {
    "user_id": 1,
    "external_id": "apt-1",
    "asset_type": "real_estate",
    "name": "Test Apartment",
    "start_date": "2024-01-01",
    "original_value": 1000000,
    "appreciation_rate_annual_pct": 5.0,
    "yearly_fee_pct": 0,
    "sell_tax": 0,
    "currency": "ILS",
    "config_json": {},
}

LOAN_PAYLOAD = {
    "user_id": 1,
    "external_id": "loan-1",
    "loan_type": "fixed",
    "name": "Test Mortgage",
    "start_date": "2024-01-01",
    "original_value": 500000,
    "interest_rate_annual_pct": 3.5,
    "duration_months": 240,
    "config_json": {},
}

REVENUE_STREAM_PAYLOAD = {
    "user_id": 1,
    "stream_type": "rent",
    "name": "Test Rent",
    "start_date": "2024-01-01",
    "amount": 5000,
    "period": "monthly",
    "tax_rate": 0,
    "growth_rate": 2.0,
    "config_json": {},
}


def _create_asset(**overrides) -> dict:
    payload = {**ASSET_PAYLOAD, **overrides}
    resp = client.post("/api/assets/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_loan(**overrides) -> dict:
    payload = {**LOAN_PAYLOAD, **overrides}
    resp = client.post("/api/loans/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_revenue_stream(**overrides) -> dict:
    payload = {**REVENUE_STREAM_PAYLOAD, **overrides}
    resp = client.post("/api/revenue-streams/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ===========================================================================
# Health
# ===========================================================================


class TestHealth:
    def test_health_check(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


# ===========================================================================
# Assets CRUD
# ===========================================================================


class TestAssets:
    def test_create_asset(self):
        data = _create_asset()
        assert data["name"] == "Test Apartment"
        assert data["asset_type"] == "real_estate"
        assert data["id"] is not None
        assert data["user_id"] == 1

    def test_list_assets(self):
        _create_asset()
        resp = client.get("/api/assets/", params={"user_id": 1})
        assert resp.status_code == 200
        assets = resp.json()
        assert len(assets) >= 1
        assert assets[0]["name"] == "Test Apartment"

    def test_get_asset(self):
        created = _create_asset()
        resp = client.get(f"/api/assets/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Apartment"

    def test_update_asset(self):
        created = _create_asset()
        resp = client.put(
            f"/api/assets/{created['id']}",
            json={"name": "Updated Apartment"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Apartment"

    def test_delete_asset(self):
        created = _create_asset()
        resp = client.delete(f"/api/assets/{created['id']}")
        assert resp.status_code == 204

        # Verify it's gone
        resp = client.get(f"/api/assets/{created['id']}")
        assert resp.status_code == 404

    def test_create_asset_duplicate_external_id(self):
        _create_asset()
        resp = client.post("/api/assets/", json=ASSET_PAYLOAD)
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    def test_get_nonexistent_asset(self):
        resp = client.get("/api/assets/99999")
        assert resp.status_code == 404


# ===========================================================================
# Loans CRUD
# ===========================================================================


class TestLoans:
    def test_create_loan(self):
        data = _create_loan()
        assert data["name"] == "Test Mortgage"
        assert data["loan_type"] == "fixed"
        assert data["id"] is not None

    def test_list_loans(self):
        _create_loan()
        resp = client.get("/api/loans/", params={"user_id": 1})
        assert resp.status_code == 200
        loans = resp.json()
        assert len(loans) >= 1

    def test_get_loan(self):
        created = _create_loan()
        resp = client.get(f"/api/loans/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Mortgage"

    def test_update_loan(self):
        created = _create_loan()
        resp = client.put(
            f"/api/loans/{created['id']}",
            json={"name": "Updated Mortgage"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Mortgage"

    def test_delete_loan(self):
        created = _create_loan()
        resp = client.delete(f"/api/loans/{created['id']}")
        assert resp.status_code == 204

        resp = client.get(f"/api/loans/{created['id']}")
        assert resp.status_code == 404

    def test_create_loan_duplicate_external_id(self):
        _create_loan()
        resp = client.post("/api/loans/", json=LOAN_PAYLOAD)
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    def test_get_nonexistent_loan(self):
        resp = client.get("/api/loans/99999")
        assert resp.status_code == 404


# ===========================================================================
# Revenue Streams CRUD
# ===========================================================================


class TestRevenueStreams:
    def test_create_revenue_stream(self):
        data = _create_revenue_stream()
        assert data["name"] == "Test Rent"
        assert data["stream_type"] == "rent"
        assert data["id"] is not None

    def test_list_revenue_streams(self):
        _create_revenue_stream()
        resp = client.get("/api/revenue-streams/", params={"user_id": 1})
        assert resp.status_code == 200
        streams = resp.json()
        assert len(streams) >= 1

    def test_get_revenue_stream(self):
        created = _create_revenue_stream()
        resp = client.get(f"/api/revenue-streams/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Rent"

    def test_update_revenue_stream(self):
        created = _create_revenue_stream()
        resp = client.put(
            f"/api/revenue-streams/{created['id']}",
            json={"name": "Updated Rent"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Rent"

    def test_delete_revenue_stream(self):
        created = _create_revenue_stream()
        resp = client.delete(f"/api/revenue-streams/{created['id']}")
        assert resp.status_code == 204

        resp = client.get(f"/api/revenue-streams/{created['id']}")
        assert resp.status_code == 404

    def test_get_nonexistent_revenue_stream(self):
        resp = client.get("/api/revenue-streams/99999")
        assert resp.status_code == 404


# ===========================================================================
# Portfolio Summary
# ===========================================================================


class TestPortfolioSummary:
    def test_portfolio_summary(self):
        _create_asset()
        _create_loan()
        _create_revenue_stream()

        resp = client.get("/api/projections/portfolio/summary", params={"user_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == 1
        assert data["asset_count"] == 1
        assert data["loan_count"] == 1
        assert data["revenue_stream_count"] == 1
        assert float(data["total_assets"]) > 0
        assert float(data["total_liabilities"]) > 0

    def test_portfolio_summary_empty(self):
        resp = client.get("/api/projections/portfolio/summary", params={"user_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_count"] == 0
        assert data["loan_count"] == 0
        assert float(data["net_worth"]) == 0.0
