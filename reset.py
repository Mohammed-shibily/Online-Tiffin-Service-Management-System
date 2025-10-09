import os
import shutil
from pathlib import Path

# Find all database files
db_files = ['app.db', 'app.db-journal', 'app.db-wal', 'app.db-shm']

for db_file in db_files:
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            print(f"✓ Deleted {db_file}")
        except:
            try:
                # Try moving it instead
                shutil.move(db_file, f"{db_file}.old")
                print(f"✓ Moved {db_file} to {db_file}.old")
            except:
                print(f"❌ Could not remove {db_file}")

# Also check for backup files
for backup in Path('.').glob('app.db.backup.*'):
    print(f"Found backup: {backup}")

print("\n✓ Cleanup complete! Run: python app.py")