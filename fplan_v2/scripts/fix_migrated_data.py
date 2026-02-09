"""
One-time DB fix script for migrated v1 data:

1. Fix from_own_capital: Set employer deposits to false (only deposit_ibi is own capital)
2. Fix pension asset types: Change stock -> pension for pension_y, pension_y2, menahalim_n
3. Set conversion config (conversion_date, conversion_coefficient) on pension assets
4. Remove stale revenue streams (payout_pension_y, payout_pension_y2, payout_menahalim_n)
   since pension payouts are now dynamically calculated via conversion model

Usage:
    python3 -m fplan_v2.scripts.fix_migrated_data
"""

from datetime import date
from dateutil.relativedelta import relativedelta
from fplan_v2.db.connection import get_db_manager
from fplan_v2.db.models import Asset, CashFlow, Loan, RevenueStream, User

TARGET_EMAIL = "sinyab@gmail.com"

# Deposits that are NOT from own capital (employer contributions)
EMPLOYER_DEPOSIT_NAMES = [
    "deposit_hishtalmut_n",
    "deposit_hishtalmut_y",
    "deposit_pension_y",
    "deposit_pension_y2",
    "deposit_menahalim_n",
]

# Assets that should be pension type with conversion config
PENSION_ASSETS = {
    "pension_y": {"conversion_date": "2031-09-30", "conversion_coefficient": 200},
    "pension_y2": {"conversion_date": "2031-09-30", "conversion_coefficient": 200},
    "menahalim_n": {"conversion_date": "2027-07-31", "conversion_coefficient": 200},
}

# Revenue streams to delete (will be replaced by conversion model)
STALE_REVENUE_NAMES = [
    "payout_pension_y",
    "payout_pension_y2",
    "payout_menahalim_n",
]


def fix():
    db = get_db_manager()

    with db.session() as session:
        user = session.query(User).filter_by(email=TARGET_EMAIL).first()
        if not user:
            print(f"User {TARGET_EMAIL} not found!")
            return

        print(f"User: {user.id} ({user.email})")

        # --- Fix 1: Set from_own_capital=false for employer deposits ---
        employer_deposits = (
            session.query(CashFlow)
            .filter(
                CashFlow.user_id == user.id,
                CashFlow.name.in_(EMPLOYER_DEPOSIT_NAMES),
            )
            .all()
        )
        for cf in employer_deposits:
            old_val = cf.from_own_capital
            cf.from_own_capital = False
            print(f"  CashFlow '{cf.name}': from_own_capital {old_val} -> False")

        if not employer_deposits:
            print("  No employer deposits found to fix")

        # --- Fix 2: Change asset_type to pension + set conversion config ---
        for asset_name, conv_config in PENSION_ASSETS.items():
            asset = (
                session.query(Asset)
                .filter(Asset.user_id == user.id, Asset.external_id == asset_name)
                .first()
            )
            if not asset:
                print(f"  Asset '{asset_name}' not found, skipping")
                continue

            old_type = asset.asset_type
            asset.asset_type = "pension"

            # Merge conversion config into existing config_json
            config = dict(asset.config_json) if asset.config_json else {}
            config["conversion_date"] = conv_config["conversion_date"]
            config["conversion_coefficient"] = conv_config["conversion_coefficient"]
            asset.config_json = config

            # Sync sell_date = conversion_date (conversion replaces sell for pension)
            asset.sell_date = date.fromisoformat(conv_config["conversion_date"])
            asset.sell_tax = 0

            print(
                f"  Asset '{asset_name}': type {old_type} -> pension, "
                f"conversion_date={conv_config['conversion_date']}, "
                f"coefficient={conv_config['conversion_coefficient']}, "
                f"sell_date synced to conversion_date"
            )

        # --- Fix 3: Delete stale revenue streams ---
        stale_revenues = (
            session.query(RevenueStream)
            .filter(
                RevenueStream.user_id == user.id,
                RevenueStream.name.in_(STALE_REVENUE_NAMES),
            )
            .all()
        )
        for rev in stale_revenues:
            print(f"  Deleting RevenueStream '{rev.name}' (id={rev.id}, amount={rev.amount}/mo)")
            session.delete(rev)

        if not stale_revenues:
            print("  No stale revenue streams found to delete")

        # --- Fix 4: Add end_date to loan config_json ---
        loans = session.query(Loan).filter(Loan.user_id == user.id).all()
        for loan in loans:
            if loan.start_date and loan.duration_months:
                end_date = loan.start_date + relativedelta(months=loan.duration_months)
                config = dict(loan.config_json) if loan.config_json else {}
                config["end_date"] = end_date.isoformat()
                loan.config_json = config
                print(f"  Loan '{loan.name}': added end_date={end_date.isoformat()}")

        print("\nFix complete!")


if __name__ == "__main__":
    fix()
