"""
Perfect Books - Flask REST API

This module provides a RESTful API for the Perfect Books personal finance application.
It uses Flask with Flask-Login for session-based authentication and serves endpoints for:

Authentication:
- User registration and login
- Session management with cookies

Financial Operations:
- Account management (CRUD)
- Transaction logging (income, expenses, transfers)
- Recurring expense automation with category support
- Loan tracking and payments

Analytics:
- Financial summaries and net worth calculation
- Transaction history with filtering
- Category-based expense analysis

Security:
- Flask-Login for session management
- User data segregation (all endpoints validate user_id)
- CORS enabled for cross-origin requests (web interface)
- bcrypt password hashing (handled by engine)

Author: Matthew Jenkins
License: MIT
Related Project: Digital Harvest (Uses similar Flask API architecture)
"""

from flask import Flask, jsonify, request, send_from_directory, redirect, url_for, session
from flask_cors import CORS
import json
from decimal import Decimal
import datetime
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os

# Debug: Print environment variables BEFORE importing engine
print("=" * 60)
print("ENVIRONMENT VARIABLES IN API.PY:")
print(f"  DB_HOST: {os.getenv('DB_HOST')}")
print(f"  DB_PORT: {os.getenv('DB_PORT')}")
print(f"  DB_USER: {os.getenv('DB_USER')}")
print(f"  DB_NAME: {os.getenv('DB_NAME')}")
print(f"  DB_PASSWORD: {'***' if os.getenv('DB_PASSWORD') else 'NOT SET'}")
print("=" * 60)

from src.engine import BusinessSimulator


class CustomEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for handling Decimal and datetime objects.

    Converts:
    - Decimal to float for JSON serialization
    - datetime/date to ISO 8601 format strings
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)


# =============================================================================
# FLASK APPLICATION SETUP
# =============================================================================

app = Flask(__name__, static_url_path='', static_folder='../')
app.json_encoder = CustomEncoder

# Security configuration
app.config['SECRET_KEY'] = 'a_super_secret_key_you_should_change'  # TODO: Change in production
app.config['SESSION_COOKIE_SAMESITE'] = "None"
app.config['SESSION_COOKIE_SECURE'] = True

# Enable CORS for web interface (allows requests from different origins)
CORS(app, supports_credentials=True)

# Initialize the stateless business simulator
try:
    sim = BusinessSimulator()
except Exception as e:
    print(f"FATAL: Could not initialize simulator. Is the database running? Error: {e}")
    sim = None

# --- FLASK-LOGIN SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'serve_login_page'

