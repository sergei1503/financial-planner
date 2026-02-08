"""
Projection endpoint integration tests using in-memory SQLite.

Verifies that the projection engine runs without crashing for various
portfolio configurations, including cash flows with string dates.

Run: python -m pytest fplan_v2/tests/test_projections_integration.py -v
"""

import pytest
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, JSON
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fplan_v2.db.models import Base, User, Asset, Loan, CashFlow, RevenueStream
from fplan_v2.db.connection import get_db_session
from fplan_v2.api.main import app

# ---------------------------------------------------------------------------
# SQLite compatibility: swap JSONB -> JSON before table creation
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_stock_asset_with_deposits(db_session=None):
    """Create a stock asset with deposit and withdrawal cash flows."""
    db = db_session or TestingSessionLocal()
    try:
        asset = Asset(
            user_id=1,
            external_id="stock-1",
            asset_type="stock",
            name="Test Stock",
            start_date=date(2024, 1, 1),
            original_value=100000,
            appreciation_rate_annual_pct=7.0,
            yearly_fee_pct=0.5,
            sell_tax=25,
            currency="ILS",
            config_json={},
        )
        db.add(asset)
        db.flush()

        # Deposit
        deposit = CashFlow(
            user_id=1,
            flow_type="deposit",
            target_asset_id=asset.id,
            name="Monthly deposit",
            amount=2000,
            from_date=date(2024, 1, 1),
            to_date=date(2026, 12, 1),
            from_own_capital=True,
        )
        db.add(deposit)

        # Withdrawal
        withdrawal = CashFlow(
            user_id=1,
            flow_type="withdrawal",
            target_asset_id=asset.id,
            name="Emergency withdrawal",
            amount=500,
            from_date=date(2025, 6, 1),
            to_date=date(2025, 12, 1),
            from_own_capital=False,
        )
        db.add(withdrawal)

        db.commit()
        return asset.id
    finally:
        if not db_session:
            db.close()


def _seed_cash_asset():
    db = TestingSessionLocal()
    try:
        asset = Asset(
            user_id=1,
            external_id="cash-1",
            asset_type="cash",
            name="Cash",
            start_date=date(2024, 1, 1),
            original_value=50000,
            appreciation_rate_annual_pct=0,
            yearly_fee_pct=0,
            sell_tax=0,
            currency="ILS",
            config_json={},
        )
        db.add(asset)
        db.commit()
        return asset.id
    finally:
        db.close()


def _seed_pension_asset_with_deposits():
    db = TestingSessionLocal()
    try:
        asset = Asset(
            user_id=1,
            external_id="pension-1",
            asset_type="pension",
            name="Pension Fund",
            start_date=date(2024, 1, 1),
            original_value=200000,
            appreciation_rate_annual_pct=4.0,
            yearly_fee_pct=0.3,
            sell_tax=0,
            currency="ILS",
            config_json={"end_date": "2060-01-01"},
        )
        db.add(asset)
        db.flush()

        deposit = CashFlow(
            user_id=1,
            flow_type="deposit",
            target_asset_id=asset.id,
            name="Employer contribution",
            amount=3000,
            from_date=date(2024, 1, 1),
            to_date=date(2055, 1, 1),
            from_own_capital=False,
        )
        db.add(deposit)
        db.commit()
        return asset.id
    finally:
        db.close()


def _seed_fixed_loan():
    db = TestingSessionLocal()
    try:
        loan = Loan(
            user_id=1,
            external_id="loan-fixed-1",
            loan_type="fixed",
            name="Fixed Mortgage",
            start_date=date(2024, 1, 1),
            original_value=500000,
            interest_rate_annual_pct=3.5,
            duration_months=240,
            config_json={"history": []},
        )
        db.add(loan)
        db.commit()
        return loan.id
    finally:
        db.close()


