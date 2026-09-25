import os
import sys
import json
import time
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import URL

# --- Globals & Engine Cache ---
_ENGINE_CACHE = {}
_SHARED_FLASK_APP = None
PENDING_EFFECTS = {}
_CONFIG_CACHE = {}
_ACTIVE_STATUS_CACHE = {}
CACHE_TTL = 5  # 5 seconds cache

def get_engine(url):
    """Gibt eine gecachte SQLAlchemy-Engine für die URL zurück."""
    if url not in _ENGINE_CACHE:
        if url.startswith("sqlite"):
            from sqlalchemy.pool import NullPool
            _ENGINE_CACHE[url] = create_engine(url, poolclass=NullPool, connect_args={'timeout': 30})
        else:
            _ENGINE_CACHE[url] = create_engine(url, pool_pre_ping=True)
    return _ENGINE_CACHE[url]

# Basispfade bestimmen
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DASHBOARD_DIR = os.path.join(PROJECT_ROOT, 'web_dashboard')
INSTANCE_DIR = os.path.join(PROJECT_ROOT, 'instance')
DB_PATH = os.path.join(INSTANCE_DIR, 'app.db')

# Env laden - expliziter Pfad zum Root
ENV_FILE = os.path.join(PROJECT_ROOT, '.env')
print(f"DEBUG: Loading env from {ENV_FILE} - Exists: {os.path.exists(ENV_FILE)}")
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE, override=True) # Override to be sure

def get_db_url():
    """Gibt die konfigurierte Datenbank-URL zurück oder fällt auf SQLite zurück."""
    final_url = None
    
    # 1. Discrete Environment Variables
    db_name = os.environ.get('DB_NAME')
    db_user = os.environ.get('DB_USER')
    db_host = os.environ.get('DB_HOST')
    
    if db_user and db_host and db_name:
        db_password = os.environ.get('DB_PASSWORD')
        db_port = os.environ.get('DB_PORT')
        db_driver = os.environ.get('DB_DRIVER', 'mysql+pymysql')
        
        query = {"charset": "utf8mb4"} if "mysql" in db_driver else {}
        url_obj = URL.create(
            drivername=db_driver,
            username=db_user,
            password=db_password,
            host=db_host,
            port=int(db_port) if db_port else None,
            database=db_name,
            query=query
        )
        final_url = str(url_obj)

    # 2. Fallback DATABASE_URL
    if not final_url:
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            if "mysql" in db_url and "charset=utf8mb4" not in db_url:
                separator = "&" if "?" in db_url else "?"
                db_url += f"{separator}charset=utf8mb4"
            final_url = db_url
    
    # 3. Fallback SQLite
    if not final_url:
        if not os.path.exists(INSTANCE_DIR):
            os.makedirs(INSTANCE_DIR, exist_ok=True)
        final_url = f"sqlite:///{DB_PATH}"

    # Log masked URL for debugging (hiding password)
    masked_url = final_url
    if '@' in final_url:
        prefix = final_url.split('@')[0]
        suffix = final_url.split('@')[1]
        if ':' in prefix:
            base = prefix.split(':')[0]
            masked_url = f"{base}:****@{suffix}"
            
    print(f"DEBUG: Database initialized via {'Discrete Env' if db_user else ('DATABASE_URL' if os.environ.get('DATABASE_URL') else 'SQLite Fallback')}")
    # logger.info(f"Database connection: {masked_url}") # Optional: can be un-commented if needed
    
    return final_url

def get_bot_config(bot_name):
    """Optimiertes Laden der Bot-Konfiguration."""
    now = time.time()
    if bot_name in _CONFIG_CACHE:
        val, cache_time = _CONFIG_CACHE[bot_name]
        if now - cache_time < CACHE_TTL:
            return val

    try:
        url = get_db_url()
        if url.startswith("sqlite") and not os.path.exists(DB_PATH):
            return {}

        engine = get_engine(url)
        with engine.connect() as conn:
            # Tabelle prüfen bevor Query (optional, kann entfernt werden, wenn Tabelle immer existiert)
            if not inspect(engine).has_table("bot_settings"):
                return {}
                
            result = conn.execute(
                text("SELECT config_json FROM bot_settings WHERE bot_name = :name"),
                {"name": bot_name}
            ).fetchone()
            
            val = {}
            if result and result[0]:
                val = json.loads(result[0])
            _CONFIG_CACHE[bot_name] = (val, now)
            return val
    except Exception as e:
        sys.stderr.write(f"ERROR: get_bot_config({bot_name}): {e}\n")
    return {}

