from flask import Flask, jsonify, request
from flask_cors import CORS
from engine import BusinessSimulator
import json
from decimal import Decimal
import datetime

# This custom class helps convert complex Python data types (like dates and decimals)
# into a format that can be sent over the web as JSON.
class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)

# --- FLASK APP SETUP ---
app = Flask(__name__)
app.json_encoder = CustomEncoder

# This is the crucial line that fixes the CORS error.
# It tells the browser that it's safe for the web page to make requests to this server.
CORS(app) 

# Create a single simulator instance to be used by all requests.
# This ensures your game state is consistent.
try:
    sim = BusinessSimulator()
except Exception as e:
    print(f"FATAL: Could not initialize simulator. Is the database running? Error: {e}")
    # We'll let the server run, but endpoints will show an error if the sim isn't ready.
    sim = None

def check_sim(func):
    """A decorator to check if the simulator is initialized before running a route."""
    def wrapper(*args, **kwargs):
        if not sim:
            return jsonify({"error": "Simulator not initialized. Check terminal for database connection errors."}), 500
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__ # This helps Flask with naming
    return wrapper

# --- API ROUTES ---

@app.route('/api/status', methods=['GET'])
@check_sim
def get_status():
    return jsonify(sim.get_status_summary())

@app.route('/api/sales_history', methods=['GET'])
@check_sim
def get_sales_history():
    return jsonify(sim.get_sales_history())

@app.route('/api/accounts', methods=['GET'])
@check_sim
def get_accounts():
    """Endpoint to get all user accounts and their balance"""
    # This loops through the items, keeping the ID
    accounts_list = [
        {'account_id': acc_id, **acc_data}
        for acc_id, acc_data in sim.get_accounts_list().items()
    ]
    return jsonify(accounts_list)

@app.route('/api/ledger', methods=['GET'])
@check_sim
def get_ledger():
    """Endpoint to get ther most recent transaction ledger entries."""
    return jsonify(sim.get_ledger_entries())

@app.route('/api/expenses', methods=['GET'])
@check_sim
def get_expenses():
    return jsonify(sim.get_all_expenses())

@app.route('/api/loans/offers', methods=['GET'])
@check_sim
def get_loan_offers():
    return jsonify(sim.get_loan_offers())

# --- POST Routes (Actions) ---

@app.route('/api/advance_time', methods=['POST'])
@check_sim
def advance_time():
    data = request.get_json()
    days = data.get('days', 1)
    result = sim.advance_time(days)
    return jsonify({"success": True, "message": f"Time advanced by {days} days.", "result": result})

@app.route('/api/loans/accept', methods=['POST'])
@check_sim
def accept_loan():
    data = request.get_json()
    offer_id = data.get('offer_id')
    success, message = sim.accept_loan(offer_id)
    return jsonify({"success": success, "message": message})
    
@app.route('/api/income', methods=['POST'])
@check_sim
def log_income_api():
    """API Endpoint to log a new income transaction"""
    # 1. Get the JSON data sent from the frontend
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided."}), 400

    # 2. Extract and validate te required fields
    account_id = data.get('account_id')
    description = data.get('description')
    amount = data.get('amount')

    if not all([account_id, description, amount]):
        return jsonify({"success": False, "message":"Missing required fields."}), 400
    
    # 3. Call the trusted engine method
    success, message = sim.log_income(
        account_id=account_id,
        description=description,
        amount=amount
    )

    # 4. Return a JSON response to the frontend
    if success:
        # On success, also send back the updated list of accounts
        updated_accounts = [
            {'account_id': acc_id, **acc_data}
            for acc_id, acc_data in sim.get_accounts_list().items()
        ]
        return jsonify({"success": True, "message": message, "accounts": updated_accounts})
    else:
        return jsonify({"success": False, "message": message}), 500

@app.route('/api/expense', methods=['POST'])
@check_sim
def log_expense_api():
    """API endpoint to log a new one-time expense transaction."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided."}), 400

    account_id = data.get('account_id')
    description = data.get('description')
    amount = data.get('amount')

    if not all([account_id, description, amount]):
        return jsonify({"success": False, "message":"Missing required fields."}), 400
    
    # The only major change is calling the correct engine method
    success, message = sim.log_expense(
        account_id=account_id,
        description=description,
        amount=amount
    )

    if success:
        # We just need to signal success; the frontend will handle the refresh
        return jsonify({"success": True, "message": message})
    else:
        # Send a more specific error code if the engine fails (e.g., insufficient funds)
        return jsonify({"success": False, "message": message}), 400

@app.route('/api/descriptions/income', methods=['GET'])
@check_sim
def get_income_descriptions():
    """Endpoint to get a unique list of past income descriptions."""
    return jsonify(sim.get_unique_descriptions(transaction_type='income'))

@app.route('/api/descriptions/expense', methods=['GET'])
@check_sim
def get_expense_descriptions():
    """Endpoint to get a unique list of past expense descriptions."""
    return jsonify(sim.get_unique_descriptions(transaction_type='expense'))

# --- RUN THE APP ---
if __name__ == '__main__':
    # Setting debug=True gives you helpful error messages in the browser
    # and automatically reloads the server when you save changes.
    app.run(debug=True, port=5000)
