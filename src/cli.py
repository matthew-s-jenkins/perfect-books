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
    """Handles adding recurring expenses"""
    print("\n--- Manage Recurring Expenses ---")
    while True:
        description = input("Enter new expense description (or type 'done' to finish): ")
        if description.lower() == 'done':
            break
        try:
            amount_str = input(f"Enter the monthly amount for '{description}: $")
            amount = float(amount_str)

            # Call the function from engine
            success, message = sim.add_recurring_expense(description, 'Bills', amount)
            print(f"  -> {message}")
        except ValueError:
            print("  -> Invalid amount. Please enter a number.")

    print("\nFinished managing expenses.")
    input("Press Enter to return to the main menu...")

def run_setup_wizard():
    print("Welcome to Perfect Books! Let's get you set up.")
    
    starting_cash = input("What is your current cash or checking account balance? $")
    
    while True:
        description = input("Enter new expense description (or type 'done' to finish): ")
        if description.lower() == 'done':
            break
        try:
            amount_str = input(f"Enter the monthly amount for '{description}: $")
            amount = float(amount_str)

            # Call the function from engine
            success, message = sim.add_recurring_expense(description, 'Bills', amount)
            print(f"  -> {message}")
        except ValueError:
            print("  -> Invalid amount. Please enter a number.")
    
    try:
        conn = mysql.connector.connect(
            user=os.getenv('DB_USER'), 
            password=os.getenv('DB_PASSWORD'), 
            host=os.getenv('DB_HOST'), 
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor()

        # Save the starting cash
        cursor.execute("INSERT INTO business_state (state_key, state_value) VALUES (%s, %s)", ('cash_on_hand', starting_cash))

        # Save the current date as the start date
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO business_state (state_key, state_value) VALUES (%s, %s)", ('current_date', now))
        cursor.execute("INSERT INTO business_state (state_key, state_value) VALUES (%s, %s)", ('start_date', now))
        
        conn.commit()
        
        print("\n✅ Setup complete!")
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
        sim.auto_advance_time()
    except Exception as e:
        print(f"FATAL: Could not initialize simulator. Is the database running? Error: {e}")
        return
    while True:
        print_status(sim)
        print("\n--- MAIN MENU ---")
        print("1. Manage Expenses")
        print("2. Advance Time")
        print("3. Exit")
        
        choice = input("> ")
        
        if choice == '1':
            handle_manage_expenses(sim)
        elif choice == '2':
            handle_advance_time(sim)
        elif choice == '3':
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
        cursor.execute("SELECT 1 FROM business_state LIMIT 1")
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
        run_main_menu()

if __name__ == "__main__":
    main()