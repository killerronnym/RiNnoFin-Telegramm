import os
import sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
from shared_bot_utils import get_shared_flask_app
from web_dashboard.app.models import GroupEvent, db

app = get_shared_flask_app()
def check_db(db_path):
    print(f"\n--- Checking DB: {db_path} ---")
    if not os.path.exists(db_path):
        print("File does not exist.")
        return
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Tables: {tables}")
        for t in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {t}")
            count = cursor.fetchone()[0]
            print(f"Table {t}: {count} rows")
            
        if 'user' in tables:
            cursor.execute("SELECT id, username FROM user")
            rows = cursor.fetchall()
            for r in rows:
                print(f"  USER -> ID: {r[0]} | Name: {r[1]}")
            
        if 'group_event' in tables:
            cursor.execute("SELECT id, title, message_id, chat_id FROM group_event")
            rows = cursor.fetchall()
            if not rows:
                print("  (Table group_event is EMPTY)")
            for r in rows:
                print(f"  EVENT -> ID: {r[0]} | Title: {r[1]} | MsgID: {r[2]} | Chat: {r[3]}")
    except Exception as e:
        print(f"Error reading DB: {e}")

check_db(os.path.join(PROJECT_ROOT, "app.db"))
check_db(os.path.join(PROJECT_ROOT, "instance", "app.db"))
check_db(os.path.join(PROJECT_ROOT, "instance", "dashboard.db"))
