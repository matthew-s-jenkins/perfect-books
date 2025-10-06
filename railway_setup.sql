-- Railway Database Setup - Complete schema from local MySQL
-- Tables ordered by foreign key dependencies

CREATE TABLE IF NOT EXISTS `users` (
  `user_id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE IF NOT EXISTS `accounts` (
  `account_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `name` varchar(100) NOT NULL,
  `type` enum('CHECKING','SAVINGS','CREDIT_CARD','CASH','LOAN','FIXED_ASSET','EQUITY') NOT NULL,
  `balance` decimal(12,2) NOT NULL DEFAULT '0.00',
  `interest_rate` decimal(5,2) DEFAULT '18.00',
  `last_interest_date` date DEFAULT NULL,
  `credit_limit` decimal(12,2) DEFAULT NULL,
  PRIMARY KEY (`account_id`),
  KEY `idx_user_id` (`user_id`),
  CONSTRAINT `accounts_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE IF NOT EXISTS `expense_categories` (
  `category_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `name` varchar(100) NOT NULL,
  `color` varchar(7) DEFAULT '#6366f1',
  `is_default` tinyint(1) DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`category_id`),
  UNIQUE KEY `unique_user_category` (`user_id`,`name`),
  KEY `idx_user_id` (`user_id`),
  CONSTRAINT `expense_categories_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE IF NOT EXISTS `financial_ledger` (
  `entry_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `transaction_uuid` varchar(50) NOT NULL,
  `transaction_date` datetime NOT NULL,
  `account` varchar(100) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `debit` decimal(10,2) DEFAULT '0.00',
  `credit` decimal(10,2) DEFAULT '0.00',
  `category_id` int DEFAULT NULL,
  PRIMARY KEY (`entry_id`),
  KEY `idx_user_id_date` (`user_id`,`transaction_date` DESC),
  KEY `idx_category_id` (`category_id`),
  CONSTRAINT `financial_ledger_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE IF NOT EXISTS `recurring_expenses` (
  `expense_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `description` varchar(255) NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `frequency` enum('DAILY','WEEKLY','MONTHLY') NOT NULL,
  `due_day_of_month` int NOT NULL DEFAULT '1',
  `is_variable` tinyint(1) DEFAULT '0',
  `estimated_amount` decimal(10,2) DEFAULT NULL,
  `last_processed_date` date DEFAULT NULL,
  `payment_account_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  PRIMARY KEY (`expense_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_category_id` (`category_id`),
  CONSTRAINT `recurring_expenses_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `recurring_expenses_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `expense_categories` (`category_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE IF NOT EXISTS `recurring_income` (
  `income_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `description` varchar(255) NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `deposit_account_id` int NOT NULL,
  `deposit_day_of_month` int NOT NULL,
  `is_variable` tinyint(1) DEFAULT '0',
  `estimated_amount` decimal(10,2) DEFAULT NULL,
  `last_processed_date` date DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`income_id`),
  KEY `user_id` (`user_id`),
  KEY `deposit_account_id` (`deposit_account_id`),
  CONSTRAINT `recurring_income_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `recurring_income_ibfk_2` FOREIGN KEY (`deposit_account_id`) REFERENCES `accounts` (`account_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE IF NOT EXISTS `loans` (
  `loan_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `principal_amount` decimal(12,2) NOT NULL,
  `outstanding_balance` decimal(12,2) NOT NULL,
  `interest_rate` float NOT NULL,
  `monthly_payment` decimal(10,2) NOT NULL,
  `next_payment_date` date NOT NULL,
  `status` enum('ACTIVE','PAID') NOT NULL DEFAULT 'ACTIVE',
  PRIMARY KEY (`loan_id`),
  KEY `idx_user_id` (`user_id`),
  CONSTRAINT `loans_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE IF NOT EXISTS `pending_transactions` (
  `pending_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `recurring_expense_id` int DEFAULT NULL,
  `recurring_income_id` int DEFAULT NULL,
  `description` varchar(255) NOT NULL,
  `estimated_amount` decimal(10,2) NOT NULL,
  `actual_amount` decimal(10,2) DEFAULT NULL,
  `due_date` date NOT NULL,
  `payment_account_id` int DEFAULT NULL,
  `deposit_account_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `status` varchar(20) DEFAULT 'PENDING',
  `resolved_at` timestamp NULL DEFAULT NULL,
  `transaction_type` varchar(20) DEFAULT NULL,
  `related_account_id` int DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`pending_id`),
  KEY `user_id` (`user_id`),
  KEY `recurring_expense_id` (`recurring_expense_id`),
  KEY `payment_account_id` (`payment_account_id`),
  KEY `deposit_account_id` (`deposit_account_id`),
  KEY `category_id` (`category_id`),
  CONSTRAINT `pending_transactions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `pending_transactions_ibfk_2` FOREIGN KEY (`recurring_expense_id`) REFERENCES `recurring_expenses` (`expense_id`) ON DELETE CASCADE,
  CONSTRAINT `pending_transactions_ibfk_3` FOREIGN KEY (`payment_account_id`) REFERENCES `accounts` (`account_id`) ON DELETE SET NULL,
  CONSTRAINT `pending_transactions_ibfk_4` FOREIGN KEY (`deposit_account_id`) REFERENCES `accounts` (`account_id`) ON DELETE SET NULL,
  CONSTRAINT `pending_transactions_ibfk_5` FOREIGN KEY (`category_id`) REFERENCES `expense_categories` (`category_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

