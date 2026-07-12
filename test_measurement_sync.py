#!/usr/bin/env python3
"""
Test that asset current_value stays in sync with the latest-by-date measurement.

Covers the שווי נוכחי bug: current_value must always reflect the measurement
with the latest measurement_date — not the last-inserted one — and must be
re-synced after measurement edits and deletes.
"""

import sys
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, '/Users/sergeibenkovitch/repos/financial-planner')

from fplan_v2.db.models import Base, User, Asset
from fplan_v2.db.repositories import (
    AssetRepository,
    HistoricalMeasurementRepository,
)
from fplan_v2.api.routes.historical_measurements import _sync_entity_value

# Production models use Postgres JSONB columns; teach the SQLite compiler (used
# for these in-memory tests) to render JSONB as JSON so create_all() succeeds.
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def check(label, actual, expected):
    status = "✓" if actual == expected else "✗"
    print(f"{status} {label}: current_value={actual} (expected {expected})")
    return actual == expected


def test_measurement_sync():
    session = Session()
    ok = True

    try:
        user = User(email="test@example.com", name="Test User", portfolio_version=1)
        session.add(user)
        session.flush()

        asset_repo = AssetRepository(session)
        asset = asset_repo.create(
            user_id=user.id,
            external_id="test-asset-1",
            asset_type="stock",
            name="Test Stock",
            original_value=50.0,
            start_date=date(2026, 1, 1),
        )

        m_repo = HistoricalMeasurementRepository(session)

        def log(value, mdate):
            m = m_repo.create(
                user_id=user.id,
                entity_type="asset",
                entity_id=asset.id,
                measurement_date=mdate,
                actual_value=value,
                source="manual",
            )
            _sync_entity_value(session, user.id, "asset", asset.id)
            session.refresh(asset)
            return m

        # 1. Log 100 today → current_value = 100
        m_today = log(100.0, date(2026, 7, 12))
        ok &= check("log 100 (today)", asset.current_value, 100.0)

        # 2. Backfill 80 a month ago → current_value stays 100 (old bug: dropped to 80)
        m_old = log(80.0, date(2026, 6, 12))
        ok &= check("backfill 80 (older date)", asset.current_value, 100.0)

        # 3. Edit today's measurement to 120 → current_value = 120
        m_repo.update(m_today.id, actual_value=120.0)
        _sync_entity_value(session, user.id, "asset", asset.id)
        session.refresh(asset)
        ok &= check("edit today's to 120", asset.current_value, 120.0)

        # 4. Delete today's measurement → current_value falls back to 80
        m_repo.delete(m_today.id)
        _sync_entity_value(session, user.id, "asset", asset.id)
        session.refresh(asset)
        ok &= check("delete today's", asset.current_value, 80.0)

        # 5. Delete the last measurement → current_value left unchanged
        m_repo.delete(m_old.id)
        _sync_entity_value(session, user.id, "asset", asset.id)
        session.refresh(asset)
        ok &= check("delete last (value unchanged)", asset.current_value, 80.0)

        print("\n" + ("PASS" if ok else "FAIL"))
        return ok
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(0 if test_measurement_sync() else 1)