def get_bot_token():
    """Zentrale Stelle für den Bot-Token. Priorisiert ENV vor DB."""
    # 1. Check ENV (Most common way to override/fix)
    env_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if env_token and env_token.strip():
        print(f"DEBUG: Using token from ENV (starts with {env_token[:5]}...)")
        return env_token.strip()

    # 2. Fallback to DB (ID Finder / Master Bot)
    try:
        config = get_bot_config("id_finder")
        token = config.get("bot_token")
        if token and token.strip():
            print(f"DEBUG: Using token from DB (starts with {token[:5]}...)")
            return token.strip()
    except Exception as e:
        sys.stderr.write(f"ERROR: Could not load token from DB: {e}\n")
    
    print("DEBUG: No bot token found in ENV or DB.")
    return None

def get_env_var(key, default=None):
    return os.environ.get(key, default)

def is_bot_active(bot_name):
    """Effiziente Prüfung des Aktiv-Status."""
    now = time.time()
    if bot_name in _ACTIVE_STATUS_CACHE:
        val, cache_time = _ACTIVE_STATUS_CACHE[bot_name]
        if now - cache_time < CACHE_TTL:
            return val

    try:
        url = get_db_url()
        if url.startswith("sqlite") and not os.path.exists(DB_PATH):
            return False

        engine = get_engine(url)
        with engine.connect() as conn:
            # Tabelle prüfen bevor Query
            if not inspect(engine).has_table("bot_settings"):
                return False
                
            result = conn.execute(
                text("SELECT config_json, is_active FROM bot_settings WHERE bot_name = :name"),
                {"name": bot_name}
            ).fetchone()
            
            if not result:
                _ACTIVE_STATUS_CACHE[bot_name] = (False, now)
                return False
                
            # First check if there's a config_json that defines the active state
            val = False
            if result[0]:
                try:
                    cfg = json.loads(result[0])
                    if 'is_active' in cfg:
                        val = bool(cfg['is_active'])
                    elif 'is_enabled' in cfg:
                        val = bool(cfg['is_enabled'])
                except:
                    pass
            
            if not val:
                # Fallback to the database column
                val = bool(result[1]) if result[1] is not None else False
                
            _ACTIVE_STATUS_CACHE[bot_name] = (val, now)
            return val
            
    except Exception as e:
        sys.stderr.write(f"ERROR checking active status for {bot_name}: {e}\n")
        return False

def get_shared_flask_app():
    """Gibt eine geteilte Flask-App für DB-Queries zurück (Singleton)."""
    global _SHARED_FLASK_APP
    if _SHARED_FLASK_APP is None:
        # Import hier um zirkuläre Abhängigkeiten zu vermeiden
        from web_dashboard.app import create_app
        _SHARED_FLASK_APP = create_app()
    return _SHARED_FLASK_APP

def log_user_interaction(user_id, username, action):
    """Loggt eine User-Interaktion für das Analytics Dashboard."""
    try:
        from web_dashboard.app.models import db, InviteLog
        app = get_shared_flask_app()
        with app.app_context():
            # Filter noise like music bot events
            if "Musik" in str(action):
                return
                
            log = InviteLog(telegram_user_id=user_id, username=username or "Unknown", action=action)
            db.session.add(log)
            db.session.commit()
            print(f"Analytics: Logged {action} for {username} ({user_id})")
    except Exception as e:
        sys.stderr.write(f"ERROR: log_user_interaction({user_id}, {username}, {action}): {e}\n")

