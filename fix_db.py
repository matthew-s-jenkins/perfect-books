import mysql.connector

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='Hecther',
    database='perfect_books'
)

cursor = conn.cursor()

# Show current structure
cursor.execute("SHOW COLUMNS FROM pending_transactions WHERE Field='transaction_type'")
print("BEFORE:")
for row in cursor:
    print(row)

# Alter the column
cursor.execute("ALTER TABLE pending_transactions MODIFY COLUMN transaction_type ENUM('EXPENSE', 'INTEREST', 'INCOME') DEFAULT 'EXPENSE'")
conn.commit()

# Show updated structure
cursor.execute("SHOW COLUMNS FROM pending_transactions WHERE Field='transaction_type'")
print("\nAFTER:")
for row in cursor:
    print(row)

cursor.close()
conn.close()
print("\nDone!")
