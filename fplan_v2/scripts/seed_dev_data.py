"""
Seed development data for FPlan v2.

Creates sample users, assets, loans, and revenue streams for local development.
Idempotent: safe to run multiple times (uses ON CONFLICT DO NOTHING pattern).

Usage:
    python -m fplan_v2.scripts.seed_dev_data
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import inspect

from fplan_v2.db.connection import get_db_manager
from fplan_v2.db.models import Base, User, Asset, Loan, RevenueStream


def seed():
    """Insert development seed data."""
    db_manager = get_db_manager()

    # Create tables if they don't exist
    print("Ensuring tables exist...")
    db_manager.create_all()

    with db_manager.session() as session:
        # --- User ---
        user = session.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, name="Dev User", email="dev@fplan.local")
            session.add(user)
            session.flush()
            print("Created user: Dev User (id=1)")
        else:
            print("User id=1 already exists, skipping.")

        # --- Assets ---
        assets_data = [
            {
                "external_id": "apartment-tlv",
                "asset_type": "real_estate",
                "name": "\u05d3\u05d9\u05e8\u05d4 \u05d1\u05ea\u05dc \u05d0\u05d1\u05d9\u05d1",
                "original_value": Decimal("2500000.00"),
                "appreciation_rate_annual_pct": Decimal("5.00"),
                "currency": "ILS",
            },
            {
                "external_id": "stock-portfolio",
                "asset_type": "stock",
                "name": "\u05ea\u05d9\u05e7 \u05de\u05e0\u05d9\u05d5\u05ea",
                "original_value": Decimal("500000.00"),
                "appreciation_rate_annual_pct": Decimal("8.00"),
                "currency": "ILS",
            },
            {
                "external_id": "pension-fund",
                "asset_type": "pension",
                "name": "\u05e4\u05e0\u05e1\u05d9\u05d4",
                "original_value": Decimal("800000.00"),
                "appreciation_rate_annual_pct": Decimal("4.00"),
                "currency": "ILS",
            },
            {
                "external_id": "checking-account",
                "asset_type": "cash",
                "name": "\u05d7\u05e9\u05d1\u05d5\u05df \u05e2\u05d5\u05f4\u05e9",
                "original_value": Decimal("150000.00"),
                "appreciation_rate_annual_pct": Decimal("0.00"),
                "currency": "ILS",
            },
        ]

        for asset_data in assets_data:
            existing = (
                session.query(Asset)
                .filter(Asset.user_id == 1, Asset.external_id == asset_data["external_id"])
                .first()
            )
            if not existing:
                asset = Asset(
                    user_id=1,
                    start_date=date(2024, 1, 1),
                    config_json={},
                    **asset_data,
                )
                session.add(asset)
                print(f"  Created asset: {asset_data['name']} ({asset_data['external_id']})")
            else:
                print(f"  Asset '{asset_data['external_id']}' already exists, skipping.")

        session.flush()

        # --- Loans ---
        loans_data = [
            {
                "external_id": "mortgage-fixed",
                "loan_type": "fixed",
                "name": "\u05de\u05e9\u05db\u05e0\u05ea\u05d0 \u05e7\u05d1\u05d5\u05e2\u05d4",
                "original_value": Decimal("1200000.00"),
                "interest_rate_annual_pct": Decimal("3.50"),
                "duration_months": 240,
            },
            {
                "external_id": "mortgage-prime",
                "loan_type": "prime_pegged",
                "name": "\u05de\u05e9\u05db\u05e0\u05ea\u05d0 \u05e4\u05e8\u05d9\u05d9\u05dd",
                "original_value": Decimal("400000.00"),
                "interest_rate_annual_pct": Decimal("1.50"),
                "duration_months": 180,
            },
        ]

        # Look up the real estate asset for collateral
        re_asset = (
            session.query(Asset)
            .filter(Asset.user_id == 1, Asset.external_id == "apartment-tlv")
            .first()
        )
        collateral_id = re_asset.id if re_asset else None

        for loan_data in loans_data:
            existing = (
                session.query(Loan)
                .filter(Loan.user_id == 1, Loan.external_id == loan_data["external_id"])
                .first()
            )
            if not existing:
                loan = Loan(
                    user_id=1,
                    start_date=date(2024, 1, 1),
                    collateral_asset_id=collateral_id,
                    config_json={},
                    **loan_data,
                )
                session.add(loan)
                print(f"  Created loan: {loan_data['name']} ({loan_data['external_id']})")
            else:
                print(f"  Loan '{loan_data['external_id']}' already exists, skipping.")

        session.flush()

        # --- Revenue Streams ---
        streams_data = [
            {
                "external_id": "rent-apartment",
                "stream_type": "rent",
                "name": "\u05e9\u05db\u05d9\u05e8\u05d5\u05ea \u05d3\u05d9\u05e8\u05d4",
                "amount": Decimal("6500.00"),
                "growth_rate": Decimal("2.00"),
                "asset_id_ref": "apartment-tlv",
            },
            {
                "external_id": "salary-main",
                "stream_type": "salary",
                "name": "\u05de\u05e9\u05db\u05d5\u05e8\u05ea",
                "amount": Decimal("25000.00"),
                "growth_rate": Decimal("3.00"),
                "asset_id_ref": None,
            },
        ]

        for stream_data in streams_data:
            existing = (
                session.query(RevenueStream)
                .filter(
                    RevenueStream.user_id == 1,
                    RevenueStream.name == stream_data["name"],
                    RevenueStream.stream_type == stream_data["stream_type"],
                )
                .first()
            )
            if not existing:
                # Resolve asset_id from external_id reference
                linked_asset_id = None
                if stream_data["asset_id_ref"]:
                    linked_asset = (
                        session.query(Asset)
                        .filter(Asset.user_id == 1, Asset.external_id == stream_data["asset_id_ref"])
                        .first()
                    )
                    linked_asset_id = linked_asset.id if linked_asset else None

                stream = RevenueStream(
                    user_id=1,
                    start_date=date(2024, 1, 1),
                    amount=stream_data["amount"],
                    stream_type=stream_data["stream_type"],
                    name=stream_data["name"],
                    growth_rate=stream_data["growth_rate"],
                    period="monthly",
                    tax_rate=Decimal("0.00"),
                    asset_id=linked_asset_id,
                    config_json={},
                )
                session.add(stream)
                print(f"  Created revenue stream: {stream_data['name']}")
            else:
                print(f"  Revenue stream '{stream_data['name']}' already exists, skipping.")

    print("\nSeed data complete.")


if __name__ == "__main__":
    seed()