@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/api/'):
        return jsonify(success=False, message="Authorization required. Please log in."), 401
    return redirect(url_for('serve_login_page'))

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    if not sim: return None
    conn, cursor = sim._get_db_connection()
    cursor.execute("SELECT user_id, username FROM users WHERE user_id = %s", (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()
    if user_data:
        return User(id=str(user_data['user_id']), username=user_data['username'])
    return None

def check_sim(func):
    def wrapper(*args, **kwargs):
        if not sim:
            return jsonify({"error": "Simulator not initialized. Check terminal for errors."}), 500
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# --- HTML SERVING ROUTES ---
@app.route('/')
@login_required
def serve_main_app():
    return send_from_directory('../', 'index.html')

@app.route('/login')
def serve_login_page():
    return send_from_directory('../', 'login.html')

@app.route('/register')
def serve_register_page():
    return send_from_directory('../', 'register.html')

@app.route('/setup')
@login_required
def serve_setup_page():
    return send_from_directory('../', 'setup.html')

# --- AUTHENTICATION API ROUTES ---

@app.route('/api/register', methods=['POST'])
@check_sim
def register_user_api():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not all([username, password]) or len(password) < 8:
        return jsonify({"success": False, "message": "Username and a password of at least 8 characters are required."}), 400
    
    success, message, new_user_id = sim.register_user(username, password)
    if success:
        user = User(id=str(new_user_id), username=username)
        login_user(user)
        # Since this is a new user, they will always need to go to setup.
        return jsonify({"success": True, "message": message, "setup_needed": True}), 200
    else:
        status_code = 409 if "exists" in message else 500
        return jsonify({"success": False, "message": message}), status_code

@app.route('/api/login', methods=['POST'])
@check_sim
def login_user_api():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not all([username, password]):
        return jsonify({"success": False, "message": "Username and password are required."}), 400

    user_data, message = sim.login_user(username, password)
    if user_data:
        user = User(id=str(user_data['user_id']), username=user_data['username'])
        login_user(user)
        has_accounts = sim.check_user_has_accounts(user.id)
        return jsonify({"success": True, "message": message, "setup_needed": not has_accounts})
    else:
        return jsonify({"success": False, "message": message}), 401

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({"success": True, "message": "You have been logged out."})

@app.route('/api/check_session', methods=['GET'])
@login_required
def check_session():
    return jsonify({"logged_in": True, "username": current_user.username})

# --- ACCOUNT MANAGEMENT API ROUTES ---

@app.route('/api/accounts', methods=['GET'])
@check_sim
@login_required
def get_accounts():
    accounts = sim.get_accounts_list(user_id=current_user.id)
    return jsonify(accounts)

@app.route('/api/accounts/setup', methods=['POST'])
@check_sim
@login_required
def setup_accounts_api():
    accounts_data = request.get_json()
    if not isinstance(accounts_data, list) or not accounts_data:
        return jsonify({"success": False, "message": "Invalid data format. Expected a list of accounts."}), 400
    success, message = sim.setup_initial_accounts(user_id=current_user.id, accounts=accounts_data)
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 500

@app.route('/api/accounts', methods=['POST'])
@check_sim
@login_required
def add_single_account_api():
    data = request.get_json()
    name = data.get('name')
    acc_type = data.get('type')
    balance = data.get('balance')
    credit_limit = data.get('credit_limit') 

    if not all([name, acc_type, balance is not None]):
         return jsonify({"success": False, "message": "Missing required fields: name, type, and balance."}), 400

    success, message = sim.add_single_account(
        user_id=current_user.id,
        name=name,
        acc_type=acc_type,
        balance=balance,
        credit_limit=credit_limit
    )
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 500


@app.route('/api/account/<int:account_id>', methods=['PUT', 'DELETE'])
@check_sim
@login_required
def manage_account_api(account_id):
    if request.method == 'PUT':
        data = request.get_json()
        new_name = data.get('name')
        if not new_name:
            return jsonify({"success": False, "message": "New name is required."}), 400

        success, message = sim.update_account_name(
            user_id=current_user.id,
            account_id=account_id,
            new_name=new_name
        )
        if success:
            return jsonify({"success": True, "message": message})
        else:
            status_code = 404 if "not found" in message else 500
            return jsonify({"success": False, "message": message}), status_code

    elif request.method == 'DELETE':
        success, message = sim.delete_account(
            user_id=current_user.id,
            account_id=account_id
        )
        if success:
            return jsonify({"success": True, "message": message})
        else:
            status_code = 404 if "not found" in message else 400
            return jsonify({"success": False, "message": message}), status_code

# --- RECURRING EXPENSES API ROUTES ---

@app.route('/api/recurring_expenses', methods=['GET'])
@check_sim
@login_required
def get_recurring_expenses_api():
    try:
        expenses = sim.get_recurring_expenses(user_id=current_user.id)
        print(f"DEBUG: Found {len(expenses)} recurring expenses for user {current_user.id}")
        return jsonify(expenses)
    except Exception as e:
        print(f"ERROR in get_recurring_expenses_api: {e}")
        import traceback
        traceback.print_exc()
        return jsonify([])

@app.route('/api/recurring_expenses', methods=['POST'])
@check_sim
@login_required
def add_recurring_expense_api():
    data = request.get_json()
    description = data.get('description')
    amount = data.get('amount')
    payment_account_id = data.get('payment_account_id')
    due_day_of_month = data.get('due_day_of_month')
    category_id = data.get('category_id')  # Optional category

    if not all([description, amount, payment_account_id, due_day_of_month]):
        return jsonify({"success": False, "message": "All fields are required."}), 400

    success, message = sim.add_recurring_expense(
        user_id=current_user.id,
        description=description,
        amount=amount,
        payment_account_id=payment_account_id,
        due_day_of_month=due_day_of_month,
        category_id=category_id
    )
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 500

@app.route('/api/recurring_expenses/<int:expense_id>', methods=['PUT', 'DELETE'])
@check_sim
@login_required
def manage_recurring_expense_api(expense_id):
    if request.method == 'PUT':
        data = request.get_json()
        description = data.get('description')
        amount = data.get('amount')
        due_day_of_month = data.get('due_day_of_month')
        category_id = data.get('category_id')  # Optional category
        is_variable = data.get('is_variable', False)
        estimated_amount = data.get('estimated_amount')

        if not all([description, due_day_of_month]):
            return jsonify({"success": False, "message": "Description and due day are required."}), 400

        success, message = sim.update_recurring_expense(
            user_id=current_user.id,
            expense_id=expense_id,
            description=description,
            amount=amount,
            due_day_of_month=due_day_of_month,
            category_id=category_id,
            is_variable=is_variable,
            estimated_amount=estimated_amount
        )
        if success:
            return jsonify({"success": True, "message": message})
        else:
            status_code = 404 if "not found" in message else 500
            return jsonify({"success": False, "message": message}), status_code

    elif request.method == 'DELETE':
        success, message = sim.delete_recurring_expense(
            user_id=current_user.id,
            expense_id=expense_id
        )
        if success:
            return jsonify({"success": True, "message": message})
        else:
            status_code = 404 if "not found" in message else 500
            return jsonify({"success": False, "message": message}), status_code

# --- RECURRING INCOME API ROUTES ---

@app.route('/api/recurring_income', methods=['GET'])
@check_sim
@login_required
def get_recurring_income_api():
    try:
        income = sim.get_recurring_income(user_id=current_user.id)
        return jsonify(income)
    except Exception as e:
        return jsonify([])

@app.route('/api/recurring_income', methods=['POST'])
@check_sim
@login_required
def add_recurring_income_api():
    data = request.get_json()
    description = data.get('description')
    amount = data.get('amount')
    deposit_account_id = data.get('deposit_account_id')
    deposit_day_of_month = data.get('deposit_day_of_month')
    is_variable = data.get('is_variable', False)
    estimated_amount = data.get('estimated_amount')

    if not all([description, deposit_account_id, deposit_day_of_month]):
        return jsonify({"success": False, "message": "Description, account, and deposit day are required."}), 400

    success, message = sim.add_recurring_income(
        user_id=current_user.id,
        description=description,
        amount=amount,
        deposit_account_id=deposit_account_id,
        deposit_day_of_month=deposit_day_of_month,
        is_variable=is_variable,
        estimated_amount=estimated_amount
    )

    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 400

@app.route('/api/recurring_income/<int:income_id>', methods=['PUT', 'DELETE'])
@check_sim
@login_required
def manage_recurring_income_api(income_id):
    if request.method == 'PUT':
        data = request.get_json()
        print(f"PUT /api/recurring_income/{income_id} received data:", data)
        description = data.get('description')
        amount = data.get('amount')
        deposit_day_of_month = data.get('deposit_day_of_month')
        is_variable = data.get('is_variable', False)
        estimated_amount = data.get('estimated_amount')

        if not all([description, deposit_day_of_month]):
            return jsonify({"success": False, "message": "Description and deposit day are required."}), 400

        success, message = sim.update_recurring_income(
            user_id=current_user.id,
            income_id=income_id,
            description=description,
            amount=amount,
            deposit_day_of_month=deposit_day_of_month,
            is_variable=is_variable,
            estimated_amount=estimated_amount
        )
        print(f"update_recurring_income returned: success={success}, message={message}")
        if success:
            return jsonify({"success": True, "message": message})
        else:
            status_code = 404 if "not found" in message else 500
            return jsonify({"success": False, "message": message}), status_code

    elif request.method == 'DELETE':
        success, message = sim.delete_recurring_income(
            user_id=current_user.id,
            income_id=income_id
        )
        if success:
            return jsonify({"success": True, "message": message})
        else:
            status_code = 404 if "not found" in message else 500
            return jsonify({"success": False, "message": message}), status_code

# --- OTHER DATA ROUTES ---

@app.route('/api/status', methods=['GET'])
@check_sim
@login_required
def get_status():
    return jsonify(sim.get_status_summary(user_id=current_user.id))

@app.route('/api/ledger', methods=['GET'])
@check_sim
@login_required
def get_ledger():
    return jsonify(sim.get_ledger_entries(user_id=current_user.id))

@app.route('/api/descriptions/income', methods=['GET'])
@check_sim
@login_required
def get_income_descriptions():
    return jsonify(sim.get_unique_descriptions(user_id=current_user.id, transaction_type='income'))

@app.route('/api/descriptions/expense', methods=['GET'])
@check_sim
@login_required
def get_expense_descriptions():
    return jsonify(sim.get_unique_descriptions(user_id=current_user.id, transaction_type='expense'))

@app.route('/api/meter/summary', methods=['GET'])
@check_sim
@login_required
def get_meter_summary():
    try:
        conn, cursor = sim._get_db_connection()
        user_current_date = sim._get_user_current_date(cursor, user_id=current_user.id)
        cursor.close()
        conn.close()
        burn_rate = sim.calculate_daily_burn_rate(user_id=current_user.id)
        daily_net = sim.get_daily_net(user_id=current_user.id, for_date=user_current_date)
        return jsonify({'daily_burn_rate': burn_rate, 'today_net_income': daily_net})
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500

@app.route('/api/meter/n_day_average', methods=['GET'])
@check_sim
@login_required
def get_n_day_average():
    try:
        days = request.args.get('days', default=7, type=int)
        if days < 1 or days > 365:
            return jsonify({"error": "Days must be between 1 and 365"}), 400

        result = sim.get_n_day_average(user_id=current_user.id, days=days)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500

# --- EXPENSE CATEGORIES API ROUTES ---

@app.route('/api/expense_categories', methods=['GET'])
@check_sim
@login_required
def get_expense_categories_api():
    categories = sim.get_expense_categories(user_id=current_user.id)
    return jsonify(categories)

@app.route('/api/expense_categories', methods=['POST'])
@check_sim
@login_required
def add_expense_category_api():
    data = request.get_json()
    name = data.get('name')
    color = data.get('color', '#6366f1')

    if not name:
        return jsonify({"success": False, "message": "Category name is required."}), 400

    success, message, category_id = sim.add_expense_category(
        user_id=current_user.id,
        name=name,
        color=color
    )
    if success:
        return jsonify({"success": True, "message": message, "category_id": category_id})
    else:
        return jsonify({"success": False, "message": message}), 400

@app.route('/api/expense_categories/<int:category_id>', methods=['PUT', 'DELETE'])
@check_sim
@login_required
def manage_expense_category_api(category_id):
    if request.method == 'PUT':
        data = request.get_json()
        name = data.get('name')
        color = data.get('color')

        if not all([name, color]):
            return jsonify({"success": False, "message": "Name and color are required."}), 400

        success, message = sim.update_expense_category(
            user_id=current_user.id,
            category_id=category_id,
            name=name,
            color=color
        )
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "message": message}), 400

    elif request.method == 'DELETE':
        success, message = sim.delete_expense_category(
            user_id=current_user.id,
            category_id=category_id
        )
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "message": message}), 400

