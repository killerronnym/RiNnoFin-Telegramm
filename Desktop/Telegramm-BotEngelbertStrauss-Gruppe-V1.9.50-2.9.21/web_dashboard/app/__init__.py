from flask import Flask, redirect, url_for, request
from .models import db, User 
from flask_login import LoginManager
from dotenv import load_dotenv
from .config import Config
from flask_apscheduler import APScheduler
import os
import json
import logging
from .utils import datetimeformat
 
# --- Zentrale Logging Konfiguration ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
CRITICAL_LOG_FILE = os.path.join(LOG_DIR, "critical_errors.log")

# Custom Formatter
log_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s', datefmt='%d.%m.%Y %H:%M:%S')

# File Handler für kritische Fehler
crit_handler = logging.FileHandler(CRITICAL_LOG_FILE, encoding='utf-8')
crit_handler.setLevel(logging.ERROR)
crit_handler.setFormatter(log_formatter)

# File Handler für das Dashboard (Allgemein)
DASHBOARD_LOG_FILE = os.path.join(LOG_DIR, "dashboard.log")
dash_handler = logging.FileHandler(DASHBOARD_LOG_FILE, encoding='utf-8')
dash_handler.setLevel(logging.INFO)
dash_handler.setFormatter(log_formatter)

# Root Logger konfigurieren
root_logger = logging.getLogger()
root_logger.addHandler(crit_handler)
root_logger.addHandler(dash_handler)
root_logger.setLevel(logging.INFO)

