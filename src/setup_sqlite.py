"""
Perfect Books - SQLite Database Setup & Initialization

This module creates and initializes the Perfect Books SQLite database schema.
It creates all tables with proper foreign key relationships and indexes.

Database Schema Overview:
------------------------
- users: User authentication and account management
- accounts: Financial accounts (checking, savings, credit cards, loans, etc.)
- financial_ledger: Double-entry accounting ledger (immutable audit trail)
- expense_categories: User-defined expense categorization with colors
- recurring_expenses: Automated monthly bill payments with categories
- recurring_income: Automated income deposits (paychecks, etc.)
- loans: Debt tracking with payment schedules
- schema_version: Track applied database migrations

Key Design Features:
- Foreign key constraints for referential integrity
- Indexes on frequently queried columns for performance
- Cascade deletes for user data (complete user removal)
- TEXT storage for monetary values (preserves exact precision)
- Category support for expense tracking and analytics
- Reversal tracking for transaction corrections

Author: Matthew Jenkins
License: MIT
"""

import sqlite3
from pathlib import Path
from datetime import datetime


def get_db_path():
    """Return the path to the SQLite database file"""
    return Path(__file__).parent / "data" / "perfectbooks.db"


def create_database():
    """
    Create a fresh Perfect Books SQLite database with all tables.

    [WARNING]  WARNING: If the database already exists, this will NOT drop it.
    Use reset_database() if you want to start fresh.
    """
    db_path = get_db_path()

    # Create data directory if it doesn't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect to SQLite database (creates file if doesn't exist)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Enable foreign key constraints (CRITICAL for data integrity)
    cursor.execute("PRAGMA foreign_keys = ON;")

    print(f"--- Creating Perfect Books Database ---")
    print(f"Location: {db_path}")
    print()

    try:
        # =================================================================
        # TABLE 1: users - User authentication
        # =================================================================
        print("Creating table 'users'...", end=" ")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("OK")

        # =================================================================
        # TABLE 2: accounts - Financial accounts
        # =================================================================
        print("Creating table 'accounts'...", end=" ")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                type TEXT CHECK(type IN ('CHECKING', 'SAVINGS', 'CREDIT_CARD', 'CASH', 'LOAN', 'FIXED_ASSET', 'EQUITY')) NOT NULL,
                balance TEXT NOT NULL DEFAULT '0.00',
                interest_rate REAL DEFAULT NULL,
                last_interest_date TEXT DEFAULT NULL,
                credit_limit TEXT DEFAULT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id);")
        print("OK")

        # =================================================================
        # TABLE 3: expense_categories - User-defined categories
        # =================================================================
        print("Creating table 'expense_categories'...", end=" ")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expense_categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                color TEXT DEFAULT '#6366f1',
                is_default INTEGER DEFAULT 0,
                is_monthly INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                UNIQUE(user_id, name)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_categories_user_id ON expense_categories(user_id);")
        print("OK")

        # =================================================================
        # TABLE 4: financial_ledger - Double-entry accounting ledger
        # =================================================================
        print("Creating table 'financial_ledger'...", end=" ")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_ledger (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                transaction_uuid TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                account TEXT NOT NULL,
                description TEXT,
                debit TEXT DEFAULT '0.00',
                credit TEXT DEFAULT '0.00',
                category_id INTEGER DEFAULT NULL,
                is_reversal INTEGER DEFAULT 0,
                reversal_of_id INTEGER DEFAULT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_user_date ON financial_ledger(user_id, transaction_date DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_category ON financial_ledger(category_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_reversal ON financial_ledger(is_reversal);")
        print("OK")

        # =================================================================
        # TABLE 5: recurring_expenses - Automated bill payments
        # =================================================================
        print("Creating table 'recurring_expenses'...", end=" ")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recurring_expenses (
                expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                amount TEXT NOT NULL,
                frequency TEXT CHECK(frequency IN ('DAILY', 'WEEKLY', 'MONTHLY')) NOT NULL,
                due_day_of_month INTEGER NOT NULL DEFAULT 1,
                last_processed_date TEXT DEFAULT NULL,
                payment_account_id INTEGER DEFAULT NULL,
                category_id INTEGER DEFAULT NULL,
                is_variable INTEGER DEFAULT 0,
                estimated_amount TEXT DEFAULT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES expense_categories(category_id) ON DELETE SET NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recurring_expenses_user_id ON recurring_expenses(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recurring_expenses_category_id ON recurring_expenses(category_id);")
        print("OK")

        # =================================================================
        # TABLE 6: recurring_income - Automated income deposits
        # =================================================================
        print("Creating table 'recurring_income'...", end=" ")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recurring_income (
                income_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT NULL,
                amount TEXT NOT NULL,
                frequency TEXT CHECK(frequency IN ('DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY')) NOT NULL,
                destination_account_id INTEGER NOT NULL,
                last_processed_date TEXT DEFAULT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_variable INTEGER DEFAULT 0,
                estimated_amount TEXT DEFAULT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (destination_account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recurring_income_user_id ON recurring_income(user_id);")
        print("OK")

        # =================================================================
        # TABLE 7: loans - Debt tracking with payment schedules
        # =================================================================
        print("Creating table 'loans'...", end=" ")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loans (
                loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                principal_amount TEXT NOT NULL,
                outstanding_balance TEXT NOT NULL,
                interest_rate REAL NOT NULL,
                monthly_payment TEXT NOT NULL,
                next_payment_date TEXT NOT NULL,
                status TEXT CHECK(status IN ('ACTIVE', 'PAID')) NOT NULL DEFAULT 'ACTIVE',
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_loans_user_id ON loans(user_id);")
        print("OK")

        # =================================================================
        # TABLE 8: schema_version - Migration tracking
        # =================================================================
        print("Creating table 'schema_version'...", end=" ")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("OK")

        # Commit all changes
        conn.commit()
        print()
        print("[OK] Database schema created successfully!")
        print(f"[OK] Database file: {db_path}")

        return True

    except sqlite3.Error as err:
        print(f"\n[ERROR] Error creating database: {err}")
        conn.rollback()
        return False

    finally:
        conn.close()


def reset_database():
    """
    [WARNING]  DANGER: Delete the existing database and create a fresh one.
    All data will be permanently lost!
    """
    db_path = get_db_path()

    if db_path.exists():
        print(f"[WARNING]  WARNING: Deleting existing database at {db_path}")
        db_path.unlink()
        print("[OK] Old database deleted")

    return create_database()


def verify_schema():
    """Verify that all tables and indexes exist"""
    db_path = get_db_path()

    if not db_path.exists():
        print("[ERROR] Database does not exist")
        return False

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Expected tables
    expected_tables = [
        'users',
        'accounts',
        'expense_categories',
        'financial_ledger',
        'recurring_expenses',
        'recurring_income',
        'loans',
        'schema_version'
    ]

    print("Verifying database schema...")
    print()

    # Check each table exists
    for table in expected_tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if cursor.fetchone():
            print(f"[OK] Table '{table}' exists")
        else:
            print(f"[ERROR] Table '{table}' MISSING")
            conn.close()
            return False

    # Check foreign keys are enabled
    cursor.execute("PRAGMA foreign_keys;")
    fk_status = cursor.fetchone()[0]
    print()
    print(f"Foreign key enforcement: {'[OK] ENABLED' if fk_status else '[ERROR] DISABLED (WARNING!)'}")

    conn.close()
    print()
    print("[OK] Schema verification complete")
    return True


def get_table_info(table_name):
    """Display schema information for a specific table"""
    db_path = get_db_path()

    if not db_path.exists():
        print("[ERROR] Database does not exist")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()

    print(f"\nTable: {table_name}")
    print("=" * 80)
    print(f"{'Column':<25} {'Type':<15} {'NotNull':<10} {'Default':<20}")
    print("-" * 80)

    for col in columns:
        cid, name, col_type, notnull, default_val, pk = col
        print(f"{name:<25} {col_type:<15} {str(bool(notnull)):<10} {str(default_val):<20}")

    # Show indexes
    cursor.execute(f"PRAGMA index_list({table_name});")
    indexes = cursor.fetchall()

    if indexes:
        print()
        print("Indexes:")
        for idx in indexes:
            seq, name, unique, origin, partial = idx
            print(f"  - {name} {'(UNIQUE)' if unique else ''}")

    conn.close()


if __name__ == "__main__":
    print("=" * 80)
    print("Perfect Books - SQLite Database Setup")
    print("=" * 80)
    print()

    db_path = get_db_path()

    if db_path.exists():
        print(f"Database already exists at: {db_path}")
        print()
        choice = input("Choose an option:\n  1. Verify existing schema\n  2. Reset database ([WARNING]  DELETES ALL DATA)\n  3. Cancel\n\nChoice: ")

        if choice == '1':
            verify_schema()
        elif choice == '2':
            confirm = input("\n[WARNING]  WARNING: This will DELETE ALL DATA. Type 'DELETE' to confirm: ")
            if confirm == 'DELETE':
                reset_database()
                verify_schema()
            else:
                print("Reset cancelled.")
        else:
            print("Cancelled.")
    else:
        print("No existing database found. Creating new database...")
        print()
        create_database()
        verify_schema()
