import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import errorcode

load_dotenv()

# --- DATABASE CONFIGURATION ---
DB_CONFIG = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT')
}
DB_NAME = 'perfect_books'

# --- SCHEMA DEFINITION ---
TABLES = {}

TABLES['financial_ledger'] = (
    "CREATE TABLE `financial_ledger` ("
    "  `entry_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `transaction_uuid` VARCHAR(36) NOT NULL,"
    "  `transaction_date` DATETIME NOT NULL,"
    "  `account` VARCHAR(100) NOT NULL,"
    "  `description` VARCHAR(255),"
    "  `debit` DECIMAL(10, 2) DEFAULT 0.00,"
    "  `credit` DECIMAL(10, 2) DEFAULT 0.00,"
    "  INDEX `idx_transaction_uuid` (`transaction_uuid`)"
    ") ENGINE=InnoDB")

TABLES['recurring_expenses'] = (
    "CREATE TABLE `recurring_expenses` ("
    "  `expense_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `description` VARCHAR(255) NOT NULL,"
    "  `account` VARCHAR(100) NOT NULL,"
    "  `amount` DECIMAL(10, 2) NOT NULL,"
    "  `frequency` ENUM('DAILY', 'WEEKLY', 'MONTHLY') NOT NULL,"
    "  `last_processed_date` DATE DEFAULT NULL"
    ") ENGINE=InnoDB")

TABLES['loans'] = (
    "CREATE TABLE `loans` ("
    "  `loan_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `principal_amount` DECIMAL(12, 2) NOT NULL,"
    "  `outstanding_balance` DECIMAL(12, 2) NOT NULL,"
    "  `interest_rate` FLOAT NOT NULL,"
    "  `monthly_payment` DECIMAL(10, 2) NOT NULL,"
    "  `next_payment_date` DATE NOT NULL,"
    "  `status` ENUM('ACTIVE', 'PAID') NOT NULL DEFAULT 'ACTIVE'"
    ") ENGINE=InnoDB")

TABLES['accounts'] = (
    "CREATE TABLE `accounts` ("
    " `account_id` INT AUTO_INCREMENT PRIMARY KEY,"
    " `name` VARCHAR(100) NOT NULL UNIQUE,"
    " `type` ENUM('CHECKING', 'SAVINGS', 'CREDIT_CARD', 'CASH') NOT NULL,"
    " `balance` DECIMAL(12, 2) NOT NULL DEFAULT 0.00"
    ") ENGINE=InnoDB")

# --- STARTING GAME DATA ---
# (none currently)


def main():
    try:
        db_connection = mysql.connector.connect(**DB_CONFIG)
        cursor = db_connection.cursor()
        print(f"--- Resetting Database: '{DB_NAME}' ---")
        cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        print(f"  - Dropped database '{DB_NAME}' (if it existed).")
        cursor.execute(f"CREATE DATABASE {DB_NAME} DEFAULT CHARACTER SET 'utf8'")
        print(f"  - Created new database '{DB_NAME}'.")
        db_connection.database = DB_NAME
        print(f"Successfully connected to database '{DB_NAME}'.")

        print("\n--- Creating Tables ---")
        for table_name, table_description in TABLES.items():
            try:
                print(f"Creating table '{table_name}': ", end='')
                cursor.execute(table_description)
                print("OK")
            except mysql.connector.Error as err:
                print(f"Error creating table {table_name}: {err.msg}")
                return

        print("\n--- Populating Initial Data ---")
        
        db_connection.commit()
        print("\n--- Initial data populated successfully! ---")

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            print(err)
    finally:
        if 'db_connection' in locals() and db_connection.is_connected():
            cursor.close()
            db_connection.close()
            print("\nSetup complete. MySQL connection closed.")

if __name__ == "__main__":
    confirm = input(
        f"WARNING: This script will completely reset the '{DB_NAME}' database.\n"
        "Are you sure you want to proceed? (y/n): "
    ).lower()
    if confirm == 'y':
        main()
    else:
        print("Setup cancelled.")