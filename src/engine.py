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
- **Stateless Architecture**: All state is stored in SQLite database
- **User Segregation**: Complete data isolation between users
- **Security First**: Password hashing, user validation on all operations
- **Audit Trail**: Immutable ledger with transaction UUIDs
- **BI-Ready**: Normalized schema for direct Power BI connection

Author: Matthew Jenkins
License: MIT
Related Project: Digital Harvest (Business Simulation with similar accounting principles)
"""

import os
import sqlite3
import datetime
import time
from decimal import Decimal
from pathlib import Path
import bcrypt

# --- DATABASE CONFIGURATION ---
# SQLite database path (portable, no server needed)
DB_PATH = Path(__file__).parent / "data" / "perfectbooks.db"

# Debug: Print database location on startup
print("=" * 60)
print("DATABASE CONFIGURATION:")
print(f"  Database: SQLite (portable)")
print(f"  Location: {DB_PATH}")
print(f"  Exists: {DB_PATH.exists()}")
print("=" * 60)


class BusinessSimulator:
    """
    Stateless personal finance engine for Perfect Books.

    This class provides all business logic for the application without maintaining
    state between method calls. All data is persisted in the SQLite database and
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

    # =============================================================================
    # SQLITE HELPER METHODS
    # =============================================================================

    @staticmethod
    def _to_money_str(value):
        """Convert Decimal or float to string for SQLite storage"""
        if value is None:
            return None
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
        return str(value)

    @staticmethod
    def _from_money_str(value):
        """Convert string from SQLite to Decimal for calculations"""
        if value is None or value == '':
            return Decimal('0.00')
        return Decimal(str(value))

    @staticmethod
    def _to_bool_int(value):
        """Convert Python boolean to SQLite integer (0/1)"""
        return 1 if value else 0

    @staticmethod
    def _from_bool_int(value):
        """Convert SQLite integer (0/1) to Python boolean"""
        return bool(value)

    @staticmethod
    def _to_datetime_str(dt):
        """Convert datetime object to SQLite TEXT format"""
        if dt is None:
            return None
        if isinstance(dt, datetime.datetime):
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(dt, datetime.date):
            return dt.strftime('%Y-%m-%d')
        return str(dt)

    @staticmethod
    def _from_datetime_str(value):
        """Convert SQLite TEXT to datetime object"""
        if value is None or value == '':
            return None
        if isinstance(value, str):
            # Try datetime format first
            try:
                return datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                # Try date-only format
                try:
                    return datetime.datetime.strptime(value, '%Y-%m-%d')
                except ValueError:
                    return None
        return value

    @staticmethod
    def _row_to_dict(row):
        """Convert sqlite3.Row to dictionary for JSON serialization"""
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def _rows_to_dicts(rows):
        """Convert list of sqlite3.Row objects to list of dicts"""
        return [dict(row) for row in rows]

    # =============================================================================
    # DATABASE CONNECTION
    # =============================================================================

    def _get_db_connection(self):
        """
        Establish a new database connection.

        Returns:
            tuple: (connection, cursor) - SQLite connection and cursor

        Note:
            Callers are responsible for closing the connection and cursor.
            SQLite connections use Row factory for dictionary-style access.
        """
        # Create data directory if it doesn't exist
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Connect to SQLite database
        conn = sqlite3.connect(str(DB_PATH))

        # Enable foreign key constraints (CRITICAL for data integrity)
        conn.execute("PRAGMA foreign_keys = ON;")

        # Use Row factory for dictionary-style access (like MySQL dictionary cursor)
        conn.row_factory = sqlite3.Row

        return conn, conn.cursor()

    def _get_user_current_date(self, cursor, user_id):
        # Get the current_date from users table (set by advance_time)
        cursor.execute(
            "SELECT current_date FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = self._row_to_dict(cursor.fetchone())
        if result and result['current_date']:
            # Return as-is (string format expected by callers)
            return result['current_date']
        # Fallback to today's date if not set
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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
            cursor.execute("SELECT user_id, username, password_hash FROM users WHERE username = ?", (username,))
            user_data = self._row_to_dict(cursor.fetchone())
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
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            if self._row_to_dict(cursor.fetchone()):
                return False, "Username already exists.", None

            password_bytes = password.encode('utf-8')
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password_bytes, salt)

            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash.decode('utf-8'))
            )
            new_user_id = cursor.lastrowid
            conn.commit()

            # Initialize default expense categories for the new user (separate connection)
            self.initialize_default_categories(new_user_id)

            return True, "User registered successfully.", new_user_id
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}", None
        finally:
            cursor.close()
            conn.close()

    def change_password(self, user_id, current_password, new_password):
        """
        Change a user's password after verifying their current password.

        Args:
            user_id (int): The user's ID
            current_password (str): Current plain-text password for verification
            new_password (str): New plain-text password (will be hashed)

        Returns:
            tuple: (success bool, message str)
                   - (True, "Password changed successfully.") on success
                   - (False, error_message) on failure

        Example:
            success, msg = sim.change_password(1, "oldpass", "newpass")
        """
        conn, cursor = self._get_db_connection()
        try:
            # Verify user exists and get current password hash
            cursor.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,))
            user_data = self._row_to_dict(cursor.fetchone())
            if not user_data:
                return False, "User not found."

            # Verify current password
            current_password_bytes = current_password.encode('utf-8')
            password_hash_bytes = user_data['password_hash'].encode('utf-8')

            if not bcrypt.checkpw(current_password_bytes, password_hash_bytes):
                return False, "Current password is incorrect."

            # Validate new password
            if len(new_password) < 3:
                return False, "New password must be at least 3 characters long."

            # Hash new password
            new_password_bytes = new_password.encode('utf-8')
            salt = bcrypt.gensalt()
            new_password_hash = bcrypt.hashpw(new_password_bytes, salt)

            # Update password
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE user_id = ?",
                (new_password_hash.decode('utf-8'), user_id)
            )
            conn.commit()
            return True, "Password changed successfully."

        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def check_user_has_accounts(self, user_id):
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT 1 FROM accounts WHERE user_id = ? LIMIT 1", (user_id,))
            return self._row_to_dict(cursor.fetchone()) is not None
        finally:
            cursor.close()
            conn.close()

    def initialize_default_categories(self, user_id):
        """Create default expense categories and parent groups for a new user."""
        conn, cursor = self._get_db_connection()
        try:
            # ===== STEP 1: Create parent category groups (shared across all users) =====
            parent_categories = [
                ('Earned Income', 'income', 1),
                ('Investment & Passive Income', 'income', 2),
                ('Essential Living', 'expense', 3),
                ('Transportation', 'expense', 4),
                ('Food & Lifestyle', 'expense', 5),
                ('Personal & Healthcare', 'expense', 6),
                ('Other', 'both', 7),
            ]

            parent_id_map = {}
            for name, cat_type, display_order in parent_categories:
                # Check if parent already exists
                cursor.execute("SELECT parent_id FROM parent_categories WHERE name = ?", (name,))
                existing = cursor.fetchone()
                if existing:
                    parent_id_map[name] = existing[0]
                else:
                    cursor.execute(
                        "INSERT INTO parent_categories (name, type, display_order) VALUES (?, ?, ?)",
                        (name, cat_type, display_order)
                    )
                    parent_id_map[name] = cursor.lastrowid

            # ===== STEP 2: Create user categories with parent assignments =====
            # Format: (name, color, is_default, parent_name)
            default_categories = [
                # System default
                ('Uncategorized', '#6b7280', True, 'Other'),

                # Income categories
                ('W2 Job Income', '#10b981', False, 'Earned Income'),
                ('Freelance Income', '#059669', False, 'Earned Income'),
                ('Business Income', '#6ee7b7', False, 'Earned Income'),
                ('Investment Income', '#34d399', False, 'Investment & Passive Income'),
                ('Other Income', '#a7f3d0', False, 'Other'),

                # Expense categories
                ('Housing', '#8b5cf6', False, 'Essential Living'),
                ('Utilities', '#3b82f6', False, 'Essential Living'),
                ('Transportation', '#f59e0b', False, 'Transportation'),
                ('Food & Dining', '#ef4444', False, 'Food & Lifestyle'),
                ('Entertainment', '#ec4899', False, 'Food & Lifestyle'),
                ('Shopping', '#10b981', False, 'Food & Lifestyle'),
                ('Healthcare', '#14b8a6', False, 'Personal & Healthcare'),
                ('Personal', '#f97316', False, 'Personal & Healthcare'),
                ('Other Expenses', '#6366f1', False, 'Other'),
            ]

            for name, color, is_default, parent_name in default_categories:
                parent_id = parent_id_map.get(parent_name)
                cursor.execute(
                    "INSERT INTO expense_categories (user_id, name, color, is_default, parent_id) VALUES (?, ?, ?, ?, ?)",
                    (user_id, name, color, is_default, parent_id)
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
            total_cash = sum(self._from_money_str(acc['balance']) for acc in accounts if acc['type'] in ['CHECKING', 'SAVINGS', 'CASH'])
            current_date = self._get_user_current_date(cursor, user_id)
            summary = { 'cash': float(total_cash), 'date': current_date }
            return summary
        finally:
            cursor.close()
            conn.close()
    
    def get_accounts_list(self, user_id):
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT * FROM accounts WHERE user_id = ? AND type != 'EQUITY' ORDER BY name", (user_id,))
            accounts = self._rows_to_dicts(cursor.fetchall())

            # Calculate balance from ledger for each account
            for account in accounts:
                cursor.execute(
                    "SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as ledger_balance "
                    "FROM financial_ledger WHERE user_id = ? AND account = ?",
                    (user_id, account['name'])
                )
                ledger_balance = float(self._row_to_dict(cursor.fetchone())['ledger_balance'] or 0)
                account['balance'] = ledger_balance

            return accounts
        finally:
            cursor.close()
            conn.close()

    def get_ledger_entries(self, user_id, transaction_limit=20, transaction_offset=0, account_filter=None, start_date=None, end_date=None, show_reversals=True, search_query=None, category_id=None):
        """
        Get ledger entries for a user, optionally filtered to a specific account and/or date range.

        Args:
            user_id: The user ID
            transaction_limit: Maximum number of transactions to return
            transaction_offset: Number of transactions to skip (for pagination)
            account_filter: Optional account name to filter by. If provided, only shows
                          transactions that involve this account.
            start_date: Optional start date (YYYY-MM-DD format) for date range filtering
            end_date: Optional end date (YYYY-MM-DD format) for date range filtering
            show_reversals: Whether to include reversal transactions (default True)
            search_query: Optional search string to filter by description or account
            category_id: Optional category ID to filter by

        Returns:
            List of ledger entries with running balance if filtered to one account
        """
        conn, cursor = self._get_db_connection()
        try:
            # Build date filter conditions
            date_conditions = []
            date_params = []
            if start_date:
                date_conditions.append("transaction_date >= ?")
                date_params.append(start_date)
            if end_date:
                date_conditions.append("transaction_date <= ?")
                date_params.append(end_date)
            date_filter = " AND " + " AND ".join(date_conditions) if date_conditions else ""

            # Build reversal filter condition
            reversal_filter = "" if show_reversals else " AND is_reversal = 0"

            # Build search filter condition
            search_filter = ""
            search_params = []
            if search_query and search_query.strip():
                search_term = f"%{search_query.strip()}%"
                search_filter = " AND (description LIKE ? OR account LIKE ? OR CAST(debit AS TEXT) LIKE ? OR CAST(credit AS TEXT) LIKE ?)"
                search_params = [search_term, search_term, search_term, search_term]

            # Build category filter condition
            category_filter = ""
            category_params = []
            if category_id is not None:
                category_filter = " AND category_id = ?"
                category_params = [category_id]

            if account_filter:
                # When filtering by account, get all entries for transactions involving that account
                query = (
                    "SELECT l.entry_id, l.transaction_uuid, l.transaction_date, l.description, l.account, l.debit, l.credit, "
                    "l.category_id, c.name as category_name, c.color as category_color, l.is_business "
                    "FROM financial_ledger l "
                    "LEFT JOIN expense_categories c ON l.category_id = c.category_id "
                    "JOIN ( "
                    "    SELECT DISTINCT transaction_uuid, MAX(transaction_date) as max_date, MAX(entry_id) as max_id "
                    "    FROM financial_ledger "
                    "    WHERE user_id = ? AND description != 'Time Advanced' AND description != 'Initial Balance' " + date_filter + reversal_filter + search_filter + category_filter +
                    "      AND transaction_uuid IN ( "
                    "        SELECT transaction_uuid FROM financial_ledger WHERE user_id = ? AND account = ? " + date_filter + reversal_filter +
                    "      ) "
                    "    GROUP BY transaction_uuid "
                    "    ORDER BY max_date DESC, max_id DESC "
                    "    LIMIT ? OFFSET ? "
                    ") AS recent_t "
                    "ON l.transaction_uuid = recent_t.transaction_uuid "
                    "WHERE l.user_id = ? ORDER BY l.transaction_date DESC, l.entry_id DESC"
                )
                params = [user_id] + date_params + search_params + category_params + [user_id, account_filter] + date_params + [transaction_limit, transaction_offset, user_id]
                cursor.execute(query, params)
            else:
                # Original query - no account filter
                query = (
                    "SELECT l.entry_id, l.transaction_uuid, l.transaction_date, l.description, l.account, l.debit, l.credit, "
                    "l.category_id, c.name as category_name, c.color as category_color, l.is_business "
                    "FROM financial_ledger l "
                    "LEFT JOIN expense_categories c ON l.category_id = c.category_id "
                    "JOIN ( "
                    "    SELECT transaction_uuid, MAX(transaction_date) as max_date, MAX(entry_id) as max_id "
                    "    FROM financial_ledger "
                    "    WHERE user_id = ? AND description != 'Time Advanced' AND description != 'Initial Balance' " + date_filter + reversal_filter + search_filter + category_filter +
                    "    GROUP BY transaction_uuid "
                    "    ORDER BY max_date DESC, max_id DESC "
                    "    LIMIT ? OFFSET ? "
                    ") AS recent_t "
                    "ON l.transaction_uuid = recent_t.transaction_uuid "
                    "WHERE l.user_id = ? ORDER BY l.transaction_date DESC, l.entry_id DESC"
                )
                params = [user_id] + date_params + search_params + category_params + [transaction_limit, transaction_offset, user_id]
                cursor.execute(query, params)

            entries = self._rows_to_dicts(cursor.fetchall())

            # If filtering by account, calculate running balance
            if account_filter and entries:
                # Sort entries by date DESCENDING (newest first)
                sorted_entries = sorted(entries, key=lambda x: (x['transaction_date'], x['entry_id']), reverse=True)

                # Get the most recent transaction date shown
                most_recent_date = sorted_entries[0]['transaction_date']
                most_recent_entry_id = sorted_entries[0]['entry_id']

                # Calculate balance UP TO the most recent transaction shown (not all time)
                # This ensures the running balance matches what's visible in the ledger
                # Exclude reversals from balance calculation if show_reversals is False
                balance_reversal_filter = "" if show_reversals else " AND is_reversal = 0"
                cursor.execute(
                    "SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as balance "
                    "FROM financial_ledger "
                    "WHERE user_id = ? AND account = ? " + balance_reversal_filter +
                    " AND (transaction_date < ? OR (transaction_date = ? AND entry_id <= ?))",
                    (user_id, account_filter, most_recent_date, most_recent_date, most_recent_entry_id)
                )
                current_balance = float(self._row_to_dict(cursor.fetchone())['balance'] or 0)

                running_balance = current_balance
                balance_map = {}  # Map entry_id to running balance

                # Group entries by transaction to process them together
                from collections import defaultdict
                transactions = defaultdict(list)
                for entry in sorted_entries:
                    transactions[entry['transaction_uuid']].append(entry)

                # Process transactions in reverse chronological order (newest to oldest)
                for tx_uuid in sorted(transactions.keys(), key=lambda uuid: max(e['transaction_date'] for e in transactions[uuid]), reverse=True):
                    tx_entries = transactions[tx_uuid]

                    # Assign the CURRENT running balance to all entries in this transaction FIRST
                    # (so all sides of the transaction show the same balance - the balance AFTER this transaction)
                    for entry in tx_entries:
                        balance_map[entry['entry_id']] = running_balance

                    # Then update the running balance by reversing this transaction
                    # (subtracting debits, adding back credits to go backwards in time)
                    filtered_entry_found = False
                    for entry in tx_entries:
                        if entry['account'] == account_filter:
                            filtered_entry_found = True
                            debit_val = float(entry['debit']) if entry['debit'] else 0
                            credit_val = float(entry['credit']) if entry['credit'] else 0
                            if debit_val > 0:
                                running_balance -= debit_val  # Reverse: subtract debits
                            if credit_val > 0:
                                running_balance += credit_val  # Reverse: add back credits
                            break

                    # Safety check: if no entry matched the filter, don't update running balance
                    # This shouldn't happen based on the query, but prevents calculation errors
                    if not filtered_entry_found:
                        print(f"[WARNING] Transaction {tx_uuid} has no entry for account '{account_filter}'")


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
                SELECT r.expense_id, r.description, r.amount, r.frequency, r.due_day_of_month, r.last_processed_date, r.category_id,
                       r.is_variable, r.estimated_amount,
                       a.name AS payment_account_name, c.name AS category_name, c.color AS category_color
                FROM recurring_expenses r
                JOIN accounts a ON r.payment_account_id = a.account_id
                LEFT JOIN expense_categories c ON r.category_id = c.category_id
                WHERE r.user_id = ?
                ORDER BY r.due_day_of_month, r.description
            """
            cursor.execute(query, (user_id,))
            return self._rows_to_dicts(cursor.fetchall())
        finally:
            cursor.close()
            conn.close()

    def get_unique_descriptions(self, user_id, transaction_type='expense'):
        """Get unique transaction descriptions from the last 30 days, excluding reversals."""
        conn, cursor = self._get_db_connection()
        try:
            # Get current user date
            current_date_str = self._get_user_current_date(cursor, user_id)
            current_date = self._from_datetime_str(current_date_str)
            thirty_days_ago = current_date - datetime.timedelta(days=30)
            thirty_days_ago_str = self._to_datetime_str(thirty_days_ago)

            base_query = """
                SELECT DISTINCT description
                FROM financial_ledger
                WHERE user_id = ?
                    AND description != ''
                    AND is_reversal = 0
                    AND transaction_date >= ?
            """

            if transaction_type == 'income':
                query = f"{base_query} AND account = 'Income' ORDER BY description"
                cursor.execute(query, (user_id, thirty_days_ago_str))
            else:
                query = f"{base_query} AND account = 'Expenses' ORDER BY description"
                cursor.execute(query, (user_id, thirty_days_ago_str))

            return [row['description'] for row in self._rows_to_dicts(cursor.fetchall())]
        finally:
            cursor.close()
            conn.close()
    
    def calculate_daily_burn_rate(self, user_id):
        conn, cursor = self._get_db_connection()
        try:
            query = "SELECT SUM(amount) AS total_monthly FROM recurring_expenses WHERE user_id = ? AND frequency = 'MONTHLY'"
            cursor.execute(query, (user_id,))
            result = self._row_to_dict(cursor.fetchone())
            if result and result['total_monthly']:
                return float(result['total_monthly']) / 30
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
                """SELECT ec.category_id, ec.name, ec.color, ec.is_default, ec.is_monthly, ec.created_at,
                          ec.parent_id, pc.name as parent_name
                   FROM expense_categories ec
                   LEFT JOIN parent_categories pc ON ec.parent_id = pc.parent_id
                   WHERE ec.user_id = ?
                   ORDER BY pc.display_order, ec.is_default DESC, ec.name ASC""",
                (user_id,)
            )
            return self._rows_to_dicts(cursor.fetchall())
        finally:
            cursor.close()
            conn.close()

    def get_default_category_id(self, user_id):
        """Get the default category ID for a user (Uncategorized)."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute(
                "SELECT category_id FROM expense_categories WHERE user_id = ? AND is_default = 1 LIMIT 1",
                (user_id,)
            )
            result = self._row_to_dict(cursor.fetchone())
            return result['category_id'] if result else None
        finally:
            cursor.close()
            conn.close()

    def add_expense_category(self, user_id, name, color='#6366f1'):
        """Add a new expense category."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute(
                "INSERT INTO expense_categories (user_id, name, color) VALUES (?, ?, ?)",
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

    def update_expense_category(self, user_id, category_id, name, color, is_monthly=False, parent_id=None):
        """Update an expense category."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute(
                "SELECT user_id FROM expense_categories WHERE category_id = ?",
                (category_id,)
            )
            result = self._row_to_dict(cursor.fetchone())
            if not result or str(result['user_id']) != str(user_id):
                return False, "Category not found or you don't have permission to edit it."

            cursor.execute(
                "UPDATE expense_categories SET name = ?, color = ?, is_monthly = ?, parent_id = ? WHERE category_id = ?",
                (name, color, is_monthly, parent_id, category_id)
            )
            conn.commit()
            return True, "Category updated successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def get_category_transaction_count(self, user_id, category_id):
        """Get the count of transactions using a specific category."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute(
                "SELECT COUNT(DISTINCT transaction_uuid) FROM financial_ledger WHERE user_id = ? AND category_id = ?",
                (user_id, category_id)
            )
            count = cursor.fetchone()[0]
            return count
        finally:
            cursor.close()
            conn.close()

    def delete_expense_category(self, user_id, category_id):
        """Delete an expense category (reassign to default first)."""
        conn, cursor = self._get_db_connection()
        try:
            # Check ownership and if it's not the default
            cursor.execute(
                "SELECT user_id, is_default FROM expense_categories WHERE category_id = ?",
                (category_id,)
            )
            result = self._row_to_dict(cursor.fetchone())
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
                "UPDATE financial_ledger SET category_id = ? WHERE user_id = ? AND category_id = ?",
                (default_category_id, user_id, category_id)
            )

            # Delete the category
            cursor.execute(
                "DELETE FROM expense_categories WHERE category_id = ?",
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

    # --- INCOME CATEGORY METHODS ---
    def get_income_categories(self, user_id):
        """Get all income categories for a user."""
        # Income categories feature not yet implemented in schema
        # Return empty list for now to prevent crashes
        return []

    def add_income_category(self, user_id, name, color='#10b981', parent_id=None, description=None):
        """Add a new income category."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute(
                "INSERT INTO income_categories (user_id, name, color, parent_id, description) VALUES (?, ?, ?, ?, ?)",
                (user_id, name, color, parent_id, description)
            )
            conn.commit()
            return True, "Income category added successfully.", cursor.lastrowid
        except Exception as e:
            conn.rollback()
            if "UNIQUE constraint" in str(e):
                return False, "An income category with this name already exists.", None
            return False, f"An error occurred: {e}", None
        finally:
            cursor.close()
            conn.close()

    def update_income_category(self, user_id, category_id, name, color, parent_id=None, description=None):
        """Update an income category."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute(
                "SELECT user_id FROM income_categories WHERE category_id = ?",
                (category_id,)
            )
            result = self._row_to_dict(cursor.fetchone())
            if not result or str(result['user_id']) != str(user_id):
                return False, "Category not found or you don't have permission to edit it."

            cursor.execute(
                "UPDATE income_categories SET name = ?, color = ?, parent_id = ?, description = ? WHERE category_id = ?",
                (name, color, parent_id, description, category_id)
            )
            conn.commit()
            return True, "Income category updated successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def delete_income_category(self, user_id, category_id):
        """Delete an income category."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute(
                "SELECT user_id, is_default FROM income_categories WHERE category_id = ?",
                (category_id,)
            )
            result = self._row_to_dict(cursor.fetchone())
            if not result:
                return False, "Category not found."
            if str(result['user_id']) != str(user_id):
                return False, "You don't have permission to delete this category."
            if result['is_default']:
                return False, "Cannot delete the default category."

            cursor.execute(
                "DELETE FROM income_categories WHERE category_id = ?",
                (category_id,)
            )
            conn.commit()
            return True, "Income category deleted successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    # --- PARENT CATEGORY METHODS ---
    def get_parent_categories(self, cat_type=None):
        """Get parent categories, optionally filtered by type (income/expense)."""
        conn, cursor = self._get_db_connection()
        try:
            if cat_type:
                cursor.execute(
                    "SELECT parent_id, name, type, display_order FROM parent_categories WHERE type = ? OR type = 'both' ORDER BY display_order",
                    (cat_type,)
                )
            else:
                cursor.execute(
                    "SELECT parent_id, name, type, display_order FROM parent_categories ORDER BY display_order"
                )
            return self._rows_to_dicts(cursor.fetchall())
        finally:
            cursor.close()
            conn.close()

    def add_parent_category(self, name, cat_type, display_order=None):
        """Add a new parent category."""
        conn, cursor = self._get_db_connection()
        try:
            # Get max display_order if not specified
            if display_order is None:
                cursor.execute("SELECT MAX(display_order) FROM parent_categories WHERE type = ?", (cat_type,))
                max_order = cursor.fetchone()[0]
                display_order = (max_order or 0) + 10

            cursor.execute(
                "INSERT INTO parent_categories (name, type, display_order) VALUES (?, ?, ?)",
                (name, cat_type, display_order)
            )
            conn.commit()
            return True, "Parent category added successfully.", cursor.lastrowid
        except Exception as e:
            conn.rollback()
            if "UNIQUE constraint" in str(e):
                return False, "A parent category with this name already exists.", None
            return False, f"An error occurred: {e}", None
        finally:
            cursor.close()
            conn.close()

    def update_parent_category(self, parent_id, name, cat_type, display_order=None):
        """Update a parent category."""
        conn, cursor = self._get_db_connection()
        try:
            if display_order is not None:
                cursor.execute(
                    "UPDATE parent_categories SET name = ?, type = ?, display_order = ? WHERE parent_id = ?",
                    (name, cat_type, display_order, parent_id)
                )
            else:
                cursor.execute(
                    "UPDATE parent_categories SET name = ?, type = ? WHERE parent_id = ?",
                    (name, cat_type, parent_id)
                )
            conn.commit()
            return True, "Parent category updated successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def delete_parent_category(self, parent_id):
        """Delete a parent category (only if no children)."""
        conn, cursor = self._get_db_connection()
        try:
            # Check for expense category children
            cursor.execute(
                "SELECT COUNT(*) FROM expense_categories WHERE parent_id = ?",
                (parent_id,)
            )
            expense_count = cursor.fetchone()[0]

            # Check for income category children
            cursor.execute(
                "SELECT COUNT(*) FROM income_categories WHERE parent_id = ?",
                (parent_id,)
            )
            income_count = cursor.fetchone()[0]

            if expense_count > 0 or income_count > 0:
                return False, f"Cannot delete: {expense_count + income_count} categories are using this parent. Reassign them first."

            cursor.execute(
                "DELETE FROM parent_categories WHERE parent_id = ?",
                (parent_id,)
            )
            conn.commit()
            return True, "Parent category deleted successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def get_parent_category_usage(self, parent_id):
        """Get count of categories using this parent."""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT COUNT(*) FROM expense_categories WHERE parent_id = ?", (parent_id,))
            expense_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM income_categories WHERE parent_id = ?", (parent_id,))
            income_count = cursor.fetchone()[0]
            return {"expense_count": expense_count, "income_count": income_count, "total": expense_count + income_count}
        finally:
            cursor.close()
            conn.close()

    def update_transaction_category(self, user_id, transaction_uuid, category_id):
        """Update the category for an expense transaction."""
        conn, cursor = self._get_db_connection()
        try:
            # Verify the transaction belongs to the user and is an expense (has debit entry)
            cursor.execute(
                "SELECT entry_id FROM financial_ledger WHERE user_id = ? AND transaction_uuid = ? AND debit > 0 LIMIT 1",
                (user_id, transaction_uuid)
            )
            result = self._row_to_dict(cursor.fetchone())

            if not result:
                return False, "Expense transaction not found or you don't have permission."

            # Update the category for all expense entries with this transaction_uuid
            cursor.execute(
                "UPDATE financial_ledger SET category_id = ? WHERE user_id = ? AND transaction_uuid = ? AND debit > 0",
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

    def update_transaction_business(self, user_id, transaction_uuid, is_business):
        """Update the business flag for an expense or income transaction."""
        conn, cursor = self._get_db_connection()
        try:
            # Verify the transaction belongs to the user
            cursor.execute(
                "SELECT entry_id FROM financial_ledger WHERE user_id = ? AND transaction_uuid = ? LIMIT 1",
                (user_id, transaction_uuid)
            )
            result = self._row_to_dict(cursor.fetchone())

            if not result:
                return False, "Transaction not found or you don't have permission."

            # Update the is_business flag for all entries with this transaction_uuid
            cursor.execute(
                "UPDATE financial_ledger SET is_business = ? WHERE user_id = ? AND transaction_uuid = ?",
                (1 if is_business else 0, user_id, transaction_uuid)
            )

            conn.commit()
            return True, "Business flag updated successfully."
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
            if not end_date:
                end_date = self._get_user_current_date(cursor, user_id)
            if not start_date:
                # Default to last 30 days - parse end_date string to do arithmetic
                if isinstance(end_date, str):
                    end_dt = datetime.datetime.strptime(end_date.split()[0], '%Y-%m-%d')
                else:
                    end_dt = end_date
                start_date = (end_dt - datetime.timedelta(days=30)).strftime('%Y-%m-%d')

            query = """
                SELECT
                    c.category_id,
                    c.name,
                    c.color,
                    p.name as parent_name,
                    SUM(l.debit) as total_amount,
                    COUNT(DISTINCT l.transaction_uuid) as transaction_count
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                LEFT JOIN parent_categories p ON c.parent_id = p.parent_id
                WHERE l.user_id = ?
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN ? AND ?
                    AND l.category_id IS NOT NULL
                    AND l.is_reversal = 0
                GROUP BY c.category_id, c.name, c.color, p.name
                ORDER BY total_amount DESC
            """
            cursor.execute(query, (user_id, start_date, end_date))
            return self._rows_to_dicts(cursor.fetchall())
        finally:
            cursor.close()
            conn.close()

    def get_transactions_by_category(self, user_id, category_id, start_date=None, end_date=None):
        """Get transactions for a specific category within a date range."""
        conn, cursor = self._get_db_connection()
        try:
            if not end_date:
                end_date = self._get_user_current_date(cursor, user_id)
            if not start_date:
                # Default to last 30 days - parse end_date string to do arithmetic
                if isinstance(end_date, str):
                    end_dt = datetime.datetime.strptime(end_date.split()[0], '%Y-%m-%d')
                else:
                    end_dt = end_date
                start_date = (end_dt - datetime.timedelta(days=30)).strftime('%Y-%m-%d')

            query = """
                SELECT
                    l.transaction_date,
                    l.description,
                    l.debit as amount,
                    l.transaction_uuid
                FROM financial_ledger l
                WHERE l.user_id = ?
                    AND l.category_id = ?
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN ? AND ?
                    AND l.is_reversal = 0
                ORDER BY l.transaction_date DESC
            """
            cursor.execute(query, (user_id, category_id, start_date, end_date))
            return self._rows_to_dicts(cursor.fetchall())
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
                WHERE l.user_id = ?
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN ? AND ?
                    AND l.category_id IS NOT NULL
                    AND l.is_reversal = 0
                GROUP BY DATE(l.transaction_date), c.category_id, c.name, c.color
                ORDER BY date, c.name
            """
            cursor.execute(query, (user_id, start_date, end_date))
            return self._rows_to_dicts(cursor.fetchall())
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
                WHERE user_id = ? AND DATE(transaction_date) = ?
            """
            cursor.execute(query, (user_id, for_date))
            result = self._row_to_dict(cursor.fetchone())
            total_income = float(result['total_income'] or 0)
            total_expenses = float(result['total_expenses'] or 0)
            return total_income - total_expenses
        finally:
            cursor.close()
            conn.close()

    def get_n_day_average(self, user_id, days=30, weighted=True, start_date=None, end_date=None):
        conn, cursor = self._get_db_connection()
        try:
            # If explicit dates provided, use them; otherwise calculate from days
            if start_date and end_date:
                start_date_str = start_date
                current_date_str_for_query = end_date
            else:
                current_date_str = self._get_user_current_date(cursor, user_id)
                current_date = self._from_datetime_str(current_date_str)
                # Calculate start date based on requested days parameter
                start_date_obj = current_date - datetime.timedelta(days=days - 1)  # -1 because we include today
                start_date_str = start_date_obj.strftime('%Y-%m-%d')
                current_date_str_for_query = current_date.strftime('%Y-%m-%d')

            query = """
                SELECT
                    DATE(transaction_date) as day,
                    SUM(CASE WHEN account = 'Income' THEN credit ELSE 0 END) AS total_income,
                    SUM(CASE WHEN account = 'Expenses' THEN debit ELSE 0 END) AS total_expenses
                FROM financial_ledger
                WHERE user_id = ?
                    AND DATE(transaction_date) BETWEEN ? AND ?
                    AND is_reversal = 0
                    AND description != 'Time Advanced'
                    AND description != 'Initial Balance'
                GROUP BY DATE(transaction_date)
            """
            cursor.execute(query, (user_id, start_date_str, current_date_str_for_query))
            results = self._rows_to_dicts(cursor.fetchall())

            if not results:
                return {
                    'average_net': 0.0,
                    'average_income': 0.0,
                    'average_expenses': 0.0,
                    'total_net': 0.0,
                    'total_income': 0.0,
                    'total_expenses': 0.0,
                    'days': days
                }

            total_income = sum(
                self._from_money_str(row['total_income'])
                for row in results
            )
            total_expenses = sum(
                self._from_money_str(row['total_expenses'])
                for row in results
            )
            total_net = total_income - total_expenses

            # Divide by the requested number of days
            average_income = float(total_income) / days if days > 0 else 0.0
            average_expenses = float(total_expenses) / days if days > 0 else 0.0
            average_net = float(total_net) / days if days > 0 else 0.0

            return {
                'average_net': average_net,
                'average_income': average_income,
                'average_expenses': average_expenses,
                'total_net': float(total_net),
                'total_income': float(total_income),
                'total_expenses': float(total_expenses),
                'days': days
            }
        finally:
            cursor.close()
            conn.close()

    # --- ACTION METHODS ---

    def setup_initial_accounts(self, user_id, accounts):
        conn, cursor = self._get_db_connection()
        try:
            # --- FIX: Ensure a single Equity account exists ---
            cursor.execute("SELECT account_id, balance FROM accounts WHERE user_id = ? AND name = 'Equity'", (user_id,))
            equity_account = cursor.fetchone()
            if not equity_account:
                cursor.execute(
                    "INSERT INTO accounts (user_id, name, type, balance) VALUES (?, 'Equity', 'EQUITY', 0.00)",
                    (user_id,)
                )

            now = datetime.datetime.now()
            for acc in accounts:
                cursor.execute(
                    "INSERT INTO accounts (user_id, name, type, balance, credit_limit) VALUES (?, ?, ?, ?, ?)",
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
                "INSERT INTO accounts (user_id, name, type, balance, credit_limit) VALUES (?, ?, ?, ?, ?)",
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
        fin_query = "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (?, ?, ?, ?, ?, ?, ?)"

        # Convert Decimal to float for SQLite compatibility
        balance_float = float(balance) if isinstance(balance, Decimal) else balance

        if balance >= 0:
            # Asset: Debit the asset account, Credit Equity
            cursor.execute(fin_query, (user_id, uuid, transaction_date, account_name, 'Initial Balance', balance_float, 0))
            cursor.execute(fin_query, (user_id, uuid, transaction_date, 'Equity', 'Initial Balance', 0, balance_float))
        else:
            # Liability: Debit Equity, Credit the liability account
            cursor.execute(fin_query, (user_id, uuid, transaction_date, 'Equity', 'Initial Balance', abs(balance_float), 0))
            cursor.execute(fin_query, (user_id, uuid, transaction_date, account_name, 'Initial Balance', 0, abs(balance_float)))

        # Update the balance of the single Equity account
        cursor.execute(
            "UPDATE accounts SET balance = balance + ? WHERE user_id = ? AND name = 'Equity'",
            (balance_float, user_id)
        )


    def update_account_name(self, user_id, account_id, new_name):
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT name FROM accounts WHERE account_id = ? AND user_id = ?", (account_id, user_id))
            result = self._row_to_dict(cursor.fetchone())
            if not result:
                return False, "Account not found or you do not have permission to edit it."
            old_name = result['name']

            cursor.execute("UPDATE accounts SET name = ? WHERE account_id = ?", (new_name, account_id))
            cursor.execute("UPDATE financial_ledger SET account = ? WHERE user_id = ? AND account = ?", (new_name, user_id, old_name))

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
            cursor.execute("SELECT name, balance FROM accounts WHERE account_id = ? AND user_id = ?", (account_id, user_id))
            result = self._row_to_dict(cursor.fetchone())
            if not result:
                return False, "Account not found or you do not have permission to delete it."

            account_name = result['name']
            balance = float(result['balance'])

            # Check if balance is zero
            if abs(balance) > 0.01:  # Using 0.01 to account for floating point precision
                return False, f"Cannot delete account '{account_name}'. Balance must be $0.00 (current balance: ${balance:.2f})."

            # Check if account is used in any ledger entries
            cursor.execute(
                "SELECT COUNT(*) as count FROM financial_ledger WHERE user_id = ? AND account = ?",
                (user_id, account_name)
            )
            ledger_count = self._row_to_dict(cursor.fetchone())['count']

            if ledger_count > 0:
                return False, f"Cannot delete account '{account_name}'. It has {ledger_count} transaction(s) in the ledger. Accounts with history cannot be deleted."

            # Safe to delete
            cursor.execute("DELETE FROM accounts WHERE account_id = ? AND user_id = ?", (account_id, user_id))
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
                "SELECT name, balance, type FROM accounts WHERE account_id = ? AND user_id = ?",
                (account_id, user_id)
            )
            account = self._row_to_dict(cursor.fetchone())
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
                    "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, uuid, current_date, account_name, description, abs(difference), 0)
                )
                cursor.execute(
                    "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, uuid, current_date, 'Unrealized Gain', description, 0, abs(difference))
                )
            else:
                # Asset decreased in value: Credit Asset, Debit Unrealized Loss (Equity)
                cursor.execute(
                    "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, uuid, current_date, 'Unrealized Loss', description, abs(difference), 0)
                )
                cursor.execute(
                    "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, uuid, current_date, account_name, description, 0, abs(difference))
                )

            # Update account balance
            cursor.execute(
                "UPDATE accounts SET balance = ? WHERE account_id = ? AND user_id = ?",
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
                "SELECT * FROM financial_ledger WHERE user_id = ? AND transaction_uuid = ? ORDER BY entry_id",
                (user_id, transaction_uuid)
            )
            entries = self._rows_to_dicts(cursor.fetchall())

            if not entries:
                return False, "Transaction not found or you do not have permission to reverse it."

            # Check if already reversed using the new is_reversal field
            if entries[0]['is_reversal']:
                return False, "This transaction has already been reversed or is itself a reversal."

            # Create reversal entries (swap debits and credits)
            # Use the original transaction's date for the reversal
            original_transaction_date = entries[0]['transaction_date']
            reversal_uuid = f"reversal-{user_id}-{int(time.time())}"
            original_description = entries[0]['description']

            for entry in entries:
                # Convert debit/credit to float to avoid Decimal issues
                new_debit = float(entry['credit']) if entry['credit'] else 0
                new_credit = float(entry['debit']) if entry['debit'] else 0

                cursor.execute(
                    "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id, is_reversal, reversal_of_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        user_id,
                        reversal_uuid,
                        original_transaction_date,  # Use original transaction's date
                        entry['account'],
                        f"REVERSAL OF: {entry['description']}",
                        new_debit,  # Swap: old credit becomes new debit
                        new_credit,   # Swap: old debit becomes new credit
                        entry['category_id'],  # Preserve category for analytics
                        True,             # Mark as reversal
                        entry['entry_id'] # Link to original entry
                    )
                )

            # Mark the original transaction as reversed
            for entry in entries:
                cursor.execute(
                    "UPDATE financial_ledger SET description = ?, is_reversal = ? WHERE entry_id = ? AND user_id = ?",
                    (f"REVERSED: {entry['description']}", True, entry['entry_id'], user_id)
                )

            # Note: We don't manually update account balances here because the reversal
            # ledger entries (with swapped debits/credits) automatically reverse the effect
            # when the balance is calculated from the ledger.
            # Manual updates would double-count the reversal.

            conn.commit()
            return True, f"Transaction reversed successfully. Original: '{original_description}'"
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def sync_account_balances(self, user_id):
        """Recalculate all account balances from ledger entries to fix any discrepancies"""
        conn, cursor = self._get_db_connection()
        try:
            # Get all user accounts
            cursor.execute("SELECT account_id, name FROM accounts WHERE user_id = ?", (user_id,))
            accounts = self._rows_to_dicts(cursor.fetchall())

            updated = []
            for account in accounts:
                account_name = account['name']

                # Calculate balance from ledger
                cursor.execute(
                    "SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as ledger_balance "
                    "FROM financial_ledger WHERE user_id = ? AND account = ?",
                    (user_id, account_name)
                )
                ledger_balance = float(self._row_to_dict(cursor.fetchone())['ledger_balance'] or 0)

                # Update account balance
                cursor.execute(
                    "UPDATE accounts SET balance = ? WHERE account_id = ? AND user_id = ?",
                    (ledger_balance, account['account_id'], user_id)
                )
                updated.append(f"{account_name}: ${ledger_balance:.2f}")

            conn.commit()
            return {"updated": updated, "count": len(updated)}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def log_income(self, user_id, account_id, description, amount, transaction_date=None, category_id=None, is_business=False, cursor=None):
        conn = None
        if not cursor:
            conn, cursor = self._get_db_connection()
        try:
            amount = float(amount)
            if amount <= 0: return False, "Income amount must be positive."

            cursor.execute("SELECT * FROM accounts WHERE account_id = ? AND user_id = ?", (account_id, user_id))
            account = self._row_to_dict(cursor.fetchone())
            if not account:
                return False, "Invalid account specified."

            new_balance = float(account['balance']) + amount

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
            is_biz = 1 if is_business else 0

            fin_query = "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id, is_business) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(fin_query, (user_id, uuid, current_date, account['name'], description, amount, 0, category_id, is_biz))
            cursor.execute(fin_query, (user_id, uuid, current_date, 'Income', description, 0, amount, category_id, is_biz))

            # Balance is now calculated from ledger - no manual update needed
            if conn: conn.commit()
            return True, f"Successfully logged income to '{account['name']}'."

        except Exception as e:
            if conn: conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            if conn:
                if cursor: cursor.close()
                if conn: conn.close()


    def add_recurring_expense(self, user_id, description, amount, payment_account_id, due_day_of_month, category_id=None, frequency='MONTHLY', is_variable=False, estimated_amount=None):
        """
        Add a new recurring expense with optional category and frequency.

        Creates a recurring expense that will be automatically processed based on
        the specified frequency during time advancement.

        Args:
            user_id (int): User creating the recurring expense
            description (str): Description of the expense (e.g., "Rent", "Netflix")
            amount (float/Decimal): Payment amount (must be positive)
            payment_account_id (int): Account ID to pay from (must belong to user)
            due_day_of_month (int): Day of month (1-31) for monthly/quarterly/yearly,
                                    or day of week (1=Mon, 7=Sun) for weekly/bi-weekly
            category_id (int, optional): Expense category ID (must belong to user)
            frequency (str): Payment frequency - DAILY, WEEKLY, BI_WEEKLY, MONTHLY, QUARTERLY, YEARLY

        Returns:
            tuple: (success bool, message str)
                   - (True, success_message) on success
                   - (False, error_message) on failure

        Validation:
            - Amount must be positive
            - Due day must be between 1 and 31
            - Payment account must exist and belong to user
            - Category (if provided) must exist and belong to user
            - Frequency must be valid

        Example:
            success, msg = sim.add_recurring_expense(
                user_id=1,
                description="Netflix Subscription",
                amount=15.99,
                payment_account_id=1,
                due_day_of_month=15,
                category_id=6,  # Entertainment category
                frequency='MONTHLY'
            )
        """
        valid_frequencies = ('DAILY', 'WEEKLY', 'BI_WEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY')
        if frequency not in valid_frequencies:
            return False, f"Invalid frequency. Must be one of: {', '.join(valid_frequencies)}"

        conn, cursor = self._get_db_connection()
        try:
            amount = Decimal(amount)
            if amount <= 0: return False, "Amount must be positive."
            if not 1 <= due_day_of_month <= 31: return False, "Due day must be between 1 and 31."

            cursor.execute("SELECT 1 FROM accounts WHERE account_id = ? AND user_id = ?", (payment_account_id, user_id))
            if not cursor.fetchone():
                return False, "Invalid payment account specified."

            # Validate category if provided
            if category_id:
                cursor.execute("SELECT 1 FROM expense_categories WHERE category_id = ? AND user_id = ?", (category_id, user_id))
                if not cursor.fetchone():
                    return False, "Invalid category specified."

            # Convert Decimal to float for SQLite compatibility
            amount_float = float(amount)
            estimated_amount_float = float(estimated_amount) if estimated_amount else None

            cursor.execute(
                "INSERT INTO recurring_expenses (user_id, description, amount, frequency, payment_account_id, due_day_of_month, category_id, is_variable, estimated_amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, description, amount_float, frequency, payment_account_id, due_day_of_month, category_id, is_variable, estimated_amount_float)
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
            cursor.execute("DELETE FROM recurring_expenses WHERE expense_id = ? AND user_id = ?", (expense_id, user_id))
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
                SELECT ri.income_id, ri.name, ri.description, ri.amount, ri.frequency,
                       ri.due_day_of_month AS deposit_day_of_month,
                       ri.last_processed_date, ri.is_variable, ri.estimated_amount,
                       ri.category_id,
                       a.name AS deposit_account_name,
                       c.name AS category_name, c.color AS category_color
                FROM recurring_income ri
                JOIN accounts a ON ri.destination_account_id = a.account_id
                LEFT JOIN expense_categories c ON ri.category_id = c.category_id
                WHERE ri.user_id = ?
                ORDER BY ri.name
            """
            cursor.execute(query, (user_id,))
            return self._rows_to_dicts(cursor.fetchall())
        finally:
            cursor.close()
            conn.close()

    def add_recurring_income(self, user_id, name, amount, destination_account_id, frequency='MONTHLY', due_day_of_month=1, description=None, category_id=None, is_variable=False, estimated_amount=None):
        """Add a new recurring income entry."""
        conn, cursor = self._get_db_connection()
        try:
            amount = Decimal(amount) if amount else Decimal(0)
            if not is_variable and amount <= 0:
                return False, "Amount must be positive for fixed income."

            # Validate category if provided
            if category_id:
                cursor.execute("SELECT 1 FROM expense_categories WHERE category_id = ? AND user_id = ?", (category_id, user_id))
                if not cursor.fetchone():
                    return False, "Invalid category specified."

            # Convert Decimal to float for SQLite compatibility
            amount_float = float(amount)
            estimated_amount_float = float(estimated_amount) if estimated_amount else None

            cursor.execute(
                "INSERT INTO recurring_income (user_id, name, description, amount, frequency, due_day_of_month, destination_account_id, category_id, is_variable, estimated_amount) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, name, description, amount_float, frequency, due_day_of_month, destination_account_id, category_id, is_variable, estimated_amount_float)
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
            cursor.execute("DELETE FROM recurring_income WHERE income_id = ? AND user_id = ?", (income_id, user_id))
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

    def update_recurring_income(self, user_id, income_id, description, amount, deposit_day_of_month, frequency='MONTHLY', category_id=None, is_variable=False, estimated_amount=None):
        """Update a recurring income entry."""
        valid_frequencies = ('DAILY', 'WEEKLY', 'BI_WEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY')
        if frequency not in valid_frequencies:
            return False, f"Invalid frequency. Must be one of: {', '.join(valid_frequencies)}"

        conn, cursor = self._get_db_connection()
        try:
            amount = Decimal(amount) if amount else Decimal(0)
            if not is_variable and amount <= 0:
                return False, "Amount must be positive for fixed income."
            if not 1 <= deposit_day_of_month <= 31:
                return False, "Deposit day must be between 1 and 31."

            # Validate category if provided
            if category_id:
                cursor.execute("SELECT 1 FROM expense_categories WHERE category_id = ? AND user_id = ?", (category_id, user_id))
                if not cursor.fetchone():
                    return False, "Invalid category specified."

            # Check if the record exists first
            cursor.execute("SELECT income_id, user_id FROM recurring_income WHERE income_id = ?", (income_id,))
            existing = self._row_to_dict(cursor.fetchone())

            cursor.execute(
                "UPDATE recurring_income SET description = ?, amount = ?, due_day_of_month = ?, frequency = ?, category_id = ?, is_variable = ?, estimated_amount = ? "
                "WHERE income_id = ? AND user_id = ?",
                (description, amount, deposit_day_of_month, frequency, category_id, is_variable, estimated_amount, income_id, user_id)
            )

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

    def update_recurring_expense(self, user_id, expense_id, description, amount, due_day_of_month, category_id=None, frequency='MONTHLY', is_variable=False, estimated_amount=None):
        valid_frequencies = ('DAILY', 'WEEKLY', 'BI_WEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY')
        if frequency not in valid_frequencies:
            return False, f"Invalid frequency. Must be one of: {', '.join(valid_frequencies)}"

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
            cursor.execute("SELECT user_id FROM recurring_expenses WHERE expense_id = ?", (expense_id,))
            existing = self._row_to_dict(cursor.fetchone())

            if not existing:
                return False, "Expense not found."

            if str(existing['user_id']) != str(user_id):
                return False, "You do not have permission to update this expense."

            # Validate category if provided
            if category_id:
                cursor.execute("SELECT 1 FROM expense_categories WHERE category_id = ? AND user_id = ?", (category_id, user_id))
                if not self._row_to_dict(cursor.fetchone()):
                    return False, "Invalid category specified."

            # Convert estimated_amount if provided
            if estimated_amount:
                estimated_amount = Decimal(estimated_amount)

            # Perform the update
            cursor.execute(
                "UPDATE recurring_expenses SET description = ?, amount = ?, due_day_of_month = ?, category_id = ?, frequency = ?, is_variable = ?, estimated_amount = ? WHERE expense_id = ? AND user_id = ?",
                (description, amount, due_day_of_month, category_id, frequency, is_variable, estimated_amount, expense_id, user_id)
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
            amount = float(amount)
            if amount <= 0:
                return False, "Transfer amount must be positive."

            # Get both accounts
            cursor.execute(
                "SELECT * FROM accounts WHERE account_id IN (?, ?) AND user_id = ?",
                (from_account_id, to_account_id, user_id)
            )
            accounts = self._rows_to_dicts(cursor.fetchall())

            if len(accounts) != 2:
                return False, "One or both accounts not found or you don't have permission."

            from_account = next((acc for acc in accounts if acc['account_id'] == from_account_id), None)
            to_account = next((acc for acc in accounts if acc['account_id'] == to_account_id), None)

            # Calculate actual balance from ledger (not the cached balance)
            cursor.execute(
                "SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as balance "
                "FROM financial_ledger WHERE user_id = ? AND account = ?",
                (user_id, from_account['name'])
            )
            from_balance = float(self._row_to_dict(cursor.fetchone())['balance'] or 0)

            # Check if from_account has sufficient balance
            if from_account['type'] == 'CREDIT_CARD':
                credit_limit = float(from_account['credit_limit']) if from_account['credit_limit'] is not None else None
                if credit_limit is not None and (from_balance - amount) < -credit_limit:
                    return False, "Transfer declined. Would exceed credit limit."
            elif from_balance < amount:
                return False, "Insufficient funds for transfer."

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
            fin_query = "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(fin_query, (user_id, uuid, current_date, to_account['name'], description, amount, 0))
            cursor.execute(fin_query, (user_id, uuid, current_date, from_account['name'], description, 0, amount))

            # Balance is now calculated from ledger - no manual update needed

            conn.commit()
            return True, f"Successfully transferred {amount} from '{from_account['name']}' to '{to_account['name']}'."

        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()

    def log_expense(self, user_id, account_id, description, amount, transaction_date=None, category_id=None, is_business=False, cursor=None):
        conn = None
        if not cursor:
            conn, cursor = self._get_db_connection()
        try:
            amount = float(amount)
            if amount <= 0: return False, "Expense amount must be positive."

            cursor.execute("SELECT * FROM accounts WHERE account_id = ? AND user_id = ?", (account_id, user_id))
            account = self._row_to_dict(cursor.fetchone())
            if not account: return False, "Invalid account specified."

            # Calculate actual balance from ledger (not the cached balance)
            cursor.execute(
                "SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as balance "
                "FROM financial_ledger WHERE user_id = ? AND account = ?",
                (user_id, account['name'])
            )
            balance = float(self._row_to_dict(cursor.fetchone())['balance'] or 0)

            if account['type'] == 'CREDIT_CARD':
                credit_limit = float(account['credit_limit']) if account['credit_limit'] is not None else None
                if credit_limit is not None and (balance - amount) < -credit_limit:
                    return False, "Transaction declined. Exceeds credit limit."
            elif balance < amount:
                return False, "Insufficient funds."

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
            is_biz = 1 if is_business else 0

            fin_query = "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id, is_business) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(fin_query, (user_id, uuid, current_date, 'Expenses', description, amount, 0, category_id, is_biz))
            cursor.execute(fin_query, (user_id, uuid, current_date, account['name'], description, 0, amount, None, is_biz))

            # Balance is now calculated from ledger - no manual update needed

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
                WHERE p.user_id = ? AND p.status = 'PENDING'
                ORDER BY p.due_date ASC
            """
            cursor.execute(query, (user_id,))
            return self._rows_to_dicts(cursor.fetchall())
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
                WHERE pending_id = ? AND user_id = ? AND status = 'PENDING'
            """, (pending_id, user_id))

            pending = self._row_to_dict(cursor.fetchone())
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
                cursor.execute("SELECT name FROM accounts WHERE account_id = ?",
                             (pending['related_account_id'],))
                card_account = self._row_to_dict(cursor.fetchone())

                # DR Interest Expense
                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (?, ?, ?, 'Interest Expense', ?, ?, 0, NULL)
                """, (user_id, txn_uuid, pending['due_date'], pending['description'], actual_amount))

                # CR Credit Card (increases debt)
                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (?, ?, ?, ?, ?, 0, ?, NULL)
                """, (user_id, txn_uuid, pending['due_date'], card_account['name'],
                     pending['description'], actual_amount))

                # Update account balance
                cursor.execute("""
                    UPDATE accounts
                    SET balance = balance - ?, last_interest_date = ?
                    WHERE account_id = ?
                """, (actual_amount, pending['due_date'], pending['related_account_id']))

            # Update pending transaction
            cursor.execute("""
                UPDATE pending_transactions
                SET status = 'APPROVED', actual_amount = ?, resolved_at = datetime('now')
                WHERE pending_id = ?
            """, (actual_amount, pending_id))

            # Update recurring expense last_processed_date if applicable
            if pending['recurring_expense_id']:
                cursor.execute("""
                    UPDATE recurring_expenses
                    SET last_processed_date = ?
                    WHERE expense_id = ?
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
                SET status = 'REJECTED', resolved_at = datetime('now')
                WHERE pending_id = ? AND user_id = ? AND status = 'PENDING'
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
        interest_amount = float(interest_amount) if interest_amount else 0.0
        principal_amount = float(principal_amount) if principal_amount else 0.0
        escrow_amount = float(escrow_amount) if escrow_amount else 0.0

        conn, cursor = self._get_db_connection()
        try:
            if payment_date is None:
                current_date_str = self._get_user_current_date(cursor, user_id)
                payment_date = self._from_datetime_str(current_date_str)

            # Get loan/credit card account details
            cursor.execute("""
                SELECT account_id, name, balance, type
                FROM accounts
                WHERE account_id = ? AND user_id = ? AND type IN ('LOAN', 'CREDIT_CARD')
            """, (loan_id, user_id))

            loan_account = self._row_to_dict(cursor.fetchone())
            if not loan_account:
                return False, "Loan or credit card account not found."

            # Get payment account name
            cursor.execute("SELECT name FROM accounts WHERE account_id = ?", (payment_account_id,))
            payment_acct = self._row_to_dict(cursor.fetchone())
            if not payment_acct:
                return False, "Payment account not found."

            # Generate separate UUIDs for each transaction component (improves ledger filtering)
            from uuid import uuid4

            # Get Interest Expense category (create if doesn't exist)
            cursor.execute("""
                SELECT category_id FROM expense_categories
                WHERE user_id = ? AND name = 'Interest Expense'
            """, (user_id,))
            interest_cat = self._row_to_dict(cursor.fetchone())
            if not interest_cat:
                cursor.execute("""
                    INSERT INTO expense_categories (user_id, name, color, is_default, is_monthly)
                    VALUES (?, 'Interest Expense', '#ef4444', 0, 1)
                """, (user_id,))
                interest_category_id = cursor.lastrowid
            else:
                interest_category_id = interest_cat['category_id']

            # Calculate total payment
            total_payment = interest_amount + principal_amount + escrow_amount
            if other_amounts:
                for item in other_amounts:
                    total_payment += float(item['amount'])

            # Create ledger entries - each component gets its own UUID for independent ledger display
            # 1. Interest Expense transaction (DR Expenses, CR Payment Account)
            if interest_amount > 0:
                interest_uuid = str(uuid4())
                # DR Interest Expense
                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (?, ?, ?, 'Expenses', ?, ?, 0, ?)
                """, (user_id, interest_uuid, payment_date, f"{loan_account['name']} - Interest",
                      interest_amount, interest_category_id))
                # CR Payment Account
                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (?, ?, ?, ?, ?, 0, ?, NULL)
                """, (user_id, interest_uuid, payment_date, payment_acct['name'],
                      f"{loan_account['name']} - Interest", interest_amount))

            # 2. Principal Payment transaction (DR Loan Account, CR Payment Account)
            if principal_amount > 0:
                principal_uuid = str(uuid4())
                # DR Loan/Credit Card (reduces liability)
                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (?, ?, ?, ?, 'Payment - Principal', ?, 0, NULL)
                """, (user_id, principal_uuid, payment_date, loan_account['name'], principal_amount))
                # CR Payment Account
                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (?, ?, ?, ?, 'Payment - Principal', 0, ?, NULL)
                """, (user_id, principal_uuid, payment_date, payment_acct['name'], principal_amount))

            # 3. Escrow transaction (DR Expenses, CR Payment Account)
            if escrow_amount > 0:
                escrow_uuid = str(uuid4())
                # Get or create Escrow/Housing category
                cursor.execute("""
                    SELECT category_id FROM expense_categories
                    WHERE user_id = ? AND name = 'Escrow/Housing'
                """, (user_id,))
                escrow_cat = self._row_to_dict(cursor.fetchone())
                if not escrow_cat:
                    cursor.execute("""
                        INSERT INTO expense_categories (user_id, name, color, is_default, is_monthly)
                        VALUES (?, 'Escrow/Housing', '#3b82f6', 0, 1)
                    """, (user_id,))
                    escrow_category_id = cursor.lastrowid
                else:
                    escrow_category_id = escrow_cat['category_id']

                # DR Escrow Expense
                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (?, ?, ?, 'Expenses', ?, ?, 0, ?)
                """, (user_id, escrow_uuid, payment_date, f"{loan_account['name']} - Escrow",
                      escrow_amount, escrow_category_id))
                # CR Payment Account
                cursor.execute("""
                    INSERT INTO financial_ledger
                    (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                    VALUES (?, ?, ?, ?, ?, 0, ?, NULL)
                """, (user_id, escrow_uuid, payment_date, payment_acct['name'],
                      f"{loan_account['name']} - Escrow", escrow_amount))

            # 4. Other amounts (fees, etc.) - each gets its own transaction
            if other_amounts:
                # Get or create Fees category
                cursor.execute("""
                    SELECT category_id FROM expense_categories
                    WHERE user_id = ? AND name = 'Fees & Charges'
                """, (user_id,))
                fees_cat = self._row_to_dict(cursor.fetchone())
                if not fees_cat:
                    cursor.execute("""
                        INSERT INTO expense_categories (user_id, name, color, is_default, is_monthly)
                        VALUES (?, 'Fees & Charges', '#f59e0b', 0, 1)
                    """, (user_id,))
                    fees_category_id = cursor.lastrowid
                else:
                    fees_category_id = fees_cat['category_id']

                for item in other_amounts:
                    amount = float(item['amount'])
                    if amount > 0:
                        fee_uuid = str(uuid4())
                        # DR Fee Expense
                        cursor.execute("""
                            INSERT INTO financial_ledger
                            (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                            VALUES (?, ?, ?, 'Expenses', ?, ?, 0, ?)
                        """, (user_id, fee_uuid, payment_date, f"{loan_account['name']} - {item['label']}",
                              amount, fees_category_id))
                        # CR Payment Account
                        cursor.execute("""
                            INSERT INTO financial_ledger
                            (user_id, transaction_uuid, transaction_date, account, description, debit, credit, category_id)
                            VALUES (?, ?, ?, ?, ?, 0, ?, NULL)
                        """, (user_id, fee_uuid, payment_date, payment_acct['name'],
                              f"{loan_account['name']} - {item['label']}", amount))

            # Balance is now calculated from ledger - no manual update needed

            # Fetch new loan balance (calculated from ledger)
            cursor.execute(
                "SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as ledger_balance "
                "FROM financial_ledger WHERE user_id = ? AND account = ?",
                (user_id, loan_account['name'])
            )
            new_balance = abs(float(self._row_to_dict(cursor.fetchone())['ledger_balance'] or 0))

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
                    if float(item['amount']) > 0:
                        msg_parts.append(f"${float(item['amount']):,.2f} {item['label']}")

            msg = f"Payment processed: {', '.join(msg_parts)}. New balance: ${new_balance:,.2f}"
            return True, msg

        except Exception as e:
            conn.rollback()
            # Error in make_loan_payment
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
                WHERE loan_id = ? AND user_id = ?
                ORDER BY payment_date DESC
            """, (loan_id, user_id))
            return self._rows_to_dicts(cursor.fetchall())
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
                WHERE account_id = ? AND user_id = ? AND type = 'CREDIT_CARD'
            """, (card_account_id, user_id))

            card = self._row_to_dict(cursor.fetchone())
            if not card:
                return False, "Credit card account not found."

            # Check if interest is due
            if card['last_interest_date']:
                last_interest_date = self._from_datetime_str(card['last_interest_date'])
                days_since = (self._from_datetime_str(current_date) - last_interest_date).days
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
                VALUES (?, NULL, ?, ?, date('now'), ?, NULL, 'PENDING', 'INTEREST', ?)
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
            cursor.execute("SELECT * FROM recurring_expenses WHERE user_id = ?", (user_id,))
            recurring_expenses = self._rows_to_dicts(cursor.fetchall())

            cursor.execute("SELECT * FROM recurring_income WHERE user_id = ?", (user_id,))
            recurring_income = self._rows_to_dicts(cursor.fetchall())

            for i in range(days_to_advance):
                current_day = simulation_start_date + datetime.timedelta(days=i + 1)
                days_in_month = calendar.monthrange(current_day.year, current_day.month)[1]

                for expense in recurring_expenses:
                    frequency = expense.get('frequency', 'MONTHLY')
                    is_due_for_payment = False
                    last_processed = expense.get('last_processed_date')

                    # Ensure last_processed is a date object (not datetime)
                    if last_processed and isinstance(last_processed, datetime.datetime):
                        last_processed = last_processed.date()
                    elif last_processed and isinstance(last_processed, str):
                        try:
                            last_processed = datetime.datetime.strptime(last_processed.split(' ')[0], '%Y-%m-%d').date()
                        except ValueError:
                            last_processed = None

                    # Determine if payment is due based on frequency
                    if frequency == 'DAILY':
                        # Due every day
                        if not last_processed or current_day > last_processed:
                            is_due_for_payment = True

                    elif frequency == 'WEEKLY':
                        # Due every 7 days from due_day_of_month (treated as day of week: 1=Mon, 7=Sun)
                        due_weekday = (expense['due_day_of_month'] - 1) % 7  # Convert to Python weekday (0=Mon)
                        if current_day.weekday() == due_weekday:
                            if not last_processed or (current_day - last_processed).days >= 7:
                                is_due_for_payment = True

                    elif frequency == 'BI_WEEKLY':
                        # Due every 14 days from due_day_of_month (treated as day of week)
                        due_weekday = (expense['due_day_of_month'] - 1) % 7
                        if current_day.weekday() == due_weekday:
                            if not last_processed or (current_day - last_processed).days >= 14:
                                is_due_for_payment = True

                    elif frequency == 'MONTHLY':
                        # Handle bills due on days that don't exist in current month
                        effective_due_day = min(expense['due_day_of_month'], days_in_month)
                        if current_day.day == effective_due_day:
                            if not last_processed:
                                is_due_for_payment = True
                            elif (current_day.year, current_day.month) > (last_processed.year, last_processed.month):
                                is_due_for_payment = True

                    elif frequency == 'QUARTERLY':
                        # Due every 3 months on due_day_of_month
                        effective_due_day = min(expense['due_day_of_month'], days_in_month)
                        if current_day.day == effective_due_day:
                            if not last_processed:
                                is_due_for_payment = True
                            else:
                                months_diff = (current_day.year - last_processed.year) * 12 + (current_day.month - last_processed.month)
                                if months_diff >= 3:
                                    is_due_for_payment = True

                    elif frequency == 'YEARLY':
                        # Due once a year on due_day_of_month in the same month as first payment
                        effective_due_day = min(expense['due_day_of_month'], days_in_month)
                        if current_day.day == effective_due_day:
                            if not last_processed:
                                is_due_for_payment = True
                            elif current_day.year > last_processed.year and current_day.month >= last_processed.month:
                                is_due_for_payment = True

                    if is_due_for_payment:
                            # Check if this is a variable expense
                            if expense.get('is_variable'):
                                # CREATE PENDING TRANSACTION instead of auto-paying
                                cursor.execute("""
                                    INSERT INTO pending_transactions
                                    (user_id, recurring_expense_id, description, estimated_amount,
                                     due_date, payment_account_id, category_id, status, transaction_type)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', 'EXPENSE')
                                """, (
                                    user_id,
                                    expense['expense_id'],
                                    expense['description'],
                                    expense.get('estimated_amount') or expense['amount'],
                                    self._to_datetime_str(current_day),
                                    expense['payment_account_id'],
                                    expense.get('category_id')
                                ))

                                # Update last_processed_date so it doesn't create duplicate pending transactions
                                current_day_str = self._to_datetime_str(current_day)
                                cursor.execute(
                                    "UPDATE recurring_expenses SET last_processed_date = ? WHERE expense_id = ?",
                                    (current_day_str, expense['expense_id'])
                                )
                                expense['last_processed_date'] = current_day_str
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
                                    current_day_str = self._to_datetime_str(current_day)
                                    cursor.execute(
                                        "UPDATE recurring_expenses SET last_processed_date = ? WHERE expense_id = ?",
                                        (current_day_str, expense['expense_id'])
                                    )
                                    # Update the in-memory record to prevent re-payment in the same run
                                    expense['last_processed_date'] = current_day_str
                                    processing_log.append(f"On {current_day.strftime('%Y-%m-%d')}: Paid {expense['description']} (${expense['amount']}).")
                                else:
                                    processing_log.append(f"On {current_day.strftime('%Y-%m-%d')}: FAILED to pay {expense['description']} - {message}")

                # Process recurring income
                for income in recurring_income:
                    frequency = income.get('frequency', 'MONTHLY')
                    is_due_for_deposit = False
                    last_processed = income.get('last_processed_date')

                    # Ensure last_processed is a date object
                    if last_processed and isinstance(last_processed, datetime.datetime):
                        last_processed = last_processed.date()
                    elif last_processed and isinstance(last_processed, str):
                        try:
                            last_processed = datetime.datetime.strptime(last_processed.split(' ')[0], '%Y-%m-%d').date()
                        except ValueError:
                            last_processed = None

                    due_day = income.get('deposit_day_of_month') or income.get('due_day_of_month', 1)

                    # Determine if income is due based on frequency
                    if frequency == 'DAILY':
                        if not last_processed or current_day > last_processed:
                            is_due_for_deposit = True

                    elif frequency == 'WEEKLY':
                        due_weekday = (due_day - 1) % 7
                        if current_day.weekday() == due_weekday:
                            if not last_processed or (current_day - last_processed).days >= 7:
                                is_due_for_deposit = True

                    elif frequency == 'BI_WEEKLY':
                        due_weekday = (due_day - 1) % 7
                        if current_day.weekday() == due_weekday:
                            if not last_processed or (current_day - last_processed).days >= 14:
                                is_due_for_deposit = True

                    elif frequency == 'MONTHLY':
                        effective_due_day = min(due_day, days_in_month)
                        if current_day.day == effective_due_day:
                            if not last_processed:
                                is_due_for_deposit = True
                            elif (current_day.year, current_day.month) > (last_processed.year, last_processed.month):
                                is_due_for_deposit = True

                    elif frequency == 'QUARTERLY':
                        effective_due_day = min(due_day, days_in_month)
                        if current_day.day == effective_due_day:
                            if not last_processed:
                                is_due_for_deposit = True
                            else:
                                months_diff = (current_day.year - last_processed.year) * 12 + (current_day.month - last_processed.month)
                                if months_diff >= 3:
                                    is_due_for_deposit = True

                    elif frequency == 'YEARLY':
                        effective_due_day = min(due_day, days_in_month)
                        if current_day.day == effective_due_day:
                            if not last_processed:
                                is_due_for_deposit = True
                            elif current_day.year > last_processed.year and current_day.month >= last_processed.month:
                                is_due_for_deposit = True

                    if is_due_for_deposit:
                            # Check if this is a variable income
                            if income.get('is_variable'):
                                # CREATE PENDING TRANSACTION instead of auto-depositing
                                cursor.execute("""
                                    INSERT INTO pending_transactions
                                    (user_id, recurring_income_id, description, estimated_amount,
                                     due_date, payment_account_id, status, transaction_type)
                                    VALUES (?, ?, ?, ?, ?, ?, 'PENDING', 'INCOME')
                                """, (
                                    user_id,
                                    income['income_id'],
                                    income['description'],
                                    income.get('estimated_amount') or income['amount'],
                                    self._to_datetime_str(current_day),
                                    income['deposit_account_id']
                                ))

                                # Update last_processed_date so it doesn't create duplicate pending transactions
                                current_day_str = self._to_datetime_str(current_day)
                                cursor.execute(
                                    "UPDATE recurring_income SET last_processed_date = ? WHERE income_id = ?",
                                    (current_day_str, income['income_id'])
                                )
                                income['last_processed_date'] = current_day_str
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
                                    current_day_str = self._to_datetime_str(current_day)
                                    cursor.execute(
                                        "UPDATE recurring_income SET last_processed_date = ? WHERE income_id = ?",
                                        (current_day_str, income['income_id'])
                                    )
                                    income['last_processed_date'] = current_day_str
                                    processing_log.append(f"On {current_day.strftime('%Y-%m-%d')}: Deposited {income['description']} (${income['amount']}).")
                                else:
                                    processing_log.append(f"On {current_day.strftime('%Y-%m-%d')}: FAILED to deposit {income['description']} - {message}")

            final_date = simulation_start_date + datetime.timedelta(days=days_to_advance)
            # Check if we need to insert a time marker using the existing cursor
            cursor.execute(
                "SELECT transaction_date FROM financial_ledger WHERE user_id = ? ORDER BY transaction_date DESC, entry_id DESC LIMIT 1",
                (user_id,)
            )
            last_entry = self._row_to_dict(cursor.fetchone())

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
                    "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description) VALUES (?, ?, ?, 'System', 'Time Advanced')",
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

    def auto_advance_time(self, user_id, client_date=None):
        """
        Automatically advance time to today's date if the user's last transaction
        is in the past. This is called on login to keep the simulation current.

        Args:
            user_id (int): The ID of the user
            client_date (str, optional): Client's current date in YYYY-MM-DD format.
                                         Used to handle timezone differences between
                                         client and server.

        Returns:
            dict: Result with log messages from the advance
        """
        conn, cursor = self._get_db_connection()
        try:
            # Get the user's current date (last transaction date)
            current_date_raw = self._get_user_current_date(cursor, user_id)
            cursor.close()
            conn.close()

            # Convert to date object if it's a string
            if isinstance(current_date_raw, str):
                current_date = self._from_datetime_str(current_date_raw)
                if isinstance(current_date, datetime.datetime):
                    current_date = current_date.date()
            else:
                current_date = current_date_raw

            # Use client's date if provided (handles timezone differences), otherwise use server date
            if client_date:
                if isinstance(client_date, str):
                    # Handle both YYYY-MM-DD and ISO format with time
                    today = datetime.datetime.strptime(client_date.split('T')[0], '%Y-%m-%d').date()
                else:
                    today = client_date
            else:
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
                WHERE user_id = ?
                  AND account = 'Income'
                  AND transaction_date BETWEEN ? AND ?
                GROUP BY description
                ORDER BY amount DESC
            """, (user_id, start_date, end_date))
            revenue_details = self._rows_to_dicts(cursor.fetchall())
            total_revenue = sum(self._from_money_str(r['amount']) for r in revenue_details)

            # Get all expenses by category (only include Expenses account or debits from CHECKING/SAVINGS/CASH/CREDIT accounts)
            cursor.execute("""
                SELECT
                    COALESCE(ec.name, 'Uncategorized') as category,
                    SUM(fl.debit) as amount
                FROM financial_ledger fl
                LEFT JOIN expense_categories ec ON fl.category_id = ec.category_id
                LEFT JOIN accounts a ON fl.account = a.name AND fl.user_id = a.user_id
                WHERE fl.user_id = ?
                  AND fl.debit > 0
                  AND fl.transaction_date BETWEEN ? AND ?
                  AND (fl.account = 'Expenses' OR a.type IN ('CHECKING', 'SAVINGS', 'CASH', 'CREDIT'))
                GROUP BY ec.name
                ORDER BY amount DESC
            """, (user_id, start_date, end_date))
            expense_details = self._rows_to_dicts(cursor.fetchall())
            total_expenses = sum(self._from_money_str(e['amount']) for e in expense_details)

            return {
                'revenue': {
                    'total': float(total_revenue),
                    'details': revenue_details
                },
                'expenses': {
                    'total': float(total_expenses),
                    'by_category': expense_details
                },
                'net_income': float(total_revenue - total_expenses)
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
                WHERE a.user_id = ?
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
                    WHERE user_id = ?
                      AND account = ?
                      AND transaction_date <= ?
                """, (user_id, acc['name'], as_of_date))
                result = self._row_to_dict(cursor.fetchone())
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
                WHERE fl.user_id = ?
                  AND fl.transaction_date BETWEEN ? AND ?
            """, (user_id, start_date, end_date))
            operating = self._row_to_dict(cursor.fetchone())
            operating_cash = float(self._from_money_str(operating['income'] or 0)) - float(self._from_money_str(operating['expenses'] or 0))

            # Investing Activities: Fixed asset purchases and investment account changes
            cursor.execute("""
                SELECT
                    SUM(credit) - SUM(debit) as investing_flow
                FROM financial_ledger fl
                JOIN accounts a ON fl.account = a.name AND fl.user_id = a.user_id
                WHERE fl.user_id = ?
                  AND a.type IN ('INVESTMENT', 'FIXED_ASSET')
                  AND fl.transaction_date BETWEEN ? AND ?
            """, (user_id, start_date, end_date))
            investing = self._row_to_dict(cursor.fetchone())
            investing_cash = float(self._from_money_str(investing['investing_flow'] or 0))

            # Financing Activities: Loan payments, credit card changes
            cursor.execute("""
                SELECT
                    SUM(debit) - SUM(credit) as financing_flow
                FROM financial_ledger fl
                JOIN accounts a ON fl.account = a.name AND fl.user_id = a.user_id
                WHERE fl.user_id = ?
                  AND a.type IN ('LOAN', 'CREDIT_CARD')
                  AND fl.transaction_date BETWEEN ? AND ?
            """, (user_id, start_date, end_date))
            financing = self._row_to_dict(cursor.fetchone())
            financing_cash = float(self._from_money_str(financing['financing_flow'] or 0))

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
            current_date_raw = self._get_user_current_date(cursor, user_id)
            current_date = self._from_datetime_str(current_date_raw)
            start_date = current_date - datetime.timedelta(days=days - 1)  # -1 to include today
            start_date_str = self._to_datetime_str(start_date)
            current_date_str = self._to_datetime_str(current_date)  # Convert current_date back to string for query

            # Find the earliest transaction date for this user (for chart limiting)
            cursor.execute("""
                SELECT MIN(transaction_date) as first_date
                FROM financial_ledger
                WHERE user_id = ? AND description != 'Time Advanced' AND description != 'Initial Balance'
            """, (user_id,))
            first_date_result = self._row_to_dict(cursor.fetchone())
            first_transaction_date_str = first_date_result['first_date'] if first_date_result and first_date_result['first_date'] else start_date_str

            # Use the later of: requested start date or first transaction date
            # This prevents showing zeros before any data exists
            if first_transaction_date_str > start_date_str:
                effective_start_date_str = first_transaction_date_str
            else:
                effective_start_date_str = start_date_str

            # Get total income and expenses for the period (exclude reversals and system entries)
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN account = 'Income' THEN credit ELSE 0 END) as total_income,
                    SUM(CASE WHEN account = 'Expenses' THEN debit ELSE 0 END) as total_expenses
                FROM financial_ledger
                WHERE user_id = ? AND transaction_date BETWEEN ? AND ?
                    AND is_reversal = 0
                    AND description != 'Time Advanced'
                    AND description != 'Initial Balance'
            """, (user_id, start_date_str, current_date_str))
            totals = self._row_to_dict(cursor.fetchone())

            # Get spending by category (exclude reversals and system entries)
            cursor.execute("""
                SELECT c.name, c.color, SUM(l.debit) as amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = ?
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN ? AND ?
                    AND l.category_id IS NOT NULL
                    AND l.is_reversal = 0
                    AND l.description != 'Time Advanced'
                    AND l.description != 'Initial Balance'
                GROUP BY c.category_id, c.name, c.color
                ORDER BY amount DESC
            """, (user_id, start_date_str, current_date_str))
            spending_by_category = self._rows_to_dicts(cursor.fetchall())

            # Get income breakdown by description (for Income by Source chart)
            cursor.execute("""
                SELECT description, SUM(credit) as amount
                FROM financial_ledger
                WHERE user_id = ?
                    AND account = 'Income'
                    AND transaction_date BETWEEN ? AND ?
                    AND is_reversal = 0
                    AND description != 'Time Advanced'
                    AND description != 'Initial Balance'
                GROUP BY description
                ORDER BY amount DESC
            """, (user_id, start_date_str, current_date_str))
            income_by_description = self._rows_to_dicts(cursor.fetchall())

            # Get income breakdown by category (for Income by Source chart)
            # Uses expense_categories since income categories are stored there with parent_id linking to income parent groups
            cursor.execute("""
                SELECT
                    COALESCE(ec.name, 'Uncategorized') as name,
                    COALESCE(ec.color, '#10b981') as color,
                    SUM(l.credit) as amount
                FROM financial_ledger l
                LEFT JOIN expense_categories ec ON l.category_id = ec.category_id
                WHERE l.user_id = ?
                    AND l.account = 'Income'
                    AND l.transaction_date BETWEEN ? AND ?
                    AND l.is_reversal = 0
                    AND l.description != 'Time Advanced'
                    AND l.description != 'Initial Balance'
                GROUP BY ec.category_id, ec.name, ec.color
                ORDER BY amount DESC
            """, (user_id, start_date_str, current_date_str))
            income_by_category = self._rows_to_dicts(cursor.fetchall())

            # Get net worth over time (daily snapshots) - exclude reversals
            # Use effective_start_date_str to avoid showing zeros before first transaction
            cursor.execute("""
                SELECT DATE(transaction_date) as date,
                    SUM(CASE WHEN a.type IN ('CHECKING', 'SAVINGS', 'CASH') THEN debit - credit ELSE 0 END) as daily_change
                FROM financial_ledger l
                JOIN accounts a ON l.account = a.name AND l.user_id = a.user_id
                WHERE l.user_id = ? AND transaction_date BETWEEN ? AND ?
                    AND l.is_reversal = 0
                GROUP BY DATE(transaction_date)
                ORDER BY date
            """, (user_id, effective_start_date_str, current_date_str))
            daily_changes = self._rows_to_dicts(cursor.fetchall())

            # Calculate starting balance at the beginning of the effective period (exclude reversals)
            cursor.execute("""
                SELECT SUM(CASE WHEN a.type IN ('CHECKING', 'SAVINGS', 'CASH') THEN debit - credit ELSE 0 END) as balance_before_period
                FROM financial_ledger l
                JOIN accounts a ON l.account = a.name AND l.user_id = a.user_id
                WHERE l.user_id = ? AND transaction_date < ?
                    AND l.is_reversal = 0
            """, (user_id, effective_start_date_str))
            result = self._row_to_dict(cursor.fetchone())
            starting_balance = self._from_money_str(result['balance_before_period']) if result and result['balance_before_period'] else Decimal('0.0')

            # Start with the balance at the beginning of the effective period
            net_worth_trend = [{
                'date': effective_start_date_str,
                'net_worth': float(starting_balance)
            }]
            cumulative = float(starting_balance)
            for row in daily_changes:
                daily_change = float(self._from_money_str(row['daily_change'])) if row['daily_change'] else 0.0
                cumulative += daily_change
                net_worth_trend.append({
                    'date': row['date'],  # Already a string from SQLite DATE()
                    'net_worth': float(cumulative)
                })

            # Calculate savings rate
            total_income = float(self._from_money_str(totals['total_income']))
            total_expenses = float(self._from_money_str(totals['total_expenses']))
            savings_rate = ((total_income - total_expenses) / total_income * 100) if total_income > 0 else 0

            # Get monthly income vs expenses for bar chart (exclude reversals)
            cursor.execute("""
                SELECT
                    strftime('%Y-%m', transaction_date) as month,
                    SUM(CASE WHEN account = 'Income' THEN credit ELSE 0 END) as income,
                    SUM(CASE WHEN account = 'Expenses' THEN debit ELSE 0 END) as expenses
                FROM financial_ledger
                WHERE user_id = ? AND transaction_date BETWEEN ? AND ?
                    AND is_reversal = 0
                GROUP BY strftime('%Y-%m', transaction_date)
                ORDER BY month
            """, (user_id, start_date_str, current_date_str))
            monthly_data = self._rows_to_dicts(cursor.fetchall())
            income_vs_expenses = [
                {
                    'month': row['month'],
                    'income': float(self._from_money_str(row['income'])),
                    'expenses': float(self._from_money_str(row['expenses']))
                } for row in monthly_data
            ]

            # Get weekly income vs expenses for dashboard line chart (exclude reversals)
            cursor.execute("""
                SELECT
                    MIN(transaction_date) as week_start,
                    strftime('%Y-%W', transaction_date) as year_week,
                    SUM(CASE WHEN account = 'Income' THEN credit ELSE 0 END) as income,
                    SUM(CASE WHEN account = 'Expenses' THEN debit ELSE 0 END) as expenses
                FROM financial_ledger
                WHERE user_id = ? AND transaction_date BETWEEN ? AND ?
                    AND is_reversal = 0
                GROUP BY strftime('%Y-%W', transaction_date)
                ORDER BY year_week
            """, (user_id, start_date_str, current_date_str))
            weekly_data = self._rows_to_dicts(cursor.fetchall())

            # Format weekly data
            weekly_income_expenses = []
            for row in weekly_data:
                weekly_income_expenses.append({
                    'week_start': row['week_start'],  # Already a string from SQLite
                    'income': float(self._from_money_str(row['income'])),
                    'expenses': float(self._from_money_str(row['expenses']))
                })

            # Get weekly expenses by category - monthly categories show as weekly average
            cursor.execute("""
                SELECT
                    MIN(l.transaction_date) as week_start,
                    strftime('%Y-%W', l.transaction_date) as year_week,
                    c.name as category,
                    c.color,
                    c.is_monthly,
                    SUM(l.debit) as amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = ?
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN ? AND ?
                    AND l.category_id IS NOT NULL
                GROUP BY strftime('%Y-%W', l.transaction_date), c.category_id, c.name, c.color, c.is_monthly
                ORDER BY year_week, amount DESC
            """, (user_id, start_date_str, current_date_str))
            weekly_expenses_raw = self._rows_to_dicts(cursor.fetchall())

            # Build a complete weekly series and smooth monthly categories across all weeks
            # 1) Collect all ISO weeks in range (week starts Monday)
            def week_monday(d):
                if isinstance(d, str):
                    # Try datetime format first (with time), then date-only format
                    try:
                        d = datetime.datetime.strptime(d, '%Y-%m-%d %H:%M:%S').date()
                    except ValueError:
                        d = datetime.datetime.strptime(d, '%Y-%m-%d').date()
                elif isinstance(d, datetime.datetime):
                    d = d.date()
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
                    raw_ws = row['week_start']  # Already a string from SQLite
                    # Normalize to Monday of that week for consistent x-axis
                    ws = week_monday(raw_ws)
                    key = (ws, row['category'])
                    non_monthly_map[key] = {
                        'week_start': ws.strftime('%Y-%m-%d'),
                        'category': row['category'],
                        'color': row['color'],
                        'is_monthly': False,
                        'amount': round(float(self._from_money_str(row['amount'])), 2)
                    }

            # 3) Compute monthly totals for monthly categories
            cursor.execute("""
                SELECT
                    strftime('%Y-%m', l.transaction_date) as ym,
                    c.name as category,
                    c.color,
                    SUM(l.debit) as monthly_amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = ?
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN ? AND ?
                    AND l.category_id IS NOT NULL
                    AND c.is_monthly = 1
                GROUP BY ym, c.category_id, c.name, c.color
            """, (user_id, start_date_str, current_date_str))
            monthly_totals = self._rows_to_dicts(cursor.fetchall())

            monthly_map = {}  # (ym, category) -> {color, monthly_amount}
            monthly_categories = set()
            for row in monthly_totals:
                ym = row['ym']
                cat = row['category']
                monthly_map[(ym, cat)] = {
                    'color': row['color'],
                    'monthly_amount': float(self._from_money_str(row['monthly_amount']))
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
                    strftime('%Y-%m', l.transaction_date) as month,
                    c.name as category,
                    c.color,
                    SUM(l.debit) as amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = ?
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN ? AND ?
                    AND l.category_id IS NOT NULL
                GROUP BY strftime('%Y-%m', l.transaction_date), c.category_id, c.name, c.color
                ORDER BY month, amount DESC
            """, (user_id, start_date, current_date))
            expenses_over_time = self._rows_to_dicts(cursor.fetchall())

            # Get weekly expenses by category for trends chart
            cursor.execute("""
                SELECT
                    MIN(l.transaction_date) as week_start,
                    strftime('%Y-%W', l.transaction_date) as year_week,
                    c.name as category,
                    c.color,
                    SUM(l.debit) as amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = ?
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN ? AND ?
                    AND l.category_id IS NOT NULL
                GROUP BY strftime('%Y-%W', l.transaction_date), c.category_id, c.name, c.color
                ORDER BY year_week, amount DESC
            """, (user_id, start_date_str, current_date_str))
            weekly_expenses_raw = self._rows_to_dicts(cursor.fetchall())

            # Format weekly expenses data
            weekly_expenses_by_category = []
            for row in weekly_expenses_raw:
                # Check if week_start is a string or datetime object
                week_start_val = row['week_start']
                if isinstance(week_start_val, str):
                    formatted_week_start = week_start_val
                elif week_start_val:
                    formatted_week_start = week_start_val.strftime('%Y-%m-%d')
                else:
                    formatted_week_start = None

                weekly_expenses_by_category.append({
                    'week_start': formatted_week_start,
                    'category': row['category'],
                    'color': row['color'],
                    'amount': float(row['amount'] or 0)
                })

            # Get assets vs liabilities over time (area chart)
            # Use effective_start_date_str to avoid showing zeros before first transaction
            cursor.execute("""
                SELECT DATE(transaction_date) as date,
                    SUM(CASE WHEN a.type IN ('CHECKING', 'SAVINGS', 'CASH', 'INVESTMENT', 'FIXED_ASSET') THEN debit - credit ELSE 0 END) as asset_change,
                    SUM(CASE WHEN a.type IN ('LOAN', 'CREDIT_CARD') THEN credit - debit ELSE 0 END) as liability_change
                FROM financial_ledger l
                JOIN accounts a ON l.account = a.name AND l.user_id = a.user_id
                WHERE l.user_id = ? AND transaction_date BETWEEN ? AND ?
                GROUP BY DATE(transaction_date)
                ORDER BY date
            """, (user_id, effective_start_date_str, current_date_str))
            daily_balance_changes = self._rows_to_dicts(cursor.fetchall())

            # Calculate starting assets and liabilities at the effective start date
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN a.type IN ('CHECKING', 'SAVINGS', 'CASH', 'INVESTMENT', 'FIXED_ASSET') THEN debit - credit ELSE 0 END) as starting_assets,
                    SUM(CASE WHEN a.type IN ('LOAN', 'CREDIT_CARD') THEN credit - debit ELSE 0 END) as starting_liabilities
                FROM financial_ledger l
                JOIN accounts a ON l.account = a.name AND l.user_id = a.user_id
                WHERE l.user_id = ? AND transaction_date < ?
            """, (user_id, effective_start_date_str))
            starting = self._row_to_dict(cursor.fetchone())
            cumulative_assets = float(starting['starting_assets'] or 0) if starting else 0.0
            cumulative_liabilities = float(starting['starting_liabilities'] or 0) if starting else 0.0

            # Start with the balance at the beginning of the effective period
            assets_vs_liabilities = [{
                'date': effective_start_date_str,
                'assets': float(cumulative_assets),
                'liabilities': float(cumulative_liabilities)
            }]
            for row in daily_balance_changes:
                cumulative_assets += float(row['asset_change'] or 0)
                cumulative_liabilities += float(row['liability_change'] or 0)
                # Check if date is a string or datetime object
                date_val = row['date']
                if isinstance(date_val, str):
                    formatted_date = date_val
                else:
                    formatted_date = date_val.strftime('%Y-%m-%d')

                assets_vs_liabilities.append({
                    'date': formatted_date,
                    'assets': float(cumulative_assets),
                    'liabilities': float(cumulative_liabilities)
                })

            # Get top 5 expense categories (horizontal bar)
            cursor.execute("""
                SELECT c.name, c.color, SUM(l.debit) as amount
                FROM financial_ledger l
                LEFT JOIN expense_categories c ON l.category_id = c.category_id
                WHERE l.user_id = ?
                    AND l.account = 'Expenses'
                    AND l.transaction_date BETWEEN ? AND ?
                    AND l.category_id IS NOT NULL
                GROUP BY c.category_id, c.name, c.color
                ORDER BY amount DESC
                LIMIT 5
            """, (user_id, start_date, current_date))
            top_categories = self._rows_to_dicts(cursor.fetchall())

            # Get credit balance over time (credit cards + loans)
            # First, get all credit accounts for this user
            cursor.execute("""
                SELECT account_id, name, type
                FROM accounts
                WHERE user_id = ? AND type IN ('CREDIT_CARD', 'LOAN')
                ORDER BY name
            """, (user_id,))
            credit_accounts = self._rows_to_dicts(cursor.fetchall())

            # Get daily balance changes for credit accounts
            cursor.execute("""
                SELECT DATE(transaction_date) as date,
                    a.account_id,
                    a.name as account_name,
                    a.type as account_type,
                    SUM(credit - debit) as daily_change
                FROM financial_ledger l
                JOIN accounts a ON l.account = a.name AND l.user_id = a.user_id
                WHERE l.user_id = ?
                    AND a.type IN ('CREDIT_CARD', 'LOAN')
                    AND transaction_date BETWEEN ? AND ?
                GROUP BY DATE(transaction_date), a.account_id, a.name, a.type
                ORDER BY date, a.name
            """, (user_id, start_date, current_date))
            daily_credit_changes = self._rows_to_dicts(cursor.fetchall())

            # Calculate starting balance for each credit account before the period
            cursor.execute("""
                SELECT
                    a.account_id,
                    a.name as account_name,
                    a.type as account_type,
                    SUM(credit - debit) as balance_before_period
                FROM financial_ledger l
                JOIN accounts a ON l.account = a.name AND l.user_id = a.user_id
                WHERE l.user_id = ?
                    AND a.type IN ('CREDIT_CARD', 'LOAN')
                    AND transaction_date < ?
                GROUP BY a.account_id, a.name, a.type
            """, (user_id, start_date_str))
            starting_balances = self._rows_to_dicts(cursor.fetchall())

            # Build a map of starting balances by account_id
            starting_balance_map = {}
            for row in starting_balances:
                starting_balance_map[row['account_id']] = float(row['balance_before_period'] or 0)

            # Build cumulative balance by date for each account
            credit_balance_by_account = {}
            for account in credit_accounts:
                account_id = account['account_id']
                account_name = account['name']
                account_type = account['type']

                # Initialize with starting balance
                cumulative = starting_balance_map.get(account_id, 0.0)
                credit_balance_by_account[account_id] = {
                    'account_id': account_id,
                    'account_name': account_name,
                    'account_type': account_type,
                    'starting_balance': cumulative,  # Include starting balance for chart
                    'balances': {
                        start_date_str: cumulative  # Add starting balance as first data point
                    }
                }

                # Add daily changes
                for row in daily_credit_changes:
                    if row['account_id'] == account_id:
                        cumulative += float(row['daily_change'] or 0)
                        # Check if date is a string or datetime object
                        date_val = row['date']
                        if isinstance(date_val, str):
                            date_str = date_val
                        else:
                            date_str = date_val.strftime('%Y-%m-%d')
                        credit_balance_by_account[account_id]['balances'][date_str] = float(cumulative)

            # Calculate total credit balance trend (sum of all selected accounts)
            # Get all unique dates
            all_dates = set()
            for row in daily_credit_changes:
                # Check if date is a string or datetime object
                date_val = row['date']
                if isinstance(date_val, str):
                    all_dates.add(date_val)
                else:
                    all_dates.add(date_val.strftime('%Y-%m-%d'))
            all_dates = sorted(list(all_dates))

            credit_balance_trend = []
            for date_str in all_dates:
                total_balance = 0.0
                for account_id, account_data in credit_balance_by_account.items():
                    # Find the most recent balance for this date or before
                    balance = None
                    for d in sorted(account_data['balances'].keys()):
                        if d <= date_str:
                            balance = account_data['balances'][d]
                    if balance is not None:
                        total_balance += balance
                    else:
                        # Use starting balance if no transactions yet
                        total_balance += starting_balance_map.get(account_id, 0.0)

                credit_balance_trend.append({
                    'date': date_str,
                    'total_balance': round(total_balance, 2)
                })

            # Get weekly business income vs expenses (is_business = 1)
            cursor.execute("""
                SELECT
                    MIN(transaction_date) as week_start,
                    strftime('%Y-%W', transaction_date) as year_week,
                    SUM(CASE WHEN account = 'Income' THEN credit ELSE 0 END) as income,
                    SUM(CASE WHEN account = 'Expenses' THEN debit ELSE 0 END) as expenses
                FROM financial_ledger
                WHERE user_id = ? AND transaction_date BETWEEN ? AND ?
                    AND is_reversal = 0
                    AND is_business = 1
                GROUP BY strftime('%Y-%W', transaction_date)
                ORDER BY year_week
            """, (user_id, start_date_str, current_date_str))
            business_weekly_data = self._rows_to_dicts(cursor.fetchall())
            business_weekly = [
                {
                    'week_start': row['week_start'],
                    'income': float(self._from_money_str(row['income'])),
                    'expenses': float(self._from_money_str(row['expenses']))
                } for row in business_weekly_data
            ]

            # Get average monthly personal expenses for RUNWAY calculation
            # Always use 90 days (or all data if less exists) - independent of date range selector
            runway_start = current_date - datetime.timedelta(days=90)
            runway_start_str = self._to_datetime_str(runway_start)

            cursor.execute("""
                SELECT AVG(monthly_total) as avg_monthly, COUNT(*) as month_count
                FROM (
                    SELECT SUM(debit) as monthly_total
                    FROM financial_ledger
                    WHERE user_id = ? AND account = 'Expenses'
                        AND is_reversal = 0
                        AND is_business = 0
                        AND transaction_date BETWEEN ? AND ?
                    GROUP BY strftime('%Y-%m', transaction_date)
                )
            """, (user_id, runway_start_str, current_date_str))
            personal_avg_result = self._row_to_dict(cursor.fetchone())
            personal_monthly_avg = float(self._from_money_str(personal_avg_result['avg_monthly'])) if personal_avg_result and personal_avg_result['avg_monthly'] else 0.0
            runway_months_of_data = int(personal_avg_result['month_count'] or 0) if personal_avg_result else 0

            return {
                'total_income': total_income,
                'total_expenses': total_expenses,
                'net_income': total_income - total_expenses,
                'savings_rate': round(savings_rate, 1),
                'spending_by_category': spending_by_category,
                'income_by_description': income_by_description,
                'income_by_category': income_by_category,
                'net_worth_trend': net_worth_trend,
                'income_vs_expenses': income_vs_expenses,
                'weekly_income_expenses': weekly_income_expenses,
                'business_weekly': business_weekly,
                'personal_monthly_avg': personal_monthly_avg,
                'runway_months_of_data': runway_months_of_data,
                'expenses_over_time': expenses_over_time,
                'weekly_expenses_by_category': weekly_expenses_by_category,
                'assets_vs_liabilities': assets_vs_liabilities,
                'top_categories': top_categories,
                'credit_accounts': [{'account_id': a['account_id'], 'name': a['name'], 'type': a['type']} for a in credit_accounts],
                'credit_balance_by_account': credit_balance_by_account,
                'credit_balance_trend': credit_balance_trend,
                'period_days': days
            }
        finally:
            cursor.close()
            conn.close()

    # =========================================================================
    # BUDGET MANAGEMENT
    # =========================================================================

    def get_budgets(self, user_id):
        """Get all budgets for a user with current month spending"""
        conn, cursor = self._get_db_connection()
        try:
            # Get current month's date range
            current_date_raw = self._get_user_current_date(cursor, user_id)
            # Convert to datetime if it's a string
            if isinstance(current_date_raw, str):
                current_date = datetime.datetime.strptime(current_date_raw[:10], '%Y-%m-%d')
            else:
                current_date = current_date_raw
            month_start = current_date.replace(day=1).strftime('%Y-%m-%d')
            # Get last day of month
            if current_date.month == 12:
                next_month = current_date.replace(year=current_date.year + 1, month=1, day=1)
            else:
                next_month = current_date.replace(month=current_date.month + 1, day=1)
            month_end = (next_month - datetime.timedelta(days=1)).strftime('%Y-%m-%d')

            query = """
                SELECT b.budget_id, b.category_id, b.monthly_limit,
                       c.name as category_name, c.color as category_color,
                       COALESCE(SUM(CASE
                           WHEN l.transaction_date >= ? AND l.transaction_date <= ?
                           AND l.account = 'Expenses' AND l.is_reversal = 0
                           THEN CAST(l.debit AS REAL)
                           ELSE 0
                       END), 0) as spent
                FROM budgets b
                JOIN expense_categories c ON b.category_id = c.category_id
                LEFT JOIN financial_ledger l ON l.category_id = b.category_id AND l.user_id = b.user_id
                WHERE b.user_id = ?
                GROUP BY b.budget_id, b.category_id, b.monthly_limit, c.name, c.color
                ORDER BY c.name
            """
            cursor.execute(query, (month_start, month_end, user_id))
            budgets = self._rows_to_dicts(cursor.fetchall())

            # Calculate percentages and status
            for budget in budgets:
                limit = float(budget['monthly_limit'])
                spent = float(budget['spent'])
                budget['percentage'] = (spent / limit * 100) if limit > 0 else 0
                budget['remaining'] = limit - spent
                if budget['percentage'] >= 100:
                    budget['status'] = 'exceeded'
                elif budget['percentage'] >= 80:
                    budget['status'] = 'warning'
                else:
                    budget['status'] = 'ok'

            return budgets
        finally:
            cursor.close()
            conn.close()

    def set_budget(self, user_id, category_id, monthly_limit):
        """Set or update a budget for a category"""
        conn, cursor = self._get_db_connection()
        try:
            # Use INSERT OR REPLACE to handle both new and existing budgets
            cursor.execute("""
                INSERT OR REPLACE INTO budgets (user_id, category_id, monthly_limit)
                VALUES (?, ?, ?)
            """, (user_id, category_id, str(monthly_limit)))
            conn.commit()
            return True, "Budget saved successfully"
        except Exception as e:
            conn.rollback()
            return False, f"Failed to save budget: {e}"
        finally:
            cursor.close()
            conn.close()

    def delete_budget(self, user_id, budget_id):
        """Delete a budget"""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("DELETE FROM budgets WHERE budget_id = ? AND user_id = ?", (budget_id, user_id))
            conn.commit()
            return True, "Budget deleted"
        except Exception as e:
            conn.rollback()
            return False, f"Failed to delete budget: {e}"
        finally:
            cursor.close()
            conn.close()

    # =========================================================================
    # SAVINGS GOALS
    # =========================================================================

    def get_savings_goals(self, user_id):
        """Get all savings goals for a user"""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("""
                SELECT g.goal_id, g.name, g.target_amount, g.current_amount, g.target_date,
                       g.color, g.icon, g.created_at, g.completed_at, g.account_id,
                       a.name as account_name, a.balance as account_balance
                FROM savings_goals g
                LEFT JOIN accounts a ON g.account_id = a.account_id
                WHERE g.user_id = ?
                ORDER BY g.completed_at IS NOT NULL, g.target_date, g.name
            """, (user_id,))
            goals = self._rows_to_dicts(cursor.fetchall())

            # Calculate percentages - use account balance if linked
            for goal in goals:
                target = float(goal['target_amount'])
                # If linked to an account, use account balance as current amount
                if goal['account_id'] and goal['account_balance'] is not None:
                    current = float(goal['account_balance'])
                    goal['current_amount'] = str(current)
                    goal['uses_account_balance'] = True
                else:
                    current = float(goal['current_amount'])
                    goal['uses_account_balance'] = False
                goal['percentage'] = (current / target * 100) if target > 0 else 0
                goal['remaining'] = target - current

            return goals
        finally:
            cursor.close()
            conn.close()

    def add_savings_goal(self, user_id, name, target_amount, target_date=None, color='#10b981', icon='piggy-bank', account_id=None):
        """Add a new savings goal"""
        conn, cursor = self._get_db_connection()
        try:
            # Check if account is already linked to another goal
            if account_id:
                cursor.execute(
                    "SELECT goal_id, name FROM savings_goals WHERE user_id = ? AND account_id = ?",
                    (user_id, account_id)
                )
                existing = cursor.fetchone()
                if existing:
                    return False, f"This account is already linked to goal '{existing[1]}'"

            cursor.execute("""
                INSERT INTO savings_goals (user_id, name, target_amount, target_date, color, icon, account_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, name, str(target_amount), target_date, color, icon, account_id))
            conn.commit()
            return True, cursor.lastrowid
        except Exception as e:
            conn.rollback()
            return False, f"Failed to add goal: {e}"
        finally:
            cursor.close()
            conn.close()

    def update_savings_goal(self, user_id, goal_id, name=None, target_amount=None, current_amount=None, target_date=None, color=None, icon=None, account_id=None, clear_account=False):
        """Update a savings goal"""
        conn, cursor = self._get_db_connection()
        try:
            # Check if account is already linked to another goal (not this one)
            if account_id and not clear_account:
                cursor.execute(
                    "SELECT goal_id, name FROM savings_goals WHERE user_id = ? AND account_id = ? AND goal_id != ?",
                    (user_id, account_id, goal_id)
                )
                existing = cursor.fetchone()
                if existing:
                    return False, f"This account is already linked to goal '{existing[1]}'"

            # Build dynamic update query
            updates = []
            params = []
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if target_amount is not None:
                updates.append("target_amount = ?")
                params.append(str(target_amount))
            if current_amount is not None:
                updates.append("current_amount = ?")
                params.append(str(current_amount))
                # Check if goal is now complete
                cursor.execute("SELECT target_amount FROM savings_goals WHERE goal_id = ? AND user_id = ?", (goal_id, user_id))
                row = cursor.fetchone()
                if row and float(current_amount) >= float(row[0]):
                    updates.append("completed_at = CURRENT_TIMESTAMP")
                else:
                    updates.append("completed_at = NULL")
            if target_date is not None:
                updates.append("target_date = ?")
                params.append(target_date)
            if color is not None:
                updates.append("color = ?")
                params.append(color)
            if icon is not None:
                updates.append("icon = ?")
                params.append(icon)
            if clear_account:
                updates.append("account_id = NULL")
            elif account_id is not None:
                updates.append("account_id = ?")
                params.append(account_id)

            if not updates:
                return False, "No updates provided"

            params.extend([goal_id, user_id])
            query = f"UPDATE savings_goals SET {', '.join(updates)} WHERE goal_id = ? AND user_id = ?"
            cursor.execute(query, params)
            conn.commit()
            return True, "Goal updated"
        except Exception as e:
            conn.rollback()
            return False, f"Failed to update goal: {e}"
        finally:
            cursor.close()
            conn.close()

    def contribute_to_goal(self, user_id, goal_id, amount):
        """Add or withdraw money from a savings goal (positive = add, negative = withdraw)"""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("SELECT current_amount, target_amount FROM savings_goals WHERE goal_id = ? AND user_id = ?", (goal_id, user_id))
            row = cursor.fetchone()
            if not row:
                return False, "Goal not found"

            current = float(row[0])
            target = float(row[1])
            new_amount = current + float(amount)

            # Don't allow negative balance
            if new_amount < 0:
                return False, "Cannot withdraw more than current balance"

            # Update amount and check if complete
            if new_amount >= target:
                cursor.execute("""
                    UPDATE savings_goals
                    SET current_amount = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE goal_id = ? AND user_id = ?
                """, (str(new_amount), goal_id, user_id))
            else:
                # If withdrawing from a completed goal, mark it incomplete
                cursor.execute("""
                    UPDATE savings_goals SET current_amount = ?, completed_at = NULL
                    WHERE goal_id = ? AND user_id = ?
                """, (str(new_amount), goal_id, user_id))

            conn.commit()
            action = "added" if float(amount) >= 0 else "withdrawn"
            return True, f"Amount {action} successfully"
        except Exception as e:
            conn.rollback()
            return False, f"Failed to contribute: {e}"
        finally:
            cursor.close()
            conn.close()

    def delete_savings_goal(self, user_id, goal_id):
        """Delete a savings goal"""
        conn, cursor = self._get_db_connection()
        try:
            cursor.execute("DELETE FROM savings_goals WHERE goal_id = ? AND user_id = ?", (goal_id, user_id))
            conn.commit()
            return True, "Goal deleted"
        except Exception as e:
            conn.rollback()
            return False, f"Failed to delete goal: {e}"
        finally:
            cursor.close()
            conn.close()