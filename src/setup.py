"""
Perfect Books - Database Setup & Initialization

This module creates and initializes the Perfect Books database schema.
It drops and recreates the entire database, creating all tables with proper
foreign key relationships and indexes.

Database Schema Overview:
------------------------
- users: User authentication and account management
- accounts: Financial accounts (checking, savings, credit cards, loans, etc.)
- financial_ledger: Double-entry accounting ledger (immutable audit trail)
- recurring_expenses: Automated monthly bill payments with categories
- loans: Debt tracking with payment schedules
- expense_categories: User-defined expense categorization with colors

Key Design Features:
- Foreign key constraints for referential integrity
- Indexes on frequently queried columns for performance
- Cascade deletes for user data (complete user removal)
- Decimal precision for all monetary values
- Category support for expense tracking and analytics

⚠️  WARNING: This script completely drops and recreates the database!
All existing data will be lost. Use only for initial setup or reset.

Author: Matthew Jenkins
License: MIT
Related Project: Digital Harvest (Uses similar normalized schema design)
"""

import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import errorcode

# Load database credentials from .env file
load_dotenv()

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

DB_CONFIG = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT')
}
DB_NAME = 'perfect_books'

# =============================================================================
# SCHEMA DEFINITION
# =============================================================================

TABLES = {}

TABLES['users'] = (
    "CREATE TABLE `users` ("
    "  `user_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `username` VARCHAR(50) NOT NULL UNIQUE,"
    "  `password_hash` VARCHAR(255) NOT NULL,"
    "  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    ") ENGINE=InnoDB")

TABLES['accounts'] = (
    "CREATE TABLE `accounts` ("
    " `account_id` INT AUTO_INCREMENT PRIMARY KEY,"
    " `user_id` INT NOT NULL,"
    " `name` VARCHAR(100) NOT NULL,"
    " `type` ENUM('CHECKING', 'SAVINGS', 'CREDIT_CARD', 'CASH', 'LOAN', 'FIXED_ASSET', 'EQUITY') NOT NULL,"
    " `balance` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,"
    " `credit_limit` DECIMAL(12, 2) DEFAULT NULL,"
    " INDEX `idx_user_id` (`user_id`),"
    " FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE"
    ") ENGINE=InnoDB")

# Create expense_categories BEFORE tables that reference it
TABLES['expense_categories'] = (
    "CREATE TABLE `expense_categories` ("
    "  `category_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `user_id` INT NOT NULL,"
    "  `name` VARCHAR(100) NOT NULL,"
    "  `color` VARCHAR(7) DEFAULT '#6366f1',"
    "  `is_default` BOOLEAN DEFAULT FALSE,"
    "  `is_monthly` BOOLEAN DEFAULT FALSE,"
    "  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
    "  INDEX `idx_user_id` (`user_id`),"
    "  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,"
    "  UNIQUE KEY `unique_user_category` (`user_id`, `name`)"
    ") ENGINE=InnoDB")

TABLES['financial_ledger'] = (
    "CREATE TABLE `financial_ledger` ("
    "  `entry_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `user_id` INT NOT NULL,"
    "  `transaction_uuid` VARCHAR(50) NOT NULL,"
    "  `transaction_date` DATETIME NOT NULL,"
    "  `account` VARCHAR(100) NOT NULL,"
    "  `description` VARCHAR(255),"
    "  `debit` DECIMAL(10, 2) DEFAULT 0.00,"
    "  `credit` DECIMAL(10, 2) DEFAULT 0.00,"
    "  `category_id` INT DEFAULT NULL,"
    "  `is_reversal` BOOLEAN DEFAULT FALSE,"
    "  `reversal_of_id` INT DEFAULT NULL,"
    "  INDEX `idx_user_id_date` (`user_id`, `transaction_date` DESC),"
    "  INDEX `idx_category_id` (`category_id`),"
    "  INDEX `idx_is_reversal` (`is_reversal`),"
    "  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE"
    ") ENGINE=InnoDB")

TABLES['recurring_expenses'] = (
    "CREATE TABLE `recurring_expenses` ("
    "  `expense_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `user_id` INT NOT NULL,"
    "  `description` VARCHAR(255) NOT NULL,"
    "  `amount` DECIMAL(10, 2) NOT NULL,"
    "  `frequency` ENUM('DAILY', 'WEEKLY', 'MONTHLY') NOT NULL,"
    "  `due_day_of_month` INT NOT NULL DEFAULT 1,"
    "  `last_processed_date` DATE DEFAULT NULL,"
    "  `payment_account_id` INT DEFAULT NULL,"
    "  `category_id` INT DEFAULT NULL,"
    "  INDEX `idx_user_id` (`user_id`),"
    "  INDEX `idx_category_id` (`category_id`),"
    "  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,"
    "  FOREIGN KEY (category_id) REFERENCES expense_categories(category_id) ON DELETE SET NULL"
    ") ENGINE=InnoDB")

TABLES['loans'] = (
    "CREATE TABLE `loans` ("
    "  `loan_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `user_id` INT NOT NULL,"
    "  `principal_amount` DECIMAL(12, 2) NOT NULL,"
    "  `outstanding_balance` DECIMAL(12, 2) NOT NULL,"
    "  `interest_rate` FLOAT NOT NULL,"
    "  `monthly_payment` DECIMAL(10, 2) NOT NULL,"
    "  `next_payment_date` DATE NOT NULL,"
    "  `status` ENUM('ACTIVE', 'PAID') NOT NULL DEFAULT 'ACTIVE',"
    "  INDEX `idx_user_id` (`user_id`),"
    "  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE"
    ") ENGINE=InnoDB")


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
        
        print("\nDatabase schema created successfully.")
        db_connection.commit()

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Access denied. Check your user/password in .env")
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
        "This will delete all users and their data. Are you sure? (y/n): "
    ).lower()
    if confirm == 'y':
        main()
    else:
        print("Setup cancelled.")