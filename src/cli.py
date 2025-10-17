from engine import BusinessSimulator
import os
import sys
import mysql.connector
from dotenv import load_dotenv
import datetime

load_dotenv()

def print_status(sim):
    """Prints a formatted summary of the business status."""
    summary = sim.get_status_summary()
    os.system('cls' if os.name == 'nt' else 'clear') # Clear the screen
    print("=" * 60)
    print("      PERFECT BOOKS - FINANCIAL STATUS")
    print("=" * 60)
    print(f"Date: {summary['date'].strftime('%Y-%m-%d')}      Cash: ${summary['cash']:,.2f}")
    print("-" * 60)
    
def handle_advance_time(sim):
    """Handles user input for advancing time."""
    print("\n--- Advance Time ---")
    try:
        days = int(input("How many days to simulate? (1-30): "))
        if 1 <= days <= 30:
            sim.advance_time(days)
        else:
            print("Please enter a number between 1 and 30.")
    except ValueError:
        print("Invalid input. Please enter a number.")
    input("\nPress Enter to return to the menu...")

def handle_manage_expenses(sim):

    """Handles adding recurring expenses linked to a specific payment account."""
    print("\n--- Manage Recurring Expenses ---")
    
    # 1. Get and display a list of accounts to pay from
    accounts = sim.get_accounts_list()
    # You can't pay recurring bills with physical cash in this simulation
    payable_accounts = {k: v for k, v in accounts.items() if v['type'] != 'CASH'}

    if not payable_accounts:
        print("No accounts available to pay expenses from (e.g., Checking, Credit Card).")
        input("\nPress Enter to return to the menu...")
        return

    print("Which account will these recurring expenses be paid from?")
    account_options = list(payable_accounts.items())
    for i, (acc_id, acc_data) in enumerate(account_options):
        print(f"  [{i+1}] {acc_data['name']} (${acc_data['balance']:,.2f})")

    try:
        # 2. Get the user's choice for the payment account
        choice_str = input("> ")
        choice_idx = int(choice_str) - 1
        
        if not 0 <= choice_idx < len(account_options):
            print("Invalid selection.")
            input("\nPress Enter to return to the menu...")
            return
            
        selected_account_id = account_options[choice_idx][0]
        account_name = account_options[choice_idx][1]['name']
        print(f"\nAdding expenses to be paid from '{account_name}'.")

        # 3. Loop to add multiple expenses for this account
        while True:
            description = input("Enter new expense description (or type 'done' to finish): ")
            if description.lower() == 'done':
                break
            
            amount_str = input(f"Enter the monthly amount for '{description}': $")
            amount = float(amount_str.replace(',',''))

            # Call the updated engine function
            success, message = sim.add_recurring_expense(description, amount, selected_account_id)
            print(f"  -> {message}")

    except (ValueError, IndexError):
        print("  -> Invalid input. Please enter valid numbers.")
    
    input("\nPress Enter to return to the main menu...")

def handle_log_income(sim):
    """Handles user input for logging a new income transaction."""
    print("\n--- Log Income ---")

    # 1. Get and display a list of valid accounts to deposit into
    accounts = sim.get_accounts_list()
    # Only asset accounts can be deposited into, not credit cards (liabilities)
    deposit_accounts = {k: v for k, v in accounts.items() if v['type'] != 'CREDIT_CARD'}

    if not deposit_accounts:
        print("No valid deposit accounts (e.g., Credit, Savings) found.")
        input("\nPress Enter to return to the menu...")
        return
    
    print("Which account did you receive the income in?")
    # Create a list for the indexed selection
    account_options = list(deposit_accounts.items())
    for i, (acc_id, acc_data) in enumerate(account_options):
        print(f" [{i+1}] {acc_data['name']} (${acc_data["balance"]:,.2f})")
    
    try:
        # 2. Get the user's choice
        choice_str = input("> ")
        choice_idx = int(choice_str) - 1

        if not 0 <= choice_idx < len(account_options):
            print("Invalid selection.")
            input("\nPress Enter to return to the menu")
            return
        
        selected_account_id = account_options[choice_idx][0]

        # 3. Get transaction details
        description = input("Enter a description for this income (e.g., 'Paycheck'):")
        amount_str = input(f"Enter the amount: $")
        amount = float(amount_str)

        # 4. Call the Transaction
        success, message = sim.log_income(selected_account_id, description, amount)
        print(f" -> {message}")
    
    except (ValueError, IndexError):
        print(" -> Invalid input. Please enter valid numbers.")
    
    input("\nPress Enter to return to the main menu")

