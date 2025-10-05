USE perfect_books;
ALTER TABLE pending_transactions MODIFY COLUMN transaction_type ENUM('EXPENSE', 'INTEREST', 'INCOME') DEFAULT 'EXPENSE';
SHOW COLUMNS FROM pending_transactions WHERE Field='transaction_type';
