#!/usr/bin/env python3
"""
Test script to verify cache invalidation works correctly.

This script:
1. Creates a test user
2. Checks initial portfolio_version
3. Creates an asset (should bump version)
4. Verifies version was bumped
5. Updates the asset (should bump again)
6. Verifies version was bumped again
7. Deletes the asset (should bump again)
8. Verifies final version bump
"""

import sys
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to the path
sys.path.insert(0, '/Users/sergeibenkovitch/repos/financial-planner')

from fplan_v2.db.models import Base, User, Asset
from fplan_v2.db.repositories.asset_repository import AssetRepository

# Production models use Postgres JSONB columns; teach the SQLite compiler (used
# for this in-memory test) to render JSONB as JSON so create_all() succeeds.
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


# Create in-memory test database
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def test_cache_invalidation():
    """Test that cache invalidation works correctly."""
    session = Session()

    try:
        # Step 1: Create test user
        user = User(
            email="test@example.com",
            name="Test User",
            portfolio_version=1
        )
        session.add(user)
        session.flush()
        user_id = user.id
        initial_version = user.portfolio_version
        print(f"✓ Created user with portfolio_version={initial_version}")

        # Step 2: Create an asset
        repo = AssetRepository(session)
        asset = repo.create(
            user_id=user_id,
            external_id="test-asset-1",
            asset_type="stock",
            name="Test Stock",
            original_value=10000.0,
            start_date=date(2026, 1, 1)
        )
        session.refresh(user)
        version_after_create = user.portfolio_version
        print(f"✓ Created asset, portfolio_version={version_after_create}")
        assert version_after_create == initial_version + 1, \
            f"Expected version {initial_version + 1}, got {version_after_create}"

        # Step 3: Update the asset
        repo.update(asset.id, current_value=12000.0)
        session.refresh(user)
        version_after_update = user.portfolio_version
        print(f"✓ Updated asset, portfolio_version={version_after_update}")
        assert version_after_update == version_after_create + 1, \
            f"Expected version {version_after_create + 1}, got {version_after_update}"

        # Step 4: Delete the asset
        repo.delete(asset.id)
        session.refresh(user)
        version_after_delete = user.portfolio_version
        print(f"✓ Deleted asset, portfolio_version={version_after_delete}")
        assert version_after_delete == version_after_update + 1, \
            f"Expected version {version_after_update + 1}, got {version_after_delete}"

        print("\n✓ All cache invalidation tests passed!")
        print(f"  Initial version: {initial_version}")
        print(f"  Final version: {version_after_delete}")
        print(f"  Total bumps: {version_after_delete - initial_version}")

        session.commit()
        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        session.rollback()
        return False
    finally:
        session.close()

if __name__ == "__main__":
    success = test_cache_invalidation()
    sys.exit(0 if success else 1)