def create_app(test_config=None):
    load_dotenv()
    
    app = Flask(__name__, instance_relative_config=True)
    
    # ProxyFix für Reverse Proxies (Synology NAS)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    if test_config:
        app.config.from_mapping(test_config)
    else:
        app.config.from_object(Config)

    db.init_app(app)
    
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except Exception as e:
            print(f"Error loading user from DB: {e}")
            return None
    
    app.jinja_env.filters['datetimeformat'] = datetimeformat
    app.jinja_env.add_extension('jinja2.ext.do')
    
    # Blueprints registrieren
    from .routes import dashboard, auth, api, install, sync, webauthn
    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(install.bp)
    app.register_blueprint(sync.bp)
    app.register_blueprint(webauthn.bp)
    
    @app.context_processor
    def inject_sync_state():
        try:
            from .live_bot import get_sync_state
            import time
            state = get_sync_state()
            trial_remaining_hours = 0
            if state.get('mode') == 'TRIAL':
                expiry = state.get('trial_expiry', 0)
                now = int(time.time())
                if expiry > now:
                    trial_remaining_hours = int((expiry - now) / 3600)
            
            from .models import BotSettings
            backup_settings = BotSettings.query.filter_by(bot_name='backup_bot').first()
            backup_config = json.loads(backup_settings.config_json) if backup_settings else {'enabled': False, 'nas_path': '', 'backup_time': '06:55', 'local_retention': 7}
            
            return dict(sync_state=state, trial_remaining_hours=trial_remaining_hours, backup_config=backup_config)
        except Exception:
            return dict(sync_state={}, trial_remaining_hours=0, backup_config={'enabled': False, 'nas_path': '', 'backup_time': '06:55', 'local_retention': 7})
            
    # Check for installation
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    INSTANCE_DIR = os.path.join(PROJECT_ROOT, 'instance')
    INSTALL_LOCK = os.path.join(INSTANCE_DIR, 'installed.lock')

    @app.before_request
    def check_for_install():
        from .live_bot import is_halted, get_sync_state, activate_live_sync, push_heartbeat
        from flask import render_template, request, redirect, session
        
        # 1. Lock Screen check (System wurde gesperrt)
        if is_halted():
            if request.endpoint and (request.endpoint.startswith('static.') or request.endpoint == 'sync.activate_web'):
                return
                
            error_msg = session.pop('activation_error', None)
            return render_template('system_error.html', error_msg=error_msg), 403
            
        # 2. Setup check
        import os
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        INSTALL_LOCK = os.path.join(project_root, 'instance', 'installed.lock')
        if not os.path.exists(INSTALL_LOCK):
            # Only allow access to setup endpoints
            allowed_endpoints = ['install.index', 'install.setup', 'install.test_token', 'install.get_group_id', 'install.check_db']
            allowed_endpoints += ['install.restore', 'install.validate_backup']
            allowed_endpoints += ['install.track_interaction']
            if request.endpoint and request.endpoint not in allowed_endpoints and not request.endpoint.startswith('static.'):
                return redirect(url_for('install.index'))

    @app.before_request
    def track_user_activity():
        from flask import session, request
        from datetime import datetime
        from flask_login import current_user
        
        if current_user and current_user.is_authenticated:
            # Passwort-Änderungszwang prüfen
            if getattr(current_user, 'must_change_password', False):
                allowed = ['auth.change_password_required', 'auth.logout', 'auth.login']
                if request.endpoint and request.endpoint not in allowed and not request.endpoint.startswith('static.'):
                    return redirect(url_for('auth.change_password_required'))

            # 1. Update or create active LoginAudit session
            from .models import LoginAudit
            audit = None
            audit_id = session.get('login_audit_id')
            if audit_id:
                try:
                    audit = db.session.get(LoginAudit, audit_id) if hasattr(db.session, 'get') else LoginAudit.query.get(audit_id)
                except Exception:
                    pass
            
            if not audit:
                # User is logged in but doesn't have an active LoginAudit session (e.g. session restored after app update)
                # Let's dynamically create a session-on-the-fly to show them immediately as active!
                try:
                    from .utils import get_client_ip
                    ip = get_client_ip()
                    audit = LoginAudit(user_id=current_user.id, username=current_user.username, ip_address=ip)
                    db.session.add(audit)
                    db.session.commit()
                    session['login_audit_id'] = audit.id
                except Exception as e:
                    db.session.rollback()
                    print(f"Error creating LoginAudit on-the-fly: {e}")
            else:
                try:
                    audit.last_activity = datetime.utcnow()
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"Error tracking user activity: {e}")
            
            # 2. Log Page View Audits for GET requests (exclude static files and APIs)
            if request.method == 'GET' and request.endpoint:
                endpoint = request.endpoint
                if not endpoint.startswith('static.') and not endpoint.startswith('api.') and not 'api' in endpoint:
                    # Mapped menus for beautiful labels
                    endpoint_map = {
                        'dashboard.index': 'Dashboard Übersicht',
                        'dashboard.bot_settings': 'Invite-Bot Einstellungen',
                        'dashboard.id_finder_dashboard': 'ID-Finder Bot',
                        'dashboard.profanity_filter': 'Schimpfwort-Filter',
                        'dashboard.minecraft_status_page': 'Minecraft Status',
                        'dashboard.tiktok_settings': 'TikTok Live-Panel',
                        'dashboard.quiz_settings': 'Quiz-Bot Einstellungen',
                        'dashboard.umfrage_settings': 'Umfrage-Bot Einstellungen',
                        'dashboard.outfit_bot_dashboard': 'Outfit-Bot Einstellungen',
                        'dashboard.birthday_settings': 'Geburtstags-Bot',
                        'dashboard.report_settings': 'Report-Bot',
                        'dashboard.event_settings': 'Event-Bot',
                        'dashboard.ip_locks': 'Sicherheits-Center (IP-Sperren & Audit)',
                        'dashboard.manage_users': 'Benutzerverwaltung',
                        'dashboard.critical_errors': 'Kritische Fehler Protokoll'
                    }
                    if endpoint in endpoint_map:
                        page_name = endpoint_map[endpoint]
                        try:
                            from .utils import log_audit
                            log_audit("Seite aufgerufen", f"Menü '{page_name}' aufgerufen")
                        except Exception as e:
                            print(f"Error logging page view: {e}")
                            
            # 3. AUTOMATISCHES DETAILLIERTES LOGGING FÜR ALLE AKTIONEN/POST (Benutzer verändern, löschen, starten, stoppen etc.)
            elif request.method == 'POST' and request.endpoint:
                endpoint = request.endpoint
                # Ignoriere rein interne APIs und statische Assets
                if not endpoint.startswith('static.') and not endpoint.startswith('api.') and not 'api' in endpoint:
                    try:
                        from .utils import log_audit
                        
                        # Mappe Endpunkte für lesbare Übersichten im Aktivitäts-Log
                        action_map = {
                            'dashboard.delete_user': 'Web-Benutzer gelöscht',
                            'dashboard.add_user': 'Web-Benutzer erstellt',
                            'dashboard.edit_user': 'Web-Benutzer bearbeitet',
                            'dashboard.id_finder_delete_user': 'Steckbrief-Benutzer gelöscht',
                            'dashboard.id_finder_toggle_pause': 'Steckbrief-Prozess geändert',
                            'dashboard.id_finder_save_config': 'Master-Konfiguration geändert',
                            'dashboard.id_finder_add_admin': 'Bot-Admin hinzugefügt',
                            'dashboard.id_finder_delete_admin': 'Bot-Admin gelöscht',
                            'dashboard.id_finder_update_admin_permissions': 'Bot-Admin Berechtigungen geändert',
                            'dashboard.quiz_settings': 'Quiz-Bot Einstellungen gespeichert',
                            'dashboard.quiz_send_random': 'Manuelles Quiz gestartet',
                            'dashboard.umfrage_settings': 'Umfrage-Bot Einstellungen gespeichert',
                            'dashboard.umfrage_send_now': 'Manuelle Umfrage gestartet',
                            'dashboard.bot_action_route': 'Bot/Modul gesteuert',
                        }
                        
                        action_name = action_map.get(endpoint, f"Aktion '{endpoint}'")
                        
                        # Sichere Extraktion der Formulardaten (Passwörter und private Tokens ausschließen!)
                        form_details = []
                        for key in request.form.keys():
                            if 'password' in key.lower() or 'token' in key.lower() or 'secret' in key.lower():
                                form_details.append(f"{key}: [GEHEIM]")
                            else:
                                vals = request.form.getlist(key)
                                if len(vals) == 1:
                                    # Wenn der Text zu lang ist, kürzen (z.B. bei massiven JSONs)
                                    val_str = vals[0]
                                    if len(val_str) > 120:
                                        val_str = val_str[:120] + "... [gekürzt]"
                                    form_details.append(f"{key}: {val_str}")
                                elif len(vals) > 1:
                                    form_details.append(f"{key}: {vals}")
                                    
                        # URL Parameter ebenfalls hinzufügen falls vorhanden (z.B. id-finder/delete-user/12345)
                        url_details = []
                        if request.view_args:
                            for k, v in request.view_args.items():
                                url_details.append(f"{k}: {v}")
                                
                        full_details = []
                        if url_details:
                            full_details.append("Parameter: " + ", ".join(url_details))
                        if form_details:
                            full_details.append("Formular: " + " | ".join(form_details))
                            
                        details_str = " - ".join(full_details) if full_details else "Keine Parameter"
                        
                        log_audit(action_name, details_str)
                    except Exception as e:
                        print(f"Error executing automatic POST logging: {e}")

    @app.template_filter('from_json')
    def from_json_filter(value):
        try:
            import json
            return json.loads(value) if value else []
        except:
            return []

    with app.app_context():
        # INITIALISIERUNG NUR WENN INSTALLIERT
        # Andernfalls stürzt die App beim Start mit SQLAlchemy-Fehlern ab,
        # wenn in der .env noch eine fehlerhafte oder alte Datenbank steht.
        if os.path.exists(INSTALL_LOCK):
            try:
                db.create_all()
                
                # 1. Dynamic Column Synchronization (Self-Healing Schema)
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                existing_tables = inspector.get_table_names()
                
                for table_name, table in db.metadata.tables.items():
                    if table_name in existing_tables:
                        existing_cols = {col['name']: col for col in inspector.get_columns(table_name)}
                        for col_name, column in table.columns.items():
                            if col_name not in existing_cols:
                                # Determine correct SQL type representation
                                dtype = str(column.type)
                                # Default value if specified
                                default_str = ""
                                if column.default is not None:
                                    if hasattr(column.default, 'arg'):
                                        val = column.default.arg
                                        if isinstance(val, bool):
                                            default_str = f" DEFAULT {1 if val else 0}"
                                        elif isinstance(val, (int, float)):
                                            default_str = f" DEFAULT {val}"
                                        elif isinstance(val, str):
                                            default_str = f" DEFAULT '{val}'"
                                            
                                try:
                                    alter_query = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {dtype}{default_str}"
                                    db.session.execute(db.text(alter_query))
                                    db.session.commit()
                                    print(f"Migration: Column {table_name}.{col_name} ({dtype}{default_str}) added dynamically.")
                                except Exception as alter_err:
                                    db.session.rollback()
                                    print(f"Failed to add column {table_name}.{col_name} dynamically: {alter_err}")
                
                # 2. Fix TopicMapping UNIQUE constraint (special SQLite index fix)
                def fix_topic_mapping_constraint():
                    try:
                        import sqlite3
                        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
                        if 'sqlite' in db_uri:
                            path = db_uri.replace('sqlite:///', '')
                            if not os.path.isabs(path):
                                path = os.path.join(app.instance_path, path)
                            
                            conn = sqlite3.connect(path)
                            cursor = conn.cursor()
                            
                            cursor.execute("PRAGMA index_list('topic_mapping')")
                            idxs = cursor.fetchall()
                            needs_migration = False
                            for ix in idxs:
                                if ix[2] == 1: # Unique
                                    cursor.execute(f"PRAGMA index_info('{ix[1]}')")
                                    cols = cursor.fetchall()
                                    if len(cols) == 1 and cols[0][2] == 'topic_id':
                                        needs_migration = True
                                        break
                            
                            if needs_migration:
                                print("Fixing TopicMapping UNIQUE constraint...")
                                cursor.execute("ALTER TABLE topic_mapping RENAME TO topic_mapping_old")
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
                                cursor.execute("""
                                    INSERT INTO topic_mapping (id, topic_id, chat_id, topic_name, is_active, is_archived, is_hidden, is_pinned, category)
                                    SELECT id, topic_id, chat_id, topic_name, is_active, is_archived, is_hidden, is_pinned, category
                                    FROM topic_mapping_old
                                """)
                                cursor.execute("DROP TABLE topic_mapping_old")
                                conn.commit()
                                print("TopicMapping constraint fixed successfully.")
                            conn.close()
                    except Exception as e:
                        print(f"TopicMapping Migration error: {e}")

                def fix_rss_config_columns():
                    try:
                        with app.app_context():
                            from .models import db
                            conn = db.engine.raw_connection()
                            cursor = conn.cursor()
                            
                            cursor.execute("PRAGMA table_info('rss_feed_config')")
                            cols = [row[1] for row in cursor.fetchall()]
                            
                            if len(cols) > 0 and 'check_interval_minutes' not in cols:
                                print("Adding missing columns to rss_feed_config...")
                                cursor.execute("ALTER TABLE rss_feed_config ADD COLUMN check_interval_minutes INTEGER DEFAULT 30")
                                cursor.execute("ALTER TABLE rss_feed_config ADD COLUMN post_time VARCHAR(5)")
                                conn.commit()
                                print("rss_feed_config updated successfully.")
                            conn.close()
                    except Exception as e:
                        print(f"RSSFeedConfig Migration error: {e}")
                        
                fix_topic_mapping_constraint()
                fix_rss_config_columns()

                if not User.query.filter_by(username='admin').first():
                    admin = User(username='admin', role='admin')
                    admin.set_password('admin') 
                    db.session.add(admin)
                    db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"CRITICAL DB Error during app context: {e}")
                print("Database appears unreachable. Please check your DB credentials or server status.")
                # REMOVED: Automatic deletion of INSTALL_LOCK. 
                # This is a security risk as it opens the setup page to anyone.

    # Root-Route leitet direkt zum Dashboard weiter
    @app.route('/')
    def root():
        return redirect(url_for('dashboard.index'))

    # Scheduler initialisieren (nur wenn installiert, sonst crasht er wegen fehlender DB!)
    if os.path.exists(INSTALL_LOCK):
        scheduler = APScheduler()
        scheduler.init_app(app)
        scheduler.start()
        
        # Auto-Update Job registrieren (läuft alle 6 Stunden)
        from .updater_task import check_and_auto_update
        scheduler.add_job(id='auto_update_job', func=check_and_auto_update, trigger='interval', hours=6, args=[app])

    # Start the Live Bot polling thread
    import threading
    def run_sync_loop():
        import time
        from .live_bot import run_background_sync
        time.sleep(5) # Give the server time to start
        while True:
            try:
                run_background_sync()
            except Exception as e:
                print(f"Background Sync Error: {e}")
            time.sleep(10) # Poll every 10 seconds

    threading.Thread(target=run_sync_loop, daemon=True).start()

    # --- AUTOMATIC TOPIC SEEDING (Self-Healing) ---
    def seed_topics():
        with app.app_context():
            try:
                from .models import db, TopicMapping
                topics = [
                    # Hauptgruppe (-1002206300882)
                    (1, -1002206300882, 'Vorstellungsrunde', 'Hauptgruppe'),
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
                    
                    # Admins & Team (-1003372573784)
                    (1, -1003372573784, 'General', 'Admins & Team'),
                    (623, -1003372573784, 'Chat', 'Admins & Team'),
                    (157, -1003372573784, 'Whitelist', 'Admins & Team'),
                    (61, -1003372573784, 'Notification / Notizen', 'Admins & Team'),
                    (208, -1003372573784, 'Bild', 'Admins & Team'),
                    (55, -1003372573784, 'Moderation', 'Admins & Team'),
                    (3, -1003372573784, 'Verwarnungen', 'Admins & Team'),
                ]
                # Bestehende (falsche) Mappings bereinigen, die nicht in der Liste sind
                valid_ids = [(t[0], t[1]) for t in topics]
                # Wir löschen alle Mappings, die keine Chat-ID haben oder in der falschen Gruppe sind
                # Aber Vorsicht: Wir löschen nur, wenn es ein bekanntes Admin-Topic in der Hauptgruppe ist
                admin_topic_ids = [623, 157, 61, 208, 55, 3] # Typische Admin IDs
                TopicMapping.query.filter(
                    TopicMapping.topic_id.in_(admin_topic_ids),
                    TopicMapping.chat_id == -1002206300882
                ).delete(synchronize_session=False)

                for tid, cid, name, cat in topics:
                    t = TopicMapping.query.filter_by(topic_id=tid, chat_id=cid).first()
                    if t:
                        t.topic_name = name
                        t.category = cat
                        t.is_deleted = False # Sicherstellen dass sie aktiv sind
                    else:
                        t = TopicMapping(topic_id=tid, chat_id=cid, topic_name=name, category=cat, is_active=True)
                        db.session.add(t)
                db.session.commit()
                print("Topics successfully seeded/updated.")
            except Exception as e:
                print(f"Seeding error: {e}")
                db.session.rollback()

    if os.path.exists(INSTALL_LOCK):
        seed_topics()

    return app

