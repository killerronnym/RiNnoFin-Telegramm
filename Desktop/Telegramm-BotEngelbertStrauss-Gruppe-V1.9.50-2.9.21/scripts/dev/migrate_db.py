import os
import sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from web_dashboard.app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    engine = db.engine
    columns_to_add = [
        ("no_media", "BOOLEAN DEFAULT 0"),
        ("no_links", "BOOLEAN DEFAULT 0"),
        ("no_stickers", "BOOLEAN DEFAULT 0"),
        ("slow_mode_seconds", "INTEGER DEFAULT 0"),
        ("is_shadow_banned", "BOOLEAN DEFAULT 0"),
        ("last_message_at", "DATETIME")
    ]
    
    with engine.connect() as conn:
        for col_name, col_type in columns_to_add:
            try:
                # Check if column exists
                conn.execute(text(f"SELECT {col_name} FROM user_restriction LIMIT 1"))
                print(f"Column {col_name} already exists.")
            except Exception:
                # Add column
                try:
                    conn.execute(text(f"ALTER TABLE user_restriction ADD COLUMN {col_name} {col_type}"))
                    print(f"Added column {col_name}.")
                except Exception as e:
                    print(f"Error adding {col_name}: {e}")
        conn.commit()

print("Migration completed.")
