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

from fplan_v2.db.models import Base, User, Portfolio, Asset, Loan, CashFlow, RevenueStream, HistoricalMeasurement
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
        db.flush()
        # Every seeded entity below sets portfolio_id=1, so pre-seed the matching
        # default Portfolio row here. Without this, get_current_portfolio() would
        # auto-create its own default portfolio (still id=1 on a fresh DB) but
        # relying on that side effect is fragile -- seed it explicitly instead.
        portfolio = Portfolio(id=1, user_id=1, name="Test Portfolio", is_default=True)
        db.add(portfolio)
        db.commit()
    finally:
        db.close()

    # This module's TestClient must resolve get_db_session to ITS OWN isolated
    # in-memory engine. Other integration test files in this directory (e.g.
    # test_api_integration.py, test_cash_flows_api.py) do the same thing at import
    # time against the same shared `app` singleton -- if all files register their
    # override once at module import, whichever module pytest collects LAST wins
    # for every test in the whole run (silently pointing other files' requests at
    # the wrong engine, whose tables may not even be created yet -> "no such table").
    # Apply/restore the override per-test instead, so file collection order can't
    # matter.
    previous_override = app.dependency_overrides.get(get_db_session)
    app.dependency_overrides[get_db_session] = override_get_db_session

    yield

    if previous_override is not None:
        app.dependency_overrides[get_db_session] = previous_override
    else:
        app.dependency_overrides.pop(get_db_session, None)

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
            portfolio_id=1,
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
            portfolio_id=1,
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
            portfolio_id=1,
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
            portfolio_id=1,
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
            portfolio_id=1,
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
            portfolio_id=1,
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
            portfolio_id=1,
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
            portfolio_id=1,
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

    # compute_projection() (fplan_v2/api/routes/projections.py) always appends a
    # synthetic "accumulated cash" virtual entry (asset_id=0, name "מזומנים מצטברים")
    # to asset_projections whenever cash_flow_breakdown.net_series is non-empty --
    # which in practice is true for essentially every non-empty projection window,
    # deposits or not. Product decision (confirmed): the virtual accumulated-cash
    # asset SHOULD always appear in asset_projections. The four tests below assert
    # `len(asset_projections) == <seeded asset count> + 1` to account for it.
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
        # +1 for the always-present virtual accumulated-cash asset (asset_id=0)
        assert len(data["asset_projections"]) == 3
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
                portfolio_id=1,
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
        # +1 for the always-present virtual accumulated-cash asset (asset_id=0)
        assert len(data["asset_projections"]) == 3

    def test_projection_with_pension_deposits(self):
        """PensionAsset with deposits from cash_flows should not crash (A3 regression)."""
        _seed_pension_asset_with_deposits()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01",
            "end_date": "2027-01-01",
        })
        assert resp.status_code == 200, f"Projection failed: {resp.text}"
        data = resp.json()
        # +1 for the always-present virtual accumulated-cash asset (asset_id=0)
        assert len(data["asset_projections"]) == 2

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
        # +1 for the always-present virtual accumulated-cash asset (asset_id=0)
        assert len(data["asset_projections"]) == 4
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
                portfolio_id=1,
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
                portfolio_id=1,
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
                portfolio_id=1,
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


def _series_for(data, asset_name):
    """Return {date: value} for the named asset projection."""
    for ap in data["asset_projections"]:
        if ap["asset_name"] == asset_name:
            return {p["date"]: float(p["value"]) for p in ap["time_series"]}
    return {}


