-- Perfect Books v2.1 Database Migrations
-- This script adds support for:
-- 1. Variable recurring expenses
-- 2. Loan payment tracking with principal/interest split
-- 3. Credit card interest calculation

-- ============================================================================
-- FEATURE 1: VARIABLE RECURRING EXPENSES
-- ============================================================================

-- Add columns to recurring_expenses table
ALTER TABLE recurring_expenses
ADD COLUMN is_variable BOOLEAN DEFAULT FALSE AFTER category_id;

ALTER TABLE recurring_expenses
ADD COLUMN estimated_amount DECIMAL(10,2) NULL AFTER is_variable;

-- Create pending_transactions table
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
  FOREIGN KEY (recurring_expense_id) REFERENCES recurring_expenses(expense_id) ON DELETE SET NULL,
  FOREIGN KEY (payment_account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
  FOREIGN KEY (category_id) REFERENCES expense_categories(category_id) ON DELETE SET NULL,
  FOREIGN KEY (related_account_id) REFERENCES accounts(account_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================================
-- FEATURE 2: LOAN PAYMENT SPLIT
-- ============================================================================

-- Add interest tracking to loans table
ALTER TABLE loans
ADD COLUMN total_interest_paid DECIMAL(12,2) DEFAULT 0.00 AFTER status;

ALTER TABLE loans
ADD COLUMN total_principal_paid DECIMAL(12,2) DEFAULT 0.00 AFTER total_interest_paid;

-- Create loan_payments table
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

-- ============================================================================
-- FEATURE 3: CREDIT CARD INTEREST
-- ============================================================================

-- Add interest_rate to accounts table for credit cards
ALTER TABLE accounts
ADD COLUMN interest_rate FLOAT DEFAULT 0.00 AFTER credit_limit;

ALTER TABLE accounts
ADD COLUMN last_interest_date DATE NULL AFTER interest_rate;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
