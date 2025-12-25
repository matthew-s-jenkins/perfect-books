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
from dotenv import load_dotenv
# Load environment variables (for SECRET_KEY, etc.)
load_dotenv()

# Import engine - handle both local dev and Railway deployment
try:
    from engine import BusinessSimulator
except ModuleNotFoundError:
    from src.engine import BusinessSimulator


class CustomEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for handling Decimal and datetime objects.

    Converts:
    - Decimal to float for JSON serialization
    - datetime to ISO 8601 format with time (e.g., "2025-10-18T12:00:00")
    - date to ISO 8601 format with noon time to avoid timezone issues
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime.datetime):
            # datetime objects already have time, return as-is
            return obj.isoformat()
        if isinstance(obj, datetime.date):
            # date objects need time appended to avoid UTC interpretation
            # Use noon (12:00:00) to avoid any midnight boundary issues
            return obj.isoformat() + 'T12:00:00'
        return super().default(obj)


# =============================================================================
# FLASK APPLICATION SETUP
# =============================================================================

app = Flask(__name__, static_url_path='', static_folder='../')

# Configure Flask 3.0+ JSON encoder using the json provider interface
from flask.json.provider import DefaultJSONProvider
class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, datetime.date):
            # Append time to avoid UTC interpretation issues
            return obj.isoformat() + 'T12:00:00'
        return super().default(obj)

app.json = CustomJSONProvider(app)

# Security configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_SAMESITE'] = "None"
app.config['SESSION_COOKIE_SECURE'] = True

# Enable CORS for web interface (allows requests from different origins)
CORS(app, supports_credentials=True)

# Initialize database if it doesn't exist (for Railway deployment)
try:
    from setup_sqlite import create_database, get_db_path
except ModuleNotFoundError:
    from src.setup_sqlite import create_database, get_db_path

if not get_db_path().exists():
    print("Database not found - creating fresh database...")
    create_database()

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
    cursor.execute("SELECT user_id, username FROM users WHERE user_id = ?", (user_id,))
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
    client_date = data.get('client_date')  # Client's local date for timezone handling
    if not all([username, password]):
        return jsonify({"success": False, "message": "Username and password are required."}), 400

    user_data, message = sim.login_user(username, password)
    if user_data:
        user = User(id=str(user_data['user_id']), username=user_data['username'])
        login_user(user)

        # Auto-advance time to today's date if needed (using client's date for timezone accuracy)
        try:
            result = sim.auto_advance_time(int(user.id), client_date=client_date)
        except Exception as e:
            print(f"[LOGIN] Auto-advance failed for user {user.id}: {e}")
            import traceback
            traceback.print_exc()

        has_accounts = sim.check_user_has_accounts(user.id)
        return jsonify({"success": True, "message": message, "setup_needed": not has_accounts})
    else:
        return jsonify({"success": False, "message": message}), 401

