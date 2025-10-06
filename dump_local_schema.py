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

# Get all table names
cursor.execute("SHOW TABLES")
tables = [row[0] for row in cursor.fetchall()]

print("-- Schema dump from local MySQL\n")

for table in tables:
    cursor.execute(f"SHOW CREATE TABLE {table}")
    create_statement = cursor.fetchone()[1]
    # Make it CREATE TABLE IF NOT EXISTS
    create_statement = create_statement.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS")
    print(f"{create_statement};\n")

cursor.close()
conn.close()
