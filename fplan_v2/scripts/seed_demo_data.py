"""
Seed demo data for FPlan v2 public showcase.

Creates a demo user (clerk_id="demo") with a realistic Israeli portfolio.
Idempotent: deletes existing demo data and re-seeds from scratch.

Usage:
    python -m fplan_v2.scripts.seed_demo_data
"""

from datetime import date
from decimal import Decimal

from fplan_v2.db.connection import get_db_manager
from fplan_v2.db.models import User, Asset, Loan, RevenueStream, CashFlow

DEMO_CLERK_ID = "demo"


def delete_demo_data(session):
    """Delete all data belonging to the demo user."""
    demo_user = session.query(User).filter_by(clerk_id=DEMO_CLERK_ID).first()
    if demo_user:
        # Cascade delete handles assets, loans, revenue_streams, cash_flows
        session.delete(demo_user)
        session.flush()
        print("Deleted existing demo user and all associated data.")


def seed_demo_data(session):
    """Create demo user with realistic Israeli portfolio data."""
    # --- Demo User ---
    user = User(
        name="Demo User",
        email="demo@fplan.example",
        clerk_id=DEMO_CLERK_ID,
        auth_provider="demo",
    )
    session.add(user)
    session.flush()
    print(f"Created demo user (id={user.id})")

    # --- Assets ---
    apartment = Asset(
        user_id=user.id,
        external_id="apartment-tlv",
        asset_type="real_estate",
        name="\u05d3\u05d9\u05e8\u05d4 \u05d1\u05ea\u05dc \u05d0\u05d1\u05d9\u05d1",
        start_date=date(2021, 3, 1),
        original_value=Decimal("2500000.00"),
        appreciation_rate_annual_pct=Decimal("5.00"),
        currency="ILS",
        config_json={},
    )
    stocks = Asset(
        user_id=user.id,
        external_id="stock-portfolio",
        asset_type="stock",
        name="\u05ea\u05d9\u05e7 \u05de\u05e0\u05d9\u05d5\u05ea",
        start_date=date(2020, 1, 1),
        original_value=Decimal("500000.00"),
        appreciation_rate_annual_pct=Decimal("8.00"),
        currency="ILS",
        config_json={},
    )
    pension = Asset(
        user_id=user.id,
        external_id="pension-fund",
        asset_type="pension",
        name="\u05e4\u05e0\u05e1\u05d9\u05d4",
        start_date=date(2015, 6, 1),
        original_value=Decimal("800000.00"),
        appreciation_rate_annual_pct=Decimal("4.00"),
        currency="ILS",
        config_json={
            "conversion_date": "2052-01-01",
            "conversion_coefficient": 200,
        },
    )
    checking = Asset(
        user_id=user.id,
        external_id="checking-account",
        asset_type="cash",
        name="\u05d7\u05e9\u05d1\u05d5\u05df \u05e2\u05d5\u05f4\u05e9",
        start_date=date(2020, 1, 1),
        original_value=Decimal("150000.00"),
        appreciation_rate_annual_pct=Decimal("0.00"),
        currency="ILS",
        config_json={},
    )
    session.add_all([apartment, stocks, pension, checking])
    session.flush()
    print(f"  Created 4 assets")

    # --- Loans (linked to apartment) ---
    mortgage_fixed = Loan(
        user_id=user.id,
        external_id="mortgage-fixed",
        loan_type="fixed",
        name="\u05de\u05e9\u05db\u05e0\u05ea\u05d0 \u05e7\u05d1\u05d5\u05e2\u05d4",
        start_date=date(2021, 3, 1),
        original_value=Decimal("1200000.00"),
        interest_rate_annual_pct=Decimal("3.50"),
        duration_months=240,
        collateral_asset_id=apartment.id,
        config_json={},
    )
    mortgage_prime = Loan(
        user_id=user.id,
        external_id="mortgage-prime",
        loan_type="prime_pegged",
        name="\u05de\u05e9\u05db\u05e0\u05ea\u05d0 \u05e4\u05e8\u05d9\u05d9\u05dd",
        start_date=date(2021, 3, 1),
        original_value=Decimal("400000.00"),
        interest_rate_annual_pct=Decimal("1.50"),
        duration_months=180,
        collateral_asset_id=apartment.id,
        config_json={},
    )
    session.add_all([mortgage_fixed, mortgage_prime])
    session.flush()
    print(f"  Created 2 loans")

    # --- Revenue Streams ---
    rent = RevenueStream(
        user_id=user.id,
        asset_id=apartment.id,
        stream_type="rent",
        name="\u05e9\u05db\u05d9\u05e8\u05d5\u05ea \u05d3\u05d9\u05e8\u05d4",
        start_date=date(2021, 6, 1),
        amount=Decimal("6500.00"),
        period="monthly",
        tax_rate=Decimal("10.00"),
        growth_rate=Decimal("2.00"),
        config_json={},
    )
    salary = RevenueStream(
        user_id=user.id,
        asset_id=None,
        stream_type="salary",
        name="\u05de\u05e9\u05db\u05d5\u05e8\u05ea",
        start_date=date(2020, 1, 1),
        amount=Decimal("25000.00"),
        period="monthly",
        tax_rate=Decimal("30.00"),
        growth_rate=Decimal("3.00"),
        config_json={},
    )
    dividends = RevenueStream(
        user_id=user.id,
        asset_id=stocks.id,
        stream_type="dividend",
        name="\u05d3\u05d9\u05d1\u05d9\u05d3\u05e0\u05d3\u05d9\u05dd",
        start_date=date(2020, 6, 1),
        amount=Decimal("5000.00"),
        period="quarterly",
        tax_rate=Decimal("25.00"),
        growth_rate=Decimal("2.00"),
        config_json={},
    )
    session.add_all([rent, salary, dividends])
    session.flush()
    print(f"  Created 3 revenue streams")

    # --- Cash Flows ---
    pension_deposit = CashFlow(
        user_id=user.id,
        flow_type="deposit",
        target_asset_id=pension.id,
        name="\u05d4\u05e4\u05e7\u05d3\u05d4 \u05dc\u05e4\u05e0\u05e1\u05d9\u05d4",
        amount=Decimal("3000.00"),
        from_date=date(2020, 1, 1),
        to_date=date(2052, 1, 1),
        from_own_capital=True,
    )
    employer_pension = CashFlow(
        user_id=user.id,
        flow_type="deposit",
        target_asset_id=pension.id,
        name="\u05d4\u05e4\u05e7\u05d3\u05ea \u05de\u05e2\u05e1\u05d9\u05e7",
        amount=Decimal("2000.00"),
        from_date=date(2020, 1, 1),
        to_date=date(2052, 1, 1),
        from_own_capital=False,
    )
    session.add_all([pension_deposit, employer_pension])
    session.flush()
    print(f"  Created 2 cash flows")


def seed():
    """Full seed: delete existing demo data, then re-seed."""
    db_manager = get_db_manager()
    db_manager.create_all()

    with db_manager.session() as session:
        delete_demo_data(session)
        seed_demo_data(session)

    print("\nDemo data seeding complete.")


if __name__ == "__main__":
    seed()
