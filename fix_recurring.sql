USE perfect_books;

DROP TABLE IF EXISTS recurring_income;
DROP TABLE IF EXISTS recurring_expenses;

CREATE TABLE recurring_income (
    income_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    deposit_account_id INT NOT NULL,
    deposit_day_of_month INT NOT NULL,
    is_variable BOOLEAN DEFAULT FALSE,
    estimated_amount DECIMAL(10,2) NULL,
    last_processed_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (deposit_account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE recurring_expenses (
    expense_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    payment_account_id INT NOT NULL,
    due_day_of_month INT NOT NULL,
    category_id INT,
    is_variable BOOLEAN DEFAULT FALSE,
    estimated_amount DECIMAL(10,2) NULL,
    last_processed_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (payment_account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES expense_categories(category_id) ON DELETE SET NULL
) ENGINE=InnoDB;
