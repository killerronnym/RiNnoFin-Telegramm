import sqlite3
import os
from datetime import datetime

db_path = '../instance/app.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- LATEST AUDIT LOG ---")
try:
    cursor.execute("SELECT action, details, timestamp FROM audit_log ORDER BY timestamp DESC LIMIT 5")
    for row in cursor.fetchall():
        print(f"{row[2]}: {row[0]} - {row[1]}")
except Exception as e:
    print(f"Error: {e}")

print("\n--- LATEST MESSAGE ---")
try:
    cursor.execute("SELECT timestamp FROM id_finder_message ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        print(f"Latest Message: {row[0]}")
except Exception as e:
    print(f"Error: {e}")

conn.close()
