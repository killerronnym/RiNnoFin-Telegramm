
import sqlite3
import os

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "instance", "app.db"))
if not os.path.exists(db_path):
    # Fallback
    db_path = "instance/app.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE topic_mapping ADD COLUMN is_active BOOLEAN DEFAULT 1")
        conn.commit()
        print("Spalte is_active erfolgreich hinzugefügt.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Spalte existiert bereits.")
        else:
            print(f"Fehler: {e}")
    finally:
        conn.close()
else:
    print("Datenbank nicht gefunden.")
