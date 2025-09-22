import mysql.connector
from mysql.connector import errorcode

# --- DATABASE CONFIGURATION ---
DB_CONFIG = {
    'user': 'root',
    'password': 'Hecther',
    'host': 'localhost',
    'port': 3306
}
DB_NAME = 'digital_harvest_v2'

# --- SCHEMA DEFINITION ---
TABLES = {}
TABLES['product_categories'] = (
    "CREATE TABLE `product_categories` ("
    "  `category_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `name` VARCHAR(255) NOT NULL UNIQUE,"
    "  `status` ENUM('UNLOCKED', 'LOCKED') NOT NULL DEFAULT 'UNLOCKED'"
    ") ENGINE=InnoDB")

TABLES['vendors'] = (
    "CREATE TABLE `vendors` ("
    "  `vendor_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `name` VARCHAR(255) NOT NULL UNIQUE,"
    "  `vendor_type` ENUM('MANUFACTURER', 'DISTRIBUTOR', 'BOUTIQUE') NOT NULL,"
    "  `location` VARCHAR(100),"
    "  `base_lead_time_days` INT NOT NULL,"
    "  `reliability_score` FLOAT NOT NULL DEFAULT 0.98,"
    "  `relationship_score` INT NOT NULL DEFAULT 50,"
    "  `minimum_order_value` DECIMAL(10, 2) DEFAULT 0.00,"
    "  `payment_terms` VARCHAR(50) DEFAULT 'NET 30',"
    "  `shipping_cost_type` ENUM('FLAT_RATE', 'HYBRID') NOT NULL DEFAULT 'FLAT_RATE',"
    "  `shipping_flat_fee` DECIMAL(10, 2) DEFAULT 0.00,"
    "  `shipping_variable_rate` FLOAT DEFAULT 0.00"
    ") ENGINE=InnoDB")
    
TABLES['products'] = (
    "CREATE TABLE `products` ("
    "  `product_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `name` VARCHAR(255) NOT NULL UNIQUE,"
    "  `category_id` INT NOT NULL,"
    "  `manufacturer_id` INT,"
    "  `base_demand` INT NOT NULL,"
    "  `price_sensitivity` FLOAT NOT NULL,"
    "  `status` ENUM('LOCKED', 'UNLOCKED') NOT NULL DEFAULT 'UNLOCKED',"
    "  `switch_type` ENUM('LINEAR', 'TACTILE', 'CLICKY') DEFAULT NULL,"
    "  `switch_feel` ENUM('LIGHT', 'MEDIUM', 'HEAVY') DEFAULT NULL,"
    "  `sound_profile` ENUM('QUIET', 'MODERATE', 'LOUD') DEFAULT NULL,"
    "  FOREIGN KEY (`category_id`) REFERENCES `product_categories` (`category_id`),"
    "  FOREIGN KEY (`manufacturer_id`) REFERENCES `vendors` (`vendor_id`)"
    ") ENGINE=InnoDB")

TABLES['market_events'] = (
    "CREATE TABLE `market_events` ("
    "  `event_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `name` VARCHAR(255) NOT NULL,"
    "  `description` TEXT,"
    "  `start_date` DATE NOT NULL,"
    "  `end_date` DATE NOT NULL,"
    "  `demand_boost_multiplier` FLOAT NOT NULL,"
    "  `target_switch_type` ENUM('LINEAR', 'TACTILE', 'CLICKY') DEFAULT NULL,"
    "  `target_switch_feel` ENUM('LIGHT', 'MEDIUM', 'HEAVY') DEFAULT NULL,"
    "  `target_sound_profile` ENUM('QUIET', 'MODERATE', 'LOUD') DEFAULT NULL"
    ") ENGINE=InnoDB")

TABLES['vendor_products'] = (
    "CREATE TABLE `vendor_products` ("
    "  `vendor_product_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `vendor_id` INT NOT NULL,"
    "  `product_id` INT NOT NULL,"
    "  FOREIGN KEY (`vendor_id`) REFERENCES `vendors` (`vendor_id`),"
    "  FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`),"
    "  UNIQUE KEY `unique_vendor_product` (`vendor_id`, `product_id`)"
    ") ENGINE=InnoDB")

TABLES['volume_discounts'] = (
    "CREATE TABLE `volume_discounts` ("
    "  `discount_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `vendor_product_id` INT NOT NULL,"
    "  `min_quantity` INT NOT NULL,"
    "  `max_quantity` INT,"
    "  `unit_cost` DECIMAL(10, 4) NOT NULL,"
    "  FOREIGN KEY (`vendor_product_id`) REFERENCES `vendor_products` (`vendor_product_id`)"
    ") ENGINE=InnoDB")

