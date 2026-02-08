"""
Cash flow API endpoint tests using in-memory SQLite.

Run: python -m pytest fplan_v2/tests/test_cash_flows_api.py -v
"""

import pytest
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, JSON
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fplan_v2.db.models import Base, User, Asset, CashFlow
from fplan_v2.db.connection import get_db_session
from fplan_v2.api.main import app

# ---------------------------------------------------------------------------
# SQLite compatibility
# ---------------------------------------------------------------------------

from sqlalchemy.dialects.postgresql import JSONB


@event.listens_for(Base.metadata, "column_reflect")
def _reflect_col(inspector, table, column_info):
    if isinstance(column_info.get("type"), JSONB):
        column_info["type"] = JSON()


def _patch_jsonb_columns():
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
    _patch_jsonb_columns()
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        user = User(id=1, name="Test User", email="test@fplan.local")
        db.add(user)
        db.commit()
    finally:
        db.close()

    yield

    Base.metadata.drop_all(bind=engine)


def _seed_asset_with_cash_flows():
    """Create an asset with two deposit and one withdrawal cash flows."""
    db = TestingSessionLocal()
    try:
        asset = Asset(
            user_id=1,
            external_id="stock-cf",
            asset_type="stock",
            name="Stock with CFs",
            start_date=date(2024, 1, 1),
            original_value=100000,
            appreciation_rate_annual_pct=5.0,
            yearly_fee_pct=0,
            sell_tax=0,
            currency="ILS",
            config_json={},
        )
        db.add(asset)
        db.flush()

        cf1 = CashFlow(
            user_id=1,
            flow_type="deposit",
            target_asset_id=asset.id,
            name="Monthly deposit",
            amount=1000,
            from_date=date(2024, 1, 1),
            to_date=date(2025, 12, 1),
            from_own_capital=True,
        )
        cf2 = CashFlow(
            user_id=1,
            flow_type="deposit",
            target_asset_id=asset.id,
            name="Bonus deposit",
            amount=5000,
            from_date=date(2024, 6, 1),
            to_date=date(2024, 6, 1),
            from_own_capital=True,
        )
        cf3 = CashFlow(
            user_id=1,
            flow_type="withdrawal",
            target_asset_id=asset.id,
            name="Emergency fund",
            amount=2000,
            from_date=date(2025, 1, 1),
            to_date=date(2025, 6, 1),
            from_own_capital=False,
        )
        db.add_all([cf1, cf2, cf3])
        db.commit()
        return asset.id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCashFlowsAPI:
    def test_list_cash_flows(self):
        """GET /api/cash-flows/ returns all cash flows for the user."""
        asset_id = _seed_asset_with_cash_flows()

        resp = client.get("/api/cash-flows/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        flow_types = {cf["flow_type"] for cf in data}
        assert "deposit" in flow_types
        assert "withdrawal" in flow_types

    def test_cash_flows_by_asset(self):
        """GET /api/cash-flows/asset/{id} returns filtered cash flows."""
        asset_id = _seed_asset_with_cash_flows()

        resp = client.get(f"/api/cash-flows/asset/{asset_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert all(cf["target_asset_id"] == asset_id for cf in data)

    def test_cash_flows_empty_asset(self):
        """Asset with no cash flows returns empty list."""
        db = TestingSessionLocal()
        try:
            asset = Asset(
                user_id=1,
                external_id="empty-cf",
                asset_type="cash",
                name="No CFs",
                start_date=date(2024, 1, 1),
                original_value=10000,
                appreciation_rate_annual_pct=0,
                yearly_fee_pct=0,
                sell_tax=0,
                currency="ILS",
                config_json={},
            )
            db.add(asset)
            db.commit()
            asset_id = asset.id
        finally:
            db.close()

        resp = client.get(f"/api/cash-flows/asset/{asset_id}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_cash_flows_empty_user(self):
        """User with no assets/cash flows gets empty list."""
        resp = client.get("/api/cash-flows/")
        assert resp.status_code == 200
        assert resp.json() == []
