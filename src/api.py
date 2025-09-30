from flask import Flask, jsonify, request, send_from_directory, redirect, url_for, session
from flask_cors import CORS
from engine import BusinessSimulator
import json
from decimal import Decimal
import datetime
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os

# Custom JSON encoder for handling special data types like Decimal and datetime
class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)

# --- FLASK APP SETUP ---
app = Flask(__name__, static_url_path='', static_folder='../')
app.json_encoder = CustomEncoder
app.config['SECRET_KEY'] = 'a_super_secret_key_you_should_change'
app.config['SESSION_COOKIE_SAMESITE'] = "None"
app.config['SESSION_COOKIE_SECURE'] = True
CORS(app, supports_credentials=True)

# --- STATELESS ENGINE INSTANCE ---
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


@app.route('/api/account/<int:account_id>', methods=['PUT'])
@check_sim
@login_required
def update_account_api(account_id):
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

# --- RECURRING EXPENSES API ROUTES ---

@app.route('/api/recurring_expenses', methods=['GET'])
@check_sim
@login_required
def get_recurring_expenses_api():
    expenses = sim.get_recurring_expenses(user_id=current_user.id)
    return jsonify(expenses)

@app.route('/api/recurring_expenses', methods=['POST'])
@check_sim
@login_required
def add_recurring_expense_api():
    data = request.get_json()
    description = data.get('description')
    amount = data.get('amount')
    payment_account_id = data.get('payment_account_id')
    due_day_of_month = data.get('due_day_of_month')

    if not all([description, amount, payment_account_id, due_day_of_month]):
        return jsonify({"success": False, "message": "All fields are required."}), 400
    
    success, message = sim.add_recurring_expense(
        user_id=current_user.id,
        description=description,
        amount=amount,
        payment_account_id=payment_account_id,
        due_day_of_month=due_day_of_month
    )
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 500

@app.route('/api/recurring_expenses/<int:expense_id>', methods=['PUT', 'DELETE'])
@check_sim
@login_required
def manage_recurring_expense_api(expense_id):
    print(f"DEBUG: manage_recurring_expense_api called with expense_id={expense_id}, method={request.method}")
    if request.method == 'PUT':
        data = request.get_json()
        description = data.get('description')
        amount = data.get('amount')
        due_day_of_month = data.get('due_day_of_month')

        if not all([description, amount, due_day_of_month]):
            return jsonify({"success": False, "message": "Description, amount, and due day are required."}), 400
            
        success, message = sim.update_recurring_expense(
            user_id=current_user.id,
            expense_id=expense_id,
            description=description,
            amount=amount,
            due_day_of_month=due_day_of_month
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

# --- ACTION ROUTES ---
@app.route('/api/advance_time', methods=['POST'])
@check_sim
@login_required
def advance_time():
    days = request.get_json().get('days', 1)
    result = sim.advance_time(user_id=current_user.id, days_to_advance=days)
    return jsonify({"success": True, "message": f"Time advanced by {days} days.", "result": result})

@app.route('/api/income', methods=['POST'])
@check_sim
@login_required
def log_income_api():
    data = request.get_json()
    account_id = data.get('account_id')
    description = data.get('description')
    amount = data.get('amount')
    if not all([account_id, description, amount]):
        return jsonify({"success": False, "message":"Missing required fields."}), 400
    success, message = sim.log_income(user_id=current_user.id, account_id=account_id, description=description, amount=amount)
    return jsonify({"success": success, "message": message}), 200 if success else 400

@app.route('/api/expense', methods=['POST'])
@check_sim
@login_required
def log_expense_api():
    data = request.get_json()
    account_id = data.get('account_id')
    description = data.get('description')
    amount = data.get('amount')
    if not all([account_id, description, amount]):
        return jsonify({"success": False, "message":"Missing required fields."}), 400
    success, message = sim.log_expense(user_id=current_user.id, account_id=account_id, description=description, amount=amount)
    return jsonify({"success": success, "message": message}), 200 if success else 400

# --- RUN THE APP ---
if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)