import mysql.connector
import datetime
import math
import random
from decimal import Decimal

# --- DATABASE CONFIGURATION ---
DB_CONFIG = {
    'user': 'root',
    'password': 'Hecther',
    'host': 'localhost',
    'port': 3306,
    'database': 'digital_harvest_v2'
}

class BusinessSimulator:
    def __init__(self):
        self._load_state()
        self.unlockables = [
            {'type': 'product', 'id': 4, 'condition_type': 'total_revenue', 'value': 10000, 'message': 'Premium Clicky Switches (Cherry MX Blue) now available!'},
            {'type': 'product', 'id': 5, 'condition_type': 'total_revenue', 'value': 25000, 'message': 'Heavy Linear Switches (Cherry MX Black) now available!'},
        ]
        self.event_templates = [
            {'name': 'Streamer Craze: Quiet Linears', 'description': 'A popular streamer praised Quiet, Linear switches for gaming!', 'duration': 14, 'boost': 1.5, 'metrics': {'target_switch_type': 'LINEAR', 'target_sound_profile': 'QUIET'}},
            {'name': 'Ergonomics Trend: Tactile Switches', 'description': 'A new study on workplace ergonomics is boosting demand for tactile switches.', 'duration': 20, 'boost': 1.3, 'metrics': {'target_switch_type': 'TACTILE'}},
            {'name': 'ASMR Popularity: Loud Switches', 'description': 'The ASMR community is driving unexpected demand for loud, clicky switches.', 'duration': 10, 'boost': 1.75, 'metrics': {'target_sound_profile': 'LOUD'}},
        ]
        print(f"✅ Business simulation engine v2 initialized. Cash: ${self.cash:,.2f}, Date: {self.current_date.date()}")
    
    def _get_db_connection(self):
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn, conn.cursor(dictionary=True, buffered=True)

    def _load_state(self):
        conn, cursor = self._get_db_connection()
        cursor.execute("SELECT state_key, state_value FROM business_state")
        state = {row['state_key']: row['state_value'] for row in cursor.fetchall()}
        self.cash = Decimal(state.get('cash_on_hand', '20000.00'))
        self.current_date = datetime.datetime.strptime(state.get('current_date', '2025-01-01 09:00:00'), "%Y-%m-%d %H:%M:%S")
        self.simulation_start_date = datetime.datetime.strptime(state.get('start_date', '2025-01-01 09:00:00'), "%Y-%m-%d %H:%M:%S")
        cursor.close()
        conn.close()

    def _save_state(self):
        conn, cursor = self._get_db_connection()
        query = "INSERT INTO business_state (state_key, state_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE state_value = VALUES(state_value)"
        cursor.execute(query, ('cash_on_hand', str(self.cash)))
        cursor.execute(query, ('current_date', self.current_date.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        cursor.close()
        conn.close()

    def _get_current_stock(self, product_id):
        conn, cursor = self._get_db_connection()
        query = ("SELECT quantity_on_hand_after FROM inventory_ledger "
                 "WHERE product_id = %s ORDER BY transaction_date DESC, entry_id DESC LIMIT 1")
        cursor.execute(query, (product_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result['quantity_on_hand_after'] if result else 0

    def _get_unit_cost(self, vendor_id, product_id, quantity):
        conn, cursor = self._get_db_connection()
        query = ("SELECT vd.unit_cost FROM volume_discounts vd "
                 "JOIN vendor_products vp ON vd.vendor_product_id = vp.vendor_product_id "
                 "WHERE vp.vendor_id = %s AND vp.product_id = %s "
                 "AND vd.min_quantity <= %s AND (vd.max_quantity IS NULL OR vd.max_quantity >= %s)")
        cursor.execute(query, (vendor_id, product_id, quantity, quantity))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result['unit_cost'] if result else None
        
    def _get_average_cost(self, product_id):
        conn, cursor = self._get_db_connection()
        query = ("SELECT unit_cost FROM inventory_ledger WHERE product_id = %s AND type = 'Purchase' "
                 "ORDER BY transaction_date DESC, entry_id DESC LIMIT 10")
        cursor.execute(query, (product_id,))
        results = cursor.fetchall()
        
        if not results:
            cost_query = "SELECT vd.unit_cost FROM volume_discounts vd JOIN vendor_products vp ON vd.vendor_product_id = vp.vendor_product_id WHERE vp.product_id = %s ORDER BY vd.unit_cost ASC LIMIT 1"
            cursor.execute(cost_query, (product_id,))
            res = cursor.fetchone()
            cursor.close()
            conn.close()
            return res['unit_cost'] if res else Decimal(0)
        
        total_cost = sum(r['unit_cost'] for r in results)
        cursor.close()
        conn.close()
        return total_cost / len(results)

    def _get_manufacturer_spend(self):
        conn, cursor = self._get_db_connection()
        query = ("SELECT p.manufacturer_id, SUM(poi.quantity * poi.unit_cost) as total_spend "
                 "FROM purchase_order_items poi "
                 "JOIN products p ON poi.product_id = p.product_id "
                 "WHERE p.manufacturer_id IS NOT NULL "
                 "GROUP BY p.manufacturer_id")
        cursor.execute(query)
        spend_data = cursor.fetchall()
        cursor.close()
        conn.close()
        return {row['manufacturer_id']: float(row['total_spend']) for row in spend_data}

    def _get_sales_velocity(self, product_id, days=30):
        conn, cursor = self._get_db_connection()
        start_date = self.current_date - datetime.timedelta(days=days)
        query = ("SELECT SUM(quantity_change) as units_sold FROM inventory_ledger "
                 "WHERE product_id = %s AND type = 'Sale' AND transaction_date >= %s")
        cursor.execute(query, (product_id, start_date))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return abs(result['units_sold']) if result and result['units_sold'] else 0

    def _get_total_inventory_value(self):
        conn, cursor = self._get_db_connection()
        query = (
            "SELECT SUM(i.quantity_on_hand_after * COALESCE(ac.avg_cost, 0)) as total_value "
            "FROM ( "
            "    SELECT product_id, quantity_on_hand_after "
            "    FROM inventory_ledger il1 "
            "    WHERE entry_id = (SELECT MAX(entry_id) FROM inventory_ledger il2 WHERE il1.product_id = il2.product_id) "
            ") i "
            "LEFT JOIN ( "
            "    SELECT product_id, AVG(unit_cost) as avg_cost "
            "    FROM inventory_ledger "
            "    WHERE type = 'Purchase' "
            "    GROUP BY product_id "
            ") ac ON i.product_id = ac.product_id "
            "WHERE i.quantity_on_hand_after > 0"
        )
        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result['total_value'] if result and result['total_value'] else Decimal(0)

    def get_inventory_value_by_category(self):
        conn, cursor = self._get_db_connection()
        query = (
            "SELECT pc.name as category_name, SUM(i.quantity_on_hand_after * COALESCE(ac.avg_cost, 0)) as category_value "
            "FROM ( "
            "    SELECT product_id, quantity_on_hand_after "
            "    FROM inventory_ledger il1 "
            "    WHERE entry_id = (SELECT MAX(entry_id) FROM inventory_ledger il2 WHERE il1.product_id = il2.product_id) "
            ") i "
            "LEFT JOIN ( "
            "    SELECT product_id, AVG(unit_cost) as avg_cost "
            "    FROM inventory_ledger "
            "    WHERE type = 'Purchase' "
            "    GROUP BY product_id "
            ") ac ON i.product_id = ac.product_id "
            "JOIN products p ON i.product_id = p.product_id "
            "JOIN product_categories pc ON p.category_id = pc.category_id "
            "WHERE i.quantity_on_hand_after > 0 "
            "GROUP BY pc.name"
        )
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        for row in results:
            row['category_value'] = float(row['category_value'])
        return results

    def get_status_summary(self):
        conn, cursor = self._get_db_connection()
        ap_query = "SELECT SUM(amount_due) as total_ap FROM accounts_payable WHERE status = 'UNPAID'"
        cursor.execute(ap_query)
        ap_result = cursor.fetchone()
        loans_query = "SELECT SUM(outstanding_balance) as total_debt FROM loans WHERE status = 'ACTIVE'"
        cursor.execute(loans_query)
        debt_result = cursor.fetchone()
        summary = {
            'cash': float(self.cash),
            'date': self.current_date,
            'accounts_payable': float(ap_result['total_ap']) if ap_result and ap_result['total_ap'] else 0.0,
            'total_debt': float(debt_result['total_debt']) if debt_result and debt_result['total_debt'] else 0.0,
            'total_inventory_value': float(self._get_total_inventory_value())
        }
        cursor.close()
        conn.close()
        return summary
        
    def get_all_vendors(self):
        conn, cursor = self._get_db_connection()
        query = "SELECT * FROM vendors"
        cursor.execute(query)
        all_vendors = cursor.fetchall()
        manufacturer_spend = self._get_manufacturer_spend()
        available = []
        prospective = []
        PROSPECTIVE_VRS_THRESHOLD = 75
        for vendor in all_vendors:
            vendor['minimum_order_value'] = float(vendor['minimum_order_value'])
            is_unlocked = vendor['relationship_score'] >= PROSPECTIVE_VRS_THRESHOLD
            if vendor['vendor_type'] in ('MANUFACTURER', 'BOUTIQUE') and not is_unlocked:
                vendor['unlock_progress'] = {
                    'relationship_needed': PROSPECTIVE_VRS_THRESHOLD,
                    'current_spend': manufacturer_spend.get(vendor['vendor_id'], 0)
                }
                prospective.append(vendor)
            else:
                available.append(vendor)
        cursor.close()
        conn.close()
        return {'available': available, 'prospective': prospective}

    def get_products_for_vendor(self, vendor_id):
        conn, cursor = self._get_db_connection()
        query = ("SELECT p.product_id, p.name, vd.unit_cost, vd.min_quantity "
                 "FROM products p "
                 "JOIN vendor_products vp ON p.product_id = vp.product_id "
                 "JOIN volume_discounts vd ON vp.vendor_product_id = vd.vendor_product_id "
                 "WHERE vp.vendor_id = %s AND p.status = 'UNLOCKED' "
                 "ORDER BY p.name, vd.min_quantity")
        cursor.execute(query, (vendor_id,))
        products = cursor.fetchall()
        for product in products:
            product['unit_cost'] = float(product['unit_cost'])
            product['current_stock'] = self._get_current_stock(product['product_id'])
            product['sales_velocity_30_day'] = self._get_sales_velocity(product['product_id'])
        cursor.close()
        conn.close()
        return products
    
    def get_sales_history(self):
        conn, cursor = self._get_db_connection()
        days_elapsed = (self.current_date - self.simulation_start_date).days
        if days_elapsed < 30:
            start_date = self.simulation_start_date.date()
            num_days = days_elapsed if days_elapsed > 0 else 1
        else:
            start_date = (self.current_date - datetime.timedelta(days=30)).date()
            num_days = 30
        query = ("SELECT DATE(transaction_date) as sale_date, SUM(credit) as daily_revenue "
                 "FROM financial_ledger "
                 "WHERE account = 'Sales Revenue' AND transaction_date >= %s "
                 "GROUP BY DATE(transaction_date) "
                 "ORDER BY sale_date ASC")
        cursor.execute(query, (start_date,))
        sales_data = {row['sale_date']: float(row['daily_revenue']) for row in cursor.fetchall()}
        full_history = []
        for i in range(num_days):
            current_day = start_date + datetime.timedelta(days=i)
            if current_day >= self.current_date.date(): break
            full_history.append({
                'sale_date': current_day,
                'daily_revenue': sales_data.get(current_day, 0.0)
            })
        cursor.close()
        conn.close()
        return full_history

    def get_inventory(self):
        conn, cursor = self._get_db_connection()
        query = ("SELECT p.product_id, p.name, p.status, p.switch_type, p.switch_feel, p.sound_profile, "
                 "s.current_selling_price, s.default_price "
                 "FROM products p JOIN player_product_settings s ON p.product_id = s.product_id")
        cursor.execute(query)
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        inventory = []
        for p in products:
            p['stock'] = self._get_current_stock(p['product_id'])
            inventory.append(p)
        return inventory

    def set_product_price(self, product_id, new_price):
        try:
            price = Decimal(new_price)
            if price < 0: return False, "Price cannot be negative."
        except:
            return False, "Invalid price format."
        conn, cursor = self._get_db_connection()
        try:
            query = "UPDATE player_product_settings SET current_selling_price = %s WHERE product_id = %s"
            cursor.execute(query, (price, product_id))
            conn.commit()
            return True, f"Price updated successfully."
        except Exception as e:
            conn.rollback()
            return False, f"Database error: {e}"
        finally:
            cursor.close(); conn.close()

    def get_unlocks(self):
        return self.unlockables

    def get_active_events(self):
        conn, cursor = self._get_db_connection()
        query = "SELECT event_id, name, description, end_date FROM market_events WHERE end_date >= %s"
        cursor.execute(query, (self.current_date.date(),))
        events = cursor.fetchall()
        cursor.close()
        conn.close()
        return events

    def get_all_expenses(self):
        conn, cursor = self._get_db_connection()
        query = "SELECT description, amount, frequency, account FROM recurring_expenses ORDER BY amount DESC"
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results

    def get_loan_offers(self):
        principal = Decimal("50000.00")
        annual_rate = Decimal("0.06")
        years = 3
        num_payments = years * 12
        monthly_rate = annual_rate / 12
        if monthly_rate > 0:
            monthly_payment = (principal * monthly_rate * ((1 + monthly_rate) ** num_payments)) / (((1 + monthly_rate) ** num_payments) - 1)
        else:
            monthly_payment = principal / num_payments
        offer = {"id": 1, "principal": float(principal), "apr": float(annual_rate * 100), "term_months": num_payments, "monthly_payment": float(round(monthly_payment, 2))}
        return [offer]

    def accept_loan(self, offer_id):
        if offer_id != 1: return False, "Invalid loan offer."
        conn, cursor = self._get_db_connection()
        cursor.execute("SELECT loan_id FROM loans WHERE status = 'ACTIVE'")
        if cursor.fetchone():
            cursor.close(); conn.close()
            return False, "An active loan already exists."
        offers = self.get_loan_offers()
        offer = offers[0]
        principal = Decimal(offer['principal'])
        monthly_payment = Decimal(offer['monthly_payment'])
        self.cash += principal
        today = self.current_date.date()
        next_month = (today.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
        try:
            loan_query = "INSERT INTO loans (principal_amount, outstanding_balance, interest_rate, monthly_payment, next_payment_date, status) VALUES (%s, %s, %s, %s, %s, 'ACTIVE')"
            cursor.execute(loan_query, (principal, principal, offer['apr']/100, monthly_payment, next_month))
            loan_id = cursor.lastrowid
            uuid = f"loan-{loan_id}"
            fin_query = "INSERT INTO financial_ledger (transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(fin_query, (uuid, self.current_date, 'Cash', 'Loan principal received', principal, 0))
            cursor.execute(fin_query, (uuid, self.current_date, 'Loans Payable', 'Loan liability created', 0, principal))
            self._save_state()
            conn.commit()
            return True, "Loan accepted and funds added to cash."
        except Exception as e:
            conn.rollback()
            return False, f"Database error: {e}"
        finally:
            cursor.close(); conn.close()

    def get_campaign_offers(self):
        return [
            {'id': 1, 'name': 'Product Blitz', 'cost': 350.00, 'duration_days': 7, 'boost': 1.5, 'target_type': 'PRODUCT', 'description': 'Target a single product with a +50% demand boost for 7 days.'},
            {'id': 2, 'name': 'Category Push', 'cost': 1200.00, 'duration_days': 14, 'boost': 1.3, 'target_type': 'CATEGORY', 'description': 'Boost an entire product category by +30% for 14 days.'},
            {'id': 3, 'name': 'Holiday Sale', 'cost': 4500.00, 'duration_days': 30, 'boost': 1.25, 'target_type': 'ALL', 'description': 'Boost demand for ALL products by +25% for 30 days.'},
        ]

    def get_campaign_targets(self):
        conn, cursor = self._get_db_connection()
        cursor.execute("SELECT product_id as id, name FROM products WHERE status = 'UNLOCKED' ORDER BY name ASC")
        products = cursor.fetchall()
        cursor.execute("SELECT category_id as id, name FROM product_categories ORDER BY name ASC")
        categories = cursor.fetchall()
        cursor.close()
        conn.close()
        return {'products': products, 'categories': categories}

    def get_active_campaigns(self):
        conn, cursor = self._get_db_connection()
        query = "SELECT * FROM marketing_campaigns WHERE end_date >= %s"
        cursor.execute(query, (self.current_date.date(),))
        active_campaigns = cursor.fetchall()
        cursor.close()
        conn.close()
        return active_campaigns

    def get_upcoming_bills(self):
        conn, cursor = self._get_db_connection()
        query = """
            SELECT v.name as vendor_name, ap.amount_due, ap.due_date
            FROM accounts_payable ap
            JOIN vendors v ON ap.vendor_id = v.vendor_id
            WHERE ap.status = 'UNPAID' AND ap.due_date IS NOT NULL
            AND ap.due_date <= DATE_ADD(%s, INTERVAL 30 DAY)
            ORDER BY ap.due_date ASC
        """
        cursor.execute(query, (self.current_date.date(),))
        bills = cursor.fetchall()
        cursor.close()
        conn.close()
        return bills

    def get_all_bills(self):
        conn, cursor = self._get_db_connection()
        query = """
            SELECT v.name as vendor_name, ap.amount_due, ap.due_date
            FROM accounts_payable ap
            JOIN vendors v ON ap.vendor_id = v.vendor_id
            WHERE ap.status = 'UNPAID' AND ap.due_date IS NOT NULL
            ORDER BY ap.due_date ASC
        """
        cursor.execute(query)
        bills = cursor.fetchall()
        cursor.close()
        conn.close()
        return bills
    
    def get_open_purchase_orders(self):
        conn, cursor = self._get_db_connection()
        query = """
            SELECT 
                po.order_id,
                v.name as vendor_name,
                po.expected_arrival_date,
                ap.amount_due
            FROM purchase_orders po
            JOIN vendors v ON po.vendor_id = v.vendor_id
            JOIN accounts_payable ap ON po.order_id = ap.purchase_order_id
            WHERE po.status IN ('PENDING', 'IN_TRANSIT', 'DELAYED')
            ORDER BY po.expected_arrival_date ASC
        """
        cursor.execute(query)
        orders = cursor.fetchall()
        cursor.close()
        conn.close()
        return orders

    def launch_campaign(self, offer_id, target_id=None):
        offers = self.get_campaign_offers()
        offer = next((o for o in offers if o['id'] == offer_id), None)
        if not offer: return False, "Invalid campaign offer."
        cost = Decimal(offer['cost'])
        if self.cash < cost: return False, "Insufficient cash to launch campaign."
        self.cash -= cost
        start_date = self.current_date.date()
        end_date = start_date + datetime.timedelta(days=offer['duration_days'])
        conn, cursor = self._get_db_connection()
        try:
            query = ("INSERT INTO marketing_campaigns (target_type, target_id, start_date, end_date, "
                     "demand_boost_multiplier, cost, name) VALUES (%s, %s, %s, %s, %s, %s, %s)")
            cursor.execute(query, (offer['target_type'], target_id, start_date, end_date, offer['boost'], cost, offer['name']))
            campaign_id = cursor.lastrowid
            uuid = f"campaign-{campaign_id}"
            fin_query = "INSERT INTO financial_ledger (transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(fin_query, (uuid, self.current_date, 'Marketing Expense', f"Launch '{offer['name']}' campaign", cost, 0))
            cursor.execute(fin_query, (uuid, self.current_date, 'Cash', f"Payment for '{offer['name']}' campaign", 0, cost))
            self._save_state()
            conn.commit()
            return True, f"Campaign '{offer['name']}' launched successfully!"
        except Exception as e:
            conn.rollback()
            return False, f"Database error: {e}"
        finally:
            cursor.close(); conn.close()

    def calculate_shipping_preview(self, vendor_id, subtotal):
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT shipping_cost_type, shipping_flat_fee, shipping_variable_rate FROM vendors WHERE vendor_id = %s", (vendor_id,))
            vendor = cursor.fetchone()
            if not vendor: return 0.0
            subtotal_decimal = Decimal(subtotal)
            shipping_cost = Decimal('0.0')
            if vendor['shipping_cost_type'] == 'FLAT_RATE': shipping_cost = vendor['shipping_flat_fee']
            elif vendor['shipping_cost_type'] == 'HYBRID': shipping_cost = vendor['shipping_flat_fee'] + (subtotal_decimal * Decimal(vendor['shipping_variable_rate']))
            return float(shipping_cost)
        finally:
            cursor.close(); conn.close()

    def place_order(self, vendor_id, items):
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT * FROM vendors WHERE vendor_id = %s", (vendor_id,))
            vendor = cursor.fetchone()
            if not vendor: return False, "Failed to find vendor."
            subtotal = Decimal('0.0')
            line_items = []
            for product_id, quantity in items.items():
                unit_cost = self._get_unit_cost(vendor_id, product_id, quantity)
                if unit_cost is None: return False, "Could not determine unit cost for an item."
                item_subtotal = unit_cost * quantity
                subtotal += item_subtotal
                line_items.append({'product_id': product_id, 'quantity': quantity, 'unit_cost': unit_cost, 'item_subtotal': item_subtotal})
            
            if subtotal < vendor['minimum_order_value']: return False, "Order subtotal is below vendor's minimum."
            
            shipping_cost = self.calculate_shipping_preview(vendor_id, subtotal)
            grand_total = subtotal + Decimal(shipping_cost)
            
            # Allocate shipping cost proportionally to each item
            for item in line_items:
                if subtotal > 0:
                    shipping_allocation = (item['item_subtotal'] / subtotal) * Decimal(shipping_cost)
                    item['allocated_unit_cost'] = item['unit_cost'] + (shipping_allocation / item['quantity'])
                else:
                    item['allocated_unit_cost'] = item['unit_cost']
            
            order_date = self.current_date
            expected_arrival = self._add_business_days(order_date, vendor['base_lead_time_days'])
            
            po_query = "INSERT INTO purchase_orders (vendor_id, order_date, expected_arrival_date, status) VALUES (%s, %s, %s, 'PENDING')"
            cursor.execute(po_query, (vendor_id, order_date, expected_arrival))
            order_id = cursor.lastrowid
            
            poi_query = "INSERT INTO purchase_order_items (order_id, product_id, quantity, unit_cost) VALUES (%s, %s, %s, %s)"
            for item in line_items:
                # Store the allocated unit cost (including shipping) in purchase_order_items
                cursor.execute(poi_query, (order_id, item['product_id'], item['quantity'], item['allocated_unit_cost']))
            
            ap_query = ("INSERT INTO accounts_payable (purchase_order_id, vendor_id, amount_due, creation_date, due_date, status) "
                        "VALUES (%s, %s, %s, %s, NULL, 'UNPAID')")
            cursor.execute(ap_query, (order_id, vendor_id, grand_total, order_date))
            
            uuid = f"po-{order_id}"
            fin_query = "INSERT INTO financial_ledger (transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(fin_query, (uuid, self.current_date, 'Inventory', f'Goods for PO #{order_id}', grand_total, 0))
            cursor.execute(fin_query, (uuid, self.current_date, 'Accounts Payable', f'Liability for PO #{order_id}', 0, grand_total))
            
            for product_id, quantity in items.items():
                cursor.execute("SELECT manufacturer_id FROM products WHERE product_id = %s", (product_id,))
                result = cursor.fetchone()
                if result and result['manufacturer_id']:
                    manu_id = result['manufacturer_id']
                    if manu_id != vendor_id:
                        cursor.execute("UPDATE vendors SET relationship_score = relationship_score + 1 WHERE vendor_id = %s", (manu_id,))

            cursor.execute("UPDATE vendors SET relationship_score = relationship_score + 2 WHERE vendor_id = %s", (vendor_id,))
            
            conn.commit()
            print(f"SUCCESS: PO #{order_id} placed for ${grand_total:,.2f}. Bill will be due after delivery.")
            return True, "Order placed successfully."
        except Exception as e:
            conn.rollback()
            print(f"Error in place_order: {e}")
            return False, f"An internal error occurred: {e}"
        finally:
            cursor.close(); conn.close()

    def advance_time(self, days_to_advance=1):
        log_messages = []
        newly_unlocked = []

        for i in range(days_to_advance):
            log_messages.extend(self._check_for_arrivals())
            self._process_sales()
            log_messages.extend(self._apply_recurring_expenses())
            log_messages.extend(self._process_ap_payments())
            log_messages.extend(self._process_loan_payments())
            log_messages.extend(self._process_market_events())
            
            unlocked_info = self._check_for_unlocks()
            newly_unlocked.extend(unlocked_info['unlocked_products'])
            log_messages.extend(unlocked_info['messages'])
            
            self.current_date += datetime.timedelta(days=1)
        
        self._save_state()
        print("✅ Simulation advance complete.")
        return {'newly_unlocked': newly_unlocked, 'log': log_messages}

    def _process_sales(self):
        conn, cursor = self._get_db_connection()
        query = ("SELECT p.product_id, p.category_id, p.base_demand, p.price_sensitivity, "
                 "p.switch_type, p.switch_feel, p.sound_profile, "
                 "s.current_selling_price, s.default_price "
                 "FROM products p JOIN player_product_settings s ON p.product_id = s.product_id "
                 "WHERE p.status = 'UNLOCKED'")
        cursor.execute(query)
        products = cursor.fetchall()
        
        days_since_start = (self.current_date - self.simulation_start_date).days
        years_since_start = days_since_start / 365.25
        trend_factor = Decimal(1.10) ** Decimal(years_since_start)
        day_of_year = self.current_date.timetuple().tm_yday
        seasonal_factor = Decimal(1 + 0.3 * math.sin(2 * math.pi * (day_of_year - 80) / 365.25))
        weekday = self.current_date.weekday()
        weekly_factor = [Decimal('0.9'), Decimal('0.95'), Decimal('1.0'), Decimal('1.1'), Decimal('1.4'), Decimal('1.5'), Decimal('1.2')][weekday]
        
        for prod in products:
            stock = self._get_current_stock(prod['product_id'])
            if stock <= 0: continue
            
            final_boost = Decimal("1.0")
            campaign_query = ("SELECT demand_boost_multiplier FROM marketing_campaigns "
                              "WHERE start_date <= %s AND end_date >= %s AND ("
                              "  (target_type = 'PRODUCT' AND target_id = %s) OR "
                              "  (target_type = 'CATEGORY' AND target_id = %s) OR "
                              "  (target_type = 'ALL')"
                              ") ORDER BY demand_boost_multiplier DESC LIMIT 1")
            cursor.execute(campaign_query, (self.current_date.date(), self.current_date.date(), prod['product_id'], prod['category_id']))
            campaign_result = cursor.fetchone()
            if campaign_result:
                final_boost = max(final_boost, Decimal(str(campaign_result['demand_boost_multiplier'])))
            event_query = ("SELECT demand_boost_multiplier FROM market_events "
                           "WHERE start_date <= %s AND end_date >= %s "
                           "AND (target_switch_type IS NULL OR target_switch_type = %s) "
                           "AND (target_switch_feel IS NULL OR target_switch_feel = %s) "
                           "AND (target_sound_profile IS NULL OR target_sound_profile = %s) "
                           "ORDER BY demand_boost_multiplier DESC LIMIT 1")
            event_params = (
                self.current_date.date(), self.current_date.date(),
                prod['switch_type'], prod['switch_feel'], prod['sound_profile']
            )
            cursor.execute(event_query, event_params)
            event_result = cursor.fetchone()
            if event_result:
                final_boost = max(final_boost, Decimal(str(event_result['demand_boost_multiplier'])))
            price_diff_pct = (prod['current_selling_price'] - prod['default_price']) / prod['default_price']
            price_factor = Decimal(1 - (prod['price_sensitivity'] * float(price_diff_pct)))
            price_factor = max(0, price_factor)
            daily_base_demand = (Decimal(prod['base_demand']) / 7) * final_boost
            adjusted_demand = daily_base_demand * trend_factor * seasonal_factor * weekly_factor * price_factor
            calculated_demand = round(adjusted_demand * Decimal(random.uniform(0.9, 1.1)))
            units_sold = min(calculated_demand, stock)
            
            if units_sold > 0:
                revenue = units_sold * prod['current_selling_price']
                self.cash += revenue
                new_stock = stock - int(units_sold)
                uuid = f"sale-{self.current_date.date()}-{prod['product_id']}"
                avg_cost = self._get_average_cost(prod['product_id'])
                cost_of_goods_sold = units_sold * avg_cost
                inv_query = ("INSERT INTO inventory_ledger (transaction_uuid, transaction_date, product_id, type, description, "
                             "quantity_change, unit_cost, unit_price, total_value, quantity_on_hand_after) "
                             "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
                cursor.execute(inv_query, (
                    uuid, self.current_date, prod['product_id'],
                    'Sale', 'Customer Sale',
                    int(-units_sold), avg_cost, 
                    prod['current_selling_price'], revenue, new_stock
                ))
                fin_query = ("INSERT INTO financial_ledger (transaction_uuid, transaction_date, account, description, debit, credit) "
                             "VALUES (%s, %s, %s, %s, %s, %s)")
                cursor.execute(fin_query, (uuid, self.current_date, 'Cash', 'Sale', revenue, 0))
                cursor.execute(fin_query, (uuid, self.current_date, 'Sales Revenue', 'Sale', 0, revenue))
                cursor.execute(fin_query, (uuid, self.current_date, 'COGS', 'Cost for sale', cost_of_goods_sold, 0))
                cursor.execute(fin_query, (uuid, self.current_date, 'Inventory', 'Cost for sale', 0, cost_of_goods_sold))
        
        conn.commit()
        cursor.close()
        conn.close()

    def _process_ap_payments(self):
        logs = []
        conn, cursor = self._get_db_connection()
        query = "SELECT * FROM accounts_payable WHERE status = 'UNPAID' AND due_date IS NOT NULL AND due_date <= %s"
        cursor.execute(query, (self.current_date,))
        due_bills = cursor.fetchall()
        if not due_bills: 
            cursor.close(); conn.close(); return logs
        for bill in due_bills:
            amount = bill['amount_due']
            if self.cash >= amount:
                self.cash -= amount
                update_query = "UPDATE accounts_payable SET status = 'PAID', paid_date = %s WHERE payable_id = %s"
                cursor.execute(update_query, (self.current_date, bill['payable_id']))
                uuid = f"payment-po-{bill['purchase_order_id']}"
                fin_query = "INSERT INTO financial_ledger (transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(fin_query, (uuid, self.current_date, 'Accounts Payable', f'Payment for PO #{bill["purchase_order_id"]}', amount, 0))
                cursor.execute(fin_query, (uuid, self.current_date, 'Cash', f'Payment for PO #{bill["purchase_order_id"]}', 0, amount))
                logs.append(f"💸 Payment of ${amount:,.2f} made for PO #{bill['purchase_order_id']}.")
            else:
                logs.append(f"🚨 WARNING: Payment for PO #{bill['purchase_order_id']} of ${amount:,.2f} is due, but you have insufficient cash!")
        conn.commit()
        cursor.close()
        conn.close()
        return logs

    def _process_loan_payments(self):
        logs = []
        conn, cursor = self._get_db_connection()
        query = "SELECT * FROM loans WHERE status = 'ACTIVE' AND next_payment_date <= %s"
        cursor.execute(query, (self.current_date.date(),))
        due_loans = cursor.fetchall()
        for loan in due_loans:
            payment = loan['monthly_payment']
            if self.cash < payment:
                logs.append(f"🚨 LOAN PAYMENT FAILED! Insufficient cash for loan #{loan['loan_id']}.")
                continue
            self.cash -= payment
            monthly_interest_rate = loan['interest_rate'] / 12
            interest_paid = loan['outstanding_balance'] * Decimal(monthly_interest_rate)
            principal_paid = payment - interest_paid
            new_balance = loan['outstanding_balance'] - principal_paid
            uuid = f"loan-payment-{loan['loan_id']}-{self.current_date.date()}"
            fin_query = "INSERT INTO financial_ledger (transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(fin_query, (uuid, self.current_date, 'Loans Payable', 'Loan principal payment', principal_paid, 0))
            cursor.execute(fin_query, (uuid, self.current_date, 'Interest Expense', 'Loan interest payment', interest_paid, 0))
            cursor.execute(fin_query, (uuid, self.current_date, 'Cash', 'Loan payment made', 0, payment))
            next_payment_date = (loan['next_payment_date'] + datetime.timedelta(days=32)).replace(day=1)
            status = 'ACTIVE'
            if new_balance <= 0:
                new_balance = Decimal('0.00'); status = 'PAID'
                logs.append(f"🎉 Loan #{loan['loan_id']} has been fully paid off!")
            update_query = "UPDATE loans SET outstanding_balance = %s, next_payment_date = %s, status = %s WHERE loan_id = %s"
            cursor.execute(update_query, (new_balance, next_payment_date, status, loan['loan_id']))
            logs.append(f"💸 Loan payment of ${payment:,.2f} made. New balance: ${new_balance:,.2f}.")
        conn.commit()
        cursor.close()
        conn.close()
        return logs

    def _check_for_arrivals(self):
        logs = []
        conn, cursor = self._get_db_connection()
        query = ("SELECT po.*, v.reliability_score, v.name as vendor_name, v.payment_terms "
                 "FROM purchase_orders po JOIN vendors v ON po.vendor_id = v.vendor_id "
                 "WHERE po.expected_arrival_date <= %s AND po.status IN ('PENDING', 'DELAYED')")
        cursor.execute(query, (self.current_date,))
        arriving_orders = cursor.fetchall()
        
        if not arriving_orders:
            cursor.close()
            conn.close()
            return logs

        for order in arriving_orders:
            # First, check if a PENDING order should become delayed
            is_newly_delayed = False
            if order['status'] == 'PENDING' and random.random() > order['reliability_score']:
                is_newly_delayed = True
            
            if is_newly_delayed:
                # If it's newly delayed, update its status and new ETA, then skip delivery for this turn
                delay_duration = random.randint(3, 10)
                new_arrival_date = self._add_business_days(order['expected_arrival_date'], delay_duration)
                update_query = "UPDATE purchase_orders SET status = 'DELAYED', expected_arrival_date = %s WHERE order_id = %s"
                cursor.execute(update_query, (new_arrival_date, order['order_id']))
                logs.append(f"❗ PO #{order['order_id']} from {order['vendor_name']} has been delayed! New ETA: {new_arrival_date.date()}")
            else:
                # If the order is NOT newly delayed, it's ready for delivery.
                # This correctly handles both on-time PENDING orders and previously DELAYED orders.
                logs.append(f"📦 PO #{order['order_id']} from {order['vendor_name']} has arrived!")
                
                # Calculate due_date based on vendor payment terms
                import re
                payment_days = re.search(r'\d+', order['payment_terms'])
                days = int(payment_days.group()) if payment_days else 30
                due_date = self.current_date + datetime.timedelta(days=days)
                ap_update_query = "UPDATE accounts_payable SET due_date = %s WHERE purchase_order_id = %s"
                cursor.execute(ap_update_query, (due_date, order['order_id']))
                
                items_query = "SELECT * FROM purchase_order_items WHERE order_id = %s"
                cursor.execute(items_query, (order['order_id'],))
                items = cursor.fetchall()
                for item in items:
                    current_stock = self._get_current_stock(item['product_id'])
                    new_stock = current_stock + item['quantity']
                    inv_query = ("INSERT INTO inventory_ledger (transaction_uuid, transaction_date, product_id, type, description, "
                                 "quantity_change, unit_cost, total_value, quantity_on_hand_after) "
                                 "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)")
                    total_item_value = item['quantity'] * item['unit_cost']
                    cursor.execute(inv_query, (str(order['order_id']), self.current_date, item['product_id'], 'Purchase', f"PO #{order['order_id']} arrived", item['quantity'], item['unit_cost'], total_item_value, new_stock))
                update_po_query = "UPDATE purchase_orders SET status = 'DELIVERED', actual_arrival_date = %s WHERE order_id = %s"
                cursor.execute(update_po_query, (self.current_date, order['order_id']))
        
        # --- IMPORTANT: Save all the changes to the database ---
        conn.commit()
        cursor.close()
        conn.close()
        return logs

    def _apply_recurring_expenses(self):
        logs = []
        conn, cursor = self._get_db_connection()
        query = "SELECT * FROM recurring_expenses WHERE last_processed_date IS NULL OR last_processed_date < %s"
        cursor.execute(query, (self.current_date.date(),))
        due_expenses = cursor.fetchall()
        today = self.current_date.date()
        for exp in due_expenses:
            process = False
            last_processed = exp['last_processed_date']
            if exp['frequency'] == 'MONTHLY' and today.day == 1 and (last_processed is None or last_processed.month < today.month or last_processed.year < today.year):
                process = True
            if process and self.cash >= exp['amount']:
                self.cash -= exp['amount']
                uuid = f"exp-{self.current_date.date()}-{exp['expense_id']}"
                fin_query = "INSERT INTO financial_ledger (transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(fin_query, (uuid, self.current_date, exp['account'], exp['description'], exp['amount'], 0))
                cursor.execute(fin_query, (uuid, self.current_date, 'Cash', exp['description'], 0, exp['amount']))
                cursor.execute("UPDATE recurring_expenses SET last_processed_date = %s WHERE expense_id = %s", (today, exp['expense_id']))
                logs.append(f"💸 Paid recurring expense: {exp['description']} (${exp['amount']})")
            elif process and self.cash < exp['amount']:
                logs.append(f"🚨 WARNING: Could not pay recurring expense {exp['description']} due to insufficient cash.")
        conn.commit()
        cursor.close()
        conn.close()
        return logs

    def _process_market_events(self):
        logs = []
        if random.random() < 0.04:
            conn, cursor = self._get_db_connection()
            event_template = random.choice(self.event_templates)
            start_date = self.current_date.date()
            end_date = start_date + datetime.timedelta(days=event_template['duration'])
            cursor.execute("SELECT event_id FROM market_events WHERE end_date >= %s AND name = %s", (start_date, event_template['name']))
            if cursor.fetchone():
                cursor.close(); conn.close()
                return logs
            query = ("INSERT INTO market_events (name, description, start_date, end_date, demand_boost_multiplier, "
                     "target_switch_type, target_switch_feel, target_sound_profile) "
                     "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)")
            cursor.execute(query, (
                event_template['name'], event_template['description'], start_date, end_date, event_template['boost'],
                event_template['metrics'].get('target_switch_type'),
                event_template['metrics'].get('target_switch_feel'),
                event_template['metrics'].get('target_sound_profile')
            ))
            conn.commit()
            logs.append(f"🌟 NEW MARKET EVENT: {event_template['name']}")
            cursor.close()
            conn.close()
        return logs

    def _check_for_unlocks(self):
        messages = []
        unlocked_products = []
        conn, cursor = self._get_db_connection()
        cursor.execute("SELECT SUM(credit) as total_rev FROM financial_ledger WHERE account = 'Sales Revenue'")
        result = cursor.fetchone()
        total_revenue = result['total_rev'] if result and result['total_rev'] else 0
        locked_products_query = "SELECT product_id, name FROM products WHERE status = 'LOCKED'"
        cursor.execute(locked_products_query)
        locked_products = {row['product_id']: row['name'] for row in cursor.fetchall()}
        
        for unlockable in self.unlockables:
            if unlockable['type'] == 'product' and unlockable['id'] in locked_products:
                if unlockable['condition_type'] == 'total_revenue' and total_revenue >= unlockable['value']:
                    update_query = "UPDATE products SET status = 'UNLOCKED' WHERE product_id = %s"
                    cursor.execute(update_query, (unlockable['id'],))
                    messages.append(f"🎉 UNLOCKED: {unlockable['message']}")
                    unlocked_products.append(locked_products[unlockable['id']])

        conn.commit()
        cursor.close()
        conn.close()
        return {'messages': messages, 'unlocked_products': unlocked_products}

    def verify_books_balance(self):
        """Verify that total debits equal total credits"""
        conn, cursor = self._get_db_connection()
        query = "SELECT SUM(debit) as total_debits, SUM(credit) as total_credits FROM financial_ledger"
        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            debits = result['total_debits'] or 0
            credits = result['total_credits'] or 0
            return abs(debits - credits) < 0.01  # Allow for small rounding differences
        return False

    def _add_business_days(self, start_date, business_days):
        """Add business days (Mon-Fri) to a date, skipping weekends"""
        current_date = start_date
        days_added = 0
        
        while days_added < business_days:
            current_date += datetime.timedelta(days=1)
            # Monday = 0, Sunday = 6. Skip Saturday (5) and Sunday (6)
            if current_date.weekday() < 5:  # Monday through Friday
                days_added += 1
        
        return current_date
