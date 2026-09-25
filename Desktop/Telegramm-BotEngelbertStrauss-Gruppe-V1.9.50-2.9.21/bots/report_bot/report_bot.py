import logging
import os
import json
import sys
import asyncio
from datetime import datetime, timedelta

# Setup Project Root for imports
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BOT_DIR))
sys.path.append(PROJECT_ROOT)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode, ChatMemberStatus
import html

from web_dashboard.app.models import db, BotSettings, ReportedMessage, IDFinderUser, IDFinderWarning, IDFinderMessage, InviteApplication
from shared_bot_utils import is_bot_active, get_bot_config, get_shared_flask_app, log_bot_message_shared

flask_app = get_shared_flask_app()
logger = logging.getLogger(__name__)

# In-memory cooldown storage: {user_id: last_report_time}
report_cooldowns = {}
COOLDOWN_SECONDS = 30 

def get_report_config():
    return get_bot_config("report_bot") or {
        "is_active": False,
        "target_chat_id": None,
        "target_topic_id": None
    }

async def report_hilfe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reportHilfe command."""
    msg = update.effective_message
    user = update.effective_user
    is_private = update.effective_chat.type == 'private'
    
    with flask_app.app_context():
        app = InviteApplication.query.filter_by(telegram_user_id=user.id).first()
        is_member = app and app.status in ['accepted', 'completed']

    if not is_private:
        help_text = (
            "🚨 <b>Report-Hilfe (Gruppe)</b>\n\n"
            "Um eine Nachricht zu melden, nutze die <b>Antwort-Funktion</b> auf die entsprechende Nachricht:\n"
            "1. Nachricht auswählen (gedrückt halten oder wischen)\n"
            "2. <code>/report [Dein Grund]</code> schreiben\n\n"
            "Deine Meldung wird direkt an die Administratoren weitergeleitet."
        )
    else:
        if is_member:
            help_text = (
                "🚨 <b>Report-Hilfe (Privat)</b>\n\n"
                "Du kannst uns hier direkt Probleme melden:\n"
                "Schreibe einfach <code>/report [Deine Nachricht]</code>.\n\n"
                "<b>Innerhalb der Gruppe:</b>\n"
                "Dort meldest du Nachrichten, indem du per <i>Reply</i> mit <code>/report</code> auf sie antwortest."
            )
        else:
            help_text = (
                "🚨 <b>Report-Hilfe</b>\n\n"
                "Wenn du Hilfe brauchst oder ein Problem melden möchtest, schreibe uns eine Nachricht im Format:\n"
                "<code>/report [Deine Nachricht/Frage]</code>\n\n"
                "Die Administratoren werden sich schnellstmöglich bei dir melden."
            )
    await msg.reply_text(help_text, parse_mode=ParseMode.HTML)

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /report command."""
    config = get_report_config()
    if not config.get("is_active"): return

    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    is_private = chat.type == 'private'

    now = datetime.now()
    if user.id in report_cooldowns:
        elapsed = (now - report_cooldowns[user.id]).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            wait = int(COOLDOWN_SECONDS - elapsed)
            tmp = await msg.reply_text(f"⚠️ Bitte warte {wait}s bevor du erneut eine Meldung sendest.")
            async def del_tmp(m):
                await asyncio.sleep(5); 
                try: await m.delete()
                except: pass
            asyncio.create_task(del_tmp(tmp))
            if not is_private: asyncio.create_task(del_tmp(msg))
            return

    reason = " ".join(context.args) if context.args else ""
    reported_msg = msg.reply_to_message
    
    if not is_private and not reported_msg:
        await msg.reply_text("⚠️ Antworte per Reply mit <code>/report [Grund]</code> auf eine Nachricht oder nutze <code>/reportHilfe</code>.", parse_mode=ParseMode.HTML)
        return

    if is_private and not reason and not reported_msg:
        await msg.reply_text("⚠️ Bitte schreibe deine Meldung hinter den Befehl: <code>/report [Deine Nachricht]</code>")
        return

    try:
        with flask_app.app_context():
            reporter_name = f"{user.first_name} {user.last_name or ''}".strip()
            target_uid, target_name, msg_id, preview = None, None, None, reason
            
            if reported_msg:
                msg_id = reported_msg.message_id
                if reported_msg.from_user:
                    target_uid = reported_msg.from_user.id
                    target_name = f"{reported_msg.from_user.first_name} {reported_msg.from_user.last_name or ''}".strip()
                if reported_msg.photo: preview = "[BILD] " + (reported_msg.caption or reason)
                elif reported_msg.video: preview = "[VIDEO] " + (reported_msg.caption or reason)
                elif reported_msg.animation: preview = "[GIF] " + (reported_msg.caption or reason)
                elif reported_msg.text: preview = reported_msg.text[:200]
            
            new_report = ReportedMessage(
                reporter_id=user.id, reporter_name=reporter_name, reported_user_id=target_uid,
                reported_user_name=target_name, reported_message_id=msg_id, chat_id=chat.id,
                chat_type=chat.type, reason=reason, content_preview=preview, status='pending'
            )
            db.session.add(new_report); db.session.commit()
            report_id = new_report.id
            
            target_chat = config.get("target_chat_id")
            if target_chat:
                target_topic = config.get("target_topic_id")
                rep_link = f"<a href='tg://user?id={user.id}'>{html.escape(reporter_name)}</a>"
                loc = html.escape(chat.title or "Privat")
                type_indicator = "💬 Gruppe" if not is_private else "🔒 Privat"
                report_header = f"🚨 <b>NEUER REPORT (#R{report_id})</b>" if not is_private else f"📩 <b>NEUE PRIVAT-MELDUNG (#P{report_id})</b>"

                report_text = (
                    f"{report_header}\n\n"
                    f"👤 <b>Melder:</b> {rep_link} (<code>{user.id}</code>)\n"
                    f"📍 <b>Ort:</b> {loc} ({type_indicator})\n"
                )
                if target_uid:
                    target_link = f"<a href='tg://user?id={target_uid}'>{html.escape(target_name)}</a>"
                    report_text += f"👤 <b>Beschuldigter:</b> {target_link} (<code>{target_uid}</code>)\n"
                if preview: report_text += f"📝 <b>Inhalt/Grund:</b>\n<i>{html.escape(preview)}</i>\n\n"
                if not is_private and msg_id:
                    chat_id_str = str(chat.id)
                    link_id = chat_id_str[4:] if chat_id_str.startswith("-100") else chat_id_str
                    report_text += f"🔗 <a href='https://t.me/c/{link_id}/{msg_id}'>Zur Nachricht springen</a>"

                keyboard = [[InlineKeyboardButton("🛠️ Bearbeitet", callback_data=f"rep_proc_{report_id}"), InlineKeyboardButton("✅ Erledigt", callback_data=f"rep_ok_{report_id}")]]
                if not is_private: keyboard.insert(0, [InlineKeyboardButton("🗑️ Löschen", callback_data=f"rep_del_{report_id}"), InlineKeyboardButton("⚠️ Warn", callback_data=f"rep_warn_{report_id}"), InlineKeyboardButton("🚫 Ban", callback_data=f"rep_ban_{report_id}")])
                
                sent_msg = await context.bot.send_message(chat_id=target_chat, text=report_text, message_thread_id=target_topic if target_topic else None, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
                if sent_msg:
                    log_bot_message_shared(target_chat, target_topic, report_text, 'text', None, sent_msg.message_id)

            report_cooldowns[user.id] = now
            conf = await msg.reply_text("✅ Deine Meldung wurde an die Administratoren weitergeleitet.")
            async def cleanup():
                await asyncio.sleep(5)
                try: await conf.delete()
                except: pass
                if not is_private:
                    try: await msg.delete()
                    except: pass
            asyncio.create_task(cleanup())
    except Exception as e:
        logger.error(f"Error in report_command: {e}")
        await msg.reply_text("❌ Fehler beim Senden.")

async def handle_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks on report notifications."""
    query = update.callback_query
    data = query.data
    admin_user = query.from_user
    
    if not data.startswith("rep_"):
        return
        
    parts = data.split("_")
    if len(parts) < 3: return
    
    action = parts[1] # del, warn, ban, ok
    report_id = int(parts[2])
    
    await query.answer()
    
    try:
        with flask_app.app_context():
            report = ReportedMessage.query.get(report_id)
            if not report:
                await query.edit_message_text("❌ Report nicht mehr in DB.")
                return
            if report.status in ['resolved', 'dismissed'] and action != 'ok':
                await query.answer("Bereits erledigt.", show_alert=True)
                return

            result_text, new_status = "", report.status
            if action == "del":
                try:
                    await context.bot.delete_message(chat_id=report.chat_id, message_id=report.reported_message_id)
                    result_text = "🗑️ Nachricht gelöscht."
                except: result_text = "❌ Nachricht konnte nicht gelöscht werden."
                new_status = 'resolved'
            elif action == "warn":
                if report.reported_user_id:
                    warn = IDFinderWarning(telegram_user_id=report.reported_user_id, reason=f"Report #{report_id}", admin_id=admin_user.id)
                    db.session.add(warn)
                    
                    # Send warning log to administrator group topic 3
                    try:
                        admin_log_group = -1003372573784
                        admin_log_thread = 3
                        # Let's count current warnings (add 1 since it's not yet committed)
                        w_count = IDFinderWarning.query.filter_by(telegram_user_id=report.reported_user_id).count() + 1
                        target_mention = f"<a href='tg://user?id={report.reported_user_id}'>{html.escape(report.reported_user_name or str(report.reported_user_id))}</a>"
                        admin_mention = f"@{admin_user.username}" if admin_user.username else f"<b>{admin_user.first_name}</b>"
                        
                        admin_log_text = (
                            f"⚠️ <b>Neue Verwarnung erteilt (Report Bot Ticket)</b>\n\n"
                            f"👤 <b>Nutzer:</b> {target_mention} (ID: {report.reported_user_id})\n"
                            f"🛡️ <b>Verwarnt durch:</b> {admin_mention} (ID: {admin_user.id})\n"
                            f"⚖️ <b>Grund:</b> Report #{report_id}\n"
                            f"📊 <b>Status:</b> {w_count} Verwarnung(en)"
                        )
                        await context.bot.send_message(
                            chat_id=admin_log_group,
                            message_thread_id=admin_log_thread,
                            text=admin_log_text,
                            parse_mode=ParseMode.HTML
                        )
                    except Exception as log_e:
                        logger.error(f"Error sending warning log from report bot: {log_e}")
                    try: await context.bot.delete_message(chat_id=report.chat_id, message_id=report.reported_message_id)
                    except: pass
                    result_text = "⚠️ Verwarnt & Gelöscht."
                new_status = 'resolved'
            elif action == "ban":
                if report.reported_user_id:
                    try:
                        await context.bot.ban_chat_member(chat_id=report.chat_id, user_id=report.reported_user_id)
                        await context.bot.delete_message(chat_id=report.chat_id, message_id=report.reported_message_id)
                        result_text = "🚫 Gebannt & Gelöscht."
                    except: result_text = "❌ Fehler beim Bannen."
                new_status = 'resolved'
            elif action == "proc":
                result_text = "🛠️ Bearbeitet."
                new_status = 'processed'
            elif action == "ok":
                result_text = "✅ Erledigt."
                new_status = 'dismissed'
            
            report.status = new_status
            db.session.commit()
            
            orig = query.message.text_html
            new_text = f"{orig}\n\n━━━━━━\n🛠 <b>Status:</b> {result_text}\n👤 <b>Admin:</b> {admin_user.mention_html()}"
            await query.edit_message_text(text=new_text, parse_mode=ParseMode.HTML, reply_markup=None)
            
    except Exception as e:
        logger.error(f"Fehler in handle_report_callback: {e}")
        await query.answer("Kritischer Systemfehler.", show_alert=True)

def get_handlers():
    return [
        CommandHandler("report", report_command),
        CommandHandler("reportHilfe", report_hilfe_command),
        CallbackQueryHandler(handle_report_callback, pattern="^rep_")
    ]

if __name__ == "__main__":
    logger.error("Dieses Modul läuft nur via main_bot.py")