def handle_log_expense(sim):
    """Handles user input for logging a new one-time expense."""
    print("\n--- Log One-Time Expense ---")

    # 1. Get and display a list of valid accounts to deposit into
    accounts = sim.get_accounts_list()
    if not accounts:
        print("No accounts found.")
        input("\nPress Enter to return to the menu...")
        return
    
    print("Which account are you paying from?")
    # Create a list for the indexed selection
    account_options = list(accounts.items())
    for i, (acc_id, acc_data) in enumerate(account_options):
        print(f" [{i+1}] {acc_data['name']} (${acc_data["balance"]:,.2f})")
    
    try:
        # 2. Get the user's choice
        choice_str = input("> ")
        choice_idx = int(choice_str) - 1

        if not 0 <= choice_idx < len(account_options):
            print("Invalid selection.")
            input("\nPress Enter to return to the menu")
            return
        
        selected_account_id = account_options[choice_idx][0]

        # 3. Get transaction details
        description = input("Enter a description for this expense (e.g., 'Groceries'):")
        amount_str = input(f"Enter the amount: $")
        amount = float(amount_str)

        # 4. Call the engine to log the transaction
        success, message = sim.log_expense(selected_account_id, description, amount)
        print(f" -> {message}")
    
    except (ValueError, IndexError):
        print(" -> Invalid input. Please enter valid numbers.")
    
    input("\nPress Enter to return to the main menu")

def handle_view_accounts(sim):
    """Displays a formatted list of all accounts and their balances"""
    print("\n--- Your Accounts ---")
    accounts = sim.get_accounts_list()

    if not accounts:
        print("No accounts have been set up yet.")
    else:
        # Print a header for our table
        print(f"{'Account Name':<25} {'Type':<15} {'Balance':>15}")
        print("-" * 57)

        # Loop through the account data and print each row
        for acc_id, acc_data in accounts.items():
            name = acc_data['name'] 
            acc_type = acc_data['type']
            balance = acc_data['balance']
            print(f"{name:<25} {acc_type:<15} ${balance:>15,.2f}")
        
        input("\nPress Enter to return to the main menu")

def handle_view_ledger(sim):
    """Displays the most recent entries from the financial ledger."""
    print("\n--- Financial Ledger (Last 50 Entries) ---")
    entries = sim.get_ledger_entries()

    if not entries:
        print("No transactions have been recorded yet.")
    else:
        # Adjusted widths for better alignment
        print(f"{'Date':<12} {'Account':<25} {'Description':<25} {'Debit':>12} {'Credit':>12}")
        print("-" * 90)
    
        for entry in entries:
            date_str = entry['transaction_date'].strftime('%Y-%m-%d')
            account = entry['account']
            desc = entry['description']
            debit_str = f"${entry['debit']:,.2f}" if entry['debit'] > 0 else ""
            credit_str = f"${entry['credit']:,.2f}" if entry['credit'] > 0 else ""

            if len(desc) > 23:
                desc = desc[:20] + "..."

            # Adjusted f-string to match new widths
            print(f"{date_str:<12} {account:<25} {desc:<25} {debit_str:>12} {credit_str:>12}")
    
    input("\nPress Enter to return to the main menu...")

