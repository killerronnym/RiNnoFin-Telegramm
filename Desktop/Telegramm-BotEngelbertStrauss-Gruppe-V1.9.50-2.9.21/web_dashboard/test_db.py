import sqlite3
import os
import json

db_path = '../instance/app.db'
if not os.path.exists(db_path):
    print(f"DB not found at {os.path.abspath(db_path)}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- TABLES ---")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print(", ".join(tables))

print("\n--- BOT SETTINGS KEYS ---")
# Try lower case and CamelCase versions
table_name = "bot_settings" if "bot_settings" in tables else "BotSettings"
try:
    cursor.execute(f"SELECT bot_name, config_json FROM {table_name}")
    rows = cursor.fetchall()
    for row in rows:
        try:
            cfg = json.loads(row[1])
            print(f"{row[0]}: {list(cfg.keys())}")
        except:
            print(f"{row[0]}: Error parsing JSON")
except Exception as e:
    print(f"Error reading {table_name}: {e}")

conn.close()
