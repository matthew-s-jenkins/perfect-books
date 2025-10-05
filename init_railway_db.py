import mysql.connector
import os

# Use public-facing Railway MySQL credentials
db_config = {
    'host': os.getenv('MYSQLHOST'),
    'port': int(os.getenv('MYSQLPORT', 3306)),
    'user': os.getenv('MYSQLUSER'),
    'password': os.getenv('MYSQLPASSWORD'),
    'database': os.getenv('MYSQLDATABASE')
}

# Remove None values
db_config = {k: v for k, v in db_config.items() if v is not None}

print("Database config:", {k: v if k != 'password' else '***' for k, v in db_config.items()})
print("\nConnecting to Railway MySQL...")

conn = mysql.connector.connect(**db_config)
cursor = conn.cursor()

print("Reading fresh_setup.sql...")
with open('fresh_setup.sql', 'r', encoding='utf-8') as f:
    sql_script = f.read()

print("Executing SQL commands...")
# Split by semicolon and execute each statement
statements = [s.strip() for s in sql_script.split(';') if s.strip()]
for i, statement in enumerate(statements, 1):
    try:
        cursor.execute(statement)
        print(f"  ✓ Statement {i}/{len(statements)}")
    except Exception as e:
        print(f"  ✗ Statement {i} failed: {e}")

conn.commit()
print("\n✅ Database initialized successfully!")
cursor.close()
conn.close()
