"""
Perfect Books - Personal Finance Engine

This module contains the core BusinessSimulator class that provides a stateless
engine for managing personal finances with full double-entry accounting.

The simulator provides a complete personal finance management system with:
- Secure multi-user authentication with bcrypt password hashing
- Double-entry accounting with immutable financial ledger
- Multi-account management (checking, savings, credit cards, loans, etc.)
- Income and expense tracking with categorization
- Recurring expense automation with category support
- Loan management with payment tracking
- Time-based simulation for recurring transactions

Key Design Principles:
- **Stateless Architecture**: All state is stored in MySQL database
- **User Segregation**: Complete data isolation between users
- **Security First**: Password hashing, user validation on all operations
- **Audit Trail**: Immutable ledger with transaction UUIDs
- **BI-Ready**: Normalized schema for direct Power BI connection

Author: Matthew Jenkins
License: MIT
Related Project: Digital Harvest (Business Simulation with similar accounting principles)
"""

import os
from dotenv import load_dotenv
import mysql.connector
import datetime
import time
from decimal import Decimal
import bcrypt

# Load environment variables from .env file (for local development only)
if os.path.exists('.env'):
    load_dotenv()

# --- DATABASE CONFIGURATION ---
# Try environment variables first, fall back to railway_config.py if they're not set
DB_CONFIG = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 3306)) if os.getenv('DB_PORT') else 3306,
    'database': os.getenv('DB_NAME')
}

# If environment variables aren't set, try loading Railway-specific config
if not DB_CONFIG['host']:
    try:
        from railway_config import RAILWAY_DB_CONFIG
        DB_CONFIG = RAILWAY_DB_CONFIG
        print("Using railway_config.py (environment variables not available)")
    except ImportError:
        print("WARNING: No database configuration found!")

# Debug: Print config on startup (hide password)
print("=" * 60)
print("DATABASE CONFIGURATION:")
print(f"  Host: {DB_CONFIG['host']}")
print(f"  Port: {DB_CONFIG['port']}")
print(f"  User: {DB_CONFIG['user']}")
print(f"  Database: {DB_CONFIG['database']}")
print(f"  Password: {'***' if DB_CONFIG['password'] else 'NOT SET'}")
print("=" * 60)


