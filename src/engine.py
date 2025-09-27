import os
from dotenv import load_dotenv
import mysql.connector
import datetime
import math
import random
import time
from decimal import Decimal

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
    # --- Core/Setup Methods ---
    def __init__(self):
        self.accounts = {}
        self.current_date = None
        self._load_accounts_and_date()
    
    def _get_db_connection(self):
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn, conn.cursor(dictionary=True, buffered=True)

    def _load_accounts_and_date(self):
        """Loads all accounts and the last transaction date from the database."""
        conn, cursor = self._get_db_connection()
        try:
            # Load all accounts into the self.accounts dictionary
            cursor.execute("SELECT * FROM accounts")
            for row in cursor.fetchall():
                self.accounts[row['account_id']] = {
                    'name': row['name'],
                    'type': row['type'],
                    'balance': row['balance']
                }
            print(f"Loaded {len(self.accounts)} account(s),")

            # Find the most recent transaction date to set as the current date
            cursor.execute("SELECT MAX(transaction_date) AS last_date FROM financial_ledger")
            result = cursor.fetchone()
            if result and result['last_date']:
                self.current_date = result['last_date']
            else:
                # If there are no transactions, it's a fresh start, use today's date
                self.current_date = datetime.datetime.now()
            print(f"Set current date to {self.current_date.date()}.")
        
        except mysql.connector.Error as err:
            print(f"Error loading state: {err}")
            # Sets defaults if loading fails
            self.accounts = {}
            self.current_date = datetime.datetime.now()
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()

    # --- Public API Methods (Data Retrieval) ---
    def get_status_summary(self):
        # Calculate total cash from asset accounts (Checking, Savings, Cash)
        total_cash = 0
        for acc_id, acc_data in self.accounts.items():
            if acc_data['type'] in ['CHECKING', 'SAVINGS', 'CASH']:
                total_cash += acc_data['balance']
        
        conn, cursor = self._get_db_connection()
        loans_query = "SELECT SUM(outstanding_balance) as total_debt FROM loans WHERE status = 'ACTIVE'"
        cursor.execute(loans_query)
        debt_result = cursor.fetchone()
        
        summary = {
            'cash': float(total_cash),
            'date': self.current_date,
            'total_debt': float(debt_result['total_debt']) if debt_result and debt_result['total_debt'] else 0.0,
        }
        cursor.close()
        conn.close()
        return summary
    
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
                 "WHERE account = 'Income' AND transaction_date >= %s "
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

    def get_accounts_list(self):
        """Returns the dictionary of all loaded accounts"""
        return self.accounts
    
    def get_ledger_entries(self, limit=50):
        """Fetches the most recent financial ledger entries from the database."""
        conn, cursor = self._get_db_connection()
        try:
            # Fetches the last 50 entries, ordered with the most recent first.
            # This provides a reverse-chronological history of transactions.
            query = (
                "SELECT transaction_date, description, account, debit, credit "
                "FROM financial_ledger "
                "ORDER BY entry_id DESC "
                "LIMIT %s"
            )
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            return results
        except mysql.connector.Error as err:
            print(f"Database error fetching ledger: {err}")
            return [] # Return an empty list on error
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()

    # --- Public API Methods (Actions) ---
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

    def add_recurring_expense(self, description, account, amount, frequency='MONTHLY'):
        """Adds a new recurring expense to the database"""
        try:
            conn, cursor = self._get_db_connection()
            query = "INSERT INTO recurring_expenses (description, account, amount, frequency) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (description, account, amount, frequency))
            conn.commit()
            return True, f"Successfully added expense: {description}"
        except mysql.connector.Error as err:
            conn.rollback()
            return False, f"Database error: {err}"
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()

    def log_income(self, account_id, description, amount):
        """Logs an income transaction to a specific account."""
        try:
            # 1. Input Validation
            amount = Decimal(amount)
            if amount <= 0:
                return False, "Income amount must be positive."
            if account_id not in self.accounts:
                return False, "Invalid account specified."

            # 2. Update Balance in Memory
            self.accounts[account_id]['balance'] += amount
            
            # 3. Get Database Connection & Account Name
            conn, cursor = self._get_db_connection()
            account_name = self.accounts[account_id]['name']
            uuid = f"income-{int(time.time())}-{account_id}"

            # 4. Record Double-Entry Transaction
            fin_query = "INSERT INTO financial_ledger (transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s)"
            # Debit the specific asset account (e.g., 'Chase Checking')
            cursor.execute(fin_query, (uuid, self.current_date, account_name, description, amount, 0))
            # Credit Income (which increases Equity)
            cursor.execute(fin_query, (uuid, self.current_date, 'Income', description, 0, amount))

            # 5. Persist the New Balance to the Database
            update_query = "UPDATE accounts SET balance = %s WHERE account_id = %s"
            cursor.execute(update_query, (self.accounts[account_id]['balance'], account_id))

            # 6. Finalize Transaction
            conn.commit()
            return True, f"Successfully logged income to '{account_name}': ${amount:,.2f}"
        
        except Exception as e:
            if 'conn' in locals() and conn.is_connected():
                conn.rollback()
            # If something fails, revert the balance change in memory
            if 'account_id' in locals() and account_id in self.accounts:
                self.accounts[account_id]['balance'] -= amount
            return False, f"An error occurred while logging income: {e}"
        
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()
    
    def log_expense(self, account_id, description, amount):
        """Logs a one time expense to a specific account."""
        try:
            # 1. Input Validation
            amount = Decimal(amount)
            if amount <= 0:
                return False, "Expense amount must be positive."
            if account_id not in self.accounts:
                return False, "Invalid account specified."

            account_type = self.accounts[account_id]['type']
            current_balance = self.accounts[account_id]['balance']

            # 2. Sufficient Funds Check (for non-credit accounts)
            if account_type != 'CREDIT_CARD' and current_balance < amount:
                return False, f"Insufficient funds. Balance: ${current_balance:.2f}"

            # 3. Update Balance in Memory
            self.accounts[account_id]['balance'] -= amount
            
            # 4. Get Database Connection & Account Name
            conn, cursor = self._get_db_connection()
            account_name = self.accounts[account_id]['name']
            uuid = f"expense-{int(time.time())}-{account_id}"

            # 5. Record Double-Entry Transaction
            fin_query = "INSERT INTO financial_ledger (transaction_uuid, transaction_date, account, description, debit, credit) VALUES (%s, %s, %s, %s, %s, %s)"
            # Debit a general 'Expenses' account (which reduces equity)
            cursor.execute(fin_query, (uuid, self.current_date, 'Expenses', description, amount, 0))
            # Credit the specific asset/liability account used for payment
            cursor.execute(fin_query, (uuid, self.current_date, account_name, description, 0, amount))

            # 6. Persist the New Balance to the Database
            update_query = "UPDATE accounts SET balance = %s WHERE account_id = %s"
            cursor.execute(update_query, (self.accounts[account_id]['balance'], account_id))

            # 7. Finalize Transaction
            conn.commit()
            return True, f"Successfully logged expense from '{account_name}': ${amount:,.2f}"
        
        except Exception as e:
            if 'conn' in locals() and conn.is_connected():
                conn.rollback()
            # If something fails, revert the balance change in memory
            if 'account_id' in locals() and account_id in self.accounts:
                self.accounts[account_id]['balance'] += amount
            return False, f"An error occurred while logging expense: {e}"
        
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()

    def auto_advance_time(self):
        """Calculates elapsed days and runs the simulation to catch up to today."""
        today = datetime.datetime.now().date()
        last_run_date = self.current_date.date()

        if today > last_run_date:
            days_to_advance = (today - last_run_date).days
            print(f"Catching up... advancing time by {days_to_advance} day(s).")
            time.sleep(2) # Pause 2 seconds for effect
            return self.advance_time(days_to_advance)
        return None # Return nothing if no advance time was needed

    def advance_time(self, days_to_advance=1):
        log_messages = []

        for i in range(days_to_advance):
            log_messages.extend(self._apply_recurring_expenses())
            log_messages.extend(self._process_loan_payments())
                        
            self.current_date += datetime.timedelta(days=1)

        print("✅ Simulation advance complete.")
        return {'log': log_messages}

    # --- Internal Processing Methods (Helpers) ---
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
