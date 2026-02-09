"""
Migrate a v1 JSON config file into the v2 database.

Usage:
    python3 -m fplan_v2.scripts.migrate_v1_config
"""

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from fplan_v2.db.connection import get_db_manager
from fplan_v2.db.models import Asset, CashFlow, Loan, RevenueStream, User

# --- Configuration ---
V1_CONFIG_PATH = Path("/Users/sergeibenkovitch/repos/fplan/backend/configs/padres/retirement_2024.json")
TARGET_EMAIL = "sinyab@gmail.com"

# Type mapping: v1 "Type" -> v2 asset_type
ASSET_TYPE_MAP = {
    "Real Estate": "real_estate",
    "Stock": "stock",
    "Pension": "pension",
    "Cash": "cash",
}

# Loan type mapping: v1 category -> v2 loan_type
LOAN_TYPE_MAP = {
    "fixed_interest": "fixed",
    "prime_loans": "prime_pegged",
    "cpi_loans": "cpi_pegged",
}


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def migrate():
    with open(V1_CONFIG_PATH) as f:
        config = json.load(f)

    db = get_db_manager()

    with db.session() as session:
        # Find or create user
        user = session.query(User).filter_by(email=TARGET_EMAIL).first()
        if not user:
            user = User(name="Sergei", email=TARGET_EMAIL, auth_provider="clerk")
            session.add(user)
            session.flush()
            print(f"Created user: {user.id} ({user.email})")
        else:
            print(f"Found existing user: {user.id} ({user.email})")

        # Wipe existing mock data
        for model in [CashFlow, RevenueStream, Loan, Asset]:
            count = session.query(model).filter_by(user_id=user.id).delete()
            if count:
                print(f"  Deleted {count} existing {model.__tablename__}")

        # --- Assets ---
        asset_map = {}  # name -> Asset object (for linking loans/cash_flows)

        for name, data in config["asset_list"].items():
            v1_type = data.get("Type", "Stock")
            asset = Asset(
                user_id=user.id,
                external_id=name,
                asset_type=ASSET_TYPE_MAP.get(v1_type, "stock"),
                name=name,
                start_date=parse_date(data["start_date"]),
                original_value=Decimal(data["original_value"]),
                current_value=Decimal(data["original_value"]),
                appreciation_rate_annual_pct=Decimal(data.get("appreciation_rate", "0")),
                yearly_fee_pct=Decimal(data.get("yearly_fee", "0")),
                sell_date=parse_date(data["sell_date"]) if data.get("sell_date") else None,
                config_json={
                    "v1_revenue_stream": data.get("revenue_stream", {}),
                },
            )
            session.add(asset)
            session.flush()
            asset_map[name] = asset
            print(f"  Asset: {name} (id={asset.id}, type={asset.asset_type}, value={asset.original_value})")

            # --- Deposits (CashFlow) from asset config ---
            deposit_amount = Decimal(data.get("deposit_amount", "0"))
            if deposit_amount > 0 and data.get("deposit_from") and data.get("deposit_to"):
                cf = CashFlow(
                    user_id=user.id,
                    flow_type="deposit",
                    target_asset_id=asset.id,
                    name=f"deposit_{name}",
                    amount=deposit_amount,
                    from_date=parse_date(data["deposit_from"]),
                    to_date=parse_date(data["deposit_to"]),
                    from_own_capital=data.get("deposit_from_own_capital", True),
                )
                session.add(cf)
                print(f"    Deposit: {deposit_amount}/mo ({data['deposit_from']} -> {data['deposit_to']})")

            # --- Revenue streams from asset config ---
            rs = data.get("revenue_stream", {})
            monthly_payout = Decimal(rs.get("monthly_payout", "0"))
            if monthly_payout > 0 and rs.get("start_dividend_withdraw_date"):
                rev = RevenueStream(
                    user_id=user.id,
                    asset_id=asset.id,
                    stream_type="pension",
                    name=f"payout_{name}",
                    start_date=parse_date(rs["start_dividend_withdraw_date"]),
                    amount=monthly_payout,
                    period="monthly",
                    tax_rate=Decimal(rs.get("tax", "0")),
                    config_json={"v1_dividend_yield": rs.get("dividend_yield", "0")},
                )
                session.add(rev)
                print(f"    Revenue: {monthly_payout}/mo pension from {rs['start_dividend_withdraw_date']}")

        # --- Loans ---
        for loan_category, loans in config.get("loan_list", {}).items():
            v2_type = LOAN_TYPE_MAP.get(loan_category, "fixed")
            for loan_data in loans:
                collateral_name = loan_data.get("collateral_asset")
                collateral_asset = asset_map.get(collateral_name)

                config_extra = {}
                if loan_category == "cpi_loans":
                    config_extra["expected_cpi_increase_percent_yearly"] = loan_data.get(
                        "expected_cpi_increase_percent_yearly", 3
                    )

                loan = Loan(
                    user_id=user.id,
                    external_id=loan_data["name"],
                    loan_type=v2_type,
                    name=loan_data["name"],
                    start_date=parse_date(loan_data["start_date"]),
                    original_value=Decimal(str(loan_data["original_value"])),
                    current_balance=Decimal(str(loan_data["original_value"])),
                    interest_rate_annual_pct=Decimal(str(loan_data["interest_rate"])),
                    duration_months=loan_data["duration"],
                    collateral_asset_id=collateral_asset.id if collateral_asset else None,
                    config_json={
                        "v1_end_date": loan_data.get("end_date"),
                        **config_extra,
                    },
                )
                session.add(loan)
                print(
                    f"  Loan: {loan_data['name']} (type={v2_type}, "
                    f"amount={loan_data['original_value']}, rate={loan_data['interest_rate']}%, "
                    f"months={loan_data['duration']}, collateral={collateral_name})"
                )

        # --- Withdrawals ---
        for name, data in config.get("withdrawals_list", {}).items():
            amount = abs(Decimal(data["amount"]))
            cf = CashFlow(
                user_id=user.id,
                flow_type="withdrawal",
                name=name,
                amount=amount,
                from_date=parse_date(data["from"]),
                to_date=parse_date(data["to"]),
                from_own_capital=False,
            )
            session.add(cf)
            print(f"  Withdrawal: {name} ({amount}/mo from {data['from']} to {data['to']})")

        # Commit happens automatically via context manager
        print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