@app.route('/api/demo_login', methods=['POST'])
@check_sim
def demo_login():
    """
    Create or retrieve a demo user for the current session.
    Each session gets its own isolated demo user with pre-populated data.
    Demo data persists during the session but is cleared on logout/new session.
    """
    try:
        from demo_data import generate_demo_data
    except ModuleNotFoundError:
        from src.demo_data import generate_demo_data

    # Check if this session already has a demo user and clean it up
    demo_user_id = session.get('demo_user_id')

    if demo_user_id:
        # Delete the old demo user data to start fresh
        conn, cursor = sim._get_db_connection()
        try:
            cursor.execute("DELETE FROM transactions WHERE user_id = ?", (demo_user_id,))
            cursor.execute("DELETE FROM accounts WHERE user_id = ?", (demo_user_id,))
            cursor.execute("DELETE FROM recurring_expenses WHERE user_id = ?", (demo_user_id,))
            cursor.execute("DELETE FROM recurring_income WHERE user_id = ?", (demo_user_id,))
            cursor.execute("DELETE FROM loans WHERE user_id = ?", (demo_user_id,))
            cursor.execute("DELETE FROM users WHERE user_id = ?", (demo_user_id,))
            conn.commit()
            print(f"[DEMO] Cleaned up old demo user {demo_user_id}")
        except Exception as e:
            print(f"[DEMO] Error cleaning up old demo user: {e}")
        finally:
            cursor.close()
            conn.close()

        # Clear the session
        session.pop('demo_user_id', None)
        session.pop('is_demo', None)

    # Create new demo user with unique session ID
    import uuid
    demo_username = f"demo_{uuid.uuid4().hex[:8]}"
    demo_password = uuid.uuid4().hex  # Random password (user won't need it)

    success, message, new_user_id = sim.register_user(demo_username, demo_password)

    if not success:
        return jsonify({"success": False, "message": "Failed to create demo user."}), 500

    # Store demo user ID in session
    session['demo_user_id'] = new_user_id
    session['is_demo'] = True

    # Create accounts for demo user
    print(f"[API] Creating accounts for user {new_user_id}")
    success1, msg1 = sim.add_single_account(new_user_id, "Checking Account", "CHECKING", 0)
    print(f"[API] Checking account: {success1} - {msg1}")

    success2, msg2 = sim.add_single_account(new_user_id, "Savings Account", "SAVINGS", 0)
    print(f"[API] Savings account: {success2} - {msg2}")

    success3, msg3 = sim.add_single_account(new_user_id, "Visa Credit Card", "CREDIT_CARD", 0, credit_limit=5000)
    print(f"[API] Credit card: {success3} - {msg3}")

    # Generate demo data
    data = request.get_json() or {}
    client_date = data.get('client_date')

    # Auto-advance to current date (this might be deleting the accounts!)
    print(f"[API] About to call auto_advance_time")
    sim.auto_advance_time(new_user_id, client_date=client_date)
    print(f"[API] Finished auto_advance_time")

    # Get account IDs to pass to demo data generator
    print(f"[API] Fetching accounts for user {new_user_id}")
    accounts = sim.get_accounts_list(new_user_id)
    print(f"[API] Found {len(accounts)} accounts: {[acc['name'] for acc in accounts]}")

    account_ids = {}
    for acc in accounts:
        if acc['name'] == "Checking Account":
            account_ids['checking'] = acc['account_id']
        elif acc['name'] == "Savings Account":
            account_ids['savings'] = acc['account_id']
        elif acc['name'] == "Visa Credit Card":
            account_ids['credit_card'] = acc['account_id']

    print(f"[API] Account IDs: {account_ids}")

    # Generate realistic transaction history
    print(f"[API] About to call generate_demo_data for user {new_user_id}")
    demo_info = generate_demo_data(sim, new_user_id, account_ids)
    print(f"[API] generate_demo_data returned: {demo_info}")

    # Log in the demo user
    user = User(id=str(new_user_id), username=demo_username)
    login_user(user)

    return jsonify({
        "success": True,
        "message": "Welcome to Perfect Books Demo!",
        "setup_needed": False,
        "demo_info": demo_info
    })

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    # If this was a demo user, delete their data
    if session.get('is_demo'):
        demo_user_id = session.get('demo_user_id')
        if demo_user_id:
            # Delete demo user and all their data
            try:
                conn, cursor = sim._get_db_connection()
                # Delete in order to respect foreign key constraints
                cursor.execute("DELETE FROM financial_ledger WHERE user_id = ?", (demo_user_id,))
                cursor.execute("DELETE FROM recurring_expenses WHERE user_id = ?", (demo_user_id,))
                cursor.execute("DELETE FROM recurring_income WHERE user_id = ?", (demo_user_id,))
                cursor.execute("DELETE FROM expense_categories WHERE user_id = ?", (demo_user_id,))
                cursor.execute("DELETE FROM income_categories WHERE user_id = ?", (demo_user_id,))
                cursor.execute("DELETE FROM accounts WHERE user_id = ?", (demo_user_id,))
                cursor.execute("DELETE FROM users WHERE user_id = ?", (demo_user_id,))
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                print(f"Error deleting demo user data: {e}")

        # Clear demo session flags
        session.pop('demo_user_id', None)
        session.pop('is_demo', None)

    logout_user()
    return jsonify({"success": True, "message": "You have been logged out."})

@app.route('/api/change_password', methods=['POST'])
@check_sim
@login_required
def change_password():
    """Change user's password after verifying current password."""
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({"success": False, "message": "Current password and new password are required."}), 400

    success, message = sim.change_password(current_user.id, current_password, new_password)

    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 400

