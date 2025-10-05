-- Migration: Add recurring income support
-- Date: 2026-11-06

CREATE TABLE IF NOT EXISTS recurring_income (
    income_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    deposit_day_of_month INT NOT NULL CHECK (deposit_day_of_month BETWEEN 1 AND 31),
    deposit_account_id INT NOT NULL,
    last_processed_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (deposit_account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
);
