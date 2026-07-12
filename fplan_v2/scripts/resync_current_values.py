"""
One-time repair: re-sync asset current_value / loan current_balance to the
latest-by-date historical measurement.

Fixes rows left stale by the old behavior where the last-INSERTED measurement
(rather than the latest-by-date one) overwrote the entity value, and where
measurement edits/deletes never re-synced it.

Usage:
    python -m fplan_v2.scripts.resync_current_values [--dry-run]

Uses NEON_DATABASE_URL or DATABASE_URL from the environment (.env is loaded).
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fplan_v2.db.models import Asset, Loan, HistoricalMeasurement

load_dotenv()


def resync_current_values(dry_run: bool = False):
    db_url = os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("Database URL not configured")

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        measurements = session.query(HistoricalMeasurement).all()

        # Latest measurement per (entity_type, entity_id), by date then id
        latest = {}
        for m in measurements:
            key = (m.entity_type, m.entity_id)
            if key not in latest or (m.measurement_date, m.id) > (
                latest[key].measurement_date,
                latest[key].id,
            ):
                latest[key] = m

        fixed = 0
        for (entity_type, entity_id), m in sorted(latest.items()):
            if entity_type == "asset":
                entity = session.get(Asset, entity_id)
                field = "current_value"
            elif entity_type == "loan":
                entity = session.get(Loan, entity_id)
                field = "current_balance"
            else:
                continue

            if entity is None:
                print(f"  ⚠ {entity_type} {entity_id} not found (orphan measurements), skipping")
                continue

            old_value = getattr(entity, field)
            if old_value == m.actual_value:
                continue

            print(
                f"  {entity_type} {entity_id} ({getattr(entity, 'name', '?')}): "
                f"{field} {old_value} → {m.actual_value} "
                f"(measurement {m.id} on {m.measurement_date})"
            )
            if not dry_run:
                setattr(entity, field, m.actual_value)
            fixed += 1

        if dry_run:
            print(f"\nDry run: {fixed} entit(ies) would be updated")
            session.rollback()
        else:
            session.commit()
            print(f"\n✓ Updated {fixed} entit(ies)")
    finally:
        session.close()


if __name__ == "__main__":
    resync_current_values(dry_run="--dry-run" in sys.argv)