TABLES['player_product_settings'] = (
    "CREATE TABLE `player_product_settings` ("
    "  `product_id` INT PRIMARY KEY,"
    "  `current_selling_price` DECIMAL(10, 2) NOT NULL,"
    "  `default_price` DECIMAL(10, 2) NOT NULL,"
    "  FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`)"
    ") ENGINE=InnoDB")

TABLES['purchase_orders'] = (
    "CREATE TABLE `purchase_orders` ("
    "  `order_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `vendor_id` INT NOT NULL,"
    "  `order_date` DATETIME NOT NULL,"
    "  `expected_arrival_date` DATETIME NOT NULL,"
    "  `actual_arrival_date` DATETIME,"
    "  `status` ENUM('PENDING', 'IN_TRANSIT', 'DELAYED', 'DELIVERED') NOT NULL,"
    "  FOREIGN KEY (`vendor_id`) REFERENCES `vendors` (`vendor_id`)"
    ") ENGINE=InnoDB")

TABLES['purchase_order_items'] = (
    "CREATE TABLE `purchase_order_items` ("
    "  `item_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `order_id` INT NOT NULL,"
    "  `product_id` INT NOT NULL,"
    "  `quantity` INT NOT NULL,"
    "  `unit_cost` DECIMAL(10, 4) NOT NULL,"
    "  FOREIGN KEY (`order_id`) REFERENCES `purchase_orders` (`order_id`),"
    "  FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`)"
    ") ENGINE=InnoDB")

TABLES['inventory_ledger'] = (
    "CREATE TABLE `inventory_ledger` ("
    "  `entry_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `transaction_uuid` VARCHAR(36) NOT NULL,"
    "  `transaction_date` DATETIME NOT NULL,"
    "  `product_id` INT NOT NULL,"
    "  `type` VARCHAR(50) NOT NULL,"
    "  `description` VARCHAR(255),"
    "  `quantity_change` INT NOT NULL,"
    "  `unit_cost` DECIMAL(10, 4) DEFAULT 0.00,"
    "  `unit_price` DECIMAL(10, 2) DEFAULT 0.00,"
    "  `total_value` DECIMAL(10, 2) NOT NULL,"
    "  `quantity_on_hand_after` INT NOT NULL,"
    "  FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`),"
    "  INDEX `idx_transaction_uuid` (`transaction_uuid`)"
    ") ENGINE=InnoDB")

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

