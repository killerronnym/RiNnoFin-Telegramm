import logging
import os
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# --- Paths ---
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BOT_DIR))
# Import models from web_dashboard.app.models
sys.path.append(PROJECT_ROOT)

from web_dashboard.app.models import db, BotSettings, IDFinderAdmin, IDFinderUser, IDFinderMessage, TopicMapping, Broadcast, AutoCleanupTask, IDFinderWarning
from flask import Flask

from shared_bot_utils import get_db_url, get_bot_config, is_bot_active, get_shared_flask_app
flask_app = get_shared_flask_app()

# --- Logging ---
LOG_FILE = os.path.join(BOT_DIR, "id_finder_bot.log")
# Ensure logging uses UTF-8 even on Windows
# logging.basicConfig removed - handled by main_bot.py
logger = logging.getLogger(__name__)

# Force UTF-8 for stdout/stderr if possible
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    from telegram import Update, ForumTopic, ChatPermissions
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, Application
    from telegram.constants import ParseMode
except ImportError:
    logger.error("Erforderliche Bibliothek 'python-telegram-bot' nicht gefunden!")
    sys.exit(1)

from shared_bot_utils import get_bot_config

async def download_user_avatar(bot, user_id):
    """Downloads the user's profile photo and saves it to static/avatars/."""
    try:
        from shared_bot_utils import get_shared_flask_app
        
        flask_app = get_shared_flask_app()
        # AVATAR_DIR path: documents/bot t/web_dashboard/app/static/avatars/
        current_dir = os.path.dirname(os.path.abspath(__file__)) # c:\...\bots\id_finder_bot
        project_root = os.path.dirname(os.path.dirname(current_dir))
        AVATAR_DIR = os.path.join(project_root, 'web_dashboard', 'app', 'static', 'avatars')
        os.makedirs(AVATAR_DIR, exist_ok=True)

        with flask_app.app_context():
            user = IDFinderUser.query.filter_by(telegram_id=user_id).first()
            if not user: return None
            
            now = datetime.utcnow()
            # If cached recently (last 24h), skip
            if user.photo_cached_at and (now - user.photo_cached_at).total_seconds() < 86400:
                if os.path.exists(os.path.join(AVATAR_DIR, f"{user_id}.jpg")):
                    return user.photo_url

            # Fetch profile photos
            photos = await bot.get_user_profile_photos(user_id, limit=1)
            if not photos or not photos.photos:
                user.photo_url = f"https://ui-avatars.com/api/?name={user.first_name or 'U'}&background=random"
                user.photo_cached_at = now
                db.session.commit()
                return user.photo_url
            
            # Get largest version
            file_id = photos.photos[0][-1].file_id
            file = await bot.get_file(file_id)
            
            dest_path = os.path.join(AVATAR_DIR, f"{user_id}.jpg")
            await file.download_to_drive(custom_path=dest_path)
            
            user.photo_file_id = file_id
            user.photo_url = f"/static/avatars/{user_id}.jpg"
            user.photo_cached_at = now
            db.session.commit()
            return user.photo_url
    except Exception as e:
        logger.error(f"Error downloading avatar for {user_id}: {e}")
        return None

# --- Config Management ---
def get_config_from_db():
    try:
        return get_bot_config("id_finder")
    except Exception as e:
        logger.error(f"Fehler beim Laden der Konfiguration aus DB: {e}")
    return None

# --- Auto Cleanup Task ---
async def process_cleanup_tasks(context: ContextTypes.DEFAULT_TYPE):
    if not is_bot_active('id_finder'): return
    """
    Sucht nach abgelaufenen Bot-Meldungen und löscht diese aus dem Chat.
    """
    try:
        with flask_app.app_context():
            now = datetime.utcnow()
            tasks = AutoCleanupTask.query.filter(
                AutoCleanupTask.status == 'pending',
                AutoCleanupTask.cleanup_at <= now
            ).all()

            for task in tasks:
                try:
                    logger.info(f"Lösche alte Bot-Meldung: Chat {task.chat_id}, Msg {task.message_id}")
                    await context.bot.delete_message(chat_id=task.chat_id, message_id=task.message_id)
                except Exception as e:
                    logger.debug(f"Konnte Nachricht nicht löschen (evtl. schon weg): {e}")
                
                task.status = 'done'
            
            db.session.commit()
            
            # Optional: Erledigte Aufgaben ganz löschen
            AutoCleanupTask.query.filter_by(status='done').delete()
            db.session.commit()
            
    except Exception as e:
        logger.error(f"Fehler bei Auto-Cleanup: {e}")

