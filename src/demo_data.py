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

def generate_demo_data(sim, user_id, account_ids):
    """
    Generate realistic demo data for a user.

    Creates:
    - 3-6 months of income (bi-weekly paychecks)
    - Recurring expenses (rent, utilities, subscriptions)
    - Random expenses (groceries, dining, entertainment, etc.)
    - Some transfers between accounts

    Args:
        sim: BusinessSimulator instance
        user_id: User ID to generate data for
        account_ids: Dict with 'checking', 'savings', 'credit_card' account IDs
    """

    # Get current simulation date
    status = sim.get_status_summary(user_id)
    current_date = datetime.strptime(status['date'], '%Y-%m-%d').date()

    # Generate data starting 4 months ago
    start_date = current_date - timedelta(days=120)

    print(f"[DEMO] Generating demo data from {start_date} to {current_date}")
    print(f"[DEMO] User ID: {user_id}")
    print(f"[DEMO] Using account IDs: {account_ids}")

    # ===== GET CATEGORIES =====

    categories = sim.get_expense_categories(user_id)
    print(f"[DEMO] Found {len(categories)} expense categories")

    # Create category lookup by name
    category_map = {}
    for cat in categories:
        category_map[cat['name']] = cat['category_id']

    print(f"[DEMO] Category map: {category_map}")

    # Extract account IDs
    checking_account_id = account_ids.get('checking')
    savings_account_id = account_ids.get('savings')
    credit_card_id = account_ids.get('credit_card')

    print(f"[DEMO] Checking: {checking_account_id}, Savings: {savings_account_id}, CC: {credit_card_id}")

    # ===== CREATE RECURRING EXPENSES =====

    recurring_expenses = [
        {"description": "Rent", "amount": 1450, "day": 1, "category": "Housing"},
        {"description": "Electric Bill", "amount": 85, "day": 15, "category": "Utilities"},
        {"description": "Internet", "amount": 60, "day": 10, "category": "Utilities"},
        {"description": "Netflix", "amount": 15.99, "day": 5, "category": "Entertainment"},
        {"description": "Spotify", "amount": 10.99, "day": 8, "category": "Entertainment"},
        {"description": "Gym Membership", "amount": 45, "day": 1, "category": "Healthcare"},
    ]

    print(f"[DEMO] Adding {len(recurring_expenses)} recurring expenses")
    for rec in recurring_expenses:
        category_id = category_map.get(rec['category'])
        if category_id is None:
            print(f"[DEMO] WARNING: Category '{rec['category']}' not found, will be uncategorized")

        success, message = sim.add_recurring_expense(
            user_id=user_id,
            description=rec['description'],
            amount=rec['amount'],
            payment_account_id=checking_account_id,
            due_day_of_month=rec['day'],
            category_id=category_id
        )
        if not success:
            print(f"[DEMO] ERROR adding recurring expense '{rec['description']}': {message}")
        else:
            print(f"[DEMO] Added recurring expense: {rec['description']}")

    print(f"[DEMO] Recurring expenses added")

    # ===== CREATE RECURRING INCOME =====

    # Note: SQLite doesn't have a built-in way to handle bi-weekly recurring
    # so we'll add two paycheck entries (on 1st and 15th of each month)
    recurring_income = [
        {"name": "Paycheck - 1st", "description": "Bi-weekly paycheck from Acme Corp", "amount": 2100.00, "day": 1},
        {"name": "Paycheck - 15th", "description": "Bi-weekly paycheck from Acme Corp", "amount": 2100.00, "day": 15},
    ]

    print(f"[DEMO] Adding {len(recurring_income)} recurring income entries")
    for rec in recurring_income:
        success, message = sim.add_recurring_income(
            user_id=user_id,
            name=rec['name'],
            description=rec['description'],
            amount=rec['amount'],
            destination_account_id=checking_account_id,
            frequency='MONTHLY',
            due_day_of_month=rec['day']
        )
        if not success:
            print(f"[DEMO] ERROR adding recurring income '{rec['name']}': {message}")
        else:
            print(f"[DEMO] Added recurring income: {rec['name']}")

    print(f"[DEMO] Recurring income added")

    # ===== GENERATE HISTORICAL TRANSACTIONS =====

    # Get W2 Job Income category for paychecks
    w2_category_id = category_map.get('W2 Job Income')
    if not w2_category_id:
        print(f"[DEMO] WARNING: W2 Job Income category not found")

    # Generate bi-weekly paychecks (every 14 days)
    paycheck_amount = 2100.00  # ~$54,600/year after taxes
    paycheck_date = start_date
    paycheck_count = 0

    while paycheck_date <= current_date:
        sim.log_income(
            user_id=user_id,
            account_id=checking_account_id,
            description="Paycheck - Acme Corp",
            amount=paycheck_amount,
            transaction_date=paycheck_date.strftime('%Y-%m-%d'),
            category_id=w2_category_id
        )
        paycheck_date += timedelta(days=14)
        paycheck_count += 1

    print(f"[DEMO] Generated {paycheck_count} paychecks")

    # Generate random expenses over the time period
    # Use actual category names that exist in the database
    expense_templates = [
        # Groceries (weekly-ish) - maps to "Food & Dining"
        {"category": "Food & Dining", "descriptions": ["Whole Foods", "Trader Joe's", "Safeway", "Farmers Market"], "min": 40, "max": 120, "frequency": 7},

        # Dining (2-3x per week) - maps to "Food & Dining"
        {"category": "Food & Dining", "descriptions": ["Chipotle", "Local Bistro", "Pizza Place", "Thai Restaurant", "Coffee Shop"], "min": 12, "max": 65, "frequency": 3},

        # Gas (weekly)
        {"category": "Transportation", "descriptions": ["Shell Gas Station", "Chevron", "76 Gas"], "min": 35, "max": 55, "frequency": 7},

        # Shopping (occasional)
        {"category": "Shopping", "descriptions": ["Amazon", "Target", "Macy's", "Best Buy"], "min": 25, "max": 200, "frequency": 10},

        # Entertainment (occasional)
        {"category": "Entertainment", "descriptions": ["Movie Theater", "Concert Tickets", "Bowling", "Mini Golf"], "min": 20, "max": 80, "frequency": 14},

        # Health (occasional) - maps to "Healthcare"
        {"category": "Healthcare", "descriptions": ["Pharmacy", "Doctor Copay", "Dentist"], "min": 15, "max": 150, "frequency": 30},
    ]

    # Generate expenses
    expense_date = start_date
    expense_count = 0
    uncategorized_count = 0
    while expense_date <= current_date:
        for template in expense_templates:
            # Random chance based on frequency
            if random.random() < (1.0 / template['frequency']):
                category_id = category_map.get(template['category'])
                if category_id is None:
                    uncategorized_count += 1
                description = random.choice(template['descriptions'])
                amount = round(random.uniform(template['min'], template['max']), 2)

                # 80% checking, 20% credit card
                account_id = checking_account_id if random.random() < 0.8 else credit_card_id

                sim.log_expense(
                    user_id=user_id,
                    account_id=account_id,
                    description=description,
                    amount=amount,
                    category_id=category_id,
                    transaction_date=expense_date.strftime('%Y-%m-%d')
                )
                expense_count += 1

        expense_date += timedelta(days=1)

    print(f"[DEMO] Generated {expense_count} expenses ({uncategorized_count} uncategorized)")

    # ===== GENERATE SOME TRANSFERS =====

    # Transfer to savings monthly
    transfer_date = start_date + timedelta(days=15)
    while transfer_date <= current_date:
        sim.transfer_between_accounts(
            user_id=user_id,
            from_account_id=checking_account_id,
            to_account_id=savings_account_id,
            amount=random.randint(200, 500),
            description="Monthly Savings",
            transaction_date=transfer_date.strftime('%Y-%m-%d')
        )
        transfer_date += timedelta(days=30)

    # Pay off credit card a few times
    if random.random() < 0.7:
        payment_date = start_date + timedelta(days=45)
        payment_count = 0
        while payment_date <= current_date and payment_count < 3:
            # Get current credit card balance
            accounts = sim.get_accounts_list(user_id)
            cc_balance = 0
            for acc in accounts:
                if acc['name'] == "Visa Credit Card":
                    cc_balance = abs(float(acc['balance']))
                    break

            if cc_balance > 50:
                # Pay off 50-100% of balance
                payment_amount = round(cc_balance * random.uniform(0.5, 1.0), 2)
                sim.transfer_between_accounts(
                    user_id=user_id,
                    from_account_id=checking_account_id,
                    to_account_id=credit_card_id,
                    amount=payment_amount,
                    description="Credit Card Payment",
                    transaction_date=payment_date.strftime('%Y-%m-%d')
                )

            payment_date += timedelta(days=30)
            payment_count += 1

    return {
        "accounts_created": 3,
        "transactions_generated": "100+",
        "date_range": f"{start_date} to {current_date}",
        "persona": "Young Professional (~$54k/year)"
    }