class TestProjectionEngineFixes:
    """Behavioral regression tests for three projection-engine fixes."""

    def test_sold_stock_proceeds_credited_to_cash(self):
        """Fix #2: proceeds from a sale must reach cash, not be read as 0.

        StockAsset.get_projection() zeroes the sell-month row, so _apply_cash_conversions
        must use the last NON-ZERO value — the cash balance should jump by ~the pre-sale
        value. (Before the fix it read the zeroed row → 0 proceeds → cash stayed flat.)
        The stock starts before the projection window so there's no purchase adjustment,
        isolating the sale credit.
        """
        db = TestingSessionLocal()
        try:
            db.add(Asset(
                user_id=1, portfolio_id=1, external_id="cash-x", asset_type="cash", name="Cash",
                start_date=date(2020, 1, 1), original_value=50000,
                appreciation_rate_annual_pct=0, yearly_fee_pct=0, sell_tax=0,
                currency="ILS", config_json={},
            ))
            db.add(Asset(
                user_id=1, portfolio_id=1, external_id="stock-sell", asset_type="stock", name="Stock To Sell",
                start_date=date(2020, 1, 1), original_value=100000,
                appreciation_rate_annual_pct=7.0, yearly_fee_pct=0, sell_tax=0,
                sell_date=date(2030, 6, 1), currency="ILS", config_json={},
            ))
            db.commit()
        finally:
            db.close()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01", "end_date": "2035-01-01",
        })
        assert resp.status_code == 200, resp.text
        cash = _series_for(resp.json(), "Cash")
        before = cash.get("2030-05-01")
        after = cash.get("2030-06-01")
        assert before is not None and after is not None, f"missing sale-month cash points: {sorted(cash)[:3]}"
        # Pre-sale stock value is ~200k; cash must jump by roughly that, not stay flat.
        assert after - before > 100000, f"sale proceeds not credited to cash: {before} -> {after}"

    def test_all_assets_project_to_common_end_date(self):
        """Fix #3: assets with different start dates must all reach the shared end_date,
        so none drops out of the aggregate early (the phantom net-worth cliffs)."""
        db = TestingSessionLocal()
        try:
            db.add(Asset(
                user_id=1, portfolio_id=1, external_id="early", asset_type="stock", name="Early",
                start_date=date(2020, 1, 1), original_value=100000,
                appreciation_rate_annual_pct=5, yearly_fee_pct=0, sell_tax=0,
                currency="ILS", config_json={},
            ))
            db.add(Asset(
                user_id=1, portfolio_id=1, external_id="late", asset_type="stock", name="Late",
                start_date=date(2026, 1, 1), original_value=100000,
                appreciation_rate_annual_pct=5, yearly_fee_pct=0, sell_tax=0,
                currency="ILS", config_json={},
            ))
            db.commit()
        finally:
            db.close()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01", "end_date": "2050-01-01",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        early_last = _series_for(data, "Early") and list(_series_for(data, "Early"))[-1]
        late_last = _series_for(data, "Late") and list(_series_for(data, "Late"))[-1]
        # Both assets end on the same (near-end_date) month, not start+N staggered months.
        assert early_last == late_last, f"assets end on different dates: Early={early_last} Late={late_last}"
        assert early_last >= "2049-01-01", f"assets don't reach end_date: {early_last}"

    def test_annuitized_pension_zero_after_conversion(self):
        """Fix #4: a measurement shift must not resurrect the value a pension deliberately
        zeroes at conversion_date — post-conversion months must stay exactly 0, not a
        negative residual. The measurement's actual (200k) is below the projected balance,
        producing a negative delta that (before the fix) leaked onto the zeroed rows.
        """
        db = TestingSessionLocal()
        try:
            pension = Asset(
                user_id=1, portfolio_id=1, external_id="pension-conv", asset_type="pension",
                name="Annuity Pension", start_date=date(2020, 1, 1),
                original_value=200000, appreciation_rate_annual_pct=5,
                yearly_fee_pct=0, sell_tax=0, currency="ILS",
                config_json={"conversion_date": "2030-01-01",
                             "conversion_coefficient": 200,
                             "end_date": "2050-01-01"},
            )
            db.add(pension)
            db.flush()
            db.add(HistoricalMeasurement(
                user_id=1, portfolio_id=1, entity_type="asset", entity_id=pension.id,
                measurement_date=date(2024, 1, 1), actual_value=200000, source="manual",
            ))
            db.commit()
        finally:
            db.close()

        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01", "end_date": "2045-01-01",
        })
        assert resp.status_code == 200, resp.text
        pension_series = _series_for(resp.json(), "Annuity Pension")
        post = [v for d, v in pension_series.items() if d >= "2030-01-01"]
        assert post, "no post-conversion points found"
        offenders = [v for v in post if abs(v) >= 0.01]
        assert not offenders, f"pension not zero after annuitization: {offenders[:3]}"