# --- Broadcast Engine ---
async def check_and_send_broadcasts(context: ContextTypes.DEFAULT_TYPE):
    # Broadcast-Manager läuft immer, solange der Bot-Prozess aktiv ist.
    # (Auch wenn das ID-Finder Modul im Dashboard auf 'AUS' steht)
    """
    Prüft die Datenbank nach fälligen Broadcasts und versendet sie.
    """
    config = get_config_from_db()
    if not config: return
    
    main_group_id = config.get('main_group_id')
    if not main_group_id: return

    try:
        with flask_app.app_context():
            now = datetime.utcnow()
            pending_broadcasts = Broadcast.query.filter(
                Broadcast.status == 'pending',
                Broadcast.scheduled_at <= now
            ).all()

            for b in pending_broadcasts:
                logger.info(f"Sende fälligenn Broadcast: {b.id}")
                try:
                    chat_id = main_group_id
                    thread_id = int(b.topic_id) if b.topic_id and str(b.topic_id).isdigit() else None
                    has_spoiler = getattr(b, 'spoiler', False)
                    
                    msg = None
                    media_files = []
                    if b.media_files:
                        try:
                            media_files = json.loads(b.media_files)
                        except:
                            logger.error(f"Fehler beim Parsen der media_files für Broadcast {b.id}")

                    # 1. Fall: Album (Mehrere Bilder/Videos)
                    if media_files:
                        from telegram import InputMediaPhoto, InputMediaVideo
                        media_group = []
                        for i, rel_path in enumerate(media_files):
                            fpath = os.path.join(PROJECT_ROOT, 'web_dashboard', 'app', 'static', rel_path)
                            if os.path.exists(fpath):
                                cap = b.text if i == 0 else None # Caption nur beim ersten Bild
                                if rel_path.lower().endswith(('.mp4', '.mov', '.avi')):
                                    media_group.append(InputMediaVideo(open(fpath, 'rb'), caption=cap, parse_mode=ParseMode.HTML, has_spoiler=has_spoiler))
                                else:
                                    media_group.append(InputMediaPhoto(open(fpath, 'rb'), caption=cap, parse_mode=ParseMode.HTML, has_spoiler=has_spoiler))
                        
                        if media_group:
                            msgs = await context.bot.send_media_group(
                                chat_id=chat_id, media=media_group,
                                message_thread_id=thread_id, disable_notification=b.silent_send
                            )
                            msg = msgs[0] if msgs else None

                    # 2. Fall: Einzelne Datei (kompatibel zu altem System)
                    elif b.media_path:
                        full_media_path = os.path.join(PROJECT_ROOT, 'web_dashboard', 'app', 'static', b.media_path)
                        if os.path.exists(full_media_path):
                            with open(full_media_path, 'rb') as f:
                                try:
                                    if b.media_type == 'image':
                                        msg = await context.bot.send_photo(
                                            chat_id=chat_id, photo=f, caption=b.text,
                                            message_thread_id=thread_id, disable_notification=b.silent_send,
                                            parse_mode=ParseMode.HTML, has_spoiler=has_spoiler
                                        )
                                    elif b.media_type == 'video':
                                        msg = await context.bot.send_video(
                                            chat_id=chat_id, video=f, caption=b.text,
                                            message_thread_id=thread_id, disable_notification=b.silent_send,
                                            parse_mode=ParseMode.HTML, has_spoiler=has_spoiler
                                        )
                                except Exception as he:
                                    if "Can't parse entities" in str(he):
                                        logger.warning(f"HTML Parse Fehler bei Broadcast {b.id}, versende als Plaintext.")
                                        f.seek(0)
                                        if b.media_type == 'image':
                                            msg = await context.bot.send_photo(chat_id=chat_id, photo=f, caption=b.text, message_thread_id=thread_id, has_spoiler=has_spoiler)
                                        else:
                                            msg = await context.bot.send_video(chat_id=chat_id, video=f, caption=b.text, message_thread_id=thread_id, has_spoiler=has_spoiler)
                                    else: raise he
                        else:
                            logger.error(f"Mediendatei nicht gefunden: {full_media_path}")
                            b.status = 'failed'
                            continue

                    # 3. Fall: Reiner Text
                    else:
                        try:
                            msg = await context.bot.send_message(
                                chat_id=chat_id, text=b.text,
                                message_thread_id=thread_id, disable_notification=b.silent_send,
                                parse_mode=ParseMode.HTML
                            )
                        except Exception as he:
                            if "Can't parse entities" in str(he):
                                logger.warning(f"HTML Parse Fehler bei Text-Broadcast {b.id}, versende als Plaintext.")
                                msg = await context.bot.send_message(chat_id=chat_id, text=b.text, message_thread_id=thread_id)
                            else: raise he
                    
                    # Nachricht anpinnen falls gewünscht
                    if b.pin_message and msg:
                        try:
                            await context.bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id)
                        except Exception as pe:
                            logger.error(f"Konnte Nachricht {msg.message_id} nicht anpinnen: {pe}")

                    b.status = 'sent'
                    logger.info(f"Broadcast {b.id} erfolgreich gesendet.")

                    # Log to IDFinderMessage so it appears in Live feed
                    if msg:
                        try:
                            # Use internal log function
                            bot_token = context.bot.token
                            log_bot_message_sync(
                                bot_token=bot_token,
                                chat_id=chat_id,
                                thread_id=thread_id,
                                text=b.text,
                                content_type=b.media_type if b.media_path or media_files else 'text',
                                file_id=msg.photo[-1].file_id if msg.photo else (msg.video.file_id if msg.video else (msg.animation.file_id if msg.animation else None))
                            )
                        except Exception as log_e:
                            logger.error(f"Error logging broadcast to feed: {log_e}")

                except Exception as e:
                    logger.error(f"Fehler beim Senden von Broadcast {b.id}: {e}")
                    b.status = 'failed'
                
            db.session.commit()
    except Exception as e:
        logger.error(f"Fehler in der Broadcast Engine: {e}")

