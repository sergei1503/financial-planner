"""
Infrastructure tests for database layer.

Tests database connection, schema creation, and CRUD operations
WITHOUT requiring v2 business logic models to be ported.

Run these tests to verify Neon connection and schema are working
before full migration.

Usage:
    pytest fplan_v2/tests/test_db_infrastructure.py -v

Or without pytest:
    python fplan_v2/tests/test_db_infrastructure.py
"""

import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_environment_variables():
    """Test that required environment variables are set."""
    print("\n1. Testing environment variables...")

    db_url = os.getenv("NEON_DATABASE_URL")
    if not db_url:
        print("  ❌ NEON_DATABASE_URL not set")
        print("     Set it with: export NEON_DATABASE_URL='postgresql://...'")
        return False

    print(f"  ✓ NEON_DATABASE_URL is set")

    # Check if using pooler endpoint
    if "-pooler" in db_url:
        print("  ✓ Using Neon pooler endpoint (recommended)")
    else:
        print("  ⚠️  Not using pooler endpoint - consider using -pooler.neon.tech for serverless")

    return True


def test_database_connection():
    """Test basic database connectivity."""
    print("\n2. Testing database connection...")

    try:
        from fplan_v2.db.connection import check_connection

        if check_connection():
            print("  ✓ Database connection successful")
            return True
        else:
            print("  ❌ Database connection failed")
            return False
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        return False


def test_schema_creation():
    """Test that all tables can be created."""
    print("\n3. Testing schema creation...")

    try:
        from fplan_v2.db.connection import get_db_manager

        db_manager = get_db_manager()

        # Create all tables
        db_manager.create_all()
        print("  ✓ All tables created successfully")

        return True
    except Exception as e:
        print(f"  ❌ Schema creation error: {e}")
        return False


