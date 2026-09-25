import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from web_dashboard.app.models import db, TopicCleanupConfig, AutoCleanupTask
from shared_bot_utils import get_shared_flask_app

logger = logging.getLogger(__name__)
flask_app = get_shared_flask_app()

async def message_tracker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Überwacht eingehende Nachrichten in konfigurierten Topics."""
    if not update.message:
        return

    # 1. BOT-SCHUTZ: Nachrichten von Bots NIEMALS löschen
    if update.message.from_user and update.message.from_user.is_bot:
        return

    topic_id = update.message.message_thread_id
    chat_id = update.message.chat_id

    # General-Topic (None in Telegram API) wird in der Datenbank als 1 abgebildet
    db_topic_id = 1 if topic_id is None else topic_id

    try:
        with flask_app.app_context():
            # Prüfen ob Topic überwacht wird
            config = TopicCleanupConfig.query.filter(
                TopicCleanupConfig.topic_id == db_topic_id,
                TopicCleanupConfig.is_active == True
            ).first()

            if not config:
                return

            if not config.delete_admins:
                if not update.message.from_user:
                    return  # Keine User-Nachricht (z. B. Channel-Post), vorsichtshalber nicht löschen
                try:
                    member = await context.bot.get_chat_member(chat_id, update.message.from_user.id)
                    if member.status in ['administrator', 'creator']:
                        # logger.info(f"Cleanup: Admin Nachricht in Topic {topic_id} wird behalten.")
                        return
                except Exception as member_err:
                    logger.warning(f"Cleanup Tracker: Konnte Status von User {update.message.from_user.id} nicht abfragen: {member_err}")
                    # Im Zweifel (z.B. API Fehler) behalten wir die Nachricht lieber
                    return

            # Nachricht in die Lösch-Liste aufnehmen
            cleanup_at = datetime.utcnow() + timedelta(minutes=config.delay_minutes)
            task = AutoCleanupTask(
                chat_id=chat_id,
                message_id=update.message.message_id,
                cleanup_at=cleanup_at,
                status='pending'
            )
            db.session.add(task)
            db.session.commit()
            logger.info(f"Cleanup: Nachricht {update.message.message_id} in Topic {topic_id} geplant für {cleanup_at}")

    except Exception as e:
        logger.error(f"Fehler im Cleanup Tracker: {e}")

async def cleanup_worker(context: ContextTypes.DEFAULT_TYPE):
    """Hintergrund-Job der abgelaufene Nachrichten löscht."""
    try:
        now = datetime.utcnow()
        with flask_app.app_context():
            # Alle fälligen Tasks holen
            tasks = AutoCleanupTask.query.filter(
                AutoCleanupTask.cleanup_at <= now,
                AutoCleanupTask.status == 'pending'
            ).all()

            if not tasks:
                return

            logger.info(f"Cleanup Service: Lösche {len(tasks)} abgelaufene Nachrichten...")
            
            for task in tasks:
                try:
                    await context.bot.delete_message(chat_id=task.chat_id, message_id=task.message_id)
                except Exception as e:
                    # Wenn Nachricht schon weg ist, ignorieren wir das
                    if "Message to delete not found" not in str(e):
                        logger.warning(f"Konnte Nachricht {task.message_id} in {task.chat_id} nicht löschen: {e}")
                
                # Als erledigt markieren oder aus DB entfernen
                db.session.delete(task)
            
            db.session.commit()

    except Exception as e:
        logger.error(f"Kritischer Fehler im Cleanup Worker: {e}")

def setup_jobs(job_queue):
    """Registriert den Cleanup-Job (alle 30 Sekunden)."""
    job_queue.run_repeating(cleanup_worker, interval=30, first=10)
    logger.info("✅ Topic Cleanup Service: Hintergrund-Job registriert (30 Sek Intervall).")

def get_handlers():
    """Gibt den Nachrichten-Tracker zurück."""
    # Wir nutzen group=10 um andere Handler nicht zu stören
    return [
        (MessageHandler(filters.ALL, message_tracker), 10)
    ]