# --- Activity Tracking ---
def log_bot_message_sync(bot_token, chat_id, thread_id, text, content_type='text', file_id=None):
    """Logs a message sent BY the bot itself to the database."""
    try:
        with flask_app.app_context():
            bot_id = int(bot_token.split(':')[0])
            now = datetime.utcnow()
            
            # Ensure bot user exists
            bot_user = IDFinderUser.query.filter_by(telegram_id=bot_id).first()
            if not bot_user:
                bot_user = IDFinderUser(
                    telegram_id=bot_id, first_name="Strauss Bot", is_bot=True, first_contact=now
                )
                db.session.add(bot_user)
            
            # Ensure topic exists
            if thread_id:
                mapping = TopicMapping.query.filter_by(topic_id=thread_id).first()
                if not mapping:
                    db.session.add(TopicMapping(topic_id=thread_id, chat_id=chat_id, topic_name=f"Topic {thread_id}"))

            # Log the message
            new_msg = IDFinderMessage(
                telegram_user_id=bot_id,
                chat_id=chat_id,
                message_thread_id=thread_id,
                chat_type='supergroup' if thread_id else 'private',
                text=text,
                content_type=content_type,
                file_id=file_id,
                is_command=False,
                reply_to_id=None,
                reply_to_text=None,
                timestamp=now,
                text_preview=text[:190] if text else f"[{content_type}]"
            )
            db.session.add(new_msg)
            db.session.commit()
    except Exception as e:
        logger.error(f"Error logging bot's own message: {e}")

