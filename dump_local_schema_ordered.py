import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

# Connect to local MySQL
conn = mysql.connector.connect(
    host='localhost',
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)

cursor = conn.cursor()

# Tables in correct dependency order
tables_ordered = [
    'users',
    'accounts',
    'expense_categories',
    'financial_ledger',
    'recurring_expenses',
    'recurring_income',
    'loans',
    'pending_transactions'
]

print("-- Railway Database Setup - Complete schema from local MySQL")
print("-- Tables ordered by foreign key dependencies\n")

for table in tables_ordered:
    cursor.execute(f"SHOW CREATE TABLE {table}")
    create_statement = cursor.fetchone()[1]
    # Make it CREATE TABLE IF NOT EXISTS
    create_statement = create_statement.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS")
    # Remove AUTO_INCREMENT values
    import re
    create_statement = re.sub(r' AUTO_INCREMENT=\d+', '', create_statement)
    print(f"{create_statement};\n")

cursor.close()
conn.close()
