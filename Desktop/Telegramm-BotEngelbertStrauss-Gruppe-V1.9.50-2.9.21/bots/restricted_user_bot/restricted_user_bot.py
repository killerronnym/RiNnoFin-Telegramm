import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from web_dashboard.app.models import UserRestriction
from shared_bot_utils import get_shared_flask_app, get_bot_config

logger = logging.getLogger(__name__)
flask_app = get_shared_flask_app()

async def restriction_check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Kerns-Handler für Nutzer-Einschränkungen.
    Prüft ob der Nutzer stummgeschaltet ist, in einem Topic Schreibverbot hat oder Medien-Sperren aktiv sind.
    """
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    topic_id = update.message.message_thread_id

    with flask_app.app_context():
        from web_dashboard.app.models import db
        from datetime import datetime
        # Restriction aus DB holen
        restriction = UserRestriction.query.filter_by(telegram_id=user_id).first()
        
        if not restriction:
            return

        # Check for expiration
        if restriction.expires_at and restriction.expires_at < datetime.utcnow():
            db.session.delete(restriction)
            db.session.commit()
            return

        should_delete = False
        
        # A. Shadow Ban (Alles löschen)
        if restriction.is_shadow_banned:
            should_delete = True
        
        # B. Global Mute
        elif restriction.is_globally_muted:
            should_delete = True
            
        # C. Topic-spezifische Sperre
        elif restriction.restricted_topics and topic_id in restriction.restricted_topics:
            should_delete = True
            
        # D. Medien-Filter (nur wenn nicht sowieso schon gelöscht wird)
        if not should_delete:
            # Sticker / GIF / Animation
            if restriction.no_stickers and (update.message.sticker or update.message.animation):
                should_delete = True
            # Bilder / Videos / Sprachnachrichten
            elif restriction.no_media and (update.message.photo or update.message.video or update.message.video_note or update.message.voice or update.message.document):
                should_delete = True
            # Links (URL Erkennung)
            elif restriction.no_links:
                entities = (update.message.entities or []) + (update.message.caption_entities or [])
                has_link = any(e.type in ['url', 'text_link'] for e in entities)
                if has_link or "http" in (update.message.text or update.message.caption or ""):
                    should_delete = True

        # E. Personalisierter Slow-Mode
        if not should_delete and restriction.slow_mode_seconds > 0:
            now = datetime.utcnow()
            if restriction.last_message_at:
                diff = (now - restriction.last_message_at).total_seconds()
                if diff < restriction.slow_mode_seconds:
                    should_delete = True
            
            if not should_delete:
                restriction.last_message_at = now
                db.session.commit()

        if should_delete:
            try:
                await update.message.delete()
                logger.info(f"🚫 Nachricht von User {user_id} gelöscht (Filter/Einschränkung aktiv).")
                
                # Log to IDFinderMessage for Dashboard
                async def log_deletion_delayed():
                    import asyncio
                    await asyncio.sleep(2)
                    with flask_app.app_context():
                        from web_dashboard.app.models import IDFinderMessage, db
                        try:
                            # Upsert deletion record
                            db_msg = IDFinderMessage.query.filter_by(message_id=update.message.message_id, chat_id=update.message.chat.id).first()
                            if not db_msg:
                                db_msg = IDFinderMessage(
                                    telegram_user_id=user_id,
                                    message_id=update.message.message_id,
                                    chat_id=update.message.chat.id,
                                    message_thread_id=topic_id,
                                    chat_type=update.message.chat.type,
                                    text=update.message.text or update.message.caption or "",
                                    content_type='text',
                                    timestamp=datetime.utcnow()
                                )
                                db.session.add(db_msg)
                            
                            db_msg.is_deleted = True
                            db_msg.deleted_by = "System (Restriktion)"
                            db_msg.deletion_reason = restriction.reason or "Nutzer-Einschränkung aktiv"
                            db.session.commit()
                        except Exception as log_err:
                            logger.error(f"Error logging restricted deletion: {log_err}")
                
                import asyncio
                asyncio.create_task(log_deletion_delayed())
            except Exception as e:
                logger.error(f"Failed to delete restricted message: {e}")

def get_handlers():
    """
    Gibt den Handler für Nutzer-Einschränkungen zurück.
    Wird mit hoher Priorität registriert.
    """
    # Wir nutzen einen MessageHandler ohne Filter (außer Chat-Typen), um alles zu fangen
    return [
        (MessageHandler(filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP, restriction_check_handler), -10)
    ]

# Hilfsfunktion um User via API zu stummschalten (Trigger vom Dashboard)
async def sync_telegram_mute(bot, chat_id, user_id, mute_active):
    from telegram import ChatPermissions
    try:
        # Wenn mute_active=True, entziehen wir das Schreibrecht
        permissions = ChatPermissions(can_send_messages=not mute_active)
        await bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions=permissions)
        return True
    except Exception as e:
        logger.error(f"Failed to sync telegram mute for {user_id}: {e}")
        return False
