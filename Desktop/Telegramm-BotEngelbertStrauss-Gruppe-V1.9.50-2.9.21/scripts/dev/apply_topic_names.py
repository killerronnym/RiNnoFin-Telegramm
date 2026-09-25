import sqlite3
import os

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "instance", "app.db"))
if not os.path.exists(db_path):
    # Fallback to current working directory
    db_path = "instance/app.db"
if not os.path.exists(db_path):
    print("Datenbank nicht gefunden!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Check if we need migration (if topic_id has UNIQUE constraint)
cursor.execute("PRAGMA table_info('topic_mapping')")
# There's no easy way to see the UNIQUE constraint in table_info, 
# but we can check if inserting a duplicate fails (which we know it does).

print("Migriere topic_mapping Tabelle...")

try:
    # Rename old table
    cursor.execute("ALTER TABLE topic_mapping RENAME TO topic_mapping_old")
    
    # Create new table with correct constraints
    cursor.execute("""
        CREATE TABLE topic_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id BIGINT NOT NULL,
            chat_id BIGINT,
            topic_name VARCHAR(100) NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            is_archived BOOLEAN DEFAULT 0,
            is_hidden BOOLEAN DEFAULT 0,
            is_pinned BOOLEAN DEFAULT 0,
            category VARCHAR(30) DEFAULT '',
            UNIQUE(topic_id, chat_id)
        )
    """)
    
    # Copy data, but handle duplicates if any existed somehow (unlikely due to constraint)
    cursor.execute("""
        INSERT INTO topic_mapping (id, topic_id, chat_id, topic_name, is_active, is_archived, is_hidden, is_pinned, category)
        SELECT id, topic_id, chat_id, topic_name, is_active, is_archived, is_hidden, is_pinned, category
        FROM topic_mapping_old
    """)
    
    # Drop old table
    cursor.execute("DROP TABLE topic_mapping_old")
    print("Migration erfolgreich!")
    conn.commit()
except Exception as e:
    print(f"Migration fehlgeschlagen oder bereits durchgeführt: {e}")
    conn.rollback()

# Now update the names
topics = [
    # --- HAUPTGRUPPE ---
    (1, -1002206300882, 'Vorstellungsrunde', 'User Steckbriefe'),
    (275, -1002206300882, 'Chatting', 'Hauptgruppe'),
    (2081, -1002206300882, 'Chatting 2', 'Hauptgruppe'),
    (563, -1002206300882, 'Schuhe Stiefel und mehr', 'Hauptgruppe'),
    (3, -1002206300882, 'motion2020', 'Hauptgruppe'),
    (4, -1002206300882, 'motion', 'Hauptgruppe'),
    (1780, -1002206300882, 'Spotter', 'Hauptgruppe'),
    (1312, -1002206300882, 'Umfragen & Quiz', 'Hauptgruppe'),
    (8929, -1002206300882, 'Regelwerk', 'Hauptgruppe'),
    (81, -1002206300882, 'Weitere Gear', 'Hauptgruppe'),
    (17222, -1002206300882, 'Warnschutz', 'Hauptgruppe'),
    (170, -1002206300882, 'Netzfunde', 'Hauptgruppe'),
    (6, -1002206300882, 'motion 24/7', 'Hauptgruppe'),
    (872, -1002206300882, 'Treffen & Veranstaltungen', 'Hauptgruppe'),
    (34, -1002206300882, 'concrete', 'Hauptgruppe'),
    (16, -1002206300882, 'Tauschbörse', 'Hauptgruppe'),
    (11, -1002206300882, 'active', 'Hauptgruppe'),

    # --- ADMIN GRUPPE ---
    (1, -1003372573784, 'General (Admin)', 'Admins & Team'),
    (623, -1003372573784, 'Chat', 'Admins & Team'),
    (157, -1003372573784, 'Whitelist', 'Admins & Team'),
    (61, -1003372573784, 'Notification / Notizen', 'Admins & Team'),
    (208, -1003372573784, 'Bild', 'Admins & Team'),
    (55, -1003372573784, 'Moderation', 'Admins & Team'),
    (3, -1003372573784, 'Verwarnungen', 'Admins & Team'),
]

print("Bereinige Topic-Mappings...")
for tid, cid, name, cat in topics:
    cursor.execute("SELECT id FROM topic_mapping WHERE topic_id = ? AND chat_id = ?", (tid, cid))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE topic_mapping SET topic_name = ?, category = ?, is_hidden = 0, is_archived = 0 WHERE id = ?", (name, cat, row[0]))
    else:
        cursor.execute("INSERT INTO topic_mapping (topic_id, chat_id, topic_name, category, is_active) VALUES (?, ?, ?, ?, 1)", (tid, cid, name, cat))

conn.commit()
conn.close()
print("Fertig!")