@app.route('/api/check_session', methods=['GET'])
@login_required
def check_session():
    return jsonify({
        "logged_in": True,
        "username": current_user.username,
        "is_demo": session.get('is_demo', False)
    })

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
        print(f"[API] Recurring expenses for user {current_user.id}: {len(expenses)} found")
        if len(expenses) > 0:
            print(f"[API] First expense: {expenses[0]}")
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
    is_variable = data.get('is_variable', False)
    estimated_amount = data.get('estimated_amount')

    if not all([description, amount, payment_account_id, due_day_of_month]):
        return jsonify({"success": False, "message": "All fields are required."}), 400

    success, message = sim.add_recurring_expense(
        user_id=current_user.id,
        description=description,
        amount=amount,
        payment_account_id=payment_account_id,
        due_day_of_month=due_day_of_month,
        category_id=category_id,
        is_variable=is_variable,
        estimated_amount=estimated_amount
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
        print(f"[API] Recurring income for user {current_user.id}: {len(income)} found")
        if len(income) > 0:
            print(f"[API] First income: {income[0]}")
        return jsonify(income)
    except Exception as e:
        print(f"ERROR in get_recurring_income_api: {e}")
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
        # Debug: PUT /api/recurring_income received
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
        # Debug: update complete
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

@app.route('/api/auto_advance', methods=['POST'])
@check_sim
@login_required
def auto_advance():
    """Auto-advance time to today's date if needed. Called on page load."""
    try:
        data = request.get_json() or {}
        client_date = data.get('client_date')  # Client's local date for timezone handling
        result = sim.auto_advance_time(int(current_user.id), client_date=client_date)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        print(f"[AUTO-ADVANCE ERROR] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/sync_balances', methods=['POST'])
@check_sim
@login_required
def sync_balances():
    """Recalculate all account balances from ledger entries (fixes discrepancies)"""
    try:
        result = sim.sync_account_balances(user_id=current_user.id)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        print(f"[SYNC ERROR] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/ledger', methods=['GET'])
@check_sim
@login_required
def get_ledger():
    account_filter = request.args.get('account')  # Optional query parameter
    limit = request.args.get('limit', 50, type=int)  # Default 50 (increased from 20)
    offset = request.args.get('offset', 0, type=int)  # Default 0
    start_date = request.args.get('start_date')  # Optional start date (YYYY-MM-DD)
    end_date = request.args.get('end_date')  # Optional end date (YYYY-MM-DD)
    show_reversals = request.args.get('show_reversals', 'false', type=str).lower() == 'true'  # Default false (hide reversals)
    search_query = request.args.get('search')  # Optional search query
    category_id = request.args.get('category_id', type=int)  # Optional category filter
    return jsonify(sim.get_ledger_entries(
        user_id=current_user.id,
        transaction_limit=limit,
        transaction_offset=offset,
        account_filter=account_filter,
        start_date=start_date,
        end_date=end_date,
        show_reversals=show_reversals,
        search_query=search_query,
        category_id=category_id
    ))

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
        is_monthly = data.get('is_monthly', False)

        if not all([name, color]):
            return jsonify({"success": False, "message": "Name and color are required."}), 400

        success, message = sim.update_expense_category(
            user_id=current_user.id,
            category_id=category_id,
            name=name,
            color=color,
            is_monthly=is_monthly
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

@app.route('/api/expense_categories/<int:category_id>/transaction_count', methods=['GET'])
@check_sim
@login_required
def get_expense_category_transaction_count_api(category_id):
    count = sim.get_category_transaction_count(user_id=current_user.id, category_id=category_id)
    return jsonify({"count": count})

# --- INCOME CATEGORIES API ROUTES ---

@app.route('/api/income_categories', methods=['GET'])
@check_sim
@login_required
def get_income_categories_api():
    categories = sim.get_income_categories(user_id=current_user.id)
    return jsonify(categories)

@app.route('/api/income_categories', methods=['POST'])
@check_sim
@login_required
def add_income_category_api():
    data = request.get_json()
    name = data.get('name')
    color = data.get('color', '#10b981')
    parent_id = data.get('parent_id')
    description = data.get('description')

    if not name:
        return jsonify({"success": False, "message": "Category name is required."}), 400

    success, message, category_id = sim.add_income_category(
        user_id=current_user.id,
        name=name,
        color=color,
        parent_id=parent_id,
        description=description
    )
    if success:
        return jsonify({"success": True, "message": message, "category_id": category_id})
    else:
        return jsonify({"success": False, "message": message}), 400

@app.route('/api/income_categories/<int:category_id>', methods=['PUT', 'DELETE'])
@check_sim
@login_required
def manage_income_category_api(category_id):
    if request.method == 'PUT':
        data = request.get_json()
        name = data.get('name')
        color = data.get('color')
        parent_id = data.get('parent_id')
        description = data.get('description')

        if not all([name, color]):
            return jsonify({"success": False, "message": "Name and color are required."}), 400

        success, message = sim.update_income_category(
            user_id=current_user.id,
            category_id=category_id,
            name=name,
            color=color,
            parent_id=parent_id,
            description=description
        )
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "message": message}), 400

    elif request.method == 'DELETE':
        success, message = sim.delete_income_category(
            user_id=current_user.id,
            category_id=category_id
        )
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "message": message}), 400