def test_table_existence():
    """Verify all expected tables exist."""
    print("\n4. Verifying table existence...")

    try:
        from fplan_v2.db.connection import db_session

        expected_tables = [
            'users', 'assets', 'loans', 'revenue_streams', 'cash_flows',
            'historical_measurements', 'operations_log', 'index_data',
            'index_notifications', 'scenarios', 'scenario_results'
        ]

        with db_session() as session:
            # Query pg_tables to check table existence
            result = session.execute("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
            """)
            existing_tables = [row[0] for row in result]

        missing_tables = set(expected_tables) - set(existing_tables)

        if missing_tables:
            print(f"  ❌ Missing tables: {missing_tables}")
            return False

        print(f"  ✓ All {len(expected_tables)} tables exist")
        return True

    except Exception as e:
        print(f"  ❌ Table verification error: {e}")
        return False


def test_default_user_exists():
    """Test that default user (id=1) exists."""
    print("\n5. Testing default user...")

    try:
        from fplan_v2.db.connection import db_session
        from fplan_v2.db.models import User

        with db_session() as session:
            user = session.query(User).filter_by(id=1).first()

            if not user:
                print("  ❌ Default user (id=1) not found")
                print("     Run schema.sql or init_database() first")
                return False

            print(f"  ✓ Default user exists: {user.name}")
            print(f"    Settings: {user.settings}")
            return True

    except Exception as e:
        print(f"  ❌ User query error: {e}")
        return False


def test_asset_crud():
    """Test Create, Read, Update, Delete operations on assets."""
    print("\n6. Testing Asset CRUD operations...")

    try:
        from fplan_v2.db.connection import db_session
        from fplan_v2.db.models import Asset

        test_asset_id = "test_infrastructure_asset"

        # CREATE
        with db_session() as session:
            asset = Asset(
                user_id=1,
                external_id=test_asset_id,
                asset_type="stock",
                name="Test Stock",
                start_date=date(2025, 1, 1),
                original_value=Decimal("100000.00"),
                appreciation_rate_annual_pct=Decimal("8.0"),
                yearly_fee_pct=Decimal("0.5"),
                config_json={"test": True, "purpose": "infrastructure_test"}
            )
            session.add(asset)
        print("  ✓ CREATE: Asset created")

        # READ
        with db_session() as session:
            asset = session.query(Asset).filter_by(
                user_id=1,
                external_id=test_asset_id
            ).first()

            if not asset:
                print("  ❌ READ: Asset not found")
                return False

            # Verify JSONB storage
            if asset.config_json.get("test") != True:
                print("  ❌ READ: JSONB data corrupted")
                return False

        print("  ✓ READ: Asset retrieved with JSONB intact")

        # UPDATE
        with db_session() as session:
            asset = session.query(Asset).filter_by(
                user_id=1,
                external_id=test_asset_id
            ).first()

            old_updated_at = asset.updated_at
            asset.current_value = Decimal("110000.00")
            # Commit happens automatically on context exit

        # Verify update
        with db_session() as session:
            asset = session.query(Asset).filter_by(
                user_id=1,
                external_id=test_asset_id
            ).first()

            if asset.current_value != Decimal("110000.00"):
                print("  ❌ UPDATE: Value not updated")
                return False

            # Note: updated_at trigger may not fire in same transaction
            # This is expected behavior

        print("  ✓ UPDATE: Asset updated")

        # DELETE
        with db_session() as session:
            session.query(Asset).filter_by(
                user_id=1,
                external_id=test_asset_id
            ).delete()

        # Verify deletion
        with db_session() as session:
            asset = session.query(Asset).filter_by(
                user_id=1,
                external_id=test_asset_id
            ).first()

            if asset:
                print("  ❌ DELETE: Asset still exists")
                return False

        print("  ✓ DELETE: Asset deleted")

        return True

    except Exception as e:
        print(f"  ❌ Asset CRUD error: {e}")
        # Cleanup
        try:
            with db_session() as session:
                session.query(Asset).filter_by(
                    user_id=1,
                    external_id=test_asset_id
                ).delete()
        except:
            pass
        return False


def test_foreign_key_constraints():
    """Test that foreign key constraints work correctly."""
    print("\n7. Testing foreign key constraints...")

    try:
        from fplan_v2.db.connection import db_session
        from fplan_v2.db.models import Asset, Loan

        # Create test asset
        with db_session() as session:
            asset = Asset(
                user_id=1,
                external_id="test_fk_asset",
                asset_type="real_estate",
                name="Test House",
                start_date=date(2025, 1, 1),
                original_value=Decimal("500000.00"),
            )
            session.add(asset)
            session.flush()
            asset_id = asset.id

        print("  ✓ Created test asset")

        # Create loan with valid collateral
        with db_session() as session:
            loan = Loan(
                user_id=1,
                external_id="test_fk_loan",
                loan_type="fixed",
                name="Test Mortgage",
                start_date=date(2025, 1, 1),
                original_value=Decimal("400000.00"),
                interest_rate_annual_pct=Decimal("3.5"),
                duration_months=360,
                collateral_asset_id=asset_id  # Valid FK
            )
            session.add(loan)

        print("  ✓ Loan created with valid collateral FK")

        # Test CASCADE delete
        with db_session() as session:
            session.query(Asset).filter_by(external_id="test_fk_asset").delete()

        # Verify loan's collateral_asset_id was set to NULL (ON DELETE SET NULL)
        with db_session() as session:
            loan = session.query(Loan).filter_by(external_id="test_fk_loan").first()
            if loan and loan.collateral_asset_id is not None:
                print("  ❌ CASCADE: Collateral FK not nullified")
                return False

        print("  ✓ CASCADE: ON DELETE SET NULL working")

        # Cleanup
        with db_session() as session:
            session.query(Loan).filter_by(external_id="test_fk_loan").delete()

        return True

    except Exception as e:
        print(f"  ❌ Foreign key test error: {e}")
        # Cleanup
        try:
            with db_session() as session:
                session.query(Loan).filter_by(external_id="test_fk_loan").delete()
                session.query(Asset).filter_by(external_id="test_fk_asset").delete()
        except:
            pass
        return False


def test_jsonb_queries():
    """Test JSONB query capabilities."""
    print("\n8. Testing JSONB queries...")

    try:
        from fplan_v2.db.connection import db_session
        from fplan_v2.db.models import Asset
        from sqlalchemy import cast, Float

        # Create assets with different JSONB configs
        with db_session() as session:
            asset1 = Asset(
                user_id=1,
                external_id="test_jsonb_1",
                asset_type="stock",
                name="High Fee Asset",
                start_date=date(2025, 1, 1),
                original_value=Decimal("100000.00"),
                config_json={"management_fee": 1.5, "category": "active"}
            )
            asset2 = Asset(
                user_id=1,
                external_id="test_jsonb_2",
                asset_type="stock",
                name="Low Fee Asset",
                start_date=date(2025, 1, 1),
                original_value=Decimal("100000.00"),
                config_json={"management_fee": 0.2, "category": "passive"}
            )
            session.add(asset1)
            session.add(asset2)

        print("  ✓ Created assets with JSONB config")

        # Query by JSONB field
        with db_session() as session:
            # Find assets with category = "active"
            results = session.query(Asset).filter(
                Asset.config_json['category'].astext == 'active'
            ).filter(
                Asset.external_id.like('test_jsonb_%')
            ).all()

            if len(results) != 1:
                print(f"  ❌ JSONB query returned {len(results)} results, expected 1")
                return False

        print("  ✓ JSONB text queries working")

        # Query by JSONB numeric field
        with db_session() as session:
            # Find assets with management_fee > 1.0
            results = session.query(Asset).filter(
                cast(Asset.config_json['management_fee'].astext, Float) > 1.0
            ).filter(
                Asset.external_id.like('test_jsonb_%')
            ).all()

            if len(results) != 1:
                print(f"  ❌ JSONB numeric query returned {len(results)} results, expected 1")
                return False

        print("  ✓ JSONB numeric queries working")

        # Cleanup
        with db_session() as session:
            session.query(Asset).filter(
                Asset.external_id.like('test_jsonb_%')
            ).delete(synchronize_session=False)

        return True

    except Exception as e:
        print(f"  ❌ JSONB query error: {e}")
        # Cleanup
        try:
            with db_session() as session:
                session.query(Asset).filter(
                    Asset.external_id.like('test_jsonb_%')
                ).delete(synchronize_session=False)
        except:
            pass
        return False


def test_connection_pooling():
    """Test connection pooling behavior."""
    print("\n9. Testing connection pooling...")

    try:
        from fplan_v2.db.connection import get_db_manager

        db_manager = get_db_manager()

        # Check pooling mode
        is_serverless = os.getenv("VERCEL", "false").lower() == "true"

        if is_serverless:
            print("  ✓ Serverless mode detected (NullPool)")
        else:
            print("  ✓ Traditional mode detected (QueuePool)")

        # Test multiple concurrent sessions
        sessions = []
        for i in range(3):
            session = db_manager.get_session()
            session.execute("SELECT 1")
            sessions.append(session)

        print(f"  ✓ Created {len(sessions)} concurrent sessions")

        # Cleanup
        for session in sessions:
            session.close()

        return True

    except Exception as e:
        print(f"  ❌ Connection pooling error: {e}")
        return False


def run_all_tests():
    """Run all infrastructure tests."""
    print("=" * 60)
    print("DATABASE INFRASTRUCTURE TEST SUITE")
    print("=" * 60)

    tests = [
        test_environment_variables,
        test_database_connection,
        test_schema_creation,
        test_table_existence,
        test_default_user_exists,
        test_asset_crud,
        test_foreign_key_constraints,
        test_jsonb_queries,
        test_connection_pooling,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n  ❌ Unexpected error in {test.__name__}: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✅ All infrastructure tests passed!")
        print("\nDatabase layer is ready for migration.")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        print("\nFix issues before running full migration.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