@app.route('/api/expense_analysis', methods=['GET'])
@check_sim
@login_required
def get_expense_analysis_api():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        analysis = sim.get_expense_analysis(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date
        )
        return jsonify(analysis)
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500

@app.route('/api/expense/category', methods=['PUT'])
@check_sim
@login_required
def update_expense_category_api():
    data = request.get_json()
    transaction_uuid = data.get('transaction_uuid')
    category_id = data.get('category_id')

    if not transaction_uuid:
        return jsonify({"success": False, "message": "transaction_uuid is required."}), 400

    success, message = sim.update_transaction_category(
        user_id=current_user.id,
        transaction_uuid=transaction_uuid,
        category_id=category_id
    )
    return jsonify({"success": success, "message": message}), 200 if success else 400

# --- ACTION ROUTES ---
@app.route('/api/advance_time', methods=['POST'])
@check_sim
@login_required
def advance_time():
    try:
        days = request.get_json().get('days', 1)
        print(f"[ADVANCE_TIME] Starting time advance for {days} day(s)")
        result = sim.advance_time(user_id=current_user.id, days_to_advance=days)
        print(f"[ADVANCE_TIME] Result: {result}")
        return jsonify({"success": True, "message": f"Time advanced by {days} days.", "result": result})
    except Exception as e:
        print(f"[ADVANCE_TIME ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Error advancing time: {str(e)}"}), 500

