"""
Perfect Books - Demo Data Generator

Generates realistic fake financial data for demo mode.
Creates a persona with 3-6 months of transaction history.
"""

from faker import Faker
import random
from datetime import datetime, timedelta
from decimal import Decimal

fake = Faker()

def generate_demo_data(sim, user_id):
    """
    Generate realistic demo data for a user.

    Creates:
    - Checking, Savings, Credit Card accounts
    - 3-6 months of income (bi-weekly paychecks)
    - Recurring expenses (rent, utilities, subscriptions)
    - Random expenses (groceries, dining, entertainment, etc.)
    - Some transfers between accounts

    Args:
        sim: BusinessSimulator instance
        user_id: User ID to generate data for
    """

    # Get current simulation date
    status = sim.get_status(user_id)
    current_date = datetime.strptime(status['date'], '%Y-%m-%d').date()

    # Generate data starting 4 months ago
    start_date = current_date - timedelta(days=120)

    # ===== CREATE ACCOUNTS =====

    # Checking Account (primary account)
    checking_id = sim.create_account(user_id, "Checking Account", "CHECKING", 3500.00)

    # Savings Account
    savings_id = sim.create_account(user_id, "Savings Account", "SAVINGS", 12000.00)

    # Credit Card
    credit_card_id = sim.create_account(user_id, "Visa Credit Card", "CREDIT_CARD", 0.00, credit_limit=5000.00)

    # ===== GET CATEGORIES =====

    categories = sim.get_expense_categories(user_id)

    # Create category lookup by name
    category_map = {}
    for cat in categories:
        category_map[cat['name']] = cat['id']

    # ===== CREATE RECURRING EXPENSES =====

    recurring_expenses = [
        {"description": "Rent", "amount": 1450, "day": 1, "category": "Housing"},
        {"description": "Electric Bill", "amount": 85, "day": 15, "category": "Utilities"},
        {"description": "Internet", "amount": 60, "day": 10, "category": "Utilities"},
        {"description": "Netflix", "amount": 15.99, "day": 5, "category": "Entertainment"},
        {"description": "Spotify", "amount": 10.99, "day": 8, "category": "Entertainment"},
        {"description": "Gym Membership", "amount": 45, "day": 1, "category": "Health"},
    ]

    for rec in recurring_expenses:
        category_id = category_map.get(rec['category'])
        sim.add_recurring_expense(
            user_id=user_id,
            description=rec['description'],
            amount=rec['amount'],
            account_name="Checking Account",
            day_of_month=rec['day'],
            category_id=category_id
        )

    # ===== GENERATE HISTORICAL TRANSACTIONS =====

    # Generate bi-weekly paychecks (every 14 days)
    paycheck_amount = 2100.00  # ~$54,600/year after taxes
    paycheck_date = start_date

    while paycheck_date <= current_date:
        sim.add_income(
            user_id=user_id,
            description="Paycheck - Acme Corp",
            amount=paycheck_amount,
            account_name="Checking Account",
            date=paycheck_date.strftime('%Y-%m-%d')
        )
        paycheck_date += timedelta(days=14)

    # Generate random expenses over the time period
    expense_templates = [
        # Groceries (weekly-ish)
        {"category": "Groceries", "descriptions": ["Whole Foods", "Trader Joe's", "Safeway", "Farmers Market"], "min": 40, "max": 120, "frequency": 7},

        # Dining (2-3x per week)
        {"category": "Dining", "descriptions": ["Chipotle", "Local Bistro", "Pizza Place", "Thai Restaurant", "Coffee Shop"], "min": 12, "max": 65, "frequency": 3},

        # Gas (weekly)
        {"category": "Transportation", "descriptions": ["Shell Gas Station", "Chevron", "76 Gas"], "min": 35, "max": 55, "frequency": 7},

        # Shopping (occasional)
        {"category": "Shopping", "descriptions": ["Amazon", "Target", "Macy's", "Best Buy"], "min": 25, "max": 200, "frequency": 10},

        # Entertainment (occasional)
        {"category": "Entertainment", "descriptions": ["Movie Theater", "Concert Tickets", "Bowling", "Mini Golf"], "min": 20, "max": 80, "frequency": 14},

        # Health (occasional)
        {"category": "Health", "descriptions": ["Pharmacy", "Doctor Copay", "Dentist"], "min": 15, "max": 150, "frequency": 30},
    ]

    # Generate expenses
    expense_date = start_date
    while expense_date <= current_date:
        for template in expense_templates:
            # Random chance based on frequency
            if random.random() < (1.0 / template['frequency']):
                category_id = category_map.get(template['category'])
                description = random.choice(template['descriptions'])
                amount = round(random.uniform(template['min'], template['max']), 2)

                # 80% checking, 20% credit card
                account = "Checking Account" if random.random() < 0.8 else "Visa Credit Card"

                sim.add_expense(
                    user_id=user_id,
                    description=description,
                    amount=amount,
                    account_name=account,
                    category_id=category_id,
                    date=expense_date.strftime('%Y-%m-%d')
                )

        expense_date += timedelta(days=1)

    # ===== GENERATE SOME TRANSFERS =====

    # Transfer to savings monthly
    transfer_date = start_date + timedelta(days=15)
    while transfer_date <= current_date:
        sim.add_transfer(
            user_id=user_id,
            from_account="Checking Account",
            to_account="Savings Account",
            amount=random.randint(200, 500),
            description="Monthly Savings",
            date=transfer_date.strftime('%Y-%m-%d')
        )
        transfer_date += timedelta(days=30)

    # Pay off credit card a few times
    if random.random() < 0.7:
        payment_date = start_date + timedelta(days=45)
        payment_count = 0
        while payment_date <= current_date and payment_count < 3:
            # Get current credit card balance
            accounts = sim.get_accounts(user_id)
            cc_balance = 0
            for acc in accounts:
                if acc['name'] == "Visa Credit Card":
                    cc_balance = abs(float(acc['balance']))
                    break

            if cc_balance > 50:
                # Pay off 50-100% of balance
                payment_amount = round(cc_balance * random.uniform(0.5, 1.0), 2)
                sim.add_transfer(
                    user_id=user_id,
                    from_account="Checking Account",
                    to_account="Visa Credit Card",
                    amount=payment_amount,
                    description="Credit Card Payment",
                    date=payment_date.strftime('%Y-%m-%d')
                )

            payment_date += timedelta(days=30)
            payment_count += 1

    return {
        "accounts_created": 3,
        "transactions_generated": "100+",
        "date_range": f"{start_date} to {current_date}",
        "persona": "Young Professional (~$54k/year)"
    }