def db_log_message_sync(user_dict, chat_dict, msg_dict, config):
    try:
        with flask_app.app_context():
            now = datetime.utcnow()
            # Update User Registry
            db_user = IDFinderUser.query.filter_by(telegram_id=user_dict['id']).first()
            if not db_user:
                db_user = IDFinderUser(
                    telegram_id=user_dict['id'], username=user_dict['username'],
                    first_name=user_dict['first_name'], last_name=user_dict['last_name'],
                    language_code=user_dict['language_code'], is_bot=user_dict['is_bot'],
                    first_contact=now
                )
                db.session.add(db_user)
            else:
                db_user.username = user_dict['username']
                db_user.first_name = user_dict['first_name']
                db_user.last_name = user_dict['last_name']
                db_user.last_contact = now
                db_user.is_in_group = True  # If they send a message, they are in the group
            
            # Discover Topics
            if chat_dict['type'] in ["group", "supergroup"] and msg_dict.get('thread_id'):
                thread_id = msg_dict['thread_id']
                mapping = TopicMapping.query.filter_by(topic_id=thread_id).first()
                if not mapping:
                    db.session.add(TopicMapping(
                        topic_id=thread_id, 
                        chat_id=chat_dict['id'],
                        topic_name=msg_dict.get('topic_name', f"Topic {thread_id}"),
                        is_active=msg_dict.get('is_topic_active', True)
                    ))
                else:
                    # Update status if provided
                    if 'is_topic_active' in msg_dict:
                        mapping.is_active = msg_dict['is_topic_active']
                    # Update name if it was a generic one and we have a better one
                    if "Topic " in mapping.topic_name and "Topic " not in msg_dict.get('topic_name', ''):
                        mapping.topic_name = msg_dict['topic_name']
                    # Always update name if it explicitly changed (Service Message)
                    if msg_dict.get('force_name_update'):
                        mapping.topic_name = msg_dict['topic_name']

            # Log Message
            # UNBEDINGT LOGGEN (auch Commands), wie vom User gewünscht
            # if msg_dict['is_command'] and config.get("message_logging_ignore_commands", True):
            #     db.session.commit()
            #     return

            db_msg = IDFinderMessage.query.filter_by(message_id=msg_dict['id'], chat_id=chat_dict['id']).first()
            if not db_msg:
                db_msg = IDFinderMessage(
                    telegram_user_id=user_dict['id'], message_id=msg_dict['id'],
                    chat_id=chat_dict['id'], message_thread_id=msg_dict.get('thread_id'),
                    chat_type=chat_dict['type'], text=msg_dict['text'],
                    content_type=msg_dict['content_type'], file_id=msg_dict['file_id'],
                    is_command=msg_dict['is_command'], 
                    reply_to_id=msg_dict.get('reply_to_id'),
                    reply_to_text=msg_dict.get('reply_to_text'),
                    timestamp=now,
                    text_preview=msg_dict['text'][:190] if msg_dict['text'] else f"[{msg_dict['content_type']}]"
                )
                db.session.add(db_msg)
                logger.info(f"✅ Message {msg_dict['id']} from {user_dict['id']} saved to DB.")
            else:
                # Update existing (might have been created by Profanity Filter)
                # Keep is_deleted and deletion_reason if already set
                db_msg.telegram_user_id = user_dict['id']
                db_msg.message_thread_id = msg_dict.get('thread_id')
                db_msg.chat_type = chat_dict['type']
                db_msg.text = msg_dict['text']
                db_msg.content_type = msg_dict['content_type']
                db_msg.file_id = msg_dict['file_id']
                db_msg.is_command = msg_dict['is_command']
                db_msg.reply_to_id = msg_dict.get('reply_to_id')
                db_msg.reply_to_text = msg_dict.get('reply_to_text')
                # DO NOT overwrite is_deleted or deletion_reason here if already true
                logger.info(f"✅ Message {msg_dict['id']} from {user_dict['id']} updated in DB.")
            
            db.session.commit()
    except Exception as e:
        logger.error(f"❌ Fehler beim synchronen Loggen: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # logger.info("--- [DIAG] track_activity triggered ---")
    if not is_bot_active('id_finder'):
        # logger.info("--- [DIAG] is_bot_active('id_finder') returned False ---")
        # For Master Bot, we might want to log regardless or check why it's inactive
        pass 
        
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not all([msg, user, chat]):
        logger.info(f"--- [DIAG] Missing components: msg={bool(msg)}, user={bool(user)}, chat={bool(chat)} ---")
        return
    
    config = get_bot_config("id_finder")
    logger.info(f"--- [DIAG] User: {user.id}, Chat: {chat.id} ({chat.type}), Msg: {msg.message_id} ---")
    
    if not config:
        logger.warning("--- [DIAG] No config found for id_finder! ---")
        return
        
    if not config.get("message_logging_enabled", True):
        logger.info("--- [DIAG] Message Logging disabled in config. ---")
        return
        
    logger.info(f"--- [DIAG] Processing message {msg.message_id} from {user.id} in {chat.id} ---")
        
    # DM-FREISCHALTUNG: Wir loggen jetzt auch Privatnachrichten für das Dashboard
    # (Die Prüfung auf groups_only wurde entfernt für 100% Sichtbarkeit)

    user_dict = {
        'id': user.id, 'username': user.username, 'first_name': user.first_name,
        'last_name': user.last_name, 'language_code': user.language_code, 'is_bot': user.is_bot
    }
    chat_dict = {'id': chat.id, 'type': chat.type}
    
    topic_name = f"Topic {msg.message_thread_id}"
    is_topic_active = True
    force_name_update = False
    service_text = None
    
    # Topic Service Messages
    if msg.forum_topic_created:
        topic_name = msg.forum_topic_created.name
        force_name_update = True
        service_text = f"🆕 Topic erstellt: {topic_name}"
    elif msg.forum_topic_edited:
        topic_name = msg.forum_topic_edited.name
        force_name_update = True
        service_text = f"✏️ Topic umbenannt: {topic_name}"
    elif msg.forum_topic_closed:
        is_topic_active = False
        service_text = "🔒 Topic geschlossen"
    elif msg.forum_topic_reopened:
        is_topic_active = True
        service_text = "🔓 Topic wieder geöffnet"
    
    # Voice/Video Chat Service Messages
    elif msg.video_chat_started:
        service_text = "🔊 Voice Chat gestartet"
    elif msg.video_chat_ended:
        service_text = "🔴 Voice Chat beendet"
    elif msg.video_chat_scheduled:
        service_text = f"📅 Voice Chat geplant für {msg.video_chat_scheduled.start_date}"
    elif msg.video_chat_participants_invited:
        service_text = "👥 Teilnehmer zum Voice Chat eingeladen"
        
    # Other Service Messages
    elif msg.pinned_message:
        service_text = "📌 Nachricht angepinnt"
    elif msg.new_chat_members:
        service_text = f"👋 Neue Mitglieder: {', '.join([u.first_name for u in msg.new_chat_members])}"
    elif msg.left_chat_member:
        service_text = f"🚪 Mitglied verlassen: {msg.left_chat_member.first_name}"
    
    # New Service Messages for "Original-Faithful" Capture
    elif msg.new_chat_title:
        service_text = f"📌 Chat-Titel geändert: {msg.new_chat_title}"
    elif msg.new_chat_photo:
        service_text = "🖼️ Chat-Foto wurde aktualisiert"
    elif msg.delete_chat_photo:
        service_text = "🗑️ Chat-Foto wurde entfernt"
    elif msg.group_chat_created:
        service_text = "🏁 Gruppe wurde erstellt"
    elif msg.supergroup_chat_created:
        service_text = "🏁 Supergruppe wurde erstellt"
    elif msg.message_auto_delete_timer_changed:
        service_text = f"⏱️ Auto-Lösch-Timer geändert auf: {msg.message_auto_delete_timer_changed.message_auto_delete_time}s"
    elif msg.proximity_alert_triggered:
        service_text = "📍 Proximity Alert ausgelöst"
    elif msg.migrate_to_chat_id:
        service_text = f"🔄 Gruppe migriert zu: {msg.migrate_to_chat_id}"

    content_type = "text"
    file_id = None
    text_content = msg.text or msg.caption or ""
    
    if service_text:
        content_type = "service"
        text_content = service_text
            
    if msg.photo: 
        content_type = "photo"
        file_id = msg.photo[-1].file_id
    elif msg.video: 
        content_type = "video"
        file_id = msg.video.file_id
    elif msg.sticker:
        content_type = "sticker_video" if msg.sticker.is_video else "sticker"
        file_id = msg.sticker.thumbnail.file_id if msg.sticker.is_animated and msg.sticker.thumbnail else msg.sticker.file_id
    elif msg.animation:
        content_type = "animation"
        file_id = msg.animation.file_id
    elif msg.document:
        content_type = "document"
        file_id = msg.document.file_id
    elif msg.voice:
        content_type = "voice"
        file_id = msg.voice.file_id
    elif msg.audio:
        content_type = "audio"
        file_id = msg.audio.file_id
    elif msg.video_note:
        content_type = "video_note"
        file_id = msg.video_note.file_id
    elif msg.poll:
        content_type = "poll"
        text_content = f"POLL: {msg.poll.question}"
        file_id = f"poll_{msg.poll.id}"
    elif msg.venue:
        content_type = "venue"
        text_content = f"VENUE: {msg.venue.title}"
    elif msg.location:
        content_type = "location"
        text_content = "LOCATION"

    # Reply info
    reply_to_id = None
    reply_to_text = None
    if msg.reply_to_message:
        # Ignore replies to the topic creation message (which happens automatically in topics)
        if not msg.reply_to_message.forum_topic_created:
            reply_to_id = msg.reply_to_message.message_id
            
            # Extract text or descriptive media label
            rtm = msg.reply_to_message
            if rtm.text:
                reply_to_text = rtm.text
            elif rtm.caption:
                reply_to_text = rtm.caption
            else:
                # Better labels for media types
                ct = rtm.content_type if hasattr(rtm, 'content_type') else 'Media'
                if ct == 'photo': reply_to_text = "🖼️ Foto"
                elif ct == 'video': reply_to_text = "🎥 Video"
                elif ct == 'animation': reply_to_text = "🎞️ GIF"
                elif ct == 'sticker': reply_to_text = "🎨 Sticker"
                elif ct == 'voice': reply_to_text = "🎤 Sprachnachricht"
                elif ct == 'video_note': reply_to_text = "📹 Videonachricht"
                elif ct == 'audio': reply_to_text = "🎵 Audio"
                elif ct == 'document': reply_to_text = "📄 Datei"
                else: reply_to_text = f"[{ct.capitalize() if ct else 'Nachricht'}]"

    msg_dict = {
        'id': msg.message_id, 'thread_id': msg.message_thread_id, 'text': text_content,
        'content_type': content_type, 'file_id': file_id,
        'is_command': (msg.text.startswith("/") if msg.text else False),
        'topic_name': topic_name,
        'is_topic_active': is_topic_active,
        'force_name_update': force_name_update,
        'reply_to_id': reply_to_id,
        'reply_to_text': reply_to_text
    }
    
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, db_log_message_sync, user_dict, chat_dict, msg_dict, config)
    
    # Trigger avatar download in background
    asyncio.create_task(download_user_avatar(context.bot, user.id))