TABLES['business_state'] = (
    "CREATE TABLE `business_state` ("
    "  `state_key` VARCHAR(50) PRIMARY KEY,"
    "  `state_value` VARCHAR(255) NOT NULL"
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

TABLES['accounts_payable'] = (
    "CREATE TABLE `accounts_payable` ("
    "  `payable_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `purchase_order_id` INT NOT NULL,"
    "  `vendor_id` INT NOT NULL,"
    "  `amount_due` DECIMAL(10, 2) NOT NULL,"
    "  `creation_date` DATETIME NOT NULL,"
    "  `due_date` DATETIME,"
    "  `paid_date` DATETIME,"
    "  `status` ENUM('UNPAID', 'PAID') NOT NULL DEFAULT 'UNPAID',"
    "  FOREIGN KEY (`purchase_order_id`) REFERENCES `purchase_orders` (`order_id`),"
    "  FOREIGN KEY (`vendor_id`) REFERENCES `vendors` (`vendor_id`)"
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

TABLES['marketing_campaigns'] = (
    "CREATE TABLE `marketing_campaigns` ("
    "  `campaign_id` INT AUTO_INCREMENT PRIMARY KEY,"
    "  `target_type` ENUM('PRODUCT', 'CATEGORY', 'ALL') NOT NULL,"
    "  `target_id` INT,"
    "  `start_date` DATE NOT NULL,"
    "  `end_date` DATE NOT NULL,"
    "  `demand_boost_multiplier` FLOAT NOT NULL,"
    "  `cost` DECIMAL(12, 2) NOT NULL,"
    "  `name` VARCHAR(255) NOT NULL"
    ") ENGINE=InnoDB")

# --- STARTING GAME DATA ---
VENDORS_TO_ADD = [
    {"name": "US Switches LLC", "vendor_type": "DISTRIBUTOR", "location": "North America", "base_lead_time_days": 3, "reliability_score": 0.99, "minimum_order_value": 150.00, "payment_terms": "NET 30", "shipping_cost_type": "FLAT_RATE", "shipping_flat_fee": 25.00, "shipping_variable_rate": 0.00},
    {"name": "Switch World Express", "vendor_type": "DISTRIBUTOR", "location": "Asia", "base_lead_time_days": 20, "reliability_score": 0.95, "minimum_order_value": 250.00, "payment_terms": "NET 30", "shipping_cost_type": "HYBRID", "shipping_flat_fee": 100.00, "shipping_variable_rate": 0.05},
    {"name": "KeebsForAll", "vendor_type": "DISTRIBUTOR", "location": "North America", "base_lead_time_days": 6, "reliability_score": 0.98, "minimum_order_value": 400.00, "payment_terms": "NET 15", "shipping_cost_type": "FLAT_RATE", "shipping_flat_fee": 40.00, "shipping_variable_rate": 0.00},
    {"name": "Budget Switches Co.", "vendor_type": "DISTRIBUTOR", "location": "Asia", "base_lead_time_days": 25, "reliability_score": 0.92, "minimum_order_value": 200.00, "payment_terms": "NET 30", "shipping_cost_type": "HYBRID", "shipping_flat_fee": 120.00, "shipping_variable_rate": 0.06},
    {"name": "Enthusiast Keys", "vendor_type": "DISTRIBUTOR", "location": "North America", "base_lead_time_days": 5, "reliability_score": 0.97, "minimum_order_value": 500.00, "payment_terms": "NET 15", "shipping_cost_type": "FLAT_RATE", "shipping_flat_fee": 50.00, "shipping_variable_rate": 0.00},
    {"name": "EU Keys", "vendor_type": "DISTRIBUTOR", "location": "Europe", "base_lead_time_days": 10, "reliability_score": 0.98, "minimum_order_value": 300.00, "payment_terms": "NET 30", "shipping_cost_type": "HYBRID", "shipping_flat_fee": 80.00, "shipping_variable_rate": 0.04},
    {"name": "Cherry Corp", "vendor_type": "MANUFACTURER", "location": "Europe", "base_lead_time_days": 12, "reliability_score": 0.995, "minimum_order_value": 25000.00, "payment_terms": "NET 60", "shipping_cost_type": "HYBRID", "shipping_flat_fee": 500.00, "shipping_variable_rate": 0.02},
    {"name": "Gateron Manufacturing", "vendor_type": "MANUFACTURER", "location": "Asia", "base_lead_time_days": 30, "reliability_score": 0.96, "minimum_order_value": 10000.00, "payment_terms": "NET 60", "shipping_cost_type": "HYBRID", "shipping_flat_fee": 800.00, "shipping_variable_rate": 0.03},
    {"name": "Kailh Direct", "vendor_type": "MANUFACTURER", "location": "Asia", "base_lead_time_days": 28, "reliability_score": 0.95, "minimum_order_value": 15000.00, "payment_terms": "NET 60", "shipping_cost_type": "HYBRID", "shipping_flat_fee": 750.00, "shipping_variable_rate": 0.03},
    {"name": "Zeal PC", "vendor_type": "BOUTIQUE", "location": "North America", "base_lead_time_days": 15, "reliability_score": 0.99, "minimum_order_value": 5000.00, "payment_terms": "NET 30", "shipping_cost_type": "FLAT_RATE", "shipping_flat_fee": 150.00, "shipping_variable_rate": 0.00},
]

PRODUCTS_TO_ADD = [
    {"category": "Tactile Switches", "name": "Gateron Brown", "manufacturer_name": "Gateron Manufacturing", "base_demand": 350, "price_sensitivity": 1.2, "default_price": 0.65, 
     "status": "UNLOCKED", "switch_type": "TACTILE", "switch_feel": "LIGHT", "sound_profile": "MODERATE", "vendors": {
        "US Switches LLC": 0.28, "Switch World Express": 0.21, "KeebsForAll": 0.26, "Gateron Manufacturing": 0.18
    }},
    {"category": "Linear Switches", "name": "Gateron Red", "manufacturer_name": "Gateron Manufacturing", "base_demand": 320, "price_sensitivity": 1.1, "default_price": 0.65, 
     "status": "UNLOCKED", "switch_type": "LINEAR", "switch_feel": "LIGHT", "sound_profile": "QUIET", "vendors": {
        "Switch World Express": 0.21, "KeebsForAll": 0.26, "Budget Switches Co.": 0.19, "Gateron Manufacturing": 0.18
    }},
    {"category": "Clicky Switches", "name": "Kailh Box White", "manufacturer_name": "Kailh Direct", "base_demand": 250, "price_sensitivity": 1.5, "default_price": 0.75, 
     "status": "UNLOCKED", "switch_type": "CLICKY", "switch_feel": "LIGHT", "sound_profile": "LOUD", "vendors": {
        "US Switches LLC": 0.35, "Switch World Express": 0.26, "Kailh Direct": 0.22
    }},
    {"category": "Clicky Switches", "name": "Cherry MX Blue", "manufacturer_name": "Cherry Corp", "base_demand": 280, "price_sensitivity": 1.8, "default_price": 1.05, 
     "status": "LOCKED", "switch_type": "CLICKY", "switch_feel": "MEDIUM", "sound_profile": "LOUD", "vendors": {
        "US Switches LLC": 0.45, "KeebsForAll": 0.42, "EU Keys": 0.40, "Cherry Corp": 0.32
    }},
    {"category": "Linear Switches", "name": "Cherry MX Black", "manufacturer_name": "Cherry Corp", "base_demand": 200, "price_sensitivity": 1.6, "default_price": 1.05, 
     "status": "LOCKED", "switch_type": "LINEAR", "switch_feel": "HEAVY", "sound_profile": "MODERATE", "vendors": {
        "KeebsForAll": 0.42, "EU Keys": 0.40, "Cherry Corp": 0.32
    }},
]

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
        
        cursor.execute("INSERT INTO business_state (state_key, state_value) VALUES (%s, %s)", ('cash_on_hand', '50000.00'))
        cursor.execute("INSERT INTO business_state (state_key, state_value) VALUES (%s, %s)", ('current_date', '2025-01-01 09:00:00'))
        cursor.execute("INSERT INTO business_state (state_key, state_value) VALUES (%s, %s)", ('start_date', '2025-01-01 09:00:00'))
        print("  - Set initial cash to $50,000 and date to 2025-01-01.")

        category_names = {p['category'] for p in PRODUCTS_TO_ADD}
        category_map = {}
        for cat_name in category_names:
            cursor.execute("INSERT INTO product_categories (name) VALUES (%s)", (cat_name,))
            category_map[cat_name] = cursor.lastrowid
        print("  - Populated product categories.")
        
        vendor_map = {}
        for vendor in VENDORS_TO_ADD:
            cursor.execute(
                ("INSERT INTO vendors (name, vendor_type, location, base_lead_time_days, reliability_score, "
                 "minimum_order_value, payment_terms, shipping_cost_type, shipping_flat_fee, shipping_variable_rate) "
                 "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"),
                (vendor['name'], vendor['vendor_type'], vendor['location'], vendor['base_lead_time_days'], 
                 vendor['reliability_score'], vendor['minimum_order_value'], vendor['payment_terms'], vendor['shipping_cost_type'], 
                 vendor['shipping_flat_fee'], vendor['shipping_variable_rate'])
            )
            vendor_map[vendor['name']] = cursor.lastrowid
        print("  - Populated vendors.")

        for product in PRODUCTS_TO_ADD:
            cat_id = category_map[product['category']]
            manu_id = vendor_map.get(product.get('manufacturer_name'))
            
            cursor.execute(
                ("INSERT INTO products (name, category_id, manufacturer_id, base_demand, price_sensitivity, "
                 "status, switch_type, switch_feel, sound_profile) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"),
                (product['name'], cat_id, manu_id, product['base_demand'], product['price_sensitivity'],
                 product['status'], product['switch_type'], product['switch_feel'], product['sound_profile'])
            )
            product_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO player_product_settings (product_id, default_price, current_selling_price) VALUES (%s, %s, %s)",
                (product_id, product['default_price'], product['default_price'])
            )
            
            for vendor_name, cost in product['vendors'].items():
                if vendor_name in vendor_map:
                    vendor_id = vendor_map[vendor_name]
                    cursor.execute(
                        "INSERT INTO vendor_products (vendor_id, product_id) VALUES (%s, %s)",
                        (vendor_id, product_id)
                    )
                    vendor_product_id = cursor.lastrowid
                    
                    cursor.execute(
                        "INSERT INTO volume_discounts (vendor_product_id, min_quantity, max_quantity, unit_cost) VALUES (%s, %s, %s, %s)",
                        (vendor_product_id, 1, None, cost)
                    )
        print("  - Populated products, vendor links, and pricing.")
        
        cursor.execute(
            "INSERT INTO recurring_expenses (description, account, amount, frequency) VALUES (%s, %s, %s, %s)",
            ('Warehouse Rent', 'Operating Expenses', 1200.00, 'MONTHLY')
        )
        cursor.execute(
            "INSERT INTO recurring_expenses (description, account, amount, frequency) VALUES (%s, %s, %s, %s)",
            ('Warehouse Utilities', 'Operating Expenses', 250.00, 'MONTHLY')
        )
        cursor.execute(
            "INSERT INTO recurring_expenses (description, account, amount, frequency) VALUES (%s, %s, %s, %s)",
            ('Inventory Software Subscription', 'Software Expenses', 75.00, 'MONTHLY')
        )
        print("  - Populated default recurring expenses.")

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