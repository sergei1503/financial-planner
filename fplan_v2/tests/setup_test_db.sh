#!/bin/bash
# Setup script for testing database infrastructure
#
# Usage:
#   ./fplan_v2/tests/setup_test_db.sh
#
# This script will:
# 1. Check environment variables
# 2. Initialize database schema
# 3. Run infrastructure tests
# 4. Report results

set -e  # Exit on first error

echo "=========================================="
echo "FPlan v2 Database Setup & Testing"
echo "=========================================="
echo ""

# Check if NEON_DATABASE_URL is set
if [ -z "$NEON_DATABASE_URL" ]; then
    echo "❌ Error: NEON_DATABASE_URL environment variable not set"
    echo ""
    echo "Please set it with:"
    echo "  export NEON_DATABASE_URL='postgresql://user:pass@host/db?sslmode=require'"
    echo ""
    echo "Get your connection string from:"
    echo "  https://console.neon.tech"
    echo ""
    echo "Make sure to use the pooler endpoint (-pooler.neon.tech)!"
    exit 1
fi

echo "✓ NEON_DATABASE_URL is set"
echo ""

# Check if connection string uses pooler
if [[ "$NEON_DATABASE_URL" == *"-pooler"* ]]; then
    echo "✓ Using Neon pooler endpoint (recommended)"
else
    echo "⚠️  Warning: Not using pooler endpoint"
    echo "   Consider using -pooler.neon.tech for better serverless performance"
fi
echo ""

# Check Python dependencies
echo "Checking Python dependencies..."
python3 -c "import sqlalchemy; import psycopg2; import pandas" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Python dependencies installed"
else
    echo "❌ Missing Python dependencies"
    echo ""
    echo "Install with:"
    echo "  pip install -r fplan_v2/requirements.txt"
    exit 1
fi
echo ""

# Test database connection
echo "Testing database connection..."
python3 -c "from fplan_v2.db.connection import check_connection; exit(0 if check_connection() else 1)"
if [ $? -eq 0 ]; then
    echo "✓ Database connection successful"
else
    echo "❌ Database connection failed"
    echo ""
    echo "Possible issues:"
    echo "  - Database suspended (check Neon console)"
    echo "  - Wrong connection string"
    echo "  - Missing ?sslmode=require"
    exit 1
fi
echo ""

# Initialize database schema
echo "Initializing database schema..."
python3 -c "from fplan_v2.db.connection import init_database; init_database()"
if [ $? -eq 0 ]; then
    echo "✓ Database schema initialized"
else
    echo "❌ Schema initialization failed"
    exit 1
fi
echo ""

# Run infrastructure tests
echo "Running infrastructure tests..."
echo "=========================================="
python3 fplan_v2/tests/test_db_infrastructure.py
TEST_EXIT_CODE=$?

echo ""
echo "=========================================="

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ SUCCESS: All tests passed!"
    echo ""
    echo "Database infrastructure is ready for migration."
    echo ""
    echo "Next steps:"
    echo "  1. Wait for backend team to port Asset/Loan classes"
    echo "  2. Run migration: python fplan_v2/migrations/migrate_from_v1.py --config ..."
    echo "  3. Validate: python fplan_v2/migrations/validate_migration.py --baseline ..."
    echo ""
    exit 0
else
    echo ""
    echo "❌ FAILURE: Some tests failed"
    echo ""
    echo "Check the error messages above and fix issues before proceeding."
    echo ""
    echo "Common solutions:"
    echo "  - Reset database: python -c 'from fplan_v2.db.connection import get_db_manager; db=get_db_manager(); db.drop_all(); db.create_all()'"
    echo "  - Check Neon console for connection limits"
    echo "  - Verify connection string is correct"
    echo ""
    exit 1
fi