class TestRealisticModelingFixes:
    """Regression tests for the loan-realism and pension/employer cash-flow fixes."""

    def _loan_payments(self, data, name):
        for lp in data["loan_projections"]:
            if lp["loan_name"] == name:
                return {p["date"]: float(p["value"]) for p in lp["payment_series"]}
        return {}

    def _asset_series(self, data, name):
        for ap in data["asset_projections"]:
            if ap["asset_name"] == name:
                return {p["date"]: float(p["value"]) for p in ap["time_series"]}
        return {}

    def test_cpi_loan_payment_keeps_indexing_after_last_real_cpi(self):
        """A CPI-linked loan's payment must keep growing with expected CPI past the last real
        data point — not freeze flat (the dead reindex/ffill extension bug)."""
        db = TestingSessionLocal()
        try:
            db.add(Loan(
                user_id=1, portfolio_id=1, external_id="cpi-1", loan_type="cpi_pegged", name="CPI Loan",
                start_date=date(2022, 5, 1), original_value=325000,
                interest_rate_annual_pct=2.25, duration_months=360,
                config_json={"expected_cpi_increase_percent_yearly": 3},
            ))
            db.commit()
        finally:
            db.close()
        resp = client.post("/api/projections/run", json={
            "start_date": "2022-05-01", "end_date": "2052-05-01"})
        assert resp.status_code == 200, resp.text
        pay = self._loan_payments(resp.json(), "CPI Loan")
        p2026, p2050 = pay.get("2026-01-01"), pay.get("2050-01-01")
        assert p2026 and p2050, f"missing CPI payment points: {sorted(pay)[:2]}"
        # ~2.5-3%/yr indexing over 24 years should lift the payment well above 1.5x, not freeze.
        assert p2050 > p2026 * 1.5, f"CPI payment froze instead of indexing: 2026={p2026:.0f} 2050={p2050:.0f}"

    def test_prime_loan_reacts_to_rate_cycle(self):
        """A prime-pegged loan's payment must move materially with the prime cycle (2022-23
        hikes of ~+4pp), not stay nearly flat (single-step-delta bug)."""
        db = TestingSessionLocal()
        try:
            db.add(Loan(
                user_id=1, portfolio_id=1, external_id="prime-1", loan_type="prime_pegged", name="Prime Loan",
                start_date=date(2022, 5, 1), original_value=600000,
                interest_rate_annual_pct=2.4, duration_months=360, config_json={},
            ))
            db.commit()
        finally:
            db.close()
        resp = client.post("/api/projections/run", json={
            "start_date": "2022-05-01", "end_date": "2035-01-01"})
        assert resp.status_code == 200, resp.text
        vals = list(self._loan_payments(resp.json(), "Prime Loan").values())
        assert vals, "no prime payments"
        assert max(vals) > min(vals) * 1.2, f"prime payment barely reacted: {min(vals):.0f}..{max(vals):.0f}"

    def test_pension_income_item_never_negative(self):
        """The pension breakdown 'income' item must never go negative — deposit contributions
        (negative cash flow) must not leak in as negative income (the double-count bug)."""
        db = TestingSessionLocal()
        try:
            asset = Asset(
                user_id=1, portfolio_id=1, external_id="pension-x", asset_type="pension", name="Pension X",
                start_date=date(2022, 1, 1), original_value=200000,
                appreciation_rate_annual_pct=4, yearly_fee_pct=0, sell_tax=0, currency="ILS",
                config_json={"conversion_date": "2035-01-01", "conversion_coefficient": 200},
            )
            db.add(asset)
            db.flush()
            db.add(CashFlow(
                user_id=1, portfolio_id=1, flow_type="deposit", target_asset_id=asset.id, name="pension deposit",
                amount=3000, from_date=date(2022, 1, 1), to_date=date(2035, 1, 1),
                from_own_capital=True,
            ))
            db.commit()
        finally:
            db.close()
        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01", "end_date": "2045-01-01"})
        assert resp.status_code == 200, resp.text
        bd = resp.json()["cash_flow_breakdown"]
        items = [it for it in bd["items"] if it["source_name"] == "Pension X - Pension"]
        assert items, "no pension income item found"
        negs = [float(p["value"]) for it in items for p in it["time_series"] if float(p["value"]) < 0]
        assert not negs, f"pension income item leaked negative deposit values: {negs[:3]}"

    def test_employer_stock_deposit_is_not_expense_or_cash(self):
        """A from_own_capital=false (employer) deposit on a stock asset must not appear as the
        user's expense and must not be credited to the user's cash balance."""
        db = TestingSessionLocal()
        try:
            asset = Asset(
                user_id=1, portfolio_id=1, external_id="stock-emp", asset_type="stock", name="Employer Stock",
                start_date=date(2020, 1, 1), original_value=100000, appreciation_rate_annual_pct=5,
                yearly_fee_pct=0, sell_tax=0, currency="ILS", config_json={},
            )
            db.add(asset)
            db.flush()
            db.add(CashFlow(
                user_id=1, portfolio_id=1, flow_type="deposit", target_asset_id=asset.id, name="employer deposit",
                amount=2000, from_date=date(2024, 1, 1), to_date=date(2030, 1, 1),
                from_own_capital=False,
            ))
            db.add(Asset(
                user_id=1, portfolio_id=1, external_id="cash-e", asset_type="cash", name="Cash E",
                start_date=date(2020, 1, 1), original_value=50000, appreciation_rate_annual_pct=0,
                yearly_fee_pct=0, sell_tax=0, currency="ILS", config_json={},
            ))
            db.commit()
        finally:
            db.close()
        resp = client.post("/api/projections/run", json={
            "start_date": "2024-01-01", "end_date": "2028-01-01"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        bd = data["cash_flow_breakdown"]
        assert not [it for it in bd["items"] if it["source_name"] == "Employer Stock - Own Capital"], \
            "employer deposit wrongly shown as the user's expense"
        cash = self._asset_series(data, "Cash E")
        c0, c1 = cash.get("2024-02-01"), cash.get("2025-02-01")
        assert c0 is not None and c1 is not None
        # Employer money never touches the user's bank — cash stays ~flat, not +24k/yr.
        assert abs(c1 - c0) < 5000, f"employer deposit wrongly credited cash: {c0:.0f} -> {c1:.0f}"
