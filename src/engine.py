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
                "SELECT l.entry_id, l.transaction_uuid, l.transaction_date, l.description, l.account, l.debit, l.credit "
                "FROM financial_ledger l "
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
            current_date = transaction_date if transaction_date else self._get_user_current_date(cursor, user_id)
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

            # Debug: Check if expense exists
            cursor.execute("SELECT * FROM recurring_expenses WHERE expense_id = %s", (expense_id,))
            existing = cursor.fetchone()
            print(f"DEBUG: Trying to update expense_id={expense_id} for user_id={user_id}")
            print(f"DEBUG: Existing expense: {existing}")
            print(f"DEBUG: New values - description={description}, amount={amount}, due_day_of_month={due_day_of_month}")

            cursor.execute(
                "UPDATE recurring_expenses SET description = %s, amount = %s, due_day_of_month = %s WHERE expense_id = %s AND user_id = %s",
                (description, amount, due_day_of_month, expense_id, user_id)
            )
            print(f"DEBUG: cursor.rowcount = {cursor.rowcount}")

            # MySQL returns rowcount=0 when no rows are changed (even if the WHERE matched)
            # Instead, check if the expense exists with correct user_id
            if cursor.rowcount == 0 and not existing:
                return False, "Expense not found or you do not have permission to update it."

            if cursor.rowcount == 0 and existing and str(existing['user_id']) != str(user_id):
                return False, "Expense not found or you do not have permission to update it."

            conn.commit()
            return True, "Recurring expense updated successfully."
        except Exception as e:
            conn.rollback()
            return False, f"An error occurred: {e}"
        finally:
            cursor.close()
            conn.close()


    def log_expense(self, user_id, account_id, description, amount, transaction_date=None, cursor=None):
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
            current_date = transaction_date if transaction_date else self._get_user_current_date(cursor, user_id)
            uuid = f"expense-{user_id}-{int(time.time())}-{time.time()}"

            fin_query = "INSERT INTO financial_ledger (user_id, transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(fin_query, (user_id, uuid, current_date, 'Expenses', description, amount, 0))
            cursor.execute(fin_query, (user_id, uuid, current_date, account['name'], description, 0, amount))

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