@app.route('/api/income', methods=['POST'])
@check_sim
@login_required
def log_income_api():
    data = request.get_json()
    account_id = data.get('account_id')
    description = data.get('description')
    amount = data.get('amount')
    transaction_date = data.get('transaction_date')  # Optional custom date

    if not all([account_id, description, amount]):
        return jsonify({"success": False, "message":"Missing required fields."}), 400

    success, message = sim.log_income(
        user_id=current_user.id,
        account_id=account_id,
        description=description,
        amount=amount,
        transaction_date=transaction_date
    )
    return jsonify({"success": success, "message": message}), 200 if success else 400

@app.route('/api/expense', methods=['POST'])
@check_sim
@login_required
def log_expense_api():
    data = request.get_json()
    account_id = data.get('account_id')
    description = data.get('description')
    amount = data.get('amount')
    transaction_date = data.get('transaction_date')  # Optional custom date
    category_id = data.get('category_id')  # Optional category

    if not all([account_id, description, amount]):
        return jsonify({"success": False, "message":"Missing required fields."}), 400

    success, message = sim.log_expense(
        user_id=current_user.id,
        account_id=account_id,
        description=description,
        amount=amount,
        transaction_date=transaction_date,
        category_id=category_id
    )
    return jsonify({"success": success, "message": message}), 200 if success else 400