# --- PARENT CATEGORIES API ROUTES ---

@app.route('/api/parent_categories', methods=['GET'])
@check_sim
@login_required
def get_parent_categories_api():
    cat_type = request.args.get('type')  # Optional: 'income' or 'expense'
    categories = sim.get_parent_categories(cat_type=cat_type)
    return jsonify(categories)

@app.route('/api/parent_categories', methods=['POST'])
@check_sim
@login_required
def add_parent_category_api():
    data = request.get_json()
    name = data.get('name')
    cat_type = data.get('type', 'expense')  # 'income', 'expense', or 'both'
    display_order = data.get('display_order')

    if not name:
        return jsonify({"success": False, "message": "Parent category name is required."}), 400

    if cat_type not in ['income', 'expense', 'both']:
        return jsonify({"success": False, "message": "Type must be 'income', 'expense', or 'both'."}), 400

    success, message, parent_id = sim.add_parent_category(
        name=name,
        cat_type=cat_type,
        display_order=display_order
    )
    if success:
        return jsonify({"success": True, "message": message, "parent_id": parent_id})
    else:
        return jsonify({"success": False, "message": message}), 400

@app.route('/api/parent_categories/<int:parent_id>', methods=['PUT', 'DELETE'])
@check_sim
@login_required
def manage_parent_category_api(parent_id):
    if request.method == 'PUT':
        data = request.get_json()
        name = data.get('name')
        cat_type = data.get('type')
        display_order = data.get('display_order')

        if not name or not cat_type:
            return jsonify({"success": False, "message": "Name and type are required."}), 400

        success, message = sim.update_parent_category(
            parent_id=parent_id,
            name=name,
            cat_type=cat_type,
            display_order=display_order
        )
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "message": message}), 400

    elif request.method == 'DELETE':
        success, message = sim.delete_parent_category(parent_id=parent_id)
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "message": message}), 400

@app.route('/api/parent_categories/<int:parent_id>/usage', methods=['GET'])
@check_sim
@login_required
def get_parent_category_usage_api(parent_id):
    usage = sim.get_parent_category_usage(parent_id=parent_id)
    return jsonify(usage)

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

@app.route('/api/expense_trends', methods=['GET'])
@check_sim
@login_required
def get_expense_trends_api():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        trends = sim.get_expense_trends_by_category(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date
        )
        return jsonify(trends)
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500

