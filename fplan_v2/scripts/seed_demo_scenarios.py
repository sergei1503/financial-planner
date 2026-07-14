"""
Seed demo scenarios for the demo user.
Creates compelling "what-if" scenarios to showcase in the guide video.
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fplan_v2.db.models import User, Scenario, RevenueStream

load_dotenv()

DEMO_CLERK_ID = "demo"


def seed_demo_scenarios():
    """Seed demo scenarios for the demo user."""
    db_url = os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("Database URL not configured")

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Find demo user
        demo_user = session.query(User).filter_by(clerk_id=DEMO_CLERK_ID).first()
        if not demo_user:
            print(f"❌ Demo user not found (clerk_id='{DEMO_CLERK_ID}')")
            print("   Run: python -m fplan_v2.scripts.seed_demo_data first")
            return

        print(f"✓ Found demo user (ID: {demo_user.id})")

        # Delete existing demo scenarios
        deleted = session.query(Scenario).filter_by(user_id=demo_user.id).delete()
        if deleted:
            print(f"  Deleted {deleted} existing scenario(s)")

        # Get the salary revenue stream ID
        salary_stream = session.query(RevenueStream).filter_by(
            user_id=demo_user.id,
            stream_type="salary"
        ).first()

        if not salary_stream:
            print("❌ No salary revenue stream found for demo user")
            return

        print(f"  Found salary stream (ID: {salary_stream.id})")

        # Calculate future dates relative to today
        today = date.today()
        car_purchase_date = today + timedelta(days=90)  # ~3 months out
        salary_increase_date = today + timedelta(days=180)  # ~6 months out

        # Calculate 15% raise from PROJECTED salary at action_date (not base amount)
        # Need to account for growth from start_date to action_date
        base_salary = float(salary_stream.amount)
        growth_rate = float(salary_stream.growth_rate or 0) / 100.0
        salary_start_date = salary_stream.start_date

        # Calculate years from salary start to action date
        years_to_action = (
            (salary_increase_date.year - salary_start_date.year) +
            (salary_increase_date.month - salary_start_date.month) / 12.0
        )

        # Project salary to action date with growth
        projected_salary = base_salary * ((1 + growth_rate) ** years_to_action)

        # Apply 15% raise to the projected salary
        new_salary = projected_salary * 1.15

        print(f"  Salary calculation:")
        print(f"    Base (2020): ₪{base_salary:,.0f}/month")
        print(f"    Growth rate: {growth_rate*100}%/year")
        print(f"    Years to action: {years_to_action:.2f}")
        print(f"    Projected at action date: ₪{projected_salary:,.0f}/month")
        print(f"    With 15% raise: ₪{new_salary:,.0f}/month")

        # Create scenarios
        scenarios = [
            {
                "name": "Car Purchase",
                "description": "What if I buy a new car with a 5-year loan?",
                "actions_json": [
                    {
                        "type": "new_loan",
                        "action_date": car_purchase_date.isoformat(),
                        "params": {
                            "external_id": "car-loan-demo",
                            "loan_type": "fixed",
                            "name": "Car Loan",
                            "start_date": car_purchase_date.isoformat(),
                            "original_value": 120000,
                            "interest_rate_annual_pct": 5.0,
                            "duration_months": 60,
                        },
                    }
                ],
            },
            {
                "name": "Salary Increase",
                "description": "What if I get a 15% raise in June?",
                "actions_json": [
                    {
                        "type": "param_change",
                        "action_date": salary_increase_date.isoformat(),
                        "target_type": "revenue_stream",
                        "target_id": salary_stream.id,
                        "field": "amount",
                        "value": new_salary,
                    }
                ],
            },
        ]

        for scenario_data in scenarios:
            scenario = Scenario(
                user_id=demo_user.id,
                name=scenario_data["name"],
                description=scenario_data["description"],
                actions_json=scenario_data["actions_json"],
                is_active=True,
            )
            session.add(scenario)
            print(f"  Created: {scenario_data['name']}")

        session.commit()
        print("\n✓ Demo scenarios seeded successfully!\n")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Error: {e}\n")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_demo_scenarios()
