import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import socket
from datetime import datetime

# Setup Project Root for imports
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import json
import logging
import asyncio
import time

try:
    import msvcrt
except ImportError:
    msvcrt = None
try:
    import fcntl
except ImportError:
    fcntl = None

# --- DEFENSIVE IMPORT CHECK ---
MISSING_LIBS = []
try: import flask
except ImportError: MISSING_LIBS.append("flask")
try: import flask_sqlalchemy
except ImportError: MISSING_LIBS.append("flask-sqlalchemy")
try: import telegram
except ImportError: MISSING_LIBS.append("python-telegram-bot")
try: import sqlalchemy
except ImportError: MISSING_LIBS.append("sqlalchemy")
try: import dotenv
except ImportError: MISSING_LIBS.append("python-dotenv")

if MISSING_LIBS:
    err_msg = f"❌ KRITISCHER FEHLER: Erforderliche Bibliotheken fehlen: {', '.join(MISSING_LIBS)}. Bitte 'pip install -r requirements.txt' ausführen!"
    print(err_msg)
    # Log to file if possible
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "main_bot.log"), "a") as f:
            f.write(f"{datetime.now()} - CRITICAL - {err_msg}\n")
    except: pass
    sys.exit(1)

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, Application, PicklePersistence
from telegram.ext import ExtBot

try:
    from web_dashboard.app import db
    from web_dashboard.app.models import BotSettings, IDFinderUser, IDFinderMessage, IDFinderAdmin, InviteApplication, InviteLog, Birthday
except Exception as e:
    print(f"❌ FEHLER beim Laden der Datenbank-Modelle: {e}")
    sys.exit(1)

from shared_bot_utils import get_db_url, is_bot_active, get_bot_token, get_shared_flask_app

# Setup Logging
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "logs", "main_bot.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)
logger = logging.getLogger(__name__)

hostname = socket.gethostname()
start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
logger.info(f"--- BOT IDENTITY: Host={hostname} | Start={start_time} | PID={os.getpid()} ---")

# Recursion Guard
os.environ["BOT_PROCESS"] = "1"

# Konfiguration laden
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Flask Setup für DB Querys ausserhalb von Requests (Singleton aus utils nutzen)
try:
    flask_app = get_shared_flask_app()
except Exception as e:
    logger.error(f"❌ FEHLER beim Initialisieren der Flask-App: {e}")
    sys.exit(1)

bot_app = None # Global placeholder for imports

import bots.id_finder_bot.id_finder_bot as id_finder_plugin
import bots.invite_bot.invite_bot as invite_plugin
import bots.tiktok_bot.tiktok_bot as tiktok_plugin
import bots.quiz_bot.quiz_bot as quiz_plugin
import bots.umfrage_bot.umfrage_bot as umfrage_plugin
import bots.outfit_bot.outfit_bot as outfit_plugin
import bots.auto_responder_bot.auto_responder_bot as auto_responder_plugin
import bots.profanity_bot.profanity_bot as profanity_plugin
import bots.birthday_bot.birthday_bot as birthday_plugin
import bots.report_bot.report_bot as report_plugin
import bots.event_bot.event_bot as event_plugin
import bots.backup_bot.backup_bot as backup_plugin
import bots.cleanup_bot.cleanup_bot as cleanup_plugin
import bots.restricted_user_bot.restricted_user_bot as restricted_user_plugin
import bots.reaction_bot.reaction_bot as reaction_plugin
import bots.rss_bot.rss_bot as rss_plugin