@app.route('/api/revalue_asset', methods=['POST'])
@check_sim
@login_required
def revalue_asset_api():
    data = request.get_json()
    account_id = data.get('account_id')
    new_value = data.get('new_value')
    description = data.get('description', 'Asset Revaluation')
    if not all([account_id, new_value is not None]):
        return jsonify({"success": False, "message":"Missing required fields."}), 400
    success, message = sim.revalue_asset(user_id=current_user.id, account_id=account_id, new_value=new_value, description=description)
    return jsonify({"success": success, "message": message}), 200 if success else 400

@app.route('/api/reverse_transaction', methods=['POST'])
@check_sim
@login_required
def reverse_transaction_api():
    data = request.get_json()
    transaction_uuid = data.get('transaction_uuid')
    if not transaction_uuid:
        return jsonify({"success": False, "message":"Transaction UUID is required."}), 400
    success, message = sim.reverse_transaction(user_id=current_user.id, transaction_uuid=transaction_uuid)
    return jsonify({"success": success, "message": message}), 200 if success else 400

@app.route('/api/transfer', methods=['POST'])
@check_sim
@login_required
def transfer_between_accounts_api():
    data = request.get_json()
    from_account_id = data.get('from_account_id')
    to_account_id = data.get('to_account_id')
    amount = data.get('amount')
    description = data.get('description', 'Account Transfer')
    transaction_date = data.get('transaction_date')

    if not all([from_account_id, to_account_id, amount]):
        return jsonify({"success": False, "message":"Missing required fields: from_account_id, to_account_id, and amount."}), 400

    if from_account_id == to_account_id:
        return jsonify({"success": False, "message":"Cannot transfer to the same account."}), 400

    success, message = sim.transfer_between_accounts(
        user_id=current_user.id,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        amount=amount,
        description=description,
        transaction_date=transaction_date
    )
    return jsonify({"success": success, "message": message}), 200 if success else 400