def _seed_prime_pegged_loan():
    db = TestingSessionLocal()
    try:
        loan = Loan(
            user_id=1,
            external_id="loan-prime-1",
            loan_type="prime_pegged",
            name="Prime Mortgage",
            start_date=date(2024, 1, 1),
            original_value=300000,
            interest_rate_annual_pct=1.5,
            duration_months=180,
            config_json={},
        )
        db.add(loan)
        db.commit()
        return loan.id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProjectionEndpoint:
    """Tests for POST /api/projections/run"""

    def test_projection_runs_with_stock_and_cash_assets(self):
        """Stock asset with deposits/withdrawals + cash asset should project without crash."""
        _seed_cash_asset()
        _seed_stock_asset_with_deposits()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01",
            "end_date": "2027-01-01",
        })
        assert resp.status_code == 200, f"Projection failed: {resp.text}"
        data = resp.json()
        assert len(data["asset_projections"]) == 2
        assert len(data["net_worth_series"]) > 0

    def test_projection_runs_with_loans(self):
        """Fixed and prime-pegged loans should project without crash."""
        _seed_cash_asset()
        _seed_fixed_loan()
        _seed_prime_pegged_loan()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01",
            "end_date": "2027-01-01",
        })
        assert resp.status_code == 200, f"Projection failed: {resp.text}"
        data = resp.json()
        assert len(data["loan_projections"]) == 2
        assert len(data["total_liabilities_series"]) > 0

    def test_projection_runs_empty_portfolio(self):
        """Empty portfolio should return 200 with empty series."""
        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01",
            "end_date": "2027-01-01",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_projections"] == []
        assert data["loan_projections"] == []
        assert data["net_worth_series"] == []

    def test_projection_with_sell_date(self):
        """Asset with sell_date should convert to cash without crash."""
        db = TestingSessionLocal()
        try:
            asset = Asset(
                user_id=1,
                external_id="sell-apt",
                asset_type="real_estate",
                name="Sell Apartment",
                start_date=date(2024, 1, 1),
                original_value=800000,
                appreciation_rate_annual_pct=5.0,
                yearly_fee_pct=0,
                sell_tax=25,
                sell_date=date(2026, 6, 1),
                currency="ILS",
                config_json={},
            )
            db.add(asset)
            db.commit()
        finally:
            db.close()

        _seed_cash_asset()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01",
            "end_date": "2027-01-01",
        })
        assert resp.status_code == 200, f"Projection failed: {resp.text}"
        data = resp.json()
        assert len(data["asset_projections"]) == 2

    def test_projection_with_pension_deposits(self):
        """PensionAsset with deposits from cash_flows should not crash (A3 regression)."""
        _seed_pension_asset_with_deposits()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01",
            "end_date": "2027-01-01",
        })
        assert resp.status_code == 200, f"Projection failed: {resp.text}"
        data = resp.json()
        assert len(data["asset_projections"]) == 1

    def test_projection_deposit_key_name(self):
        """Cash flows should use deposit_from_own_capital key (A1 regression)."""
        _seed_stock_asset_with_deposits()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01",
            "end_date": "2026-01-01",
        })
        # If the key name is wrong, StockAsset.get_projection() raises KeyError → 500
        assert resp.status_code == 200, f"KeyError on deposit key: {resp.text}"

    def test_projection_full_portfolio(self):
        """Full portfolio: cash + stock + pension + loans should all project together."""
        _seed_cash_asset()
        _seed_stock_asset_with_deposits()
        _seed_pension_asset_with_deposits()
        _seed_fixed_loan()
        _seed_prime_pegged_loan()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01",
            "end_date": "2030-01-01",
        })
        assert resp.status_code == 200, f"Full projection failed: {resp.text}"
        data = resp.json()
        assert len(data["asset_projections"]) == 3
        assert len(data["loan_projections"]) == 2
        assert len(data["net_worth_series"]) > 0
        assert len(data["monthly_cash_flow_series"]) > 0

    def test_projection_has_cash_flow_breakdown(self):
        """Projection response should include cash_flow_breakdown with items."""
        _seed_cash_asset()
        _seed_stock_asset_with_deposits()
        _seed_fixed_loan()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01",
            "end_date": "2027-01-01",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "cash_flow_breakdown" in data
        bd = data["cash_flow_breakdown"]
        assert bd is not None
        assert len(bd["items"]) > 0
        assert len(bd["total_income_series"]) > 0
        assert len(bd["total_expense_series"]) > 0
        assert len(bd["net_series"]) > 0

        # Loan should appear as expense item
        loan_items = [i for i in bd["items"] if i["category"] == "loan_payment"]
        assert len(loan_items) > 0

    def test_projection_with_revenue_streams(self):
        """Asset with attached rent revenue stream should appear in cash flow breakdown."""
        db = TestingSessionLocal()
        try:
            asset = Asset(
                user_id=1,
                external_id="apt-rent",
                asset_type="real_estate",
                name="Rental Apartment",
                start_date=date(2024, 1, 1),
                original_value=1000000,
                appreciation_rate_annual_pct=3.0,
                yearly_fee_pct=0,
                sell_tax=25,
                currency="ILS",
                config_json={},
            )
            db.add(asset)
            db.flush()

            rent_stream = RevenueStream(
                user_id=1,
                asset_id=asset.id,
                stream_type="rent",
                name="Apartment Rent",
                start_date=date(2024, 1, 1),
                amount=5000,
                period="monthly",
                tax_rate=10,
                growth_rate=3,
                config_json={},
            )
            db.add(rent_stream)
            db.commit()
        finally:
            db.close()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01",
            "end_date": "2027-01-01",
        })
        assert resp.status_code == 200, f"Projection failed: {resp.text}"
        data = resp.json()

        bd = data["cash_flow_breakdown"]
        assert bd is not None
        # Should have rent income item
        rent_items = [i for i in bd["items"] if i["category"] == "rent"]
        assert len(rent_items) > 0, f"No rent items found. Items: {[i['category'] for i in bd['items']]}"
        assert rent_items[0]["source_type"] == "income"

    def test_standalone_salary_in_projection(self):
        """Standalone salary stream (no asset_id) should appear in cash flow breakdown."""
        _seed_cash_asset()

        db = TestingSessionLocal()
        try:
            salary = RevenueStream(
                user_id=1,
                asset_id=None,
                stream_type="salary",
                name="Main Job Salary",
                start_date=date(2024, 1, 1),
                end_date=date(2060, 1, 1),
                amount=25000,
                period="monthly",
                tax_rate=0,
                growth_rate=3,
                config_json={},
            )
            db.add(salary)
            db.commit()
        finally:
            db.close()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01",
            "end_date": "2027-01-01",
        })
        assert resp.status_code == 200, f"Projection failed: {resp.text}"
        data = resp.json()

        bd = data["cash_flow_breakdown"]
        assert bd is not None
        salary_items = [i for i in bd["items"] if i["category"] == "salary"]
        assert len(salary_items) > 0, f"No salary items found. Items: {[i['category'] for i in bd['items']]}"
        assert salary_items[0]["source_name"] == "Main Job Salary"
        assert salary_items[0]["source_type"] == "income"

        # Income series should have non-zero values
        income_values = [float(p["value"]) for p in bd["total_income_series"]]
        assert any(v > 0 for v in income_values), "Income series is all zeros"