def log_bot_outgoing_message(bot_token, chat_id, text=None, content_type='text', file_id=None, reply_to_id=None, message_id=None, message_thread_id=None, reply_markup=None, is_edit=False):
    """Zentrale Funktion zum Loggen aller vom Bot gesendeten Nachrichten."""
    try:
        from web_dashboard.app.models import db, IDFinderUser, IDFinderMessage, TopicMapping
        from datetime import datetime
        app = get_shared_flask_app()
        with app.app_context():
            bot_id = int(str(bot_token).split(':')[0])
            now = datetime.utcnow()
            
            # Bot-User sicherstellen
            bot_user = IDFinderUser.query.filter_by(telegram_id=bot_id).first()
            if not bot_user:
                bot_user = IDFinderUser(telegram_id=bot_id, first_name="Strauss Bot", is_bot=True, first_contact=now)
                db.session.add(bot_user)

            # Chat-Typ bestimmen
            chat_id_int = int(chat_id)
            is_private = chat_id_int > 0 # Telegram IDs > 0 sind meist User DMs
            
            # Topic sicherstellen (für Gruppen)
            thread_id = None
            if not is_private: # In Gruppen nach Thread suchen? Schwer ohne thread_id im Hook.
                # Wir loggen es als allgemeine Gruppennachricht ohne Thread, 
                # außer wir bekommen die thread_id später.
                pass

            # Wenn es ein Edit ist, versuchen wir die Nachricht zu finden
            if (is_edit or message_id) and message_id != 0:
                existing = IDFinderMessage.query.filter_by(message_id=message_id, chat_id=chat_id_int).first()
                if existing:
                    if text is not None: 
                        existing.previous_text = existing.text
                        existing.text = text
                        existing.is_edited = True
                    if reply_markup is not None: existing.reply_markup = reply_markup
                    if file_id is not None: existing.file_id = file_id
                    existing.timestamp = now
                    db.session.commit()
                    return True

            # Nachricht loggen (Neu)
            new_msg = IDFinderMessage(
                telegram_user_id=bot_id,
                message_id=message_id,
                chat_id=chat_id_int,
                message_thread_id=message_thread_id,
                chat_type='private' if is_private else 'supergroup',
                text=text,
                content_type=content_type,
                file_id=file_id,
                reply_to_id=reply_to_id,
                reply_markup=reply_markup,
                timestamp=now,
                text_preview=(text[:190] if text else f"[{content_type}]")
            )
            db.session.add(new_msg)
            db.session.commit()
            print(f"DEBUG: Logged outgoing bot message to {chat_id_int}: {text[:30]}...")
            return True
    except Exception as e:
        sys.stderr.write(f"ERROR logging bot outgoing message: {e}\n")
        import traceback
        traceback.print_exc()
    return False

def log_bot_message_shared(chat_id, topic_id, text, content_type='text', file_id=None, message_id=0):
    """Zusätzlicher Alias für Kompatibilität mit bestehenden Modulen (wie report_bot)."""
    # Wir benutzen einfach die neue zentrale Log-Logik
    # Hinw.: bot_token wird hier nicht übergeben, wir nehmen den Standard-Token
    token = get_bot_token()
    return log_bot_outgoing_message(token, chat_id, text, content_type, file_id, message_id=message_id, message_thread_id=topic_id)

def log_callback_query(user_id, chat_id, message_id, data, text=None, thread_id=None):
    """Protokolliert einen Button-Klick (Callback Query) in der Datenbank."""
    try:
        from web_dashboard.app.models import db, IDFinderMessage
        from datetime import datetime
        app = get_shared_flask_app()
        with app.app_context():
            now = datetime.utcnow()
            new_msg = IDFinderMessage(
                telegram_user_id=user_id,
                message_id=0, # 0 für Service/Event
                chat_id=chat_id,
                message_thread_id=thread_id,
                chat_type='private' if chat_id > 0 else 'supergroup',
                text=f"🔘 Button geklickt: {text or data}",
                content_type='callback',
                reply_to_id=message_id,
                timestamp=now
            )
            db.session.add(new_msg)
            db.session.commit()
            return True
    except Exception as e:
        sys.stderr.write(f"ERROR logging callback query: {e}\n")
    return False

def log_message_deletion(chat_id, message_id, deleted_by_id=None, deleted_by_name=None, reason=None):
    """Protokolliert die Löschung einer Nachricht in der Datenbank."""
    try:
        from web_dashboard.app.models import db, IDFinderMessage
        app = get_shared_flask_app()
        with app.app_context():
            msg = IDFinderMessage.query.filter_by(chat_id=chat_id, message_id=message_id).first()
            if msg:
                msg.is_deleted = True
                msg.deleted_by_id = deleted_by_id
                msg.deleted_by_name = deleted_by_name
                msg.deletion_reason = reason
                db.session.commit()
                print(f"DEBUG: Deletion logged for msg {message_id} in chat {chat_id}")
                return True
            return False
    except Exception as e:
        sys.stderr.write(f"ERROR logging deletion: {e}\n")
        return False