# =============================================================================
# PENDING TRANSACTIONS API (Variable Expenses & Interest Approval)
# =============================================================================

@app.route('/api/pending_transactions', methods=['GET'])
@check_sim
@login_required
def get_pending_transactions_api():
    """Get all pending transaction approvals."""
    try:
        pending = sim.get_pending_transactions(user_id=current_user.id)
        return jsonify(pending)
    except Exception as e:
        # If pending_transactions table doesn't exist, return empty list
        return jsonify([])

@app.route('/api/pending_transactions/<int:pending_id>/approve', methods=['POST'])
@check_sim
@login_required
def approve_pending_transaction_api(pending_id):
    """Approve a pending transaction with actual amount."""
    data = request.get_json()
    actual_amount = data.get('actual_amount')

    if not actual_amount:
        return jsonify({"success": False, "message": "Actual amount is required."}), 400

    success, message = sim.approve_pending_transaction(
        user_id=current_user.id,
        pending_id=pending_id,
        actual_amount=actual_amount
    )

    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 500

@app.route('/api/pending_transactions/<int:pending_id>/reject', methods=['POST'])
@check_sim
@login_required
def reject_pending_transaction_api(pending_id):
    """Reject/dismiss a pending transaction."""
    success, message = sim.reject_pending_transaction(
        user_id=current_user.id,
        pending_id=pending_id
    )
    return jsonify({"success": success, "message": message})

# =============================================================================
# LOAN PAYMENT API
# =============================================================================

@app.route('/api/loans/<int:loan_id>/payment', methods=['POST'])
@check_sim
@login_required
def make_loan_payment_api(loan_id):
    """Make a loan payment with principal/interest split and optional escrow."""
    data = request.get_json()
    payment_amount = data.get('payment_amount')
    payment_account_id = data.get('payment_account_id')
    payment_date = data.get('payment_date')
    escrow_amount = data.get('escrow_amount')

    if not all([payment_amount, payment_account_id]):
        return jsonify({"success": False, "message": "Missing required fields: payment_amount and payment_account_id."}), 400

    success, message = sim.make_loan_payment(
        user_id=current_user.id,
        loan_id=loan_id,
        payment_amount=payment_amount,
        payment_account_id=payment_account_id,
        payment_date=payment_date,
        escrow_amount=escrow_amount
    )

    return jsonify({"success": success, "message": message}), 200 if success else 400

@app.route('/api/loans/<int:loan_id>/payment_history', methods=['GET'])
@check_sim
@login_required
def get_loan_payment_history_api(loan_id):
    """Get payment history for a loan."""
    history = sim.get_loan_payment_history(user_id=current_user.id, loan_id=loan_id)
    return jsonify(history)

# =============================================================================
# CREDIT CARD INTEREST API
# =============================================================================

