-- Fresh Database Setup for Perfect Books v2.1
-- Run this to completely rebuild the database

DROP DATABASE IF EXISTS perfect_books;
CREATE DATABASE perfect_books;
USE perfect_books;

-- Users table
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Accounts table
CREATE TABLE accounts (
    account_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    type ENUM('CHECKING', 'SAVINGS', 'CREDIT_CARD', 'LOAN', 'INVESTMENT', 'CASH', 'FIXED_ASSET') NOT NULL,
    balance DECIMAL(12,2) DEFAULT 0.00,
    credit_limit DECIMAL(12,2) DEFAULT NULL,
    interest_rate FLOAT DEFAULT 0.00,
    last_interest_date DATE NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY unique_account_per_user (user_id, name)
) ENGINE=InnoDB;

-- Financial ledger table
CREATE TABLE financial_ledger (
    entry_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    transaction_date DATE NOT NULL,
    account VARCHAR(100) NOT NULL,
    debit DECIMAL(12,2) DEFAULT 0.00,
    credit DECIMAL(12,2) DEFAULT 0.00,
    description VARCHAR(255),
    transaction_uuid VARCHAR(50),
    INDEX idx_user_date (user_id, transaction_date),
    INDEX idx_transaction_uuid (transaction_uuid),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- User status table (for time simulation)
CREATE TABLE user_status (
    user_id INT PRIMARY KEY,
    current_date DATE NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Expense categories table
CREATE TABLE expense_categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(20) DEFAULT '#3B82F6',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY unique_category_per_user (user_id, name)
) ENGINE=InnoDB;

-- Recurring income table
CREATE TABLE recurring_income (
    income_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    frequency ENUM('DAILY', 'WEEKLY', 'BIWEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY') NOT NULL,
    deposit_account_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    last_processed_date DATE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (deposit_account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Recurring expenses table
CREATE TABLE recurring_expenses (
    expense_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    frequency ENUM('DAILY', 'WEEKLY', 'BIWEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY') NOT NULL,
    payment_account_id INT NOT NULL,
    category_id INT,
    is_variable BOOLEAN DEFAULT FALSE,
    estimated_amount DECIMAL(10,2) NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    last_processed_date DATE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (payment_account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES expense_categories(category_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Pending transactions table
CREATE TABLE pending_transactions (
    pending_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    recurring_expense_id INT NULL,
    description VARCHAR(255) NOT NULL,
    estimated_amount DECIMAL(10,2) NOT NULL,
    actual_amount DECIMAL(10,2) NULL,
    due_date DATE NOT NULL,
    payment_account_id INT NOT NULL,
    category_id INT NULL,
    status ENUM('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED') DEFAULT 'PENDING',
    transaction_type ENUM('EXPENSE', 'INTEREST') DEFAULT 'EXPENSE',
    related_account_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    INDEX idx_user_status (user_id, status),
    INDEX idx_due_date (due_date),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (payment_account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES expense_categories(category_id) ON DELETE SET NULL,
    FOREIGN KEY (related_account_id) REFERENCES accounts(account_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Loans table
CREATE TABLE loans (
    loan_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    account_id INT NOT NULL,
    principal DECIMAL(12,2) NOT NULL,
    interest_rate FLOAT NOT NULL,
    term_months INT NOT NULL,
    start_date DATE NOT NULL,
    monthly_payment DECIMAL(10,2) NOT NULL,
    payment_account_id INT NOT NULL,
    status ENUM('ACTIVE', 'PAID_OFF', 'DEFAULTED') DEFAULT 'ACTIVE',
    total_interest_paid DECIMAL(12,2) DEFAULT 0.00,
    total_principal_paid DECIMAL(12,2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (payment_account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Loan payments table
CREATE TABLE loan_payments (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    loan_id INT NOT NULL,
    user_id INT NOT NULL,
    payment_date DATE NOT NULL,
    total_payment DECIMAL(10,2) NOT NULL,
    principal_amount DECIMAL(10,2) NOT NULL,
    interest_amount DECIMAL(10,2) NOT NULL,
    remaining_balance DECIMAL(10,2) NOT NULL,
    transaction_uuid VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_loan (loan_id),
    INDEX idx_user_date (user_id, payment_date),
    FOREIGN KEY (loan_id) REFERENCES loans(loan_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;