@app.route('/api/transactions', methods=['GET'])
@check_sim
@login_required
def get_transactions_by_category_api():
    """Get transactions filtered by category and date range."""
    try:
        category_id = request.args.get('category_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not category_id:
            return jsonify({"error": "category_id is required"}), 400

        transactions = sim.get_transactions_by_category(
            user_id=current_user.id,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date
        )
        return jsonify(transactions)
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500


@app.route('/api/debug/weekly_expenses', methods=['GET'])
def debug_weekly_expenses_api():
    """Temporary debug endpoint to return weekly_expenses_by_category from dashboard payload.
    Allows unauthenticated access when FLASK_DEBUG=1 and the request is from localhost.
    """
    # Allow unauthenticated access only in debug mode from localhost
    if not (os.getenv('FLASK_DEBUG') == '1' and request.remote_addr in ('127.0.0.1', '::1')):
        # If not allowed, require normal authentication
        try:
            # Attempt to use session-based current_user if available
            if not current_user.is_authenticated:
                return jsonify({"error": "Debug endpoint unavailable."}), 403
        except Exception:
            return jsonify({"error": "Debug endpoint unavailable."}), 403

    try:
        days = request.args.get('days', default=30, type=int)
        # If unauthenticated debug access, we need a user context; default to first user in DB if necessary
        user_id = None
        try:
            user_id = current_user.id
        except Exception:
            # Fallback: try to infer a user (only for local debug)
            conn, cursor = sim._get_db_connection()
            cursor.execute("SELECT user_id FROM users LIMIT 1")
            r = cursor.fetchone()
            cursor.close(); conn.close()
            user_id = r['user_id'] if r else None

        if not user_id:
            return jsonify({"error": "No user context available for debug."}), 500

        dashboard = sim.get_dashboard_data(user_id=user_id, days=days)
        return jsonify({ 'weekly_expenses_by_category': dashboard.get('weekly_expenses_by_category', []) })
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
        result = sim.advance_time(user_id=current_user.id, days_to_advance=days)
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
    category_id = data.get('category_id')  # Optional category

    if not all([account_id, description, amount]):
        return jsonify({"success": False, "message":"Missing required fields."}), 400

    success, message = sim.log_income(
        user_id=current_user.id,
        account_id=account_id,
        description=description,
        amount=amount,
        transaction_date=transaction_date,
        category_id=category_id
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
    """Make a loan/credit card payment with manual interest/principal breakdown."""
    data = request.get_json()
    interest_amount = data.get('interest_amount', 0)
    principal_amount = data.get('principal_amount', 0)
    payment_account_id = data.get('payment_account_id')
    payment_date = data.get('payment_date')
    # Append time to avoid timezone interpretation issues
    if payment_date and 'T' not in payment_date:
        payment_date = payment_date + ' 12:00:00'
    escrow_amount = data.get('escrow_amount', 0)
    other_amounts = data.get('other_amounts', [])  # List of {label, amount}

    # Debug logging removed

    if not payment_account_id:
        return jsonify({"success": False, "message": "Payment account is required."}), 400

    if not interest_amount and not principal_amount:
        return jsonify({"success": False, "message": "Please enter interest and/or principal amount."}), 400

    success, message = sim.make_loan_payment(
        user_id=current_user.id,
        loan_id=loan_id,
        interest_amount=interest_amount,
        principal_amount=principal_amount,
        payment_account_id=payment_account_id,
        payment_date=payment_date,
        escrow_amount=escrow_amount,
        other_amounts=other_amounts
    )

    # Debug: payment complete

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
        # Debug: interest calculated
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

# =============================================================================
# DATABASE INITIALIZATION ENDPOINTS (SQLite version)
# =============================================================================
# Note: These endpoints are for backwards compatibility with Railway deployment.
# For SQLite, the database is auto-created on first run by setup_sqlite.py

@app.route('/api/init_db', methods=['GET', 'POST'])
def init_database():
    """Initialize database. For SQLite, the database is auto-created on startup."""
    try:
        from setup_sqlite import create_database
        success = create_database()
        if success:
            return jsonify({"success": True, "message": "SQLite database initialized successfully!"})
        else:
            return jsonify({"success": False, "error": "Failed to create database"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/rebuild_db', methods=['GET', 'POST'])
def rebuild_database():
    """DROP ALL tables and rebuild from scratch with correct schema (SQLite version)."""
    try:
        from setup_sqlite import reset_database
        success = reset_database()
        if success:
            return jsonify({"success": True, "message": "SQLite database rebuilt successfully! All data cleared."})
        else:
            return jsonify({"success": False, "error": "Failed to rebuild database"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/migrate_db', methods=['GET', 'POST'])
def migrate_database():
    """Run pending database migrations (SQLite version)."""
    try:
        # For SQLite, migrations are handled by the migration_runner
        # This endpoint is kept for backwards compatibility
        return jsonify({
            "success": True,
            "message": "SQLite migrations are handled automatically on startup. No manual migration needed."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- RUN THE APP ---
if __name__ == '__main__':
    app.run(debug=True, port=5001, use_reloader=False)