@app.route('/api/accounts/<int:account_id>/calculate_interest', methods=['POST'])
@check_sim
@login_required
def calculate_credit_card_interest_api(account_id):
    """Calculate and create pending transaction for credit card interest."""
    try:
        success, message = sim.calculate_credit_card_interest(
            user_id=current_user.id,
            card_account_id=account_id
        )
        print(f"DEBUG calculate_interest: success={success}, message={message}")
        return jsonify({"success": success, "message": message}), 200 if success else 400
    except Exception as e:
        print(f"ERROR in calculate_interest_api: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 400

# =============================================================================
# FINANCIAL STATEMENTS API
# =============================================================================

@app.route('/api/reports/income_statement', methods=['GET'])
@check_sim
@login_required
def get_income_statement_api():
    """Get Income Statement (P&L) for a date range."""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        return jsonify({"success": False, "message": "start_date and end_date are required"}), 400

    data = sim.get_income_statement(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date
    )
    return jsonify(data)

@app.route('/api/reports/balance_sheet', methods=['GET'])
@check_sim
@login_required
def get_balance_sheet_api():
    """Get Balance Sheet as of a specific date."""
    as_of_date = request.args.get('as_of_date')  # Optional, defaults to current date

    data = sim.get_balance_sheet(
        user_id=current_user.id,
        as_of_date=as_of_date
    )
    return jsonify(data)

@app.route('/api/reports/cash_flow', methods=['GET'])
@check_sim
@login_required
def get_cash_flow_api():
    """Get Cash Flow Statement for a date range."""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        return jsonify({"success": False, "message": "start_date and end_date are required"}), 400

    data = sim.get_cash_flow_statement(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date
    )
    return jsonify(data)

@app.route('/api/dashboard', methods=['GET'])
@check_sim
@login_required
def get_dashboard_data():
    try:
        days = int(request.args.get('days', 30))
        data = sim.get_dashboard_data(user_id=current_user.id, days=days)
        return jsonify(data)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        with open('dashboard_error.log', 'w') as f:
            f.write(error_msg)
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# =============================================================================
# DATABASE INITIALIZATION (Railway only)
# =============================================================================

@app.route('/api/init_db', methods=['GET', 'POST'])
def init_database():
    """Initialize Railway database tables. Run this once after deployment."""
    try:
        import mysql.connector
        from railway_config import RAILWAY_DB_CONFIG
        import os

        # Read the SQL file from parent directory
        sql_path = os.path.join(os.path.dirname(__file__), '..', 'railway_setup.sql')
        with open(sql_path, 'r') as f:
            sql_script = f.read()

        # Connect and execute
        conn = mysql.connector.connect(**RAILWAY_DB_CONFIG)
        cursor = conn.cursor()

        # Execute each statement separately
        for statement in sql_script.split(';'):
            if statement.strip():
                cursor.execute(statement)

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "Database initialized successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/migrate_db', methods=['GET', 'POST'])
def migrate_database():
    """Add missing columns to existing tables."""
    try:
        import mysql.connector
        from railway_config import RAILWAY_DB_CONFIG

        conn = mysql.connector.connect(**RAILWAY_DB_CONFIG)
        cursor = conn.cursor()

        # Check if transaction_date column exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'railway'
            AND TABLE_NAME = 'financial_ledger'
            AND COLUMN_NAME = 'transaction_date'
        """)

        if cursor.fetchone()[0] == 0:
            # Add transaction_date column if it doesn't exist
            cursor.execute("""
                ALTER TABLE financial_ledger
                ADD COLUMN transaction_date DATE NULL
                AFTER timestamp
            """)

        # Check and add legacy debit/credit/account columns for old code compatibility
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'railway'
            AND TABLE_NAME = 'financial_ledger'
            AND COLUMN_NAME = 'debit'
        """)

        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE financial_ledger
                ADD COLUMN debit DECIMAL(12,2) DEFAULT 0.00,
                ADD COLUMN credit DECIMAL(12,2) DEFAULT 0.00,
                ADD COLUMN account VARCHAR(100) NULL
            """)

        # Make all new schema columns nullable for legacy code compatibility
        cursor.execute("""
            ALTER TABLE financial_ledger
            MODIFY COLUMN account_id INT NULL,
            MODIFY COLUMN transaction_type ENUM('DEBIT', 'CREDIT') NULL,
            MODIFY COLUMN amount DECIMAL(12,2) NULL
        """)

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "Database migrated successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- RUN THE APP ---
if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)