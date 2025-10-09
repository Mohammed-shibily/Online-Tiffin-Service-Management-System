import sqlite3
import os
from datetime import datetime

# Path to your database
DB_PATH = 'app.db'

# Check if database exists
if not os.path.exists(DB_PATH):
    print(f"❌ Database file not found at {DB_PATH}")
    exit(1)

# Backup the database first
backup_path = f'app.db.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
import shutil
shutil.copy(DB_PATH, backup_path)
print(f"✓ Backup created: {backup_path}")

# Connect to database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check current schema
cursor.execute("PRAGMA table_info(customers)")
columns = cursor.fetchall()
print("\nCurrent customers table columns:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

# Check if stripe_customer_id exists
column_names = [col[1] for col in columns]

if 'stripe_customer_id' not in column_names:
    print("\n⚠ Adding missing stripe_customer_id column...")
    try:
        cursor.execute('ALTER TABLE customers ADD COLUMN stripe_customer_id VARCHAR(120)')
        print("✓ Column added successfully!")
    except sqlite3.OperationalError as e:
        print(f"❌ Error: {e}")
        conn.close()
        exit(1)
else:
    print("\n✓ stripe_customer_id column already exists!")

# Verify the change
cursor.execute("PRAGMA table_info(customers)")
columns = cursor.fetchall()
print("\nUpdated customers table columns:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

conn.commit()
conn.close()
print("\n✓ Migration complete!")
print("You can now restart your Flask application.")