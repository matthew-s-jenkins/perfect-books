import os
from dotenv import load_dotenv
import mysql.connector
import datetime
import time
from decimal import Decimal
import bcrypt

load_dotenv()

# --- DATABASE CONFIGURATION ---
DB_CONFIG = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_NAME')
}

class BusinessSimulator:
    def __init__(self):
        pass
    
    def _get_db_connection(self):
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn, conn.cursor(dictionary=True, buffered=True)

    def _get_user_current_date(self, cursor, user_id):
        cursor.execute(
            "SELECT MAX(transaction_date) AS last_date FROM financial_ledger WHERE user_id = %s",
            (user_id,)
        )
        result = cursor.fetchone()
        if result and result['last_date']:
            return result['last_date']
        return datetime.datetime.now()

    # --- USER AUTHENTICATION METHODS ---
    def login_user(self, username, password):
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT user_id, username, password_hash FROM users WHERE username = %s", (username,))
            user_data = cursor.fetchone()
            if not user_data:
                return None, "Invalid username or password."
            
            password_bytes = password.encode('utf-8')
            password_hash_bytes = user_data['password_hash'].encode('utf-8')

            if bcrypt.checkpw(password_bytes, password_hash_bytes):
                return user_data, "Login successful."
            else:
                return None, "Invalid username or password."
        
        except Exception as e:
            return None, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def register_user(self, username, password):
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return False, "Username already exists.", None

            password_bytes = password.encode('utf-8')
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password_bytes, salt)

            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash.decode('utf-8'))
            )
            new_user_id = cursor.lastrowid

            # Initialize default expense categories for the new user
            default_categories = [
                ('Uncategorized', '#6b7280', True),
                ('Food & Dining', '#ef4444', False),
                ('Transportation', '#f59e0b', False),
                ('Housing', '#8b5cf6', False),
                ('Utilities', '#3b82f6', False),
                ('Entertainment', '#ec4899', False),
                ('Shopping', '#10b981', False),
                ('Healthcare', '#14b8a6', False),
                ('Personal', '#f97316', False),
                ('Other', '#6366f1', False)
            ]

            for name, color, is_default in default_categories:
                cursor.execute(
                    "INSERT INTO expense_categories (user_id, name, color, is_default) VALUES (%s, %s, %s, %s)",
                    (new_user_id, name, color, is_default)
                )

            conn.commit()
            return True, "User registered successfully.", new_user_id
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}", None
        finally:
            cursor.close()
            conn.close()

    def check_user_has_accounts(self, user_id):
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT 1 FROM accounts WHERE user_id = %s LIMIT 1", (user_id,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()
            conn.close()

    def initialize_default_categories(self, user_id):
        """Create default expense categories for a new user."""
        conn, cursor = self._get_db_connection()
        try:
            default_categories = [
                ('Uncategorized', '#6b7280', True),
                ('Food & Dining', '#ef4444', False),
                ('Transportation', '#f59e0b', False),
                ('Housing', '#8b5cf6', False),
                ('Utilities', '#3b82f6', False),
                ('Entertainment', '#ec4899', False),
                ('Shopping', '#10b981', False),
                ('Healthcare', '#14b8a6', False),
                ('Personal', '#f97316', False),
                ('Other', '#6366f1', False)
            ]

            for name, color, is_default in default_categories:
                cursor.execute(
                    "INSERT INTO expense_categories (user_id, name, color, is_default) VALUES (%s, %s, %s, %s)",
                    (user_id, name, color, is_default)
                )

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()


    # --- DATA RETRIEVAL METHODS ---
    def get_status_summary(self, user_id):
        conn, cursor = self._get_db_connection()
        try:
            accounts = self.get_accounts_list(user_id)
            total_cash = sum(acc['balance'] for acc in accounts if acc['type'] in ['CHECKING', 'SAVINGS', 'CASH'])
            current_date = self._get_user_current_date(cursor, user_id)
            summary = { 'cash': float(total_cash), 'date': current_date }
            return summary
        finally:
            cursor.close()
            conn.close()
    
    def get_accounts_list(self, user_id):
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT * FROM accounts WHERE user_id = %s AND type != 'EQUITY' ORDER BY name", (user_id,))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def get_ledger_entries(self, user_id, transaction_limit=20):
        conn, cursor = self._get_db_connection()
        try:
            query = (
                "SELECT l.entry_id, l.transaction_uuid, l.transaction_date, l.description, l.account, l.debit, l.credit, "
                "l.category_id, c.name as category_name, c.color as category_color "
                "FROM financial_ledger l "
                "LEFT JOIN expense_categories c ON l.category_id = c.category_id "
                "JOIN ( "
                "    SELECT transaction_uuid, MAX(transaction_date) as max_date, MAX(entry_id) as max_id "
                "    FROM financial_ledger "
                "    WHERE user_id = %s AND description != 'Time Advanced' "
                "    GROUP BY transaction_uuid "
                "    ORDER BY max_date DESC, max_id DESC "
                "    LIMIT %s "
                ") AS recent_t "
                "ON l.transaction_uuid = recent_t.transaction_uuid "
                "WHERE l.user_id = %s ORDER BY l.transaction_date DESC, l.entry_id DESC"
            )
            cursor.execute(query, (user_id, transaction_limit, user_id))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
    
    def get_recurring_expenses(self, user_id):
        conn, cursor = self._get_db_connection()
        try:
            query = """
                SELECT r.expense_id, r.description, r.amount, r.due_day_of_month, r.last_processed_date, a.name AS payment_account_name
                FROM recurring_expenses r
                JOIN accounts a ON r.payment_account_id = a.account_id
                WHERE r.user_id = %s
                ORDER BY r.due_day_of_month, r.description
            """
            cursor.execute(query, (user_id,))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def get_unique_descriptions(self, user_id, transaction_type='expense'):
        conn, cursor = self._get_db_connection()
        try:
            base_query = "SELECT DISTINCT description FROM financial_ledger WHERE user_id = %s AND description != ''"
            if transaction_type == 'income':
                query = f"{base_query} AND account = 'Income' ORDER BY description"
            else:
                query = f"{base_query} AND account = 'Expenses' ORDER BY description"
            
            cursor.execute(query, (user_id,))
            return [row['description'] for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()
    
    def calculate_daily_burn_rate(self, user_id):
        conn, cursor = self._get_db_connection()
        try:
            query = "SELECT SUM(amount) AS total_monthly FROM recurring_expenses WHERE user_id = %s AND frequency = 'MONTHLY'"
            cursor.execute(query, (user_id,))
            result = cursor.fetchone()
            if result and result['total_monthly']:
                return float(Decimal(result['total_monthly']) / 30)
            return 0.0
        finally:
            cursor.close()
            conn.close()

    # --- EXPENSE CATEGORY METHODS ---
    def get_expense_categories(self, user_id):
        """Get all expense categories for a user."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute(
                "SELECT category_id, name, color, is_default FROM expense_categories WHERE user_id = %s ORDER BY is_default DESC, name ASC",
                (user_id,)
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def get_default_category_id(self, user_id):
        """Get the default category ID for a user (Uncategorized)."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute(
                "SELECT category_id FROM expense_categories WHERE user_id = %s AND is_default = TRUE LIMIT 1",
                (user_id,)
            )
            result = cursor.fetchone()
            return result['category_id'] if result else None
        finally:
            cursor.close()
            conn.close()

    def add_expense_category(self, user_id, name, color='#6366f1'):
        """Add a new expense category."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute(
                "INSERT INTO expense_categories (user_id, name, color) VALUES (%s, %s, %s)",
                (user_id, name, color)
            )
            conn.commit()
            return True, "Category added successfully.", cursor.lastrowid
        except Exception as e:
            conn.rollback()
            if "Duplicate entry" in str(e):
                return False, "A category with this name already exists.", None
            return False, f"An error occurred: {e}", None
        finally:
            cursor.close()
            conn.close()

    def update_expense_category(self, user_id, category_id, name, color):
        """Update an expense category."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute(
                "SELECT user_id FROM expense_categories WHERE category_id = %s",
                (category_id,)
            )
            result = cursor.fetchone()
            if not result or str(result['user_id']) != str(user_id):
                return False, "Category not found or you don't have permission to edit it."

            cursor.execute(
                "UPDATE expense_categories SET name = %s, color = %s WHERE category_id = %s",
                (name, color, category_id)
            )
            conn.commit()
            return True, "Category updated successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def delete_expense_category(self, user_id, category_id):
        """Delete an expense category (reassign to default first)."""
        conn, cursor = self._get_db_connection()
        try:
            # Check ownership and if it's not the default
            cursor.execute(
                "SELECT user_id, is_default FROM expense_categories WHERE category_id = %s",
                (category_id,)
            )
            result = cursor.fetchone()
            if not result:
                return False, "Category not found."
            if str(result['user_id']) != str(user_id):
                return False, "You don't have permission to delete this category."
            if result['is_default']:
                return False, "Cannot delete the default category."

            # Get default category
            default_category_id = self.get_default_category_id(user_id)

            # Reassign all transactions to default category
            cursor.execute(
                "UPDATE financial_ledger SET category_id = %s WHERE user_id = %s AND category_id = %s",
                (default_category_id, user_id, category_id)
            )

            # Delete the category
            cursor.execute(
                "DELETE FROM expense_categories WHERE category_id = %s",
                (category_id,)
            )
            conn.commit()
            return True, "Category deleted successfully. Transactions reassigned to Uncategorized."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def update_expense_category(self, user_id, transaction_uuid, category_id):
        """Update the category for an expense transaction."""
        conn, cursor = self._get_db_connection()
        try:
            # Verify the transaction belongs to the user and is an expense
            cursor.execute(
                "SELECT entry_id FROM financial_ledger WHERE user_id = %s AND transaction_uuid = %s AND account = 'Expenses' LIMIT 1",
                (user_id, transaction_uuid)
            )
            result = cursor.fetchone()

            if not result:
                return False, "Expense transaction not found or you don't have permission."

            # Update the category for the expense entry
            cursor.execute(
                "UPDATE financial_ledger SET category_id = %s WHERE user_id = %s AND transaction_uuid = %s AND account = 'Expenses'",
                (category_id, user_id, transaction_uuid)
            )

            conn.commit()
            return True, "Category updated successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def get_expense_analysis(self, user_id, start_date=None, end_date=None):
        """Get expense breakdown by category for analysis."""
        conn, cursor = self._get_db_connection()
        try:
            if not start_date:
                # Default to last 30 days
                current_date = self._get_user_current_date(cursor, user_id)
                start_date = current_date - datetime.timedelta(days=30)
            if not end_date:
                end_date = self._get_user_current_date(cursor, user_id)

            query = """
                SELECT
                    c.category_id,
                    c.name,
                    c.color,
                    SUM(l.debit) as total_amount,
                    COUNT(DISTINCT l.transaction_uuid) as transaction_count
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = %s
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN %s AND %s
                    AND l.category_id IS NOT NULL
                GROUP BY c.category_id, c.name, c.color
                ORDER BY total_amount DESC
            """
            cursor.execute(query, (user_id, start_date, end_date))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
    
    def get_daily_net(self, user_id, for_date):
        conn, cursor = self._get_db_connection()
        try:
            query = """
                SELECT
                    SUM(CASE WHEN account = 'Income' THEN credit ELSE 0 END) AS total_income,
                    SUM(CASE WHEN account = 'Expenses' THEN debit ELSE 0 END) AS total_expenses
                FROM financial_ledger
                WHERE user_id = %s AND DATE(transaction_date) = %s
            """
            cursor.execute(query, (user_id, for_date.date()))
            result = cursor.fetchone()
            total_income = result['total_income'] or Decimal('0.00')
            total_expenses = result['total_expenses'] or Decimal('0.00')
            return float(total_income - total_expenses)
        finally:
            cursor.close()
            conn.close()

    def get_n_day_average(self, user_id, days=30, weighted=True):
        conn, cursor = self._get_db_connection()
        try:
            current_date = self._get_user_current_date(cursor, user_id)

            # Get the first transaction date to know how long the user has been playing
            cursor.execute(
                """SELECT MIN(DATE(transaction_date)) as first_date
                   FROM financial_ledger
                   WHERE user_id = %s
                   AND description != 'Time Advanced'
                   AND description != 'Initial Balance'""",
                (user_id,)
            )
            first_date_result = cursor.fetchone()

            if not first_date_result or not first_date_result['first_date']:
                return {'average': 0.0, 'days_with_data': 0, 'total_net': 0.0, 'weighted': False}

            first_date = first_date_result['first_date']
            days_since_start = (current_date.date() - first_date).days + 1

            # For the first 30 days, use all available data at 100% weight
            if days_since_start <= 30:
                query = """
                    SELECT
                        DATE(transaction_date) as day,
                        SUM(CASE WHEN account = 'Income' THEN credit ELSE 0 END) AS total_income,
                        SUM(CASE WHEN account = 'Expenses' THEN debit ELSE 0 END) AS total_expenses
                    FROM financial_ledger
                    WHERE user_id = %s
                        AND DATE(transaction_date) >= %s
                        AND description != 'Time Advanced'
                        AND description != 'Initial Balance'
                    GROUP BY DATE(transaction_date)
                """
                cursor.execute(query, (user_id, first_date))
                results = cursor.fetchall()

                if not results:
                    return {'average': 0.0, 'days_with_data': 0, 'total_net': 0.0, 'weighted': False}

                total_net = sum(
                    (row['total_income'] or Decimal('0.00')) - (row['total_expenses'] or Decimal('0.00'))
                    for row in results
                )

                # Use calendar days since start, not just days with transactions
                average = float(total_net) / days_since_start if days_since_start > 0 else 0.0

                return {
                    'average': average,
                    'days_with_data': days_since_start,
                    'total_net': float(total_net),
                    'weighted': False
                }

            # After 30 days, use the most recent 30 days at 100% weight
            # TODO: Add weighted averaging for 31-60 and 61-90 days when implemented
            else:
                start_date = current_date - datetime.timedelta(days=29)  # Last 30 days including today

                query = """
                    SELECT
                        DATE(transaction_date) as day,
                        SUM(CASE WHEN account = 'Income' THEN credit ELSE 0 END) AS total_income,
                        SUM(CASE WHEN account = 'Expenses' THEN debit ELSE 0 END) AS total_expenses
                    FROM financial_ledger
                    WHERE user_id = %s
                        AND DATE(transaction_date) BETWEEN %s AND %s
                        AND description != 'Time Advanced'
                        AND description != 'Initial Balance'
                    GROUP BY DATE(transaction_date)
                """
                cursor.execute(query, (user_id, start_date.date(), current_date.date()))
                results = cursor.fetchall()

                if not results:
                    return {'average': 0.0, 'days_with_data': 0, 'total_net': 0.0, 'weighted': False}

                total_net = sum(
                    (row['total_income'] or Decimal('0.00')) - (row['total_expenses'] or Decimal('0.00'))
                    for row in results
                )

                # Always divide by 30 calendar days, not just days with transactions
                average = float(total_net) / 30.0

                return {
                    'average': average,
                    'days_with_data': 30,
                    'total_net': float(total_net),
                    'weighted': False
                }
        finally:
            cursor.close()
            conn.close()

    # --- ACTION METHODS ---

    def setup_initial_accounts(self, user_id, accounts):
        conn, cursor = self._get_db_connection()
        try:
            # --- FIX: Ensure a single Equity account exists ---
            cursor.execute("SELECT account_id, balance FROM accounts WHERE user_id = %s AND name = 'Equity'", (user_id,))
            equity_account = cursor.fetchone()
            if not equity_account:
                cursor.execute(
                    "INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, 'Equity', 'EQUITY', 0.00)",
                    (user_id,)
                )

            now = datetime.datetime.now()
            for acc in accounts:
                cursor.execute(
                    "INSERT INTO accounts (user_id, name, type, balance, credit_limit) VALUES (%s, %s, %s, %s, %s)",
                    (user_id, acc['name'], acc['type'], acc['balance'], acc.get('credit_limit'))
                )
                uuid = f"init-{user_id}-{int(time.time())}-{acc['name']}"
                balance = Decimal(acc['balance'])
                self._create_initial_balance_entry(cursor, user_id, uuid, now, acc['name'], balance)
            
            conn.commit()
            return True, "Initial accounts created successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred during account setup: {e}"
        finally:
            cursor.close()
            conn.close()

    def add_single_account(self, user_id, name, acc_type, balance, credit_limit=None):
        conn, cursor = self._get_db_connection()
        try:
            now = self._get_user_current_date(cursor, user_id)
            cursor.execute(
                "INSERT INTO accounts (user_id, name, type, balance, credit_limit) VALUES (%s, %s, %s, %s, %s)",
                (user_id, name, acc_type, balance, credit_limit)
            )
            uuid = f"add-{user_id}-{int(time.time())}-{name}"
            balance = Decimal(balance)
            self._create_initial_balance_entry(cursor, user_id, uuid, now, name, balance)

            conn.commit()
            return True, f"Account '{name}' added successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def _create_initial_balance_entry(self, cursor, user_id, uuid, transaction_date, account_name, balance):
        fin_query = "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        
        if balance >= 0:
            # Asset: Debit the asset account, Credit Equity
            cursor.execute(fin_query, (user_id, uuid, transaction_date, account_name, 'Initial Balance', balance, 0))
            cursor.execute(fin_query, (user_id, uuid, transaction_date, 'Equity', 'Initial Balance', 0, balance))
        else:
            # Liability: Debit Equity, Credit the liability account
            cursor.execute(fin_query, (user_id, uuid, transaction_date, 'Equity', 'Initial Balance', abs(balance), 0))
            cursor.execute(fin_query, (user_id, uuid, transaction_date, account_name, 'Initial Balance', 0, abs(balance)))

        # Update the balance of the single Equity account
        cursor.execute(
            "UPDATE accounts SET balance = balance + %s WHERE user_id = %s AND name = 'Equity'",
            (balance, user_id)
        )


    def update_account_name(self, user_id, account_id, new_name):
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT name FROM accounts WHERE account_id = %s AND user_id = %s", (account_id, user_id))
            result = cursor.fetchone()
            if not result:
                return False, "Account not found or you do not have permission to edit it."
            old_name = result['name']

            cursor.execute("UPDATE accounts SET name = %s WHERE account_id = %s", (new_name, account_id))
            cursor.execute("UPDATE financial_ledger SET account = %s WHERE user_id = %s AND account = %s", (new_name, user_id, old_name))

            conn.commit()
            return True, f"Account '{old_name}' has been renamed to '{new_name}'."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def delete_account(self, user_id, account_id):
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT name, balance FROM accounts WHERE account_id = %s AND user_id = %s", (account_id, user_id))
            result = cursor.fetchone()
            if not result:
                return False, "Account not found or you do not have permission to delete it."

            account_name = result['name']
            balance = float(result['balance'])

            # Check if balance is zero
            if abs(balance) > 0.01:  # Using 0.01 to account for floating point precision
                return False, f"Cannot delete account '{account_name}'. Balance must be $0.00 (current balance: ${balance:.2f})."

            # Check if account is used in any ledger entries
            cursor.execute(
                "SELECT COUNT(*) as count FROM financial_ledger WHERE user_id = %s AND account = %s",
                (user_id, account_name)
            )
            ledger_count = cursor.fetchone()['count']

            if ledger_count > 0:
                return False, f"Cannot delete account '{account_name}'. It has {ledger_count} transaction(s) in the ledger. Accounts with history cannot be deleted."

            # Safe to delete
            cursor.execute("DELETE FROM accounts WHERE account_id = %s AND user_id = %s", (account_id, user_id))
            conn.commit()
            return True, f"Account '{account_name}' has been deleted successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def revalue_asset(self, user_id, account_id, new_value, description="Asset Revaluation"):
        conn, cursor = self._get_db_connection()
        try:
            # Get current account info
            cursor.execute(
                "SELECT name, balance, type FROM accounts WHERE account_id = %s AND user_id = %s",
                (account_id, user_id)
            )
            account = cursor.fetchone()
            if not account:
                return False, "Account not found or you do not have permission to revalue it."

            # Only allow revaluation of FIXED_ASSET accounts
            if account['type'] != 'FIXED_ASSET':
                return False, "Only fixed assets can be revalued. This account is not a fixed asset."

            account_name = account['name']
            current_value = float(account['balance'])
            new_value = float(new_value)
            difference = new_value - current_value

            if abs(difference) < 0.01:
                return False, "New value is the same as current value. No revaluation needed."

            # Create transaction
            current_date = self._get_user_current_date(cursor, user_id)
            uuid = f"revalue-{user_id}-{int(time.time())}"

            if difference > 0:
                # Asset increased in value: Debit Asset, Credit Unrealized Gain (Equity)
                cursor.execute(
                    "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (user_id, uuid, current_date, account_name, description, abs(difference), 0)
                )
                cursor.execute(
                    "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (user_id, uuid, current_date, 'Unrealized Gain', description, 0, abs(difference))
                )
            else:
                # Asset decreased in value: Credit Asset, Debit Unrealized Loss (Equity)
                cursor.execute(
                    "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (user_id, uuid, current_date, 'Unrealized Loss', description, abs(difference), 0)
                )
                cursor.execute(
                    "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (user_id, uuid, current_date, account_name, description, 0, abs(difference))
                )

            # Update account balance
            cursor.execute(
                "UPDATE accounts SET balance = %s WHERE account_id = %s AND user_id = %s",
                (new_value, account_id, user_id)
            )

            conn.commit()
            change_text = "increased" if difference > 0 else "decreased"
            return True, f"Asset '{account_name}' has been revalued. Value {change_text} by {abs(difference):.2f} to {new_value:.2f}."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def reverse_transaction(self, user_id, transaction_uuid):
        conn, cursor = self._get_db_connection()
        try:
            # Get all entries for this transaction
            cursor.execute(
                "SELECT * FROM financial_ledger WHERE user_id = %s AND transaction_uuid = %s ORDER BY entry_id",
                (user_id, transaction_uuid)
            )
            entries = cursor.fetchall()

            if not entries:
                return False, "Transaction not found or you do not have permission to reverse it."

            # Check if already reversed
            original_description = entries[0]['description']
            if original_description.startswith("REVERSED:") or original_description.startswith("REVERSAL OF:"):
                return False, "This transaction has already been reversed or is itself a reversal."

            # Create reversal entries (swap debits and credits)
            current_date = self._get_user_current_date(cursor, user_id)
            reversal_uuid = f"reversal-{user_id}-{int(time.time())}"

            for entry in entries:
                cursor.execute(
                    "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        user_id,
                        reversal_uuid,
                        current_date,
                        entry['account'],
                        f"REVERSAL OF: {entry['description']}",
                        entry['credit'],  # Swap: old credit becomes new debit
                        entry['debit']    # Swap: old debit becomes new credit
                    )
                )

            # Update account balances
            for entry in entries:
                account_name = entry['account']
                debit_amount = entry['debit'] or Decimal('0.00')
                credit_amount = entry['credit'] or Decimal('0.00')

                # Reverse the effect: subtract debits, add credits
                balance_change = credit_amount - debit_amount

                cursor.execute(
                    "UPDATE accounts SET balance = balance + %s WHERE user_id = %s AND name = %s",
                    (balance_change, user_id, account_name)
                )

            conn.commit()
            return True, f"Transaction reversed successfully. Original: '{original_description}'"
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def log_income(self, user_id, account_id, description, amount, transaction_date=None, cursor=None):
        conn = None
        if not cursor:
            conn, cursor = self._get_db_connection()
        try:
            amount = Decimal(amount)
            if amount <= 0: return False, "Income amount must be positive."

            cursor.execute("SELECT * FROM accounts WHERE account_id = %s AND user_id = %s", (account_id, user_id))
            account = cursor.fetchone()
            if not account:
                return False, "Invalid account specified."

            new_balance = account['balance'] + amount

            # If transaction_date is provided, use it; otherwise get current user date
            if transaction_date:
                # If it's a string, convert to datetime
                if isinstance(transaction_date, str):
                    try:
                        current_date = datetime.datetime.fromisoformat(transaction_date.replace('Z', '+00:00'))
                    except:
                        current_date = datetime.datetime.strptime(transaction_date, '%Y-%m-%d')
                else:
                    current_date = transaction_date
            else:
                current_date = self._get_user_current_date(cursor, user_id)

            uuid = f"income-{user_id}-{int(time.time())}-{time.time()}"

            fin_query = "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(fin_query, (user_id, uuid, current_date, account['name'], description, amount, 0))
            cursor.execute(fin_query, (user_id, uuid, current_date, 'Income', description, 0, amount))

            cursor.execute("UPDATE accounts SET balance = %s WHERE account_id = %s AND user_id = %s", (new_balance, account_id, user_id))
            if conn: conn.commit()
            return True, f"Successfully logged income to '{account['name']}'."

        except Exception as e:
            if conn: conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            if conn:
                if cursor: cursor.close()
                if conn: conn.close()


    def add_recurring_expense(self, user_id, description, amount, payment_account_id, due_day_of_month):
        conn, cursor = self._get_db_connection()
        try:
            amount = Decimal(amount)
            if amount <= 0: return False, "Amount must be positive."
            if not 1 <= due_day_of_month <= 31: return False, "Due day must be between 1 and 31."

            cursor.execute("SELECT 1 FROM accounts WHERE account_id = %s AND user_id = %s", (payment_account_id, user_id))
            if not cursor.fetchone():
                return False, "Invalid payment account specified."

            cursor.execute(
                "INSERT INTO recurring_expenses (user_id, description, amount, frequency, payment_account_id, due_day_of_month) VALUES (%s, %s, %s, 'MONTHLY', %s, %s)",
                (user_id, description, amount, payment_account_id, due_day_of_month)
            )
            conn.commit()
            return True, f"Recurring expense '{description}' added."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()
    
    def delete_recurring_expense(self, user_id, expense_id):
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("DELETE FROM recurring_expenses WHERE expense_id = %s AND user_id = %s", (expense_id, user_id))
            if cursor.rowcount == 0:
                return False, "Expense not found or you do not have permission to delete it."
            
            conn.commit()
            return True, "Recurring expense deleted successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def update_recurring_expense(self, user_id, expense_id, description, amount, due_day_of_month):
        conn, cursor = self._get_db_connection()
        try:
            amount = Decimal(amount)
            if amount <= 0: return False, "Amount must be positive."
            if not 1 <= due_day_of_month <= 31: return False, "Due day must be between 1 and 31."

            # Check if expense exists and belongs to this user
            cursor.execute("SELECT user_id FROM recurring_expenses WHERE expense_id = %s", (expense_id,))
            existing = cursor.fetchone()

            if not existing:
                return False, "Expense not found."

            if str(existing['user_id']) != str(user_id):
                return False, "You do not have permission to update this expense."

            # Perform the update
            cursor.execute(
                "UPDATE recurring_expenses SET description = %s, amount = %s, due_day_of_month = %s WHERE expense_id = %s AND user_id = %s",
                (description, amount, due_day_of_month, expense_id, user_id)
            )

            conn.commit()
            return True, "Recurring expense updated successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()


    def transfer_between_accounts(self, user_id, from_account_id, to_account_id, amount, description="Account Transfer", transaction_date=None):
        """Transfer money between two accounts."""
        conn, cursor = self._get_db_connection()
        try:
            amount = Decimal(amount)
            if amount <= 0:
                return False, "Transfer amount must be positive."

            # Get both accounts
            cursor.execute(
                "SELECT * FROM accounts WHERE account_id IN (%s, %s) AND user_id = %s",
                (from_account_id, to_account_id, user_id)
            )
            accounts = cursor.fetchall()

            if len(accounts) != 2:
                return False, "One or both accounts not found or you don't have permission."

            from_account = next((acc for acc in accounts if acc['account_id'] == from_account_id), None)
            to_account = next((acc for acc in accounts if acc['account_id'] == to_account_id), None)

            # Check if from_account has sufficient balance
            if from_account['type'] == 'CREDIT_CARD':
                if from_account['credit_limit'] is not None and (from_account['balance'] - amount) < -from_account['credit_limit']:
                    return False, "Transfer declined. Would exceed credit limit."
            elif from_account['balance'] < amount:
                return False, "Insufficient funds for transfer."

            # Calculate new balances
            new_from_balance = from_account['balance'] - amount
            new_to_balance = to_account['balance'] + amount

            # Get transaction date
            if transaction_date:
                if isinstance(transaction_date, str):
                    try:
                        current_date = datetime.datetime.fromisoformat(transaction_date.replace('Z', '+00:00'))
                    except:
                        current_date = datetime.datetime.strptime(transaction_date, '%Y-%m-%d')
                else:
                    current_date = transaction_date
            else:
                current_date = self._get_user_current_date(cursor, user_id)

            # Create transaction UUID
            uuid = f"transfer-{user_id}-{int(time.time())}-{time.time()}"

            # Record the transfer in the ledger (debit to_account, credit from_account)
            fin_query = "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(fin_query, (user_id, uuid, current_date, to_account['name'], description, amount, 0))
            cursor.execute(fin_query, (user_id, uuid, current_date, from_account['name'], description, 0, amount))

            # Update account balances
            cursor.execute(
                "UPDATE accounts SET balance = %s WHERE account_id = %s AND user_id = %s",
                (new_from_balance, from_account_id, user_id)
            )
            cursor.execute(
                "UPDATE accounts SET balance = %s WHERE account_id = %s AND user_id = %s",
                (new_to_balance, to_account_id, user_id)
            )

            conn.commit()
            return True, f"Successfully transferred {amount} from '{from_account['name']}' to '{to_account['name']}'."

        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def log_expense(self, user_id, account_id, description, amount, transaction_date=None, category_id=None, cursor=None):
        conn = None
        if not cursor:
            conn, cursor = self._get_db_connection()
        try:
            amount = Decimal(amount)
            if amount <= 0: return False, "Expense amount must be positive."

            cursor.execute("SELECT * FROM accounts WHERE account_id = %s AND user_id = %s", (account_id, user_id))
            account = cursor.fetchone()
            if not account: return False, "Invalid account specified."

            if account['type'] == 'CREDIT_CARD':
                if account['credit_limit'] is not None and (account['balance'] - amount) < -account['credit_limit']:
                    return False, "Transaction declined. Exceeds credit limit."
            elif account['balance'] < amount:
                return False, "Insufficient funds."

            new_balance = account['balance'] - amount

            # If transaction_date is provided, use it; otherwise get current user date
            if transaction_date:
                # If it's a string, convert to datetime
                if isinstance(transaction_date, str):
                    try:
                        current_date = datetime.datetime.fromisoformat(transaction_date.replace('Z', '+00:00'))
                    except:
                        current_date = datetime.datetime.strptime(transaction_date, '%Y-%m-%d')
                else:
                    current_date = transaction_date
            else:
                current_date = self._get_user_current_date(cursor, user_id)

            # If no category is specified, use the default category
            if category_id is None:
                category_id = self.get_default_category_id(user_id)

            uuid = f"expense-{user_id}-{int(time.time())}-{time.time()}"

            fin_query = "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(fin_query, (user_id, uuid, current_date, 'Expenses', description, amount, 0, category_id))
            cursor.execute(fin_query, (user_id, uuid, current_date, account['name'], description, 0, amount, None))

            cursor.execute("UPDATE accounts SET balance = %s WHERE account_id = %s AND user_id = %s", (new_balance, account_id, user_id))

            if conn: # Only commit if this function owns the connection
                conn.commit()
            return True, f"Successfully logged expense from '{account['name']}'."

        except Exception as e:
            if conn: # Only rollback if this function owns the connection
                conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            if conn: # Only close if this function owns the connection
                cursor.close()
                conn.close()
    
    def advance_time(self, user_id, days_to_advance=1):
        conn, cursor = self._get_db_connection()
        try:
            simulation_start_date = self._get_user_current_date(cursor, user_id)
            processing_log = []

            # Fetch recurring expenses ONCE before the loop
            cursor.execute("SELECT * FROM recurring_expenses WHERE user_id = %s", (user_id,))
            recurring_expenses = cursor.fetchall()
            
            for i in range(days_to_advance):
                current_day = simulation_start_date + datetime.timedelta(days=i + 1)
                
                for expense in recurring_expenses:
                    # We only care about processing the bill on its due day.
                    if current_day.day == expense['due_day_of_month']:
                        is_due_for_payment = False
                        last_processed = expense.get('last_processed_date') # Use .get() for safety

                        if not last_processed:
                            # If it's never been paid, it's due today.
                            is_due_for_payment = True
                        elif (current_day.year, current_day.month) > (last_processed.year, last_processed.month):
                            # If today is in a later month than the last payment, it's due.
                            is_due_for_payment = True

                        if is_due_for_payment:
                            success, message = self.log_expense(
                                user_id, 
                                expense['payment_account_id'], 
                                expense['description'], 
                                expense['amount'],
                                transaction_date=current_day,
                                cursor=cursor # Pass the existing cursor
                            )
                            
                            if success:
                                cursor.execute(
                                    "UPDATE recurring_expenses SET last_processed_date = %s WHERE expense_id = %s",
                                    (current_day.date(), expense['expense_id'])
                                )
                                # Update the in-memory record to prevent re-payment in the same run
                                expense['last_processed_date'] = current_day.date()
                                processing_log.append(f"On {current_day.strftime('%Y-%m-%d')}: Paid {expense['description']} (${expense['amount']}).")
                            else:
                                processing_log.append(f"On {current_day.strftime('%Y-%m-%d')}: FAILED to pay {expense['description']} - {message}")

            final_date = simulation_start_date + datetime.timedelta(days=days_to_advance)
            # Check if we need to insert a time marker using the existing cursor
            cursor.execute(
                "SELECT transaction_date FROM financial_ledger WHERE user_id = %s ORDER BY transaction_date DESC, entry_id DESC LIMIT 1",
                (user_id,)
            )
            last_entry = cursor.fetchone()
            if not last_entry or last_entry['transaction_date'] < final_date:
                uuid = f"time-adv-{user_id}-{int(time.time())}"
                cursor.execute(
                    "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description) VALUES (%s, %s, %s, 'System', 'Time Advanced')",
                    (user_id, uuid, final_date)
                )
            
            if not processing_log and days_to_advance > 0:
                processing_log.append(f"Time advanced to {final_date.strftime('%Y-%m-%d')}. No bills were due.")

            conn.commit()
            return {'log': processing_log}
        except Exception as e:
            conn.rollback()
            return {'log': [f"An error occurred during time advance: {e}"]}
        finally:
            cursor.close()
            conn.close()