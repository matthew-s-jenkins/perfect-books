from flask import Flask, jsonify, request
from flask_cors import CORS
from engine_v2 import BusinessSimulator
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

@app.route('/api/vendors', methods=['GET'])
@check_sim
def get_vendors():
    return jsonify(sim.get_all_vendors())

@app.route('/api/vendors/<int:vendor_id>/products', methods=['GET'])
@check_sim
def get_vendor_products(vendor_id):
    return jsonify(sim.get_products_for_vendor(vendor_id))

@app.route('/api/inventory', methods=['GET'])
@check_sim
def get_inventory():
    return jsonify(sim.get_inventory())
    
@app.route('/api/dashboard_data', methods=['GET'])
@check_sim
def get_dashboard_data():
    data = {
        "inventory_by_category": sim.get_inventory_value_by_category()
    }
    return jsonify(data)

@app.route('/api/unlocks', methods=['GET'])
@check_sim
def get_unlocks():
    return jsonify(sim.get_unlocks())

@app.route('/api/market_events/active', methods=['GET'])
@check_sim
def get_active_events():
    return jsonify(sim.get_active_events())
    
@app.route('/api/expenses', methods=['GET'])
@check_sim
def get_expenses():
    return jsonify(sim.get_all_expenses())
    
@app.route('/api/loans/offers', methods=['GET'])
@check_sim
def get_loan_offers():
    return jsonify(sim.get_loan_offers())
    
@app.route('/api/marketing/offers', methods=['GET'])
@check_sim
def get_marketing_offers():
    return jsonify(sim.get_campaign_offers())
    
@app.route('/api/marketing/targets', methods=['GET'])
@check_sim
def get_marketing_targets():
    return jsonify(sim.get_campaign_targets())

@app.route('/api/marketing/active', methods=['GET'])
@check_sim
def get_active_campaigns():
    return jsonify(sim.get_active_campaigns())

@app.route('/api/bills/upcoming', methods=['GET'])
def get_upcoming_bills():
    return jsonify(sim.get_upcoming_bills())

@app.route('/api/bills/all', methods=['GET'])
def get_all_bills():
    return jsonify(sim.get_all_bills())

@app.route('/api/purchase_orders/open', methods=['GET'])
@check_sim
def get_open_purchase_orders():
    return jsonify(sim.get_open_purchase_orders())

@app.route('/api/purchase_orders/<int:order_id>/details', methods=['GET'])
@check_sim
def get_purchase_order_details(order_id):
    conn, cursor = sim._get_db_connection()
    
    # Get order info
    order_query = """
        SELECT po.*, v.name as vendor_name
        FROM purchase_orders po
        JOIN vendors v ON po.vendor_id = v.vendor_id
        WHERE po.order_id = %s
    """
    cursor.execute(order_query, (order_id,))
    order = cursor.fetchone()
    
    if not order:
        cursor.close()
        conn.close()
        return jsonify({"error": "Order not found"}), 404
    
    # Get order items
    items_query = """
        SELECT poi.*, p.name as product_name
        FROM purchase_order_items poi
        JOIN products p ON poi.product_id = p.product_id
        WHERE poi.order_id = %s
    """
    cursor.execute(items_query, (order_id,))
    items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({
        "order_id": order["order_id"],
        "vendor_name": order["vendor_name"],
        "order_date": order["order_date"].isoformat(),
        "expected_arrival_date": order["expected_arrival_date"].isoformat(),
        "status": order["status"],
        "items": items
    })

# --- POST Routes (Actions) ---

@app.route('/api/order', methods=['POST'])
@check_sim
def place_order():
    data = request.get_json()
    vendor_id = data.get('vendor_id')
    items = data.get('items')
    success, message = sim.place_order(vendor_id, items)
    return jsonify({"success": success, "message": message})

@app.route('/api/advance_time', methods=['POST'])
@check_sim
def advance_time():
    data = request.get_json()
    days = data.get('days', 1)
    result = sim.advance_time(days)
    return jsonify({"success": True, "message": f"Time advanced by {days} days.", "result": result})

@app.route('/api/products/price', methods=['POST'])
@check_sim
def set_price():
    data = request.get_json()
    product_id = data.get('product_id')
    price = data.get('price')
    success, message = sim.set_product_price(product_id, price)
    return jsonify({"success": success, "message": message})

@app.route('/api/shipping_preview', methods=['POST'])
@check_sim
def preview_shipping():
    data = request.get_json()
    vendor_id = data.get('vendor_id')
    subtotal = data.get('subtotal')
    cost = sim.calculate_shipping_preview(vendor_id, subtotal)
    return jsonify({"shipping_cost": cost})

@app.route('/api/loans/accept', methods=['POST'])
@check_sim
def accept_loan():
    data = request.get_json()
    offer_id = data.get('offer_id')
    success, message = sim.accept_loan(offer_id)
    return jsonify({"success": success, "message": message})
    
@app.route('/api/marketing/launch', methods=['POST'])
@check_sim
def launch_campaign():
    data = request.get_json()
    offer_id = data.get('offer_id')
    target_id = data.get('target_id')
    success, message = sim.launch_campaign(offer_id, target_id)
    return jsonify({"success": success, "message": message})


# --- RUN THE APP ---
if __name__ == '__main__':
    # Setting debug=True gives you helpful error messages in the browser
    # and automatically reloads the server when you save changes.
    app.run(debug=True, port=5000)