class BusinessSimulator:
    """
    Stateless personal finance engine for Perfect Books.

    This class provides all business logic for the application without maintaining
    state between method calls. All data is persisted in the MySQL database and
    retrieved on demand.

    The simulator enforces user segregation - every method that accesses data requires
    a user_id parameter and validates that the user owns the data being accessed.

    Methods are organized into functional groups:
    - Authentication: User registration and login
    - Account Management: Create, read, update accounts
    - Transactions: Log income, expenses, transfers
    - Recurring Expenses: Automated bill payment with categories
    - Loans: Track debt and payment schedules
    - Categories: Expense categorization and analytics
    - Simulation: Time advancement for recurring transactions
    - Analytics: Financial summaries and reporting

    Example:
        sim = BusinessSimulator()
        user_data, msg = sim.login_user("john", "password123")
        if user_data:
            accounts = sim.get_accounts(user_data['user_id'])
    """

    def __init__(self):
        """Initialize the stateless simulator (no instance state needed)."""
        pass

    def _get_db_connection(self):
        """
        Establish a new database connection.

        Returns:
            tuple: (connection, cursor) - MySQL connection and dictionary cursor

        Note:
            Callers are responsible for closing the connection and cursor.
        """
        # Explicitly specify only the parameters we want (Python 3.13 compatibility)
        conn = mysql.connector.connect(
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            database=DB_CONFIG['database']
        )
        return conn, conn.cursor(dictionary=True, buffered=True)

    def _get_user_current_date(self, cursor, user_id):
        cursor.execute(
            "SELECT MAX(transaction_date) AS last_date FROM financial_ledger WHERE user_id = %s",
            (user_id,)
        )
        result = cursor.fetchone()
        if result and result['last_date']:
            # Ensure we return a date object (not datetime)
            if isinstance(result['last_date'], datetime.datetime):
                return result['last_date'].date()
            return result['last_date']
        return datetime.datetime.now().date()

    # =============================================================================
    # USER AUTHENTICATION METHODS
    # =============================================================================

    def login_user(self, username, password):
        """
        Authenticate a user with username and password.

        Uses bcrypt to securely verify the password against the stored hash.
        Returns user data on successful authentication.

        Args:
            username (str): The username to authenticate
            password (str): Plain-text password to verify

        Returns:
            tuple: (user_data dict, message str) where user_data contains:
                   - user_id: Database ID of the user
                   - username: Username
                   - password_hash: Hashed password (for session management)
                   Returns (None, error_message) on failure

        Example:
            user_data, msg = sim.login_user("alice", "mypassword")
            if user_data:
                print(f"Welcome, {user_data['username']}!")
        """
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
        """
        Register a new user with secure password hashing.

        Creates a new user account with bcrypt-hashed password and initializes
        default expense categories for the user.

        Args:
            username (str): Desired username (must be unique)
            password (str): Plain-text password (will be hashed)

        Returns:
            tuple: (success bool, message str, user_id int or None)
                   - (True, "User registered successfully.", user_id) on success
                   - (False, error_message, None) on failure

        Note:
            Default expense categories are automatically created including:
            Uncategorized, Food & Dining, Transportation, Housing, Utilities,
            Entertainment, Shopping, Healthcare, Personal, and Other.

        Example:
            success, msg, user_id = sim.register_user("bob", "securepass123")
            if success:
                print(f"User created with ID: {user_id}")
        """
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

    def get_ledger_entries(self, user_id, transaction_limit=20, account_filter=None):
        """
        Get ledger entries for a user, optionally filtered to a specific account.

        Args:
            user_id: The user ID
            transaction_limit: Maximum number of transactions to return
            account_filter: Optional account name to filter by. If provided, only shows
                          transactions that involve this account.

        Returns:
            List of ledger entries with running balance if filtered to one account
        """
        conn, cursor = self._get_db_connection()
        try:
            if account_filter:
                # When filtering by account, get all entries for transactions involving that account
                query = (
                    "SELECT l.entry_id, l.transaction_uuid, l.transaction_date, l.description, l.account, l.debit, l.credit, "
                    "l.category_id, c.name as category_name, c.color as category_color "
                    "FROM financial_ledger l "
                    "LEFT JOIN expense_categories c ON l.category_id = c.category_id "
                    "JOIN ( "
                    "    SELECT DISTINCT transaction_uuid, MAX(transaction_date) as max_date, MAX(entry_id) as max_id "
                    "    FROM financial_ledger "
                    "    WHERE user_id = %s AND description != 'Time Advanced' "
                    "      AND transaction_uuid IN ( "
                    "        SELECT transaction_uuid FROM financial_ledger WHERE user_id = %s AND account = %s "
                    "      ) "
                    "    GROUP BY transaction_uuid "
                    "    ORDER BY max_date DESC, max_id DESC "
                    "    LIMIT %s "
                    ") AS recent_t "
                    "ON l.transaction_uuid = recent_t.transaction_uuid "
                    "WHERE l.user_id = %s ORDER BY l.transaction_date DESC, l.entry_id DESC"
                )
                cursor.execute(query, (user_id, user_id, account_filter, transaction_limit, user_id))
            else:
                # Original query - no filter
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

            entries = cursor.fetchall()

            # If filtering by account, calculate running balance
            if account_filter and entries:
                # Get initial balance for the account (sum of all transactions before the oldest one shown)
                oldest_date = min(e['transaction_date'] for e in entries)
                cursor.execute(
                    "SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as balance "
                    "FROM financial_ledger "
                    "WHERE user_id = %s AND account = %s AND transaction_date < %s",
                    (user_id, account_filter, oldest_date)
                )
                initial_balance = float(cursor.fetchone()['balance'] or 0)

                # Sort entries by date ascending for balance calculation
                sorted_entries = sorted(entries, key=lambda x: (x['transaction_date'], x['entry_id']))

                running_balance = initial_balance
                balance_map = {}  # Map entry_id to running balance

                for entry in sorted_entries:
                    if entry['account'] == account_filter:
                        # This account is involved in this entry
                        if entry['debit'] and entry['debit'] > 0:
                            running_balance += float(entry['debit'])
                        if entry['credit'] and entry['credit'] > 0:
                            running_balance -= float(entry['credit'])

                    balance_map[entry['entry_id']] = running_balance

                # Add running balance to each entry
                for entry in entries:
                    entry['running_balance'] = balance_map.get(entry['entry_id'])

            return entries
        finally:
            cursor.close()
            conn.close()
    
    # =============================================================================
    # RECURRING EXPENSES METHODS
    # =============================================================================

    def get_recurring_expenses(self, user_id):
        """
        Retrieve all recurring expenses for a user with category information.

        Returns a list of recurring expenses including payment account and
        expense category details (name and color) for UI display.

        Args:
            user_id (int): The user whose recurring expenses to fetch

        Returns:
            list: List of dictionaries containing:
                  - expense_id: Unique ID
                  - description: Expense description
                  - amount: Monthly payment amount
                  - due_day_of_month: Day of month when payment is due (1-31)
                  - last_processed_date: Last date this expense was automatically paid
                  - category_id: Category ID (may be None)
                  - payment_account_name: Name of the payment account
                  - category_name: Name of the expense category (may be None)
                  - category_color: Hex color code for category (may be None)

        Example:
            expenses = sim.get_recurring_expenses(user_id=1)
            for exp in expenses:
                print(f"{exp['description']}: ${exp['amount']} on day {exp['due_day_of_month']}")
        """
        conn, cursor = self._get_db_connection()
        try:
            query = """
                SELECT r.expense_id, r.description, r.amount, r.due_day_of_month, r.last_processed_date, r.category_id,
                       r.is_variable, r.estimated_amount,
                       a.name AS payment_account_name, c.name AS category_name, c.color AS category_color
                FROM recurring_expenses r
                JOIN accounts a ON r.payment_account_id = a.account_id
                LEFT JOIN expense_categories c ON r.category_id = c.category_id
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
                "SELECT category_id, name, color, is_default, is_monthly FROM expense_categories WHERE user_id = %s ORDER BY is_default DESC, name ASC",
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

    def update_expense_category(self, user_id, category_id, name, color, is_monthly=False):
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
                "UPDATE expense_categories SET name = %s, color = %s, is_monthly = %s WHERE category_id = %s",
                (name, color, is_monthly, category_id)
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

    def update_transaction_category(self, user_id, transaction_uuid, category_id):
        """Update the category for an expense transaction."""
        conn, cursor = self._get_db_connection()
        try:
            # Verify the transaction belongs to the user and is an expense (has debit entry)
            cursor.execute(
                "SELECT entry_id FROM financial_ledger WHERE user_id = %s AND transaction_uuid = %s AND debit > 0 LIMIT 1",
                (user_id, transaction_uuid)
            )
            result = cursor.fetchone()

            if not result:
                return False, "Expense transaction not found or you don't have permission."

            # Update the category for all expense entries with this transaction_uuid
            cursor.execute(
                "UPDATE financial_ledger SET category_id = %s WHERE user_id = %s AND transaction_uuid = %s AND debit > 0",
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

    def get_expense_trends_by_category(self, user_id, start_date=None, end_date=None):
        """Get daily expense trends by category for charting over time."""
        conn, cursor = self._get_db_connection()
        try:
            if not start_date:
                current_date = self._get_user_current_date(cursor, user_id)
                start_date = current_date - datetime.timedelta(days=30)
            if not end_date:
                end_date = self._get_user_current_date(cursor, user_id)

            query = """
                SELECT
                    DATE(l.transaction_date) as date,
                    c.category_id,
                    c.name as category_name,
                    c.color as category_color,
                    SUM(l.debit) as amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = %s
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN %s AND %s
                    AND l.category_id IS NOT NULL
                GROUP BY DATE(l.transaction_date), c.category_id, c.name, c.color
                ORDER BY date, c.name
            """
            cursor.execute(query, (user_id, start_date, end_date))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def get_daily_net(self, user_id, for_date):
        conn, cursor = self._get_db_connection()
        try:
            # Ensure for_date is a date object (handle both date and datetime)
            if isinstance(for_date, datetime.datetime):
                for_date = for_date.date()

            query = """
                SELECT
                    SUM(CASE WHEN account = 'Income' THEN credit ELSE 0 END) AS total_income,
                    SUM(CASE WHEN account = 'Expenses' THEN debit ELSE 0 END) AS total_expenses
                FROM financial_ledger
                WHERE user_id = %s AND DATE(transaction_date) = %s
            """
            cursor.execute(query, (user_id, for_date))
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
            # current_date is already a date object, no need to call .date()
            days_since_start = (current_date - first_date).days + 1

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
                # start_date and current_date are already date objects
                cursor.execute(query, (user_id, start_date, current_date))
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


    def add_recurring_expense(self, user_id, description, amount, payment_account_id, due_day_of_month, category_id=None, is_variable=False, estimated_amount=None):
        """
        Add a new monthly recurring expense with optional category.

        Creates a recurring expense that will be automatically processed on the
        specified day of each month during time advancement.

        Args:
            user_id (int): User creating the recurring expense
            description (str): Description of the expense (e.g., "Rent", "Netflix")
            amount (float/Decimal): Monthly payment amount (must be positive)
            payment_account_id (int): Account ID to pay from (must belong to user)
            due_day_of_month (int): Day of month when payment is due (1-31)
            category_id (int, optional): Expense category ID (must belong to user)

        Returns:
            tuple: (success bool, message str)
                   - (True, success_message) on success
                   - (False, error_message) on failure

        Validation:
            - Amount must be positive
            - Due day must be between 1 and 31
            - Payment account must exist and belong to user
            - Category (if provided) must exist and belong to user

        Example:
            success, msg = sim.add_recurring_expense(
                user_id=1,
                description="Netflix Subscription",
                amount=15.99,
                payment_account_id=1,
                due_day_of_month=15,
                category_id=6  # Entertainment category
            )
        """
        conn, cursor = self._get_db_connection()
        try:
            amount = Decimal(amount)
            if amount <= 0: return False, "Amount must be positive."
            if not 1 <= due_day_of_month <= 31: return False, "Due day must be between 1 and 31."

            cursor.execute("SELECT 1 FROM accounts WHERE account_id = %s AND user_id = %s", (payment_account_id, user_id))
            if not cursor.fetchone():
                return False, "Invalid payment account specified."

            # Validate category if provided
            if category_id:
                cursor.execute("SELECT 1 FROM expense_categories WHERE category_id = %s AND user_id = %s", (category_id, user_id))
                if not cursor.fetchone():
                    return False, "Invalid category specified."

            cursor.execute(
                "INSERT INTO recurring_expenses (user_id, description, amount, frequency, payment_account_id, due_day_of_month, category_id, is_variable, estimated_amount) VALUES (%s, %s, %s, 'MONTHLY', %s, %s, %s, %s, %s)",
                (user_id, description, amount, payment_account_id, due_day_of_month, category_id, is_variable, estimated_amount)
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

    # =============================================================================
    # RECURRING INCOME METHODS
    # =============================================================================

    def get_recurring_income(self, user_id):
        """Get all recurring income entries for a user."""
        conn, cursor = self._get_db_connection()
        try:
            query = """
                SELECT ri.income_id, ri.description, ri.amount, ri.deposit_day_of_month, ri.last_processed_date,
                       ri.is_variable, ri.estimated_amount,
                       a.name AS deposit_account_name
                FROM recurring_income ri
                JOIN accounts a ON ri.deposit_account_id = a.account_id
                WHERE ri.user_id = %s
                ORDER BY ri.deposit_day_of_month, ri.description
            """
            cursor.execute(query, (user_id,))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def add_recurring_income(self, user_id, description, amount, deposit_account_id, deposit_day_of_month, is_variable=False, estimated_amount=None):
        """Add a new recurring income entry."""
        conn, cursor = self._get_db_connection()
        try:
            amount = Decimal(amount) if amount else Decimal(0)
            if not is_variable and amount <= 0:
                return False, "Amount must be positive for fixed income."
            if not 1 <= deposit_day_of_month <= 31:
                return False, "Deposit day must be between 1 and 31."

            cursor.execute(
                "INSERT INTO recurring_income (user_id, description, amount, deposit_account_id, deposit_day_of_month, is_variable, estimated_amount) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (user_id, description, amount, deposit_account_id, deposit_day_of_month, is_variable, estimated_amount)
            )
            conn.commit()
            return True, "Recurring income added successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def delete_recurring_income(self, user_id, income_id):
        """Delete a recurring income entry."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("DELETE FROM recurring_income WHERE income_id = %s AND user_id = %s", (income_id, user_id))
            if cursor.rowcount == 0:
                return False, "Income not found or you do not have permission to delete it."

            conn.commit()
            return True, "Recurring income deleted successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def update_recurring_income(self, user_id, income_id, description, amount, deposit_day_of_month, is_variable=False, estimated_amount=None):
        """Update a recurring income entry."""
        conn, cursor = self._get_db_connection()
        try:
            amount = Decimal(amount) if amount else Decimal(0)
            if not is_variable and amount <= 0:
                return False, "Amount must be positive for fixed income."
            if not 1 <= deposit_day_of_month <= 31:
                return False, "Deposit day must be between 1 and 31."

            # Debug: Check if the record exists first
            cursor.execute("SELECT income_id, user_id FROM recurring_income WHERE income_id = %s", (income_id,))
            existing = cursor.fetchone()
            print(f"DEBUG update_recurring_income: Looking for income_id={income_id}, user_id={user_id}")
            print(f"DEBUG update_recurring_income: Found record: {existing}")

            cursor.execute(
                "UPDATE recurring_income SET description = %s, amount = %s, deposit_day_of_month = %s, is_variable = %s, estimated_amount = %s "
                "WHERE income_id = %s AND user_id = %s",
                (description, amount, deposit_day_of_month, is_variable, estimated_amount, income_id, user_id)
            )

            print(f"DEBUG update_recurring_income: UPDATE affected {cursor.rowcount} rows")

            if cursor.rowcount == 0:
                return False, f"Income not found or you do not have permission to update it. (income_id={income_id}, user_id={user_id})"

            conn.commit()
            return True, "Recurring income updated successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def update_recurring_expense(self, user_id, expense_id, description, amount, due_day_of_month, category_id=None, is_variable=False, estimated_amount=None):
        conn, cursor = self._get_db_connection()
        try:
            # Convert amount to Decimal if provided
            if amount is not None:
                amount = Decimal(amount)
                if amount < 0: return False, "Amount cannot be negative."

            # For non-variable expenses, amount is required
            if not is_variable and (amount is None or amount == 0):
                return False, "Amount is required for fixed expenses."

            if not 1 <= due_day_of_month <= 31: return False, "Due day must be between 1 and 31."

            # Check if expense exists and belongs to this user
            cursor.execute("SELECT user_id FROM recurring_expenses WHERE expense_id = %s", (expense_id,))
            existing = cursor.fetchone()

            if not existing:
                return False, "Expense not found."

            if str(existing['user_id']) != str(user_id):
                return False, "You do not have permission to update this expense."

            # Validate category if provided
            if category_id:
                cursor.execute("SELECT 1 FROM expense_categories WHERE category_id = %s AND user_id = %s", (category_id, user_id))
                if not cursor.fetchone():
                    return False, "Invalid category specified."

            # Convert estimated_amount if provided
            if estimated_amount:
                estimated_amount = Decimal(estimated_amount)

            # Perform the update
            cursor.execute(
                "UPDATE recurring_expenses SET description = %s, amount = %s, due_day_of_month = %s, category_id = %s, is_variable = %s, estimated_amount = %s WHERE expense_id = %s AND user_id = %s",
                (description, amount, due_day_of_month, category_id, is_variable, estimated_amount, expense_id, user_id)
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
    
    # =============================================================================
    # PENDING TRANSACTIONS METHODS (Variable Expenses & Interest Approval)
    # =============================================================================

    def get_pending_transactions(self, user_id):
        """
        Get all pending transaction approvals for a user.

        Returns pending transactions (variable expenses and credit card interest)
        that require user approval before being processed.

        Args:
            user_id (int): The user ID

        Returns:
            list: List of dictionaries containing pending transaction details
        """
        conn, cursor = self._get_db_connection()
        try:
            query = """
                SELECT p.pending_id, p.description, p.estimated_amount,
                       p.due_date, p.payment_account_id, p.category_id,
                       p.transaction_type, p.related_account_id,
                       a.name AS account_name,
                       c.name AS category_name, c.color AS category_color,
                       p.recurring_expense_id
                FROM pending_transactions p
                JOIN accounts a ON p.payment_account_id = a.account_id
                LEFT JOIN expense_categories c ON p.category_id = c.category_id
                WHERE p.user_id = %s AND p.status = 'PENDING'
                ORDER BY p.due_date ASC
            """
            cursor.execute(query, (user_id,))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def approve_pending_transaction(self, user_id, pending_id, actual_amount):
        """
        Approve a pending transaction and process the payment.

        This handles both variable recurring expenses and credit card interest charges.

        Args:
            user_id (int): The user ID
            pending_id (int): The pending transaction ID
            actual_amount (Decimal): The actual amount to charge

        Returns:
            tuple: (success bool, message str)
        """
        conn, cursor = self._get_db_connection()
        try:
            # Get pending transaction
            cursor.execute("""
                SELECT * FROM pending_transactions
                WHERE pending_id = %s AND user_id = %s AND status = 'PENDING'
            """, (pending_id, user_id))

            pending = cursor.fetchone()
            if not pending:
                return False, "Pending transaction not found."

            # Process based on transaction type
            if pending['transaction_type'] == 'EXPENSE':
                # Log the expense
                success, message = self.log_expense(
                    user_id=user_id,
                    account_id=pending['payment_account_id'],
                    description=pending['description'],
                    amount=actual_amount,
                    transaction_date=pending['due_date'],
                    category_id=pending['category_id'],
                    cursor=cursor
                )

                if not success:
                    return False, f"Failed to log expense: {message}"

            elif pending['transaction_type'] == 'INCOME':
                # Log the income
                success, message = self.log_income(
                    user_id=user_id,
                    account_id=pending['payment_account_id'],
                    description=pending['description'],
                    amount=actual_amount,
                    transaction_date=pending['due_date'],
                    cursor=cursor
                )

                if not success:
                    return False, f"Failed to log income: {message}"

            elif pending['transaction_type'] == 'INTEREST':
                # Process credit card interest
                from uuid import uuid4
                txn_uuid = str(uuid4())

                # Get account name
                cursor.execute("SELECT name FROM accounts WHERE account_id = %s",
                             (pending['related_account_id'],))
                card_account = cursor.fetchone()

                # DR Interest Expense
                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (%s, %s, %s, 'Interest Expense', %s, %s, 0, NULL)
                """, (user_id, txn_uuid, pending['due_date'], pending['description'], actual_amount))

                # CR Credit Card (increases debt)
                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (%s, %s, %s, %s, %s, 0, %s, NULL)
                """, (user_id, txn_uuid, pending['due_date'], card_account['name'],
                     pending['description'], actual_amount))

                # Update account balance
                cursor.execute("""
                    UPDATE accounts
                    SET balance = balance - %s, last_interest_date = %s
                    WHERE account_id = %s
                """, (actual_amount, pending['due_date'], pending['related_account_id']))

            # Update pending transaction
            cursor.execute("""
                UPDATE pending_transactions
                SET status = 'APPROVED', actual_amount = %s, resolved_at = NOW()
                WHERE pending_id = %s
            """, (actual_amount, pending_id))

            # Update recurring expense last_processed_date if applicable
            if pending['recurring_expense_id']:
                cursor.execute("""
                    UPDATE recurring_expenses
                    SET last_processed_date = %s
                    WHERE expense_id = %s
                """, (pending['due_date'], pending['recurring_expense_id']))

            conn.commit()
            return True, "Transaction approved and processed."

        except Exception as e:
            conn.rollback()
            return False, f"Error: {e}"
        finally:
            cursor.close()
            conn.close()

    def reject_pending_transaction(self, user_id, pending_id):
        """
        Reject/dismiss a pending transaction without processing it.

        Args:
            user_id (int): The user ID
            pending_id (int): The pending transaction ID

        Returns:
            tuple: (success bool, message str)
        """
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("""
                UPDATE pending_transactions
                SET status = 'REJECTED', resolved_at = NOW()
                WHERE pending_id = %s AND user_id = %s AND status = 'PENDING'
            """, (pending_id, user_id))

            if cursor.rowcount == 0:
                return False, "Pending transaction not found."

            conn.commit()
            return True, "Transaction rejected."
        except Exception as e:
            conn.rollback()
            return False, f"Error: {e}"
        finally:
            cursor.close()
            conn.close()

    # =============================================================================
    # LOAN PAYMENT METHODS (Principal vs Interest Split)
    # =============================================================================

    def make_loan_payment(self, user_id, loan_id, interest_amount, principal_amount, payment_account_id,
                          payment_date=None, escrow_amount=None, other_amounts=None):
        """
        Make a loan/credit card payment with manual interest/principal breakdown.

        Args:
            user_id (int): The user ID
            loan_id (int): The loan's ACCOUNT ID from the 'accounts' table (LOAN or CREDIT_CARD type)
            interest_amount (Decimal): Interest portion
            principal_amount (Decimal): Principal portion
            payment_account_id (int): Account to pay from
            payment_date (date, optional): Payment date (defaults to user's current date)
            escrow_amount (Decimal, optional): Escrow amount (for mortgages)
            other_amounts (list, optional): List of dicts with 'label' and 'amount' for fees, etc.

        Returns:
            tuple: (success bool, message str)
        """
        interest_amount = Decimal(interest_amount) if interest_amount else Decimal('0')
        principal_amount = Decimal(principal_amount) if principal_amount else Decimal('0')
        escrow_amount = Decimal(escrow_amount) if escrow_amount else Decimal('0')

        conn, cursor = self._get_db_connection()
        try:
            if payment_date is None:
                payment_date = self._get_user_current_date(cursor, user_id)

            # Get loan/credit card account details
            cursor.execute("""
                SELECT account_id, name, balance, type
                FROM accounts
                WHERE account_id = %s AND user_id = %s AND type IN ('LOAN', 'CREDIT_CARD')
            """, (loan_id, user_id))

            loan_account = cursor.fetchone()
            if not loan_account:
                return False, "Loan or credit card account not found."

            # Get payment account name
            cursor.execute("SELECT name FROM accounts WHERE account_id = %s", (payment_account_id,))
            payment_acct = cursor.fetchone()
            if not payment_acct:
                return False, "Payment account not found."

            # Generate UUID for transaction
            from uuid import uuid4
            txn_uuid = str(uuid4())

            # Get Interest Expense category (create if doesn't exist)
            cursor.execute("""
                SELECT category_id FROM expense_categories
                WHERE user_id = %s AND name = 'Interest Expense'
            """, (user_id,))
            interest_cat = cursor.fetchone()
            if not interest_cat:
                cursor.execute("""
                    INSERT INTO expense_categories (user_id, name, color, is_default, is_monthly)
                    VALUES (%s, 'Interest Expense', '#ef4444', FALSE, TRUE)
                """, (user_id,))
                interest_category_id = cursor.lastrowid
            else:
                interest_category_id = interest_cat['category_id']

            # Calculate total payment
            total_payment = interest_amount + principal_amount + escrow_amount
            if other_amounts:
                for item in other_amounts:
                    total_payment += Decimal(item['amount'])

            # Create ledger entries
            # 1. DR Interest Expense (categorized for charts)
            if interest_amount > 0:
                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (%s, %s, %s, 'Expenses', %s, %s, 0, %s)
                """, (user_id, txn_uuid, payment_date, f"{loan_account['name']} - Interest",
                      interest_amount, interest_category_id))

            # 2. DR Loan/Credit Card (reduces liability) - principal only
            if principal_amount > 0:
                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (%s, %s, %s, %s, 'Payment - Principal', %s, 0, NULL)
                """, (user_id, txn_uuid, payment_date, loan_account['name'], principal_amount))

            # 3. Handle escrow as categorized expense
            if escrow_amount > 0:
                # Get or create Escrow/Housing category
                cursor.execute("""
                    SELECT category_id FROM expense_categories
                    WHERE user_id = %s AND name = 'Escrow/Housing'
                """, (user_id,))
                escrow_cat = cursor.fetchone()
                if not escrow_cat:
                    cursor.execute("""
                        INSERT INTO expense_categories (user_id, name, color, is_default, is_monthly)
                        VALUES (%s, 'Escrow/Housing', '#3b82f6', FALSE, TRUE)
                    """, (user_id,))
                    escrow_category_id = cursor.lastrowid
                else:
                    escrow_category_id = escrow_cat['category_id']

                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (%s, %s, %s, 'Expenses', %s, %s, 0, %s)
                """, (user_id, txn_uuid, payment_date, f"{loan_account['name']} - Escrow",
                      escrow_amount, escrow_category_id))

            # 4. Handle other amounts (fees, cash advance interest, etc.) as categorized expenses
            if other_amounts:
                # Get or create Fees category
                cursor.execute("""
                    SELECT category_id FROM expense_categories
                    WHERE user_id = %s AND name = 'Fees & Charges'
                """, (user_id,))
                fees_cat = cursor.fetchone()
                if not fees_cat:
                    cursor.execute("""
                        INSERT INTO expense_categories (user_id, name, color, is_default, is_monthly)
                        VALUES (%s, 'Fees & Charges', '#f59e0b', FALSE, TRUE)
                    """, (user_id,))
                    fees_category_id = cursor.lastrowid
                else:
                    fees_category_id = fees_cat['category_id']

                for item in other_amounts:
                    amount = Decimal(item['amount'])
                    if amount > 0:
                        cursor.execute("""
                            INSERT INTO financial_ledger
                            (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                            VALUES (%s, %s, %s, 'Expenses', %s, %s, 0, %s)
                        """, (user_id, txn_uuid, payment_date, f"{loan_account['name']} - {item['label']}",
                              amount, fees_category_id))

            # 5. CR Payment Account (total cash out)
            cursor.execute("""
                INSERT INTO financial_ledger
                (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                VALUES (%s, %s, %s, %s, %s, 0, %s, NULL)
            """, (user_id, txn_uuid, payment_date, payment_acct['name'],
                  f"{loan_account['name']} Payment", total_payment))

            # Update account balances
            # Principal reduces the loan/credit card balance (increases it since it's negative)
            if principal_amount > 0:
                cursor.execute("UPDATE accounts SET balance = balance + %s WHERE account_id = %s",
                              (principal_amount, loan_id))

            # Total payment reduces cash account
            cursor.execute("UPDATE accounts SET balance = balance - %s WHERE account_id = %s",
                          (total_payment, payment_account_id))

            # Fetch new loan balance
            cursor.execute("SELECT balance FROM accounts WHERE account_id = %s", (loan_id,))
            new_balance = abs(cursor.fetchone()['balance'])

            conn.commit()

            # Build success message
            msg_parts = []
            if principal_amount > 0:
                msg_parts.append(f"${principal_amount:,.2f} principal")
            if interest_amount > 0:
                msg_parts.append(f"${interest_amount:,.2f} interest")
            if escrow_amount > 0:
                msg_parts.append(f"${escrow_amount:,.2f} escrow")
            if other_amounts:
                for item in other_amounts:
                    if Decimal(item['amount']) > 0:
                        msg_parts.append(f"${Decimal(item['amount']):,.2f} {item['label']}")

            msg = f"Payment processed: {', '.join(msg_parts)}. New balance: ${new_balance:,.2f}"
            return True, msg

        except Exception as e:
            conn.rollback()
            print(f"ERROR in make_loan_payment: {e}")
            import traceback
            traceback.print_exc()
            return False, f"An unexpected error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def get_loan_payment_history(self, user_id, loan_id):
        """
        Get payment history for a specific loan.

        Args:
            user_id (int): The user ID
            loan_id (int): The loan ID

        Returns:
            list: List of payment records
        """
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("""
                SELECT payment_date, total_payment, principal_amount,
                       interest_amount, remaining_balance
                FROM loan_payments
                WHERE loan_id = %s AND user_id = %s
                ORDER BY payment_date DESC
            """, (loan_id, user_id))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    # =============================================================================
    # CREDIT CARD INTEREST METHODS
    # =============================================================================

    def calculate_credit_card_interest(self, user_id, card_account_id):
        """
        Calculate pending credit card interest (creates pending transaction for approval).

        Only calculates interest if:
        - Account type is CREDIT_CARD
        - Balance is negative (carrying debt)
        - Last interest date was over 30 days ago (or never)

        Args:
            user_id (int): The user ID
            card_account_id (int): The credit card account ID

        Returns:
            tuple: (success bool, message str)
        """
        conn, cursor = self._get_db_connection()
        try:
            # Get user's current date
            current_date = self._get_user_current_date(cursor, user_id)

            cursor.execute("""
                SELECT * FROM accounts
                WHERE account_id = %s AND user_id = %s AND type = 'CREDIT_CARD'
            """, (card_account_id, user_id))

            card = cursor.fetchone()
            if not card:
                return False, "Credit card account not found."

            # Check if interest is due
            if card['last_interest_date']:
                days_since = (current_date - card['last_interest_date']).days
                if days_since < 30:
                    return False, f"Interest not yet due. Last charged {days_since} days ago."

            # Only charge if carrying a balance
            if card['balance'] >= 0:
                return True, "No balance, no interest charged."

            # Calculate interest
            monthly_rate = Decimal(card['interest_rate']) / Decimal(100) / Decimal(12)
            balance_owed = abs(card['balance'])
            interest = balance_owed * monthly_rate
            interest = interest.quantize(Decimal('0.01'))

            # Create pending transaction for approval
            cursor.execute("""
                INSERT INTO pending_transactions
                (user_id, recurring_expense_id, description, estimated_amount,
                 due_date, payment_account_id, category_id, status, transaction_type, related_account_id)
                VALUES (%s, NULL, %s, %s, CURDATE(), %s, NULL, 'PENDING', 'INTEREST', %s)
            """, (
                user_id,
                f"Interest Charge - {card['name']}",
                interest,
                card_account_id,  # payment_account_id (the card itself)
                card_account_id   # related_account_id (for reference)
            ))

            conn.commit()
            return True, f"Interest pending approval: ${interest:,.2f} (Balance: ${balance_owed:,.2f} @ {card['interest_rate']:.2f}% APR)"

        except Exception as e:
            conn.rollback()
            return False, f"Error: {e}"
        finally:
            cursor.close()
            conn.close()

    # =============================================================================
    # TIME SIMULATION METHODS
    # =============================================================================

    def advance_time(self, user_id, days_to_advance=1):
        import calendar
        conn, cursor = self._get_db_connection()
        try:
            simulation_start_date = self._get_user_current_date(cursor, user_id)
            processing_log = []

            # Fetch recurring expenses and income ONCE before the loop
            cursor.execute("SELECT * FROM recurring_expenses WHERE user_id = %s", (user_id,))
            recurring_expenses = cursor.fetchall()

            cursor.execute("SELECT * FROM recurring_income WHERE user_id = %s", (user_id,))
            recurring_income = cursor.fetchall()

            for i in range(days_to_advance):
                current_day = simulation_start_date + datetime.timedelta(days=i + 1)
                days_in_month = calendar.monthrange(current_day.year, current_day.month)[1]

                for expense in recurring_expenses:
                    # Handle bills due on days that don't exist in current month (e.g., day 31 in Feb)
                    # Process on last day of month if due day is greater than days in month
                    effective_due_day = min(expense['due_day_of_month'], days_in_month)

                    if current_day.day == effective_due_day:
                        is_due_for_payment = False
                        last_processed = expense.get('last_processed_date') # Use .get() for safety

                        # Ensure last_processed is a date object (not datetime)
                        if last_processed and isinstance(last_processed, datetime.datetime):
                            last_processed = last_processed.date()

                        if not last_processed:
                            # If it's never been paid, it's due today.
                            is_due_for_payment = True
                        elif (current_day.year, current_day.month) > (last_processed.year, last_processed.month):
                            # If today is in a later month than the last payment, it's due.
                            is_due_for_payment = True

                        if is_due_for_payment:
                            # Check if this is a variable expense
                            if expense.get('is_variable'):
                                # CREATE PENDING TRANSACTION instead of auto-paying
                                cursor.execute("""
                                    INSERT INTO pending_transactions
                                    (user_id, recurring_expense_id, description, estimated_amount,
                                     due_date, payment_account_id, category_id, status, transaction_type)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING', 'EXPENSE')
                                """, (
                                    user_id,
                                    expense['expense_id'],
                                    expense['description'],
                                    expense.get('estimated_amount') or expense['amount'],
                                    current_day,
                                    expense['payment_account_id'],
                                    expense.get('category_id')
                                ))

                                # Update last_processed_date so it doesn't create duplicate pending transactions
                                cursor.execute(
                                    "UPDATE recurring_expenses SET last_processed_date = %s WHERE expense_id = %s",
                                    (current_day, expense['expense_id'])
                                )
                                expense['last_processed_date'] = current_day
                                processing_log.append(f"On {current_day.strftime('%Y-%m-%d')}: {expense['description']} requires approval (variable expense)")
                            else:
                                # AUTO-PAY as before (existing code)
                                success, message = self.log_expense(
                                    user_id,
                                    expense['payment_account_id'],
                                    expense['description'],
                                    expense['amount'],
                                    transaction_date=current_day,
                                    category_id=expense.get('category_id'),  # Pass category from recurring expense
                                    cursor=cursor # Pass the existing cursor
                                )

                                if success:
                                    cursor.execute(
                                        "UPDATE recurring_expenses SET last_processed_date = %s WHERE expense_id = %s",
                                        (current_day, expense['expense_id'])
                                    )
                                    # Update the in-memory record to prevent re-payment in the same run
                                    expense['last_processed_date'] = current_day
                                    processing_log.append(f"On {current_day.strftime('%Y-%m-%d')}: Paid {expense['description']} (${expense['amount']}).")
                                else:
                                    processing_log.append(f"On {current_day.strftime('%Y-%m-%d')}: FAILED to pay {expense['description']} - {message}")

                # Process recurring income
                for income in recurring_income:
                    # Handle income due on days that don't exist in current month
                    income_effective_due_day = min(income['deposit_day_of_month'], days_in_month)

                    if current_day.day == income_effective_due_day:
                        is_due_for_deposit = False
                        last_processed = income.get('last_processed_date')

                        # Ensure last_processed is a date object (not datetime)
                        if last_processed and isinstance(last_processed, datetime.datetime):
                            last_processed = last_processed.date()

                        if not last_processed:
                            is_due_for_deposit = True
                        elif (current_day.year, current_day.month) > (last_processed.year, last_processed.month):
                            is_due_for_deposit = True

                        if is_due_for_deposit:
                            # Check if this is a variable income
                            if income.get('is_variable'):
                                # CREATE PENDING TRANSACTION instead of auto-depositing
                                cursor.execute("""
                                    INSERT INTO pending_transactions
                                    (user_id, recurring_income_id, description, estimated_amount,
                                     due_date, payment_account_id, status, transaction_type)
                                    VALUES (%s, %s, %s, %s, %s, %s, 'PENDING', 'INCOME')
                                """, (
                                    user_id,
                                    income['income_id'],
                                    income['description'],
                                    income.get('estimated_amount') or income['amount'],
                                    current_day,
                                    income['deposit_account_id']
                                ))

                                # Update last_processed_date so it doesn't create duplicate pending transactions
                                cursor.execute(
                                    "UPDATE recurring_income SET last_processed_date = %s WHERE income_id = %s",
                                    (current_day, income['income_id'])
                                )
                                income['last_processed_date'] = current_day
                                processing_log.append(f"On {current_day.strftime('%Y-%m-%d')}: {income['description']} requires approval (variable income)")
                            else:
                                # AUTO-DEPOSIT as before
                                success, message = self.log_income(
                                    user_id,
                                    income['deposit_account_id'],
                                    income['description'],
                                    income['amount'],
                                    transaction_date=current_day,
                                    cursor=cursor
                                )

                                if success:
                                    cursor.execute(
                                        "UPDATE recurring_income SET last_processed_date = %s WHERE income_id = %s",
                                        (current_day, income['income_id'])
                                    )
                                    income['last_processed_date'] = current_day
                                    processing_log.append(f"On {current_day.strftime('%Y-%m-%d')}: Deposited {income['description']} (${income['amount']}).")
                                else:
                                    processing_log.append(f"On {current_day.strftime('%Y-%m-%d')}: FAILED to deposit {income['description']} - {message}")

            final_date = simulation_start_date + datetime.timedelta(days=days_to_advance)
            # Check if we need to insert a time marker using the existing cursor
            cursor.execute(
                "SELECT transaction_date FROM financial_ledger WHERE user_id = %s ORDER BY transaction_date DESC, entry_id DESC LIMIT 1",
                (user_id,)
            )
            last_entry = cursor.fetchone()

            # Convert last transaction_date to date for comparison (it's a datetime in DB)
            last_transaction_date = None
            if last_entry and last_entry['transaction_date']:
                if isinstance(last_entry['transaction_date'], datetime.datetime):
                    last_transaction_date = last_entry['transaction_date'].date()
                else:
                    last_transaction_date = last_entry['transaction_date']

            if not last_transaction_date or last_transaction_date < final_date:
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

    def auto_advance_time(self, user_id):
        """
        Automatically advance time to today's date if the user's last transaction
        is in the past. This is called on login to keep the simulation current.

        Args:
            user_id (int): The ID of the user

        Returns:
            dict: Result with log messages from the advance
        """
        conn, cursor = self._get_db_connection()
        try:
            # Get the user's current date (last transaction date)
            current_date = self._get_user_current_date(cursor, user_id)
            cursor.close()
            conn.close()

            # Get today's actual date
            today = datetime.datetime.now().date()

            # Calculate days difference
            if current_date < today:
                days_to_advance = (today - current_date).days
                print(f"[AUTO-ADVANCE] User {user_id}: Advancing {days_to_advance} day(s) from {current_date} to {today}")
                return self.advance_time(user_id, days_to_advance)
            else:
                print(f"[AUTO-ADVANCE] User {user_id}: Already at current date ({current_date})")
                return {'log': [f"Already at current date: {current_date}"]}

        except Exception as e:
            print(f"[AUTO-ADVANCE ERROR] User {user_id}: {e}")
            return {'log': [f"Auto-advance failed: {e}"]}

    # =============================================================================
    # FINANCIAL STATEMENTS
    # =============================================================================

    def get_income_statement(self, user_id, start_date, end_date):
        """
        Generate Income Statement (Profit & Loss) for a date range.

        Returns:
            dict: {
                'revenue': {'total': Decimal, 'details': []},
                'expenses': {'total': Decimal, 'by_category': []},
                'net_income': Decimal
            }
        """
        conn, cursor = self._get_db_connection()
        try:
            # Get all revenue (Income account credits)
            cursor.execute("""
                SELECT description, SUM(credit) as amount
                FROM financial_ledger
                WHERE user_id = %s
                  AND account = 'Income'
                  AND transaction_date BETWEEN %s AND %s
                GROUP BY description
                ORDER BY amount DESC
            """, (user_id, start_date, end_date))
            revenue_details = cursor.fetchall()
            total_revenue = sum(r['amount'] for r in revenue_details)

            # Get all expenses by category (only include Expenses account or debits from CHECKING/SAVINGS/CASH/CREDIT accounts)
            cursor.execute("""
                SELECT
                    COALESCE(ec.name, 'Uncategorized') as category,
                    SUM(fl.debit) as amount
                FROM financial_ledger fl
                LEFT JOIN expense_categories ec ON fl.category_id = ec.category_id
                LEFT JOIN accounts a ON fl.account = a.name AND fl.user_id = a.user_id
                WHERE fl.user_id = %s
                  AND fl.debit > 0
                  AND fl.transaction_date BETWEEN %s AND %s
                  AND (fl.account = 'Expenses' OR a.type IN ('CHECKING', 'SAVINGS', 'CASH', 'CREDIT'))
                GROUP BY ec.name
                ORDER BY amount DESC
            """, (user_id, start_date, end_date))
            expense_details = cursor.fetchall()
            total_expenses = sum(e['amount'] for e in expense_details)

            return {
                'revenue': {
                    'total': total_revenue,
                    'details': revenue_details
                },
                'expenses': {
                    'total': total_expenses,
                    'by_category': expense_details
                },
                'net_income': total_revenue - total_expenses
            }
        finally:
            cursor.close()
            conn.close()

    def get_balance_sheet(self, user_id, as_of_date=None):
        """
        Generate Balance Sheet as of a specific date.

        Returns:
            dict: {
                'assets': {'total': Decimal, 'accounts': []},
                'liabilities': {'total': Decimal, 'accounts': []},
                'equity': Decimal
            }
        """
        conn, cursor = self._get_db_connection()
        try:
            if not as_of_date:
                as_of_date = self._get_user_current_date(cursor, user_id)

            # Get all accounts with balances as of date
            cursor.execute("""
                SELECT a.name, a.type, a.balance
                FROM accounts a
                WHERE a.user_id = %s
                ORDER BY a.type, a.name
            """, (user_id,))
            accounts = cursor.fetchall()

            # Calculate balances as of date by replaying transactions
            account_balances = {}
            for acc in accounts:
                cursor.execute("""
                    SELECT
                        COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as balance
                    FROM financial_ledger
                    WHERE user_id = %s
                      AND account = %s
                      AND transaction_date <= %s
                """, (user_id, acc['name'], as_of_date))
                result = cursor.fetchone()
                account_balances[acc['name']] = {
                    'type': acc['type'],
                    'balance': result['balance'] if result else Decimal(0)
                }

            # Categorize as assets/liabilities
            assets = []
            liabilities = []

            for name, data in account_balances.items():
                if data['type'] in ['CHECKING', 'SAVINGS', 'INVESTMENT', 'CASH', 'FIXED_ASSET']:
                    assets.append({'name': name, 'balance': data['balance']})
                elif data['type'] in ['CREDIT_CARD', 'LOAN']:
                    liabilities.append({'name': name, 'balance': abs(data['balance'])})

            total_assets = sum(a['balance'] for a in assets)
            total_liabilities = sum(l['balance'] for l in liabilities)

            return {
                'assets': {
                    'total': total_assets,
                    'accounts': assets
                },
                'liabilities': {
                    'total': total_liabilities,
                    'accounts': liabilities
                },
                'equity': total_assets - total_liabilities
            }
        finally:
            cursor.close()
            conn.close()

    def get_cash_flow_statement(self, user_id, start_date, end_date):
        """
        Generate Cash Flow Statement for a date range.

        Returns:
            dict: {
                'operating': Decimal,
                'investing': Decimal,
                'financing': Decimal,
                'net_change': Decimal
            }
        """
        conn, cursor = self._get_db_connection()
        try:
            # Operating Activities: Income and day-to-day Expenses only
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN fl.account = 'Income' THEN fl.credit ELSE 0 END) as income,
                    SUM(CASE WHEN fl.account = 'Expenses' OR a.type IN ('CHECKING', 'SAVINGS', 'CASH', 'CREDIT') THEN fl.debit ELSE 0 END) as expenses
                FROM financial_ledger fl
                LEFT JOIN accounts a ON fl.account = a.name AND fl.user_id = a.user_id
                WHERE fl.user_id = %s
                  AND fl.transaction_date BETWEEN %s AND %s
            """, (user_id, start_date, end_date))
            operating = cursor.fetchone()
            operating_cash = (operating['income'] or 0) - (operating['expenses'] or 0)

            # Investing Activities: Fixed asset purchases and investment account changes
            cursor.execute("""
                SELECT
                    SUM(credit) - SUM(debit) as investing_flow
                FROM financial_ledger fl
                JOIN accounts a ON fl.account = a.name AND fl.user_id = a.user_id
                WHERE fl.user_id = %s
                  AND a.type IN ('INVESTMENT', 'FIXED_ASSET')
                  AND fl.transaction_date BETWEEN %s AND %s
            """, (user_id, start_date, end_date))
            investing = cursor.fetchone()
            investing_cash = investing['investing_flow'] or 0

            # Financing Activities: Loan payments, credit card changes
            cursor.execute("""
                SELECT
                    SUM(debit) - SUM(credit) as financing_flow
                FROM financial_ledger fl
                JOIN accounts a ON fl.account = a.name AND fl.user_id = a.user_id
                WHERE fl.user_id = %s
                  AND a.type IN ('LOAN', 'CREDIT_CARD')
                  AND fl.transaction_date BETWEEN %s AND %s
            """, (user_id, start_date, end_date))
            financing = cursor.fetchone()
            financing_cash = financing['financing_flow'] or 0

            return {
                'operating': operating_cash,
                'investing': -investing_cash,  # Negative because investment is cash outflow
                'financing': financing_cash,
                'net_change': operating_cash - investing_cash + financing_cash
            }
        finally:
            cursor.close()
            conn.close()

    def get_dashboard_data(self, user_id, days=30):
        """Get dashboard summary data including stats and chart data."""
        conn, cursor = self._get_db_connection()
        try:
            current_date = self._get_user_current_date(cursor, user_id)
            start_date = current_date - datetime.timedelta(days=days)

            # Get total income and expenses for the period
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN account = 'Income' THEN credit ELSE 0 END) as total_income,
                    SUM(CASE WHEN account = 'Expenses' THEN debit ELSE 0 END) as total_expenses
                FROM financial_ledger
                WHERE user_id = %s AND transaction_date BETWEEN %s AND %s
            """, (user_id, start_date, current_date))
            totals = cursor.fetchone()

            # Get spending by category
            cursor.execute("""
                SELECT c.name, c.color, SUM(l.debit) as amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = %s
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN %s AND %s
                    AND l.category_id IS NOT NULL
                GROUP BY c.category_id, c.name, c.color
                ORDER BY amount DESC
            """, (user_id, start_date, current_date))
            spending_by_category = cursor.fetchall()

            # Get net worth over time (daily snapshots)
            cursor.execute("""
                SELECT DATE(transaction_date) as date,
                    SUM(CASE WHEN a.type IN ('CHECKING', 'SAVINGS', 'CASH') THEN debit - credit ELSE 0 END) as daily_change
                FROM financial_ledger l
                JOIN accounts a ON l.account = a.name AND l.user_id = a.user_id
                WHERE l.user_id = %s AND transaction_date BETWEEN %s AND %s
                GROUP BY DATE(transaction_date)
                ORDER BY date
            """, (user_id, start_date, current_date))
            daily_changes = cursor.fetchall()

            # Calculate starting balance at the beginning of the period
            cursor.execute("""
                SELECT SUM(CASE WHEN a.type IN ('CHECKING', 'SAVINGS', 'CASH') THEN debit - credit ELSE 0 END) as balance_before_period
                FROM financial_ledger l
                JOIN accounts a ON l.account = a.name AND l.user_id = a.user_id
                WHERE l.user_id = %s AND transaction_date < %s
            """, (user_id, start_date))
            result = cursor.fetchone()
            starting_balance = float(result['balance_before_period'] or 0) if result else 0.0

            net_worth_trend = []
            cumulative = starting_balance
            for row in daily_changes:
                cumulative += float(row['daily_change'] or 0)
                net_worth_trend.append({
                    'date': row['date'].strftime('%Y-%m-%d'),
                    'net_worth': float(cumulative)
                })

            # Calculate savings rate
            total_income = float(totals['total_income'] or 0)
            total_expenses = float(totals['total_expenses'] or 0)
            savings_rate = ((total_income - total_expenses) / total_income * 100) if total_income > 0 else 0

            # Get monthly income vs expenses for bar chart
            cursor.execute("""
                SELECT
                    DATE_FORMAT(transaction_date, '%%Y-%%m') as month,
                    SUM(CASE WHEN account = 'Income' THEN credit ELSE 0 END) as income,
                    SUM(CASE WHEN account = 'Expenses' THEN debit ELSE 0 END) as expenses
                FROM financial_ledger
                WHERE user_id = %s AND transaction_date BETWEEN %s AND %s
                GROUP BY DATE_FORMAT(transaction_date, '%%Y-%%m')
                ORDER BY month
            """, (user_id, start_date, current_date))
            monthly_data = cursor.fetchall()
            income_vs_expenses = [
                {
                    'month': row['month'],
                    'income': float(row['income'] or 0),
                    'expenses': float(row['expenses'] or 0)
                } for row in monthly_data
            ]

            # Get weekly income vs expenses for dashboard line chart
            cursor.execute("""
                SELECT
                    MIN(transaction_date) as week_start,
                    YEARWEEK(transaction_date, 1) as year_week,
                    SUM(CASE WHEN account = 'Income' THEN credit ELSE 0 END) as income,
                    SUM(CASE WHEN account = 'Expenses' THEN debit ELSE 0 END) as expenses
                FROM financial_ledger
                WHERE user_id = %s AND transaction_date BETWEEN %s AND %s
                GROUP BY YEARWEEK(transaction_date, 1)
                ORDER BY year_week
            """, (user_id, start_date, current_date))
            weekly_data = cursor.fetchall()

            # Format weekly data
            weekly_income_expenses = []
            for row in weekly_data:
                weekly_income_expenses.append({
                    'week_start': row['week_start'].strftime('%Y-%m-%d') if row['week_start'] else None,
                    'income': float(row['income'] or 0),
                    'expenses': float(row['expenses'] or 0)
                })

            # Get weekly expenses by category - monthly categories show as weekly average
            cursor.execute("""
                SELECT
                    MIN(l.transaction_date) as week_start,
                    YEARWEEK(l.transaction_date, 1) as year_week,
                    c.name as category,
                    c.color,
                    c.is_monthly,
                    SUM(l.debit) as amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = %s
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN %s AND %s
                    AND l.category_id IS NOT NULL
                GROUP BY YEARWEEK(l.transaction_date, 1), c.category_id, c.name, c.color, c.is_monthly
                ORDER BY year_week, amount DESC
            """, (user_id, start_date, current_date))
            weekly_expenses_raw = cursor.fetchall()

            # Build a complete weekly series and smooth monthly categories across all weeks
            # 1) Collect all ISO weeks in range (week starts Monday)
            def week_monday(d):
                return d - datetime.timedelta(days=d.weekday())

            weeks = []
            w = week_monday(start_date)
            last = week_monday(current_date)
            while w <= last:
                weeks.append(w)
                w = w + datetime.timedelta(days=7)

            # 2) Map raw weekly sums for non-monthly categories
            non_monthly_map = {}
            for row in weekly_expenses_raw:
                if not row.get('is_monthly'):
                    raw_ws = row['week_start'].date() if hasattr(row['week_start'], 'date') else row['week_start']
                    # Normalize to Monday of that week for consistent x-axis
                    ws = week_monday(raw_ws)
                    key = (ws, row['category'])
                    non_monthly_map[key] = {
                        'week_start': ws.strftime('%Y-%m-%d'),
                        'category': row['category'],
                        'color': row['color'],
                        'is_monthly': False,
                        'amount': round(float(row['amount'] or 0), 2)
                    }

            # 3) Compute monthly totals for monthly categories
            cursor.execute("""
                SELECT
                    DATE_FORMAT(l.transaction_date, '%%Y-%%m') as ym,
                    c.name as category,
                    c.color,
                    SUM(l.debit) as monthly_amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = %s
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN %s AND %s
                    AND l.category_id IS NOT NULL
                    AND c.is_monthly = 1
                GROUP BY ym, c.category_id, c.name, c.color
            """, (user_id, start_date, current_date))
            monthly_totals = cursor.fetchall()

            monthly_map = {}  # (ym, category) -> {color, monthly_amount}
            monthly_categories = set()
            for row in monthly_totals:
                ym = row['ym']
                cat = row['category']
                monthly_map[(ym, cat)] = {
                    'color': row['color'],
                    'monthly_amount': float(row['monthly_amount'] or 0)
                }
                monthly_categories.add(cat)

            # 4) Fill every week for monthly categories with monthly_avg = monthly_amount / 4.33
            final_map = { **non_monthly_map }
            for ws in weeks:
                ym = ws.strftime('%Y-%m')
                for cat in monthly_categories:
                    info = monthly_map.get((ym, cat))
                    monthly_amount = info['monthly_amount'] if info else 0.0
                    weekly_amount = monthly_amount / 4.33 if monthly_amount > 0 else 0.0
                    key = (ws, cat)
                    final_map[key] = {
                        'week_start': ws.strftime('%Y-%m-%d'),
                        'category': cat,
                        'color': (info['color'] if info else '#6366f1'),
                        'is_monthly': True,
                        'amount': round(weekly_amount, 2)
                    }

            # 5) Emit flattened list sorted by week then category
            weekly_expenses_by_category = [v for _, v in sorted(final_map.items(), key=lambda x: (x[0][0], x[0][1]))]


            # Get expenses by category over time (stacked bar)
            cursor.execute("""
                SELECT
                    DATE_FORMAT(l.transaction_date, '%%Y-%%m') as month,
                    c.name as category,
                    c.color,
                    SUM(l.debit) as amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = %s
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN %s AND %s
                    AND l.category_id IS NOT NULL
                GROUP BY DATE_FORMAT(l.transaction_date, '%%Y-%%m'), c.category_id, c.name, c.color
                ORDER BY month, amount DESC
            """, (user_id, start_date, current_date))
            expenses_over_time = cursor.fetchall()

            # Get weekly expenses by category for trends chart
            cursor.execute("""
                SELECT
                    MIN(l.transaction_date) as week_start,
                    YEARWEEK(l.transaction_date, 1) as year_week,
                    c.name as category,
                    c.color,
                    SUM(l.debit) as amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = %s
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN %s AND %s
                    AND l.category_id IS NOT NULL
                GROUP BY YEARWEEK(l.transaction_date, 1), c.category_id, c.name, c.color
                ORDER BY year_week, amount DESC
            """, (user_id, start_date, current_date))
            weekly_expenses_raw = cursor.fetchall()

            # Format weekly expenses data
            weekly_expenses_by_category = []
            for row in weekly_expenses_raw:
                weekly_expenses_by_category.append({
                    'week_start': row['week_start'].strftime('%Y-%m-%d') if row['week_start'] else None,
                    'category': row['category'],
                    'color': row['color'],
                    'amount': float(row['amount'] or 0)
                })

            # Get assets vs liabilities over time (area chart)
            cursor.execute("""
                SELECT DATE(transaction_date) as date,
                    SUM(CASE WHEN a.type IN ('CHECKING', 'SAVINGS', 'CASH', 'INVESTMENT', 'FIXED_ASSET') THEN debit - credit ELSE 0 END) as asset_change,
                    SUM(CASE WHEN a.type IN ('LOAN', 'CREDIT_CARD') THEN credit - debit ELSE 0 END) as liability_change
                FROM financial_ledger l
                JOIN accounts a ON l.account = a.name AND l.user_id = a.user_id
                WHERE l.user_id = %s AND transaction_date BETWEEN %s AND %s
                GROUP BY DATE(transaction_date)
                ORDER BY date
            """, (user_id, start_date, current_date))
            daily_balance_changes = cursor.fetchall()

            # Calculate starting assets and liabilities
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN a.type IN ('CHECKING', 'SAVINGS', 'CASH', 'INVESTMENT', 'FIXED_ASSET') THEN debit - credit ELSE 0 END) as starting_assets,
                    SUM(CASE WHEN a.type IN ('LOAN', 'CREDIT_CARD') THEN credit - debit ELSE 0 END) as starting_liabilities
                FROM financial_ledger l
                JOIN accounts a ON l.account = a.name AND l.user_id = a.user_id
                WHERE l.user_id = %s AND transaction_date < %s
            """, (user_id, start_date))
            starting = cursor.fetchone()
            cumulative_assets = float(starting['starting_assets'] or 0) if starting else 0.0
            cumulative_liabilities = float(starting['starting_liabilities'] or 0) if starting else 0.0

            assets_vs_liabilities = []
            for row in daily_balance_changes:
                cumulative_assets += float(row['asset_change'] or 0)
                cumulative_liabilities += float(row['liability_change'] or 0)
                assets_vs_liabilities.append({
                    'date': row['date'].strftime('%Y-%m-%d'),
                    'assets': float(cumulative_assets),
                    'liabilities': float(cumulative_liabilities)
                })

            # Get top 5 expense categories (horizontal bar)
            cursor.execute("""
                SELECT c.name, c.color, SUM(l.debit) as amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = %s
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN %s AND %s
                    AND l.category_id IS NOT NULL
                GROUP BY c.category_id, c.name, c.color
                ORDER BY amount DESC
                LIMIT 5
            """, (user_id, start_date, current_date))
            top_categories = cursor.fetchall()

            return {
                'total_income': total_income,
                'total_expenses': total_expenses,
                'net_income': total_income - total_expenses,
                'savings_rate': round(savings_rate, 1),
                'spending_by_category': spending_by_category,
                'net_worth_trend': net_worth_trend,
                'income_vs_expenses': income_vs_expenses,
                'weekly_income_expenses': weekly_income_expenses,
                'expenses_over_time': expenses_over_time,
                'weekly_expenses_by_category': weekly_expenses_by_category,
                'assets_vs_liabilities': assets_vs_liabilities,
                'top_categories': top_categories,
                'period_days': days
            }
        finally:
            cursor.close()
            conn.close()