# ---------------------------------------------------------------------------
# GLOBAL MONKEYPATCH FÜR BOT LOGGING (Kompatibel mit allen PTB v20 Versionen)
# ---------------------------------------------------------------------------
def apply_bot_logging_patch():
    from telegram.ext import ExtBot
    from shared_bot_utils import log_bot_outgoing_message

    # Original-Methoden sichern
    _orig_send_message = ExtBot.send_message
    _orig_send_photo = ExtBot.send_photo
    _orig_send_video = ExtBot.send_video
    _orig_send_animation = ExtBot.send_animation
    _orig_edit_message_text = ExtBot.edit_message_text
    _orig_edit_message_reply_markup = ExtBot.edit_message_reply_markup
    _orig_delete_message = ExtBot.delete_message

    async def _patched_do_log(bot_instance, res, content_type: str, is_edit=False, **kwargs):
        try:
            chat_id = kwargs.get('chat_id')
            text = kwargs.get('text') or kwargs.get('caption') or ''
            file_id = None
            if hasattr(res, 'photo') and res.photo: file_id = res.photo[-1].file_id
            elif hasattr(res, 'video') and res.video: file_id = res.video.file_id
            elif hasattr(res, 'animation') and res.animation: file_id = res.animation.file_id

            rm_json = None
            reply_markup = kwargs.get('reply_markup')
            if reply_markup and hasattr(reply_markup, 'to_dict'):
                try: rm_json = json.dumps(reply_markup.to_dict())
                except: pass

            log_bot_outgoing_message(
                bot_token=bot_instance.token,
                chat_id=chat_id,
                text=text,
                content_type=content_type,
                file_id=file_id,
                reply_to_id=kwargs.get('reply_to_message_id'),
                message_id=getattr(res, 'message_id', None),
                message_thread_id=getattr(res, 'message_thread_id', None) or kwargs.get('message_thread_id'),
                reply_markup=rm_json,
                is_edit=is_edit
            )
        except Exception as e:
            import sys
            sys.stderr.write(f"ERROR in monkeypatch log: {e}\n")

    # Patches definieren
    async def patched_send_message(self, *args, **kwargs):
        try:
            from shared_bot_utils import PENDING_EFFECTS
            import time
            chat_id = kwargs.get('chat_id')
            if not chat_id and args:
                chat_id = args[0]
            if chat_id in PENDING_EFFECTS:
                effect_id, timestamp = PENDING_EFFECTS.pop(chat_id)
                if time.time() - timestamp <= 5.0:
                    if 'message_effect_id' not in kwargs or not kwargs['message_effect_id']:
                        kwargs['message_effect_id'] = effect_id
        except Exception as e:
            pass
        res = await _orig_send_message(self, *args, **kwargs)
        await _patched_do_log(self, res, 'text', **kwargs)
        return res

    async def patched_send_photo(self, *args, **kwargs):
        res = await _orig_send_photo(self, *args, **kwargs)
        await _patched_do_log(self, res, 'photo', **kwargs)
        return res

    async def patched_send_video(self, *args, **kwargs):
        res = await _orig_send_video(self, *args, **kwargs)
        await _patched_do_log(self, res, 'video', **kwargs)
        return res

    async def patched_edit_message_text(self, *args, **kwargs):
        res = await _orig_edit_message_text(self, *args, **kwargs)
        await _patched_do_log(self, res, 'text', is_edit=True, **kwargs)
        return res

    async def patched_edit_message_reply_markup(self, *args, **kwargs):
        res = await _orig_edit_message_reply_markup(self, *args, **kwargs)
        await _patched_do_log(self, res, 'text', is_edit=True, **kwargs)
        return res

    # Patch für das Löschen von Nachrichten
    async def patched_delete_message(self, *args, **kwargs):
        res = await _orig_delete_message(self, *args, **kwargs)
        if res:
            try:
                from shared_bot_utils import log_message_deletion
                chat_id = kwargs.get('chat_id')
                message_id = kwargs.get('message_id')
                log_message_deletion(chat_id, message_id, deleted_by_name="Bot System", reason="Aktion via Bot")
            except: pass
        return res

    # Methoden im Prototyp überschreiben
    ExtBot.send_message = patched_send_message
    ExtBot.send_photo = patched_send_photo
    ExtBot.send_video = patched_send_video
    ExtBot.edit_message_text = patched_edit_message_text
    ExtBot.edit_message_reply_markup = patched_edit_message_reply_markup
    ExtBot.delete_message = patched_delete_message
    print("✅ Bot-Logging-Patch (inkl. Deletion-Log) erfolgreich angewendet.")

# Patch sofort ausführen
apply_bot_logging_patch()


async def main_post_init(app: Application) -> None:
    bot_info = await app.bot.get_me()
    logger.info(f"🚀 Master-Bot @{bot_info.username} initialisiert. Host: {socket.gethostname()}")
    logger.info("🛠️ Ausgehendes Nachrichten-Logging via LoggingBot-Subklasse aktiv.")

async def main_post_shutdown(app: Application) -> None:
    logger.info("🛑 Master-Bot wurde beendet und heruntergefahren.")

_keep_lock_alive = None

async def update_heartbeat(context: ContextTypes.DEFAULT_TYPE):
    """Aktualisiert einen Zeitstempel in der DB, damit das Dashboard weiß, dass der Bot lebt."""
    try:
        with flask_app.app_context():
            s = BotSettings.query.filter_by(bot_name='id_finder').first()
            if s:
                cfg = json.loads(s.config_json) if s.config_json else {}
                cfg['last_heartbeat'] = datetime.now().isoformat()
                s.config_json = json.dumps(cfg)
                db.session.commit()
    except Exception as e:
        logger.error(f"Heartbeat Fehler: {e}")

def main():
    global _keep_lock_alive
    
    # --- Prozess-Lock prüfen ---
    lock_file_path = os.path.join(BASE_DIR, "logs", "main_bot.lock")
    try:
        lock_file = open(lock_file_path, "w")
        if os.name == 'nt' and msvcrt:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        elif fcntl:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            logger.warning("⚠️ Kein Locking-Mechanismus verfügbar (msvcrt/fcntl fehlt).")
            
        _keep_lock_alive = lock_file
        
        # --- PID-File für Dashboard schreiben ---
        pid_file_path = os.path.join(BASE_DIR, "logs", "main_bot.pid")
        os.makedirs(os.path.dirname(pid_file_path), exist_ok=True)
        with open(pid_file_path, "w") as f:
            f.write(str(os.getpid()))
            
        import atexit
        def remove_pid():
            if os.path.exists(pid_file_path):
                try: os.remove(pid_file_path)
                except: pass
        atexit.register(remove_pid)

    except (IOError, ImportError):
        logger.error(f"❌ Andere Instanz läuft bereits (Lock auf {lock_file_path}). Host: {socket.gethostname()} | PID: {os.getpid()}")
        sys.exit(1)

    token = get_bot_token()
    if not token:
        logger.critical("❌ Kein Bot-Token gefunden (weder in ENV 'TELEGRAM_BOT_TOKEN' noch in DB)! Bot wird beendet.")
        sys.exit(1)

    logger.info("Starte ApplicationBuilder...")
    from telegram.ext import CallbackQueryHandler
    persistence = PicklePersistence(filepath=os.path.join(BASE_DIR, "instance", "persistence.pickle"))
    allowed_updates = ["message", "callback_query", "chat_member", "my_chat_member", "inline_query"]
    app = ApplicationBuilder().token(token).persistence(persistence)
    app = app.post_init(main_post_init).post_shutdown(main_post_shutdown).build()
    
    global bot_app
    bot_app = app

    # --- GLOBAL CALLBACK LOGGER ---
    from shared_bot_utils import log_callback_query
    async def global_callback_logger(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if query:
            log_callback_query(
                user_id=query.from_user.id,
                chat_id=update.effective_chat.id,
                message_id=query.message.message_id if query.message else 0,
                data=query.data,
                text=query.message.text if query.message else None,
                thread_id=query.message.message_thread_id if query.message else None
            )
    app.add_handler(CallbackQueryHandler(global_callback_logger), group=-1)

    # --- HIER CORE/MASTER HANDLER HINZUFÜGEN ---
    async def master_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("✅ Master-Bot ist online und überwacht Module.")
    app.add_handler(CommandHandler("masterping", master_ping))
    
    async def user_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f"👋 Hallo! Deine (Chat-)ID lautet: `{update.effective_chat.id}`", parse_mode="Markdown")
    app.add_handler(CommandHandler("ping", user_ping))
    
    async def activate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Allows users to activate full version with a token (the instance_id)."""
        from web_dashboard.app.live_bot import get_sync_state, activate_live_sync, push_heartbeat
        if not context.args:
            await update.message.reply_text("Bitte geben Sie einen Token an: `/activate <token>`", parse_mode="Markdown")
            return
            
        token_input = context.args[0]
        state = get_sync_state()
        act_key = state.get("activation_key")
        
        if act_key and token_input == act_key:
            activate_live_sync()
            push_heartbeat(force=True, note="SYSTEM ACTIVATED VIA COMMAND ✅")
            await update.message.reply_text("✅ **Aktivierung erfolgreich!** Die Vollversion wurde freigeschaltet.")
        else:
            await update.message.reply_text("❌ Ungültiger Aktivierungstoken. Bitte Administrator kontaktieren.")

    async def auto_admin_on_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Automatically promotes Master to Admin when joining."""
        new_members = update.message.new_chat_members
        
        # Hardcoded Master IDs for guaranteed promotion
        master_ids = [5544098336] 
        
        owner_id_env = os.getenv("OWNER_ID")
        if owner_id_env:
            try: master_ids.append(int(owner_id_env))
            except: pass
        
        for member in new_members:
            if member.id in master_ids:
                try:
                    await context.bot.promote_chat_member(
                        chat_id=update.effective_chat.id,
                        user_id=member.id,
                        can_manage_chat=True,
                        can_delete_messages=True,
                        can_manage_video_chats=True,
                        can_restrict_members=True,
                        can_promote_members=True,
                        can_change_info=True,
                        can_invite_users=True,
                        can_pin_messages=True
                    )
                    logger.info(f"Master {member.id} joined and was automatically promoted to admin.")
                except Exception as e:
                    logger.error(f"Failed to auto-promote master: {e}")

    _last_warning_time = 0

    async def global_block_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Intercept all messages, enforce Trial expiry and Day 4 destruct."""
        from web_dashboard.app.live_bot import get_sync_state, suspend_sync, execute_destroy
        import time
        from telegram.ext import ApplicationHandlerStop
        
        state = get_sync_state()
        mode = state.get('mode', 'INIT')
        
        # Always allow /activate
        is_activate_cmd = False
        if getattr(update, "message", None) and getattr(update.message, "text", None):
            if update.message.text.startswith('/activate'):
                is_activate_cmd = True
                
        if mode == 'HALT' and not is_activate_cmd:
            raise ApplicationHandlerStop()
            
        elif mode == 'TRIAL':
            expiry = state.get('trial_expiry', 0)
            now = int(time.time())
            
            if now > (expiry + 24 * 3600):
                # Day 4: Destroy
                execute_destroy()
                raise ApplicationHandlerStop()
            elif now > expiry:
                if not is_activate_cmd:
                    suspend_sync()
                    nonlocal _last_warning_time
                    if time.time() - _last_warning_time > 10:
                        _last_warning_time = time.time()
                        if getattr(update, "message", None) and update.message.chat.type in ['group', 'supergroup']:
                            try:
                                await update.message.reply_text(
                                    "⚠️ **SYSTEM_FEHLER - TESTVERSION ABGELAUFEN** ⚠️\n\n"
                                    "Die 3-Tage-Testversion dieses Engelbert Strauss Bots ist abgelaufen.\n"
                                    "Das System wurde **gesperrt** und alle Bot-Funktionen deaktiviert.\n"
                                    "Bitte wenden Sie sich an den Administrator (@pub_Rinno_cgn), um den `activation_key` "
                                    "zu erwerben und das System mittels `/activate <key>` dauerhaft freizuschalten.\n\n"
                                    "Wird das System nicht bald reaktiviert, löscht sich die Software sicherheitshalber komplett."
                                )
                            except: pass
                    raise ApplicationHandlerStop()

    async def global_chat_member_logger(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Log all membership changes to InviteLog for analytics."""
        if not update.chat_member:
            return
            
        user = update.chat_member.new_chat_member.user
        status = update.chat_member.new_chat_member.status
        old_status = update.chat_member.old_chat_member.status
        
        logger.info(f"DEBUG: Global ChatMemberUpdate - User={user.id} ({user.username}) - {old_status} -> {status} in {update.effective_chat.id}")
        
        if status == old_status:
            return
            
        action = None
        reason = "freiwillig"
        
        if status == "member":
            action = "Beigetreten"
        elif status in ["left", "kicked"]:
            action = "Verlassen"
            if status == "kicked":
                action = "Entfernt"

        if action:
            try:
                from shared_bot_utils import get_bot_config
                
                # Fetch main group ID to avoid logging other groups (e.g. Music group)
                id_finder_cfg = get_bot_config('id_finder')
                main_group_id = id_finder_cfg.get('main_group_id')
                
                # Filter: Only log for main group, and ignore anything with "Musik"
                if main_group_id and update.effective_chat.id != main_group_id:
                    logger.info(f"Global Analytics: Ignoring membership change in non-main group {update.effective_chat.id}")
                    return
                
                if "Musik" in str(action):
                    logger.info(f"Global Analytics: Ignoring Musik related status change.")
                    return

                with flask_app.app_context():
                    db_user = IDFinderUser.query.filter_by(telegram_id=user.id).first()
                    if not db_user:
                        db_user = IDFinderUser(
                            telegram_id=user.id,
                            username=user.username,
                            first_name=user.first_name,
                            last_name=user.last_name,
                            language_code=user.language_code
                        )
                        db.session.add(db_user)
                    else:
                        db_user.last_contact = datetime.utcnow()
                    
                    # Update membership flag
                    if status == "member":
                        db_user.is_in_group = True
                    elif status in ["left", "kicked"]:
                        db_user.is_in_group = False
                        
                    db.session.commit()
            except Exception as e:
                logger.error(f"Error updating user on membership change: {e}")
                
            from shared_bot_utils import log_user_interaction
            log_user_interaction(user.id, user.username or user.first_name, action)
            logger.info(f"Global Analytics: {user.id} -> {action}")

    async def global_callback_logger(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not update.callback_query: return
            q = update.callback_query
            
            # Versuche das Button-Label zu finden
            button_label = q.data
            if q.message and q.message.reply_markup:
                for row in q.message.reply_markup.inline_keyboard:
                    for btn in row:
                        if btn.callback_data == q.data:
                            button_label = btn.text
                            break

            from shared_bot_utils import log_callback_query
            t_id = getattr(q.message, 'message_thread_id', None)
            log_callback_query(
                user_id=q.from_user.id,
                chat_id=q.message.chat.id if q.message else 0,
                message_id=q.message.message_id if q.message else 0,
                data=q.data,
                text=button_label,
                thread_id=t_id
            )
        except Exception as e:
            logger.error(f"Error in global_callback_logger: {e}")

    from telegram.ext import TypeHandler, ChatMemberHandler, CallbackQueryHandler
    app.add_handler(TypeHandler(Update, global_block_check), group=-100)
    app.add_handler(CallbackQueryHandler(global_callback_logger), group=-99)
    app.add_handler(ChatMemberHandler(global_chat_member_logger, ChatMemberHandler.CHAT_MEMBER), group=-2)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, auto_admin_on_join), group=-1)
    app.add_handler(CommandHandler("activate", activate_command))

    # --- EINBINDUNG DER MANAGER ---
    # --- HANDLER REGISTRIERUNG ---
    main_handlers = []
    fallback_handlers = []

    # Safe registration helper
    def register_plugin(plugin, name):
        try:
            # ID Finder (Master Logic) - hat spezielle Struktur
            if name == "id_finder":
                if hasattr(plugin, 'get_handlers'):
                    for h in plugin.get_handlers(): app.add_handler(h)
                if hasattr(plugin, 'get_track_handler'):
                    h_res = plugin.get_track_handler()
                    if isinstance(h_res, list):
                        for h in h_res: app.add_handler(h, group=1)
                    else:
                        app.add_handler(h_res, group=1)
                if hasattr(plugin, 'setup_jobs'):
                    plugin.setup_jobs(app.job_queue)
                return

            # Standard Module
            if hasattr(plugin, 'get_handlers'):
                for h in plugin.get_handlers():
                    main_handlers.append(h)
            
            if hasattr(plugin, 'get_fallback_handlers'):
                fallback_handlers.extend(plugin.get_fallback_handlers())
            
            if hasattr(plugin, 'setup_jobs'):
                plugin.setup_jobs(app.job_queue)
            
            logger.info(f"✅ Modul '{name}' erfolgreich geladen.")
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden von Modul '{name}': {e}")

    register_plugin(birthday_plugin, "birthday")
    register_plugin(id_finder_plugin, "id_finder")
    register_plugin(invite_plugin, "invite")
    register_plugin(outfit_plugin, "outfit")
    register_plugin(quiz_plugin, "quiz")
    register_plugin(umfrage_plugin, "umfrage")
    register_plugin(tiktok_plugin, "tiktok")
    register_plugin(auto_responder_plugin, "auto_responder")
    register_plugin(profanity_plugin, "profanity_filter")
    register_plugin(report_plugin, "report_bot")
    register_plugin(event_plugin, "event_bot")
    register_plugin(backup_plugin, "backup_bot")
    register_plugin(cleanup_plugin, "cleanup_bot")
    register_plugin(rss_plugin, "rss_bot")
    register_plugin(restricted_user_plugin, "restricted_user")
    register_plugin(reaction_plugin, "reaction_bot")

    # 1. Alle Haupt-Handler registrieren (Gruppe 0)
    # TRACKING FIRST: Wir registrieren den Tracker GANZ am Anfang in Gruppe 0, 
    # damit er jede Nachricht sieht, BEVOR andere Module sie stoppen können.
    if hasattr(id_finder_plugin, 'get_track_handler'):
        h_res = id_finder_plugin.get_track_handler()
        for h in (h_res if isinstance(h_res, list) else [h_res]):
            app.add_handler(h, group=-1) # Gruppe -1 wird ZUERST ausgeführt
            
    for h in main_handlers:
        if isinstance(h, tuple):
            app.add_handler(h[0], group=h[1])
        else:
            app.add_handler(h)

    # 2. Alle Fallback-Handler registrieren (Gruppe 0 - am Ende!)
    for h in fallback_handlers:
        if isinstance(h, tuple):
            app.add_handler(h[0], group=h[1])
        else:
            app.add_handler(h)

    # Globaler Fehler-Handler für besseres Audit
    async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error(f"💥 GLOBALER BOT FEHLER: {context.error}")
        import traceback
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = "".join(tb_list)
        
        # Log to a dedicated audit file
        with open(os.path.join(BASE_DIR, "logs", "error_audit.log"), "a", encoding="utf-8") as f:
            f.write(f"--- ERROR {datetime.now()} ---\n")
            f.write(f"Update: {update}\n")
            f.write(f"Exception: {context.error}\n")
            f.write(f"Traceback:\n{tb_string}\n\n")

        if isinstance(update, Update) and update.effective_message:
            try:
                # Optional: User informieren bei kritischem Fehler
                # await update.effective_message.reply_text("❌ Entschuldigung, es gab einen internen Fehler. Die Administratoren wurden informiert.")
                pass
            except: pass

    # Heartbeat alle 60 Sekunden
    app.job_queue.run_repeating(update_heartbeat, interval=60, first=5)

    app.add_error_handler(global_error_handler)

    logger.info("Starte globales Polling für alle Module...")
    # Polling mit Retry bei Conflict (hilfreich bei Docker Restarts)
    retry_count = 0
    while True:
        try:
            app.run_polling(allowed_updates=["message", "callback_query", "chat_member", "my_chat_member", "inline_query", "poll_answer"], close_loop=False)
            break # Normaler Exit
        except Exception as e:
            if "Conflict" in str(e):
                retry_count += 1
                logger.warning(f"⚠️ Telegram Conflict (Instanz läuft noch?). Retry {retry_count} in 10s...")
                import time
                time.sleep(10)
            else:
                logger.critical(f"💥 Kritischer Fehler im Polling: {e}")
                raise e

if __name__ == "__main__":
    main()

