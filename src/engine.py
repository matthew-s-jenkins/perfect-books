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
        self._load_state()
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

    # --- Public API Methods (Data Retrieval) ---
    def get_status_summary(self):
        conn, cursor = self._get_db_connection()
        loans_query = "SELECT SUM(outstanding_balance) as total_debt FROM loans WHERE status = 'ACTIVE'"
        cursor.execute(loans_query)
        debt_result = cursor.fetchone()
        summary = {
            'cash': float(self.cash),
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
        
        self._save_state()
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