async def track_activity_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user, chat = update.edited_message, update.effective_user, update.effective_chat
    if not all([msg, user, chat]): return
    
    config = get_bot_config("id_finder")
    if not config or not config.get("message_logging_enabled", True): return
    
    try:
        with flask_app.app_context():
            # Find the original message in DB
            db_msg = IDFinderMessage.query.filter_by(message_id=msg.message_id, chat_id=chat.id).first()
            if db_msg:
                # Only log as edit if text actually changed
                new_text = msg.text or msg.caption or ""
                if db_msg.text != new_text:
                    db_msg.previous_text = db_msg.text
                    db_msg.text = new_text
                    db_msg.is_edited = True
                    db_msg.edit_timestamp = datetime.utcnow()
                    db_msg.edited_by = f"{user.first_name} {user.last_name or ''}".strip()
                    db.session.commit()
                    logger.info(f"✏️ Message {msg.message_id} edit tracked in DB.")
    except Exception as e:
        logger.error(f"Error tracking edit: {e}")

async def track_topic_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Überwacht Pins, Locks und Schließungen von Topics."""
    msg = update.effective_message
    if not msg or not msg.is_topic_message: return
    
    chat_id = update.effective_chat.id
    thread_id = msg.message_thread_id
    
    is_closed = bool(msg.forum_topic_closed)
    is_reopened = bool(msg.forum_topic_reopened)
    pinned_msg = msg.pinned_message
    
    try:
        with flask_app.app_context():
            topic = TopicMapping.query.filter_by(topic_id=thread_id, chat_id=chat_id).first()
            if topic:
                changed = False
                if is_closed:
                    topic.is_closed = True
                    changed = True
                elif is_reopened:
                    topic.is_closed = False
                    changed = True
                
                if pinned_msg:
                    topic.is_pinned = True
                    changed = True
                
                if changed:
                    db.session.commit()
                    logger.info(f"🔄 Topic {thread_id} Status-Update: closed={topic.is_closed}, pinned={topic.is_pinned}")
    except Exception as e:
        logger.error(f"Error tracking topic status: {e}")

# --- Commands ---
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_bot_active('id_finder'): return
    await update.message.reply_text(
        f"👤 *Benutzer-ID:* `{update.effective_user.id}`\n"
        f"💬 *Chat-ID:* `{update.effective_chat.id}`\n"
        f"🏷️ *Topic-ID:* `{update.effective_message.message_thread_id or 'Kein Topic'}`",
        parse_mode=ParseMode.MARKDOWN
    )

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_bot_active('id_finder'): return
    user = update.effective_user
    chat = update.effective_chat
    msg = update.effective_message
    
    config = get_config_from_db()
    
    try:
        with flask_app.app_context():
            admin = IDFinderAdmin.query.filter_by(telegram_id=user.id).first()
            if not admin or not admin.permissions.get("can_warn", False) and not admin.permissions.get("is_superadmin", False):
                await msg.reply_text("❌ Du hast keine Berechtigung, Benutzer zu verwarnen.")
                return

            if not msg.reply_to_message:
                await msg.reply_text("⚠️ Bitte antworte auf eine Nachricht des Benutzers, den du verwarnen möchtest. (/warn <Grund>)")
                return

            target_user = msg.reply_to_message.from_user
            if target_user.is_bot:
                await msg.reply_text("❌ Du kannst keine Bots verwarnen.")
                return

            reason = "Kein Grund angegeben."
            if context.args:
                reason = " ".join(context.args)

            # Ensure user exists
            db_user = IDFinderUser.query.filter_by(telegram_id=target_user.id).first()
            if not db_user:
                db_user = IDFinderUser(
                    telegram_id=target_user.id, username=target_user.username,
                    first_name=target_user.first_name, last_name=target_user.last_name,
                    is_bot=target_user.is_bot
                )
                db.session.add(db_user)
                db.session.commit()

            # Add warning
            warning = IDFinderWarning(
                telegram_user_id=target_user.id,
                reason=reason,
                admin_id=user.id,
                message_db_id=None # We'd need the db_id of the replied message ideally, but leaving None is fine for now
            )
            db.session.add(warning)
            db.session.commit()
            
            warning_count = IDFinderWarning.query.filter_by(telegram_user_id=target_user.id).count()
            max_warns = config.get('max_warnings', 3)
            punishment = config.get('punishment_type', 'none')
            
            punishment_text = ""
            if warning_count >= max_warns and punishment != 'none':
                punishment_text = f"\n\n🚨 *Limit erreicht. Aktion: {punishment.upper()}*"
                try:
                    if punishment == 'mute':
                        mute_hours = config.get('mute_duration', 24)
                        until = datetime.utcnow() + timedelta(hours=mute_hours)
                        await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target_user.id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
                        punishment_text += f"\n(Stummgeschaltet für {mute_hours}h)"
                    elif punishment == 'kick':
                        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target_user.id)
                        await context.bot.unban_chat_member(chat_id=chat.id, user_id=target_user.id)
                        punishment_text += "\n(Pausiert/Kick ausgeführt)"
                    elif punishment == 'ban':
                        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target_user.id)
                        punishment_text += "\n(Permanent gesperrt)"
                except Exception as e:
                    logger.error(f"Fehler bei Auto-Punishment: {e}")
                    punishment_text += "\n_(Konnte nicht ausgeführt werden. Missing Admin Rights?)_"

            # Send warning log to administrator group topic 3
            try:
                admin_log_group = -1003372573784
                admin_log_thread = 3
                admin_mention = f"@{user.username}" if user.username else f"<b>{user.first_name}</b>"
                target_mention = f"@{target_user.username}" if target_user.username else f"<b>{target_user.first_name}</b>"
                
                # Strip Markdown from action text for HTML send
                action_text_stripped = punishment_text.replace('*', '').replace('_', '')
                
                admin_log_text = (
                    f"⚠️ <b>Neue Verwarnung erteilt (Telegram Command)</b>\n\n"
                    f"👤 <b>Nutzer:</b> {target_mention} (ID: {target_user.id})\n"
                    f"🛡️ <b>Verwarnt durch:</b> {admin_mention} (ID: {user.id})\n"
                    f"⚖️ <b>Grund:</b> {reason}\n"
                    f"📊 <b>Status:</b> {warning_count}/{max_warns}{action_text_stripped}"
                )
                await context.bot.send_message(
                    chat_id=admin_log_group,
                    message_thread_id=admin_log_thread,
                    text=admin_log_text,
                    parse_mode=ParseMode.HTML
                )
            except Exception as log_e:
                logger.error(f"Error sending warning log to admin group: {log_e}")

            # Optional: Delete the /warn command itself
            if config and config.get("delete_commands", False):
                try:
                    await msg.delete()
                except: pass

            reply = await msg.reply_to_message.reply_text(
                f"⚠️ *Verwarnung an {target_user.first_name}*\n"
                f"Grund: {reason}\n"
                f"Verwarnung {warning_count} / {max_warns}{punishment_text}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Optional: Automatic cleanup of bot message
            cleanup_secs = config.get("bot_message_cleanup_seconds", 0)
            if cleanup_secs > 0:
                cleanup_time = datetime.utcnow() + timedelta(seconds=cleanup_secs)
                task = AutoCleanupTask(chat_id=chat.id, message_id=reply.message_id, cleanup_at=cleanup_time, status='pending')
                db.session.add(task)
                db.session.commit()

    except Exception as e:
        logger.error(f"Fehler bei /warn: {e}")
        await msg.reply_text("❌ Interner Fehler beim Verwarnen.")

def get_handlers():
    return [
        CommandHandler("id", get_id),
        CommandHandler("warn", warn_user)
    ]

def get_track_handler():
    # Wir nehmen ALLE Nachrichten (auch Commands) und EDITS
    return [
        MessageHandler(filters.ALL & ~filters.UpdateType.EDITED_MESSAGE, track_activity),
        MessageHandler(filters.UpdateType.EDITED_MESSAGE, track_activity_edit),
        MessageHandler(filters.StatusUpdate.ALL, track_topic_status)
    ]

def setup_jobs(job_queue):
    job_queue.run_repeating(check_and_send_broadcasts, interval=30)
    job_queue.run_repeating(process_cleanup_tasks, interval=10)

if __name__ == "__main__":
    # Standalone-Start ermöglicht
    from shared_bot_utils import get_bot_token
    import asyncio
    from telegram.ext import ApplicationBuilder
    token = get_bot_token("id_finder")
    if token:
        print("Starte ID-Finder Standalone...")
        app = ApplicationBuilder().token(token).build()
        for h in get_handlers(): app.add_handler(h)
        for h_list in get_track_handler():
            if isinstance(h_list, list):
                for h in h_list: app.add_handler(h, group=1)
            else: app.add_handler(h_list, group=1)
        setup_jobs(app.job_queue)
        app.run_polling()
