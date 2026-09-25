import os
import sqlite3
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "instance", "app.db"))
if not os.path.exists(db_path):
    # Fallback
    db_path = "instance/app.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT message_thread_id, text FROM id_finder_message WHERE text LIKE '%Vorstellung%' OR text LIKE '%Hallo%' LIMIT 10")
results = cursor.fetchall()
print("Search results for 'Vorstellung' or 'Hallo':")
for r in results:
    print(f"Thread ID: {r[0]}, Text: {r[1][:50]}")

# Also check for Topic 1 or NULL
cursor.execute("SELECT DISTINCT message_thread_id FROM id_finder_message WHERE message_thread_id IS NULL OR message_thread_id = 1")
print("\nUnique IDs for Topic 1/NULL:")
print(cursor.fetchall())

conn.close()