def run_setup_wizard():
    print("Welcome to Perfect Books! Let's set up your financial accounts.")
    accounts_to_add = []
    
    while True:
        print("\n--- Add a New Account ---")
        name = input("Account Name (e.g., 'Chase Checking', 'Visa Card'): ")
        if not name:
            print("Account name cannot be empty. Please try again.")
            continue

        print("Select Account Type: [1] Checking, [2] Savings, [3] Credit Card, [4] Cash")
        type_choice = input("> ")
        
        type_map = {'1': 'CHECKING', '2': 'SAVINGS', '3': 'CREDIT_CARD', '4': 'CASH'}
        account_type = type_map.get(type_choice)
        if not account_type:
            print("Invalid selection. Please try again.")
            continue

        try:
            balance_str = input(f"Current balance for '{name}': $")
            # --- NEW: Clean the input string ---
            balance = float(balance_str.replace(',', ''))
            
            # For credit cards, balance should be negative to represent debt
            if account_type == 'CREDIT_CARD' and balance > 0:
                balance = -balance
            
            credit_limit = None 
            if account_type == 'CREDIT_CARD':
                limit_str = input(f"Credit limit for '{name}': $")
                # --- NEW: Clean the input string ---
                credit_limit = float(limit_str.replace(',', ''))

        except ValueError:
            print("Invalid input. Please enter a number.")
            continue
        
        accounts_to_add.append({'name': name, 'type': account_type, 'balance': balance, 'credit_limit': credit_limit})
        print(f"Account '{name}' added.")

        add_another = input("Add another account? (y/n): ").lower()
        if add_another != 'y':
            break
    
    if not accounts_to_add:
        print("No accounts added. Exiting setup.")
        return

    try:
        conn = mysql.connector.connect(
            user=os.getenv('DB_USER'), 
            password=os.getenv('DB_PASSWORD'), 
            host=os.getenv('DB_HOST'), 
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor()

        for acc in accounts_to_add:
            cursor.execute(
                "INSERT INTO accounts (name, type, balance, credit_limit) VALUES (%s, %s, %s, %s)",
                (acc['name'], acc['type'], acc['balance'], acc['credit_limit'])
            )
        
        conn.commit()
        print("\n✅ Your accounts have been saved!")
        print("Please run the program again to access the main menu.")

    except mysql.connector.Error as err:
        print(f"\n❌ A database error occurred during setup: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def check_db_connection():
    """Tries to connect to the database and returns True on success, False on failure."""
    try:
        conn = mysql.connector.connect(
            user=os.getenv('DB_USER'), 
            password=os.getenv('DB_PASSWORD'), 
            host=os.getenv('DB_HOST'), 
            port=os.getenv('DB_PORT')
        )
        conn.close()
        return True
    except mysql.connector.Error:
        print("No connection to the database. Please check your credentials and ensure the server is running.")
        sys.exit() # This will immediately stop the program

def run_main_menu():
    try:
        sim = BusinessSimulator()
    except Exception as e:
        print(f"FATAL: Could not initialize simulator. Is the database running? Error: {e}")
        return
    while True:
        print_status(sim)
        print("\n--- MAIN MENU ---")
        print("1. View Accounts & Balances")
        print("2. View Transaction Ledger")
        print("3. Log Income")
        print("4. Log One-Time Expense")
        print("5. Manage Recurring Expenses")
        print("6. Advance Time")
        print("7. Exit")
        
        choice = input("> ")
        
        if choice == '1':
            handle_view_accounts(sim)
        elif choice == '2':
            handle_view_ledger(sim)
        elif choice == '3':
            handle_log_income(sim)
        elif choice == '4':
            handle_log_expense(sim)
        elif choice == '5':
            handle_manage_expenses(sim)
        elif choice == '6':
            handle_advance_time(sim)
        elif choice == '7':
            print("Goodbye!")
            break
        else:
            print("Invalid choice, please try again.")
            input("Press Enter to continue...")

def main():
    """Main game loop."""
    check_db_connection()
    try:
        conn = mysql.connector.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM accounts LIMIT 1")
        # If the query returns nothing (None), the table is empty and setup is needed.
        setup_needed = cursor.fetchone() is None
        cursor.close()
        conn.close()
    except mysql.connector.Error:
        # If we get an error, setup is needed.
        setup_needed = True
    if setup_needed:
        run_setup_wizard()
    else:
        # Note: CLI doesn't support multi-user yet, so auto-advance is disabled
        # Auto-advance is available in the web interface (index.html) after login
        # try:
        #     sim_for_startup = BusinessSimulator()
        #     sim_for_startup.auto_advance_time(user_id=1)  # Would need user_id
        # except Exception as e:
        #     print(f"Error during time advance: {e}")
        run_main_menu()

if __name__ == "__main__":
    main()