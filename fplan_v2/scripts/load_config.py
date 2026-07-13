"""
Load a v1 JSON config into the v2 database, INCLUDING per-asset history.

Unlike migrate_v1_config.py, this importer reads each asset's `history` array
into historical_measurements and then syncs current_value to the latest-by-date
measurement (via the same _sync_entity_value helper the API uses). That means
the שווי נוכחי column reflects the most recent logged value, not original_value.

Usage:
    python3 -m fplan_v2.scripts.load_config [CONFIG_PATH] [--user-id N] [--email E]

Defaults to the our_baseline/2025_july.json config and single-user id=1 (so a
backend running without CLERK_SECRET_KEY displays it). Respects NEON_DATABASE_URL
/ DATABASE_URL from the environment — point it at a local DB for local testing.
"""

import argparse
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from fplan_v2.db.connection import get_db_manager
from fplan_v2.db.models import (
    Asset,
    CashFlow,
    HistoricalMeasurement,
    Loan,
    RevenueStream,
    User,
)
from fplan_v2.api.routes.historical_measurements import _sync_entity_value

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "data/configs/our_baseline/2025_july.json"

ASSET_TYPE_MAP = {
    "Real Estate": "real_estate",
    "Stock": "stock",
    "Pension": "pension",
    "Cash": "cash",
}

LOAN_TYPE_MAP = {
    "fixed_interest": "fixed",
    "prime_loans": "prime_pegged",
    "cpi_loans": "cpi_pegged",
}


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def load(config_path: Path, user_id: int, email: str) -> None:
    with open(config_path) as f:
        config = json.load(f)

    db = get_db_manager()
    db.create_all()

    with db.session() as session:
        user = session.get(User, user_id)
        if not user:
            user = User(id=user_id, name="Sergei", email=email, auth_provider="clerk")
            session.add(user)
            session.flush()
            print(f"Created user id={user.id} ({user.email})")
        else:
            print(f"Reusing user id={user.id} ({user.email}) — wiping its data")

        # Wipe existing data for this user so re-runs are idempotent
        for model in [HistoricalMeasurement, CashFlow, RevenueStream, Loan, Asset]:
            count = session.query(model).filter_by(user_id=user.id).delete()
            if count:
                print(f"  Deleted {count} existing {model.__tablename__}")
        session.flush()

        asset_map = {}  # name -> Asset (for loan collateral linking)

        for name, data in config["asset_list"].items():
            v1_type = data.get("Type", "Stock")
            original = Decimal(str(data["original_value"]))
            # Pass through v2 pension fields (conversion_date / conversion_coefficient /
            # end_date) so PensionAsset can annuitize at retirement.
            config_json = {"v1_revenue_stream": data.get("revenue_stream", {})}
            for k in ("conversion_date", "conversion_coefficient", "end_date"):
                if data.get(k) is not None:
                    config_json[k] = data[k]
            asset = Asset(
                user_id=user.id,
                external_id=name,
                asset_type=ASSET_TYPE_MAP.get(v1_type, "stock"),
                name=name,
                start_date=parse_date(data["start_date"]),
                original_value=original,
                current_value=original,  # provisional; corrected by _sync_entity_value below
                appreciation_rate_annual_pct=Decimal(str(data.get("appreciation_rate", "0"))),
                yearly_fee_pct=Decimal(str(data.get("yearly_fee", "0"))),
                sell_date=parse_date(data["sell_date"]) if data.get("sell_date") else None,
                config_json=config_json,
            )
            session.add(asset)
            session.flush()
            asset_map[name] = asset

            # History -> measurements
            for entry in data.get("history", []):
                session.add(
                    HistoricalMeasurement(
                        user_id=user.id,
                        entity_type="asset",
                        entity_id=asset.id,
                        measurement_date=parse_date(entry["date"]),
                        actual_value=Decimal(str(entry["value"])),
                        source="import",
                    )
                )
            session.flush()

            # Sync current_value to the latest-by-date measurement (no-op if no history)
            _sync_entity_value(session, user.id, "asset", asset.id)
            session.refresh(asset)
            print(
                f"  Asset: {name} (id={asset.id}, type={asset.asset_type}, "
                f"original={original}, current={asset.current_value}, "
                f"history={len(data.get('history', []))})"
            )

            # Deposits (CashFlow)
            deposit_amount = Decimal(str(data.get("deposit_amount", "0")))
            if deposit_amount > 0 and data.get("deposit_from") and data.get("deposit_to"):
                session.add(
                    CashFlow(
                        user_id=user.id,
                        flow_type="deposit",
                        target_asset_id=asset.id,
                        name=f"deposit_{name}",
                        amount=deposit_amount,
                        from_date=parse_date(data["deposit_from"]),
                        to_date=parse_date(data["deposit_to"]),
                        from_own_capital=data.get("deposit_from_own_capital", True),
                    )
                )

            # Pension-style payout revenue stream
            rs = data.get("revenue_stream", {})
            monthly_payout = Decimal(str(rs.get("monthly_payout", "0")))
            if monthly_payout > 0 and rs.get("start_dividend_withdraw_date"):
                session.add(
                    RevenueStream(
                        user_id=user.id,
                        asset_id=asset.id,
                        stream_type="pension",
                        name=f"payout_{name}",
                        start_date=parse_date(rs["start_dividend_withdraw_date"]),
                        amount=monthly_payout,
                        period="monthly",
                        tax_rate=Decimal(str(rs.get("tax", "0"))),
                        config_json={"v1_dividend_yield": rs.get("dividend_yield", "0")},
                    )
                )

            # Rent revenue stream (real estate)
            if rs.get("type") == "rent" and Decimal(str(rs.get("monthly_cashflow", "0"))) > 0:
                session.add(
                    RevenueStream(
                        user_id=user.id,
                        asset_id=asset.id,
                        stream_type="rent",
                        name=f"rent_{name}",
                        start_date=parse_date(rs.get("rent_start_date", data["start_date"])),
                        amount=Decimal(str(rs["monthly_cashflow"])),
                        period=rs.get("period", "monthly"),
                        tax_rate=Decimal(str(rs.get("tax", "0"))),
                        growth_rate=Decimal(str(rs.get("growth_rate", "0"))),
                        config_json={},
                    )
                )

        # Loans
        for loan_category, loans in config.get("loan_list", {}).items():
            v2_type = LOAN_TYPE_MAP.get(loan_category, "fixed")
            for loan_data in loans:
                collateral = asset_map.get(loan_data.get("collateral_asset"))
                config_extra = {}
                if loan_category == "cpi_loans":
                    config_extra["expected_cpi_increase_percent_yearly"] = loan_data.get(
                        "expected_cpi_increase_percent_yearly", 3
                    )
                original = Decimal(str(loan_data["original_value"]))
                session.add(
                    Loan(
                        user_id=user.id,
                        external_id=loan_data["name"],
                        loan_type=v2_type,
                        name=loan_data["name"],
                        start_date=parse_date(loan_data["start_date"]),
                        original_value=original,
                        current_balance=original,
                        interest_rate_annual_pct=Decimal(str(loan_data["interest_rate"])),
                        duration_months=loan_data["duration"],
                        collateral_asset_id=collateral.id if collateral else None,
                        config_json={"v1_end_date": loan_data.get("end_date"), **config_extra},
                    )
                )
                print(f"  Loan: {loan_data['name']} (type={v2_type}, amount={original})")

        # Withdrawals
        for name, data in config.get("withdrawals_list", {}).items():
            amount = abs(Decimal(str(data["amount"])))
            session.add(
                CashFlow(
                    user_id=user.id,
                    flow_type="withdrawal",
                    name=name,
                    amount=amount,
                    from_date=parse_date(data["from"]),
                    to_date=parse_date(data["to"]),
                    from_own_capital=False,
                )
            )

        print("\nLoad complete.")


def main():
    parser = argparse.ArgumentParser(description="Load a v1 config (with history) into the v2 DB")
    parser.add_argument("config_path", nargs="?", default=str(DEFAULT_CONFIG))
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--email", default="sergei@fplan.local")
    args = parser.parse_args()
    load(Path(args.config_path), args.user_id, args.email)


if __name__ == "__main__":
    main()
