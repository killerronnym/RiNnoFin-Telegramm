import logging
import os
import json
import sys
from datetime import datetime

# Setup Project Root for imports
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BOT_DIR))
sys.path.append(PROJECT_ROOT)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, PollAnswerHandler, filters
from telegram.constants import ParseMode
from telegram.error import Forbidden
import html
import subprocess
import json

def get_video_info(file_path):
    """Uses ffprobe to extract video width, height and duration, handling rotation."""
    try:
        cmd = [
            'ffprobe', '-v', 'error', 
            '-select_streams', 'v:0', 
            '-show_entries', 'stream=width,height,duration,rotation', 
            '-of', 'json', file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            cmd = [
                'ffprobe', '-v', 'error', 
                '-select_streams', 'v:0', 
                '-show_entries', 'stream=width,height,duration:side_data=rotation', 
                '-of', 'json', file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
        data = json.loads(result.stdout)
        
        if 'streams' in data and len(data['streams']) > 0:
            stream = data['streams'][0]
            width = stream.get('width')
            height = stream.get('height')
            duration = stream.get('duration')
            
            # Detect rotation
            rotation = 0
            if 'rotation' in stream:
                rotation = abs(int(float(stream['rotation'])))
            elif 'side_data_list' in stream:
                for sd in stream['side_data_list']:
                    if 'rotation' in sd:
                        rotation = abs(int(float(sd['rotation'])))
            
            if rotation == 90 or rotation == 270:
                logger.info(f"Rotating dimensions: {width}x{height} -> {height}x{width}")
                width, height = height, width
            
            return width, height, duration
    except Exception as e:
        logger.error(f"FFprobe error for {file_path}: {e}")
    return None, None, None

def generate_video_thumbnail(video_path):
    """Generates a thumbnail for a video using ffmpeg, scaled for Telegram API (max 320px)."""
    thumb_path = video_path + "_thumb.jpg"
    try:
        # Scale to max 320px while maintaining aspect ratio
        # -1 in scale means "calculate height to maintain aspect ratio"
        # We use a filter complex to ensure the larger dimension is 320
        cmd = [
            'ffmpeg', '-y', '-i', video_path, 
            '-ss', '00:00:01', '-vframes', '1', 
            '-vf', "scale=320:320:force_original_aspect_ratio=decrease",
            '-q:v', '2', '-f', 'image2', thumb_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if os.path.exists(thumb_path):
            size_kb = os.path.getsize(thumb_path) / 1024
            logger.info(f"Thumbnail generated: {thumb_path} ({size_kb:.1f} KB)")
            return thumb_path
        else:
            logger.warning(f"FFmpeg failed to generate thumbnail. Cmd: {' '.join(cmd)}\nStderr: {res.stderr}")
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
    return None


from web_dashboard.app.models import db, BotSettings, GroupEvent, EventRSVP
from shared_bot_utils import get_bot_config, get_shared_flask_app

flask_app = get_shared_flask_app()
logger = logging.getLogger(__name__)

def smart_truncate_html(text, limit):
    """Truncates HTML text without breaking tags and ensures all tags are closed.
    Also removes newlines inside tags to satisfy Telegram's strict parser."""
    import re
    
    # 0. PRE-CLEAN: Remove newlines INSIDE tags (e.g. <a \n href="...">)
    # This also fixes the user's reported issue with newlines in link tags
    text = re.sub(r'(<[a-zA-Z1-6]+[^>]*?)\s*\n\s*(.*?>)', r'\1 \2', text)
    
    if len(text) <= limit:
        return text
    
    # Simple truncate first
    trunk = text[:limit-3]
    
    # Find active tags using a stack
    open_tags = []
    # Regex to find all HTML tags in the truncated part
    import re
    all_tags = re.findall(r'<(/?)([a-zA-Z1-6]+)([^>]*)>', trunk)
    
    for tag in all_tags:
        is_close = tag[0] == '/'
        tag_name = tag[1].lower()
        if is_close:
            if open_tags and open_tags[-1] == tag_name:
                open_tags.pop()
        else:
            # Avoid self-closing tags like img, br if present
            if tag_name not in ['br', 'img', 'hr', 'input']:
                open_tags.append(tag_name)
    
    # Close any remaining open tags in reverse order
    res = trunk + "..."
    for tag in reversed(open_tags):
        res += f"</{tag}>"
    
    return res

def get_event_markup(event, rsvp_counts):
    # Buttons are no longer needed as per user request
    return None


def format_event_text(title, description, counts, event=None, max_chars=4000):
    """Formats the event text with stats and handles length limits."""
    # Stats footer (Only show if not using a poll, to avoid redundancy)
    stats = ""
    if event:
        # Summary stats for the caption
        total_dabei = 0
        total_vielleicht = 0
        total_nicht = 0

        # RSVP counts are no longer displayed in the caption as per user request
        stats = ""
        pass

    
    # Header
    header = f"📅 <b>{html.escape(title)}</b>\n\n"
    
    # Description
    desc = description or ""
    
    # Add Dates Summary if available
    date_summary = ""
    if event and event.event_dates_json:
            try:
                dates = json.loads(event.event_dates_json)
                if dates:
                    date_summary = "\n\n<b>Termine:</b>"
                    for d in dates:
                        try:
                            dt = datetime.fromisoformat(d['start'].replace('Z', ''))
                            date_str = dt.strftime('%d.%m. um %H:%M Uhr')
                            date_summary += f"\n• {d['label']}: {date_str}"
                        except: pass
                    date_summary += "\n"
            except: pass

    # Location (clickable link)
    loc_text = ""
    if event and event.location and event.location_in_group:
        maps_url = f"https://www.google.com/maps/search/?api=1&query={html.escape(event.location)}"
        loc_text = f"\n\n📍 <b>Ort:</b>\n<a href='{maps_url}'>{html.escape(event.location)}</a>"

    # Website & Tickets (Text Links)
    links_text = ""
    if event:
        if event.website_url and event.website_in_group:
            label = event.website_label or "Webseite besuchen"
            # Prefix with emoji ONLY if not already present
            prefix = "🔗 " if not any(char in label for char in ["🌐", "🔗", "🌍"]) else ""
            links_text += f"\n\n{prefix}<a href='{event.website_url}'>{html.escape(label)}</a>"
            
        if event.tickets_url and event.tickets_in_group:
            label = event.tickets_label or "Tickets sichern"
            prefix = "🎟️ " if not any(char in label for char in ["🎟️", "🎫", "🛒"]) else ""
            links_text += f"\n\n{prefix}<a href='{event.tickets_url}'>{html.escape(label)}</a>"
    
    if links_text:
        links_text += "\n"

    # Smart truncate to avoid breaking HTML tags
    allowed = max_chars - len(header) - len(stats) - len(date_summary) - len(loc_text) - len(links_text)
    desc = smart_truncate_html(desc, allowed)
    
    return f"{header}{desc}{date_summary}{loc_text}{links_text}{stats}"

async def poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles non-anonymous poll answers for events (including multi-day)."""
    poll_answer = update.poll_answer
    poll_id = poll_answer.poll_id
    user = poll_answer.user
    
    logger.info(f"DEBUG: PollAnswer received! User={user.id}, PollID={poll_id}, Options={poll_answer.option_ids}")
    
    try:
        with flask_app.app_context():
            event = GroupEvent.query.filter_by(poll_id=poll_id).first()
            if not event:
                return

            # option_ids is a list
            if not poll_answer.option_ids:
                # User retracted their vote
                rsvp = EventRSVP.query.filter_by(event_id=event.id, telegram_user_id=user.id).first()
                if rsvp:
                    db.session.delete(rsvp)
                    db.session.commit()
                return

            # Determine Labels from Options dynamically
            options = []
            all_dates = []
            if event.event_dates_json:
                try: 
                    all_dates = json.loads(event.event_dates_json)
                except: 
                    pass

            # Dynamic sequential mapping based on poll type
            current_idx = 0
            mapping = {}
            
            # Custom Labels parsing
            cfg = {}
            if event.poll_config_json:
                try: cfg = json.loads(event.poll_config_json)
                except: pass

            # THE ORDER MUST MATCH check_pending_events EXACTLY
            poll_labels = []
            
            # 1. Yes / Participation
            if event.poll_type == 'multi_day':
                if getattr(event, 'poll_show_yes', True):
                    poll_labels.append(cfg.get('yes') or "✅ Bin dabei")
                if getattr(event, 'poll_show_all_day', True):
                    poll_labels.append(cfg.get('all_day') or "🌟 Bin an ALLEN Tagen dabei")
                if getattr(event, 'poll_show_dates', True) and event.event_dates_json:
                    try:
                        dates = json.loads(event.event_dates_json)
                        for d in dates:
                            try:
                                dt = datetime.fromisoformat(d['start'].replace('Z', ''))
                                poll_labels.append(f"📅 {d['label']} ({dt.strftime('%d.%m. %H:%M')})")
                            except: poll_labels.append(f"📅 {d['label']}")
                    except: pass
                if getattr(event, 'poll_show_maybe', True):
                    poll_labels.append(cfg.get('maybe') or "🤔 Vielleicht")
                if getattr(event, 'poll_show_no', True):
                    poll_labels.append(cfg.get('no') or "❌ Bin gar nicht dabei")
            else:
                # Standard Mode
                if getattr(event, 'poll_show_yes', True):
                    poll_labels.append(cfg.get('yes') or "✅ Bin dabei")
                if getattr(event, 'poll_show_maybe', True):
                    poll_labels.append(cfg.get('maybe') or "🤔 Vielleicht")
                if getattr(event, 'poll_show_no', True):
                    poll_labels.append(cfg.get('no') or "❌ Bin gar nicht dabei")

            for i, label in enumerate(poll_labels):
                mapping[i] = label
            
            # Determine selection
            for idx in poll_answer.option_ids:
                label = mapping.get(idx)
                if label:
                    # Check if it's one of the "Participation" labels
                    is_status = False
                    status_labels = [
                        cfg.get('yes') or "✅ Bin dabei",
                        cfg.get('all_day') or "🌟 Bin an ALLEN Tagen dabei",
                        cfg.get('maybe') or "🤔 Vielleicht",
                        cfg.get('no') or "❌ Bin gar nicht dabei"
                    ]
                    # Also include the "internal" names for fallback
                    status_labels.extend(["dabei", "vielleicht", "nicht_dabei", "Alle Tage"])
                    
                    if label in status_labels:
                        is_status = True
                    
                    if is_status:
                        options = [label] # Mutually exclusive logic for main status
                        break
                    options.append(label)
            

            if not options: options = ["unbekannt"]
            status = ", ".join(options)
            
            # Update or Create RSVP
            rsvp = EventRSVP.query.filter_by(event_id=event.id, telegram_user_id=user.id).first()
            if rsvp:
                rsvp.status = status
                rsvp.username = user.username or user.first_name
            else:
                rsvp = EventRSVP(
                    event_id=event.id,
                    telegram_user_id=user.id,
                    username=user.username or user.first_name,
                    status=status
                )
                db.session.add(rsvp)
            db.session.commit()
            
            # Mark for update in Telegram caption (stats)
            event.needs_update = True
            db.session.commit()

            # --- Trigger Private Confirmation ---
            # Rule: Don't send DM if user selected "Vielleicht" or "Nicht dabei"
            maybe_label = cfg.get('maybe') or "🤔 Vielleicht"
            no_label = cfg.get('no') or "❌ Bin gar nicht dabei"
            
            is_maybe = maybe_label in status or "vielleicht" in status or "🤔" in status
            is_no = no_label in status or "nicht_dabei" in status or "❌" in status
            
            is_participating = len(options) > 0 and not is_maybe and not is_no
            
            logger.info(f"Poll Answer: User={user.id}, Status={status}, SendConfirm={event.send_confirmation}")
            
            if is_participating and event.send_confirmation:
                logger.info(f"Triggering private confirmation for {user.id}")
                await send_private_confirmation(context.bot, event, user, rsvp)
                db.session.commit()
            else:
                logger.info(f"No private confirmation triggered for {user.id} (Participating: {is_participating}, Maybe: {is_maybe}, No: {is_no}, SendConfirm: {event.send_confirmation})")



    except Exception as e:
        logger.error(f"Error in poll_answer_handler: {e}", exc_info=True)

async def send_private_confirmation(bot, event, user, rsvp):
    """Sends a professional private DM with confirmation text, image, and multi-event .ics file."""
    import io
    try:
        # 3. Prepare Professional Text
        header = f"🎉 <b>Bestätigung: {event.title}</b>\n\n"
        body = event.confirmation_text or f"Hallo {user.first_name}! Du bist beim Event dabei. Wir freuen uns auf dich!"
        
        footer = ""
        if event.location and event.location_in_dm:
            maps_url = f"https://www.google.com/maps/search/?api=1&query={html.escape(event.location)}"
            footer += f"\n\n📍 <b>Ort:</b> <a href='{maps_url}'>{html.escape(event.location)}</a>"
        
        if event.website_url and event.website_in_dm:
            label = event.website_label or "🌐 Webseite besuchen"
            footer += f"\n🔗 <a href='{event.website_url}'>{html.escape(label)}</a>"
        
        if event.tickets_url and event.tickets_in_dm:
            label = event.tickets_label or "🎟️ Tickets sichern"
            footer += f"\n🎟️ <a href='{event.tickets_url}'>{html.escape(label)}</a>"
        
        # 4. Generate .ics file based on User Selection
        ics_file = None
        all_dates = []
        if event.event_dates_json:
            try: all_dates = json.loads(event.event_dates_json)
            except: pass
        elif event.event_start:
            all_dates = [{'label': 'Termin', 'start': event.event_start.isoformat(), 'end': (event.event_end.isoformat() if event.event_end else None)}]

        # Filter dates based on RSVP status
        selected_dates = []
        is_yes = ("DABEI" in rsvp.status.upper() or "✅" in rsvp.status or "ALLE TAGE" in rsvp.status.upper() or "🌟" in rsvp.status)
        
        if is_yes:
            selected_dates = all_dates
        else:
            # Check which labels match
            user_labels = [s.strip() for s in rsvp.status.split(',')]
            selected_dates = [d for d in all_dates if d['label'] in user_labels or f"📅 {d['label']}" in rsvp.status]

        # Final body override based on selection count
        if not is_yes:
            if len(selected_dates) >= 1:
                body = event.confirmation_text or f"Hallo {user.first_name}! Du hast dich für Termine bei <b>{event.title}</b> angemeldet."
            else:
                body = event.confirmation_text or f"Hallo {user.first_name}! Deine Auswahl wurde gespeichert: {rsvp.status}"

        dates_summary_text = ""
        if selected_dates:
            def format_ics_date(dt_str):
                try:
                    # Floating time (no Z) is often safer for local events to avoid TZ shifts
                    dt = datetime.fromisoformat(dt_str.replace('Z', ''))
                    return dt.strftime('%Y%m%dT%H%M%S')
                except: return None
                
            # Generate deterministic UID
            import hashlib
            
            ics_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//EngelbertStrauss//EventBot//DE",
                "CALSCALE:GREGORIAN",
                "METHOD:PUBLISH",
                f"X-WR-CALNAME:{event.title}",
                "X-WR-TIMEZONE:Europe/Berlin",
                "BEGIN:VTIMEZONE",
                "TZID:Europe/Berlin",
                "BEGIN:DAYLIGHT",
                "TZOFFSETFROM:+0100",
                "TZOFFSETTO:+0200",
                "TZNAME:CEST",
                "DTSTART:19700329T020000",
                "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
                "END:DAYLIGHT",
                "BEGIN:STANDARD",
                "TZOFFSETFROM:+0200",
                "TZOFFSETTO:+0100",
                "TZNAME:CET",
                "DTSTART:19701025T030000",
                "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
                "END:STANDARD",
                "END:VTIMEZONE"
            ]
            
            dates_summary_text = "\n\n📅 <b>Deine gewählten Termine:</b>\n"
            for d in selected_dates:
                start_raw = d['start']
                end_raw = d.get('end')
                
                start = format_ics_date(start_raw)
                if not start: continue
                
                # Intelligent End-Date Logic (Overnight support)
                if end_raw:
                    try:
                        dt_s = datetime.fromisoformat(start_raw.replace('Z', ''))
                        dt_e = datetime.fromisoformat(end_raw.replace('Z', ''))
                        if dt_e <= dt_s:
                            dt_e = dt_e + timedelta(days=1)
                        end = dt_e.strftime('%Y%m%dT%H%M%S')
                    except: end = start
                else:
                    try:
                        dt_s = datetime.fromisoformat(start_raw.replace('Z', ''))
                        dt_e = dt_s + timedelta(hours=1)
                        end = dt_e.strftime('%Y%m%dT%H%M%S')
                    except: end = start
                
                summary = f"{event.calendar_title or event.title} ({d['label']})"
                
                # Helper for clean text description (strip HTML)
                import re
                def clean_html(raw_html):
                    cleanr = re.compile('<.*?>')
                    return re.sub(cleanr, '', raw_html)

                # Prepare the note (all DM info without HTML)
                note_text = clean_html(f"{header}\n{body}\n{footer}")

                # ICS Special escaping
                def escape_ics(t):
                    if not t: return ""
                    return str(t).replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')

                # Deterministic UID
                uid_seed = f"event_{event.id}_{d['start']}_{d['label']}"
                uid = f"{hashlib.md5(uid_seed.encode()).hexdigest()}@strauss-bot.de"
                dtstamp = datetime.now().strftime('%Y%m%dT%H%M%S')
                
                ics_lines.extend([
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{dtstamp}",
                    f"SUMMARY:{escape_ics(summary)}",
                    f"DTSTART;TZID=Europe/Berlin:{start}",
                    f"DTEND;TZID=Europe/Berlin:{end}",
                    f"LOCATION:{escape_ics(event.location if event.location_in_dm else '')}",
                    f"DESCRIPTION:{escape_ics(note_text)[:2000]}",
                    "TRANSP:OPAQUE",
                    "SEQUENCE:0",
                    "STATUS:CONFIRMED",
                    "END:VEVENT"
                ])
                
                # Add to text summary for DM
                try:
                    dt = datetime.fromisoformat(d['start'].replace('Z', ''))
                    dates_summary_text += f"• {d['label']}: {dt.strftime('%d.%m. um %H:%M')}\n"
                except: pass
            
            ics_lines.append("END:VCALENDAR")
            ics_content = "\r\n".join(ics_lines) + "\r\n"
            
            ics_file = io.BytesIO(ics_content.encode('utf-8'))
            fname = event.calendar_filename or "termine.ics"
            if not fname.lower().endswith(".ics"): fname += ".ics"
            ics_file.name = fname
            
        full_text = f"{header}{body}{footer}{dates_summary_text}\n\n<i>Tipp: Du findest den Kalendereintrag im Anhang!</i>"


        # 3. Send
        try:
            # Fix: Define dm_markup (empty as buttons are no longer needed)
            dm_markup = None
            
            media_path = event.confirmation_image_path or event.image_path
            full_path = None
            if media_path:
                full_path = os.path.join(PROJECT_ROOT, 'web_dashboard', 'app', media_path.lstrip('/'))
                if not os.path.exists(full_path): full_path = None

            if full_path:
                is_video = full_path.lower().endswith(('.mp4', '.mov', '.avi', '.webm'))
                with open(full_path, 'rb') as f:
                    if is_video:
                        w, h, dur = get_video_dimensions(full_path)
                        await bot.send_video(
                            chat_id=user.id,
                            video=f,
                            width=w,
                            height=h,
                            duration=dur,
                            supports_streaming=True,
                            caption=full_text,
                            parse_mode=ParseMode.HTML
                        )
                    else:
                        await bot.send_photo(
                            chat_id=user.id, 
                            photo=f, 
                            caption=full_text, 
                            parse_mode=ParseMode.HTML
                        )
            else:
                await bot.send_message(chat_id=user.id, text=full_text, parse_mode=ParseMode.HTML)

            
            if ics_file:
                logger.info(f"Sending ICS file {fname} to user {user.id}")
                await bot.send_document(
                    chat_id=user.id, 
                    document=ics_file, 
                    filename=fname,
                    caption="📅 Deine Kalender-Termine"
                )
            
            rsvp.dm_sent_status = 'success'
            rsvp.dm_error = None
        except Forbidden:
            rsvp.dm_sent_status = 'failed'
            rsvp.dm_error = "User hat Bot blockiert."
        except Exception as e:
            rsvp.dm_sent_status = 'failed'
            rsvp.dm_error = str(e)
            logger.error(f"Failed to send DM to {user.id}: {e}")
    except Exception as e:
        logger.error(f"Critical error in confirmation logic: {e}")

async def check_pending_events(context: ContextTypes.DEFAULT_TYPE):
    """Poll DB for events that haven't been posted yet or need updates."""
    try:
        from datetime import datetime
        now = datetime.utcnow()
        with flask_app.app_context():
            db.session.remove()
            all_events = GroupEvent.query.all()
            
            # 1. Post new events
            pending = [e for e in all_events if not e.message_id and e.chat_id]
            for event in pending:
                try:
                    # Check schedule
                    if event.scheduled_time and event.scheduled_time > now:
                        continue

                    limit = 1024 if (event.image_path and not event.is_split) else 4000
                    text = format_event_text(event.title, event.description, {}, event=event, max_chars=limit)
                    
                    # Instead of buttons, we will send a poll later
                    topic_id_int = None
                    if event.topic_id:
                        try:
                            topic_id_int = int(event.topic_id)
                        except (ValueError, TypeError):
                            logger.warning(f"EVENT-BOT: topic_id '{event.topic_id}' is not an integer. Using None (General).")
                    
                    logger.info(f"EVENT-BOT: Attempting to post/update event {event.id} to Chat:{event.chat_id}, Topic:{topic_id_int}")
                    
                    posted_msg = None
                    if event.image_path:
                        img_path = os.path.join(PROJECT_ROOT, 'web_dashboard', 'app', event.image_path.lstrip('/'))
                        if os.path.exists(img_path):
                            import io
                            from telegram import InputFile
                            
                            # If split, caption is empty (or just the title)
                            caption_text = event.title if event.is_split else text
                            
                            try:
                                with open(img_path, 'rb') as f_stream:
                                    # Use InputFile to ensure the filename is passed to Telegram
                                    media_input = InputFile(f_stream, filename=os.path.basename(img_path))
                                    
                                    as_doc = getattr(event, 'send_as_document', False)
                                    logger.info(f"Media Send: Event={event.id}, Type={event.media_type}, AsDocument={as_doc}")
                                    
                                    if as_doc:
                                        logger.info(f"Forcing Original Quality (send_document) for event {event.id}")
                                        posted_msg = await context.bot.send_document(
                                            document=media_input, 
                                            chat_id=event.chat_id,
                                            message_thread_id=topic_id_int,
                                            caption=caption_text,
                                            parse_mode=ParseMode.HTML,
                                            disable_notification=event.is_silent,
                                            write_timeout=120
                                        )
                                    elif event.media_type == 'video':
                                        logger.info(f"Sending as Video Player for event {event.id}")
                                        v_info = get_video_info(img_path)
                                        v_width, v_height, v_dur = v_info
                                        logger.info(f"Video Info: {v_width}x{v_height}, Dur: {v_dur}")
                                        
                                        # Generation of Thumbnail for correct Aspect Ratio
                                        v_thumb_path = generate_video_thumbnail(img_path)
                                        v_thumb = None
                                        if v_thumb_path:
                                            v_thumb = open(v_thumb_path, 'rb')

                                        # Conversion to int for API
                                        try:
                                            v_width = int(v_width) if v_width else None
                                            v_height = int(v_height) if v_height else None
                                            v_dur = int(float(v_dur)) if v_dur else None
                                        except: pass

                                        try:
                                            # Using a fresh file handle for the video
                                            with open(img_path, 'rb') as v_file:
                                                posted_msg = await context.bot.send_video(
                                                    video=v_file, 
                                                    chat_id=event.chat_id,
                                                    message_thread_id=topic_id_int,
                                                    caption=caption_text,
                                                    parse_mode=ParseMode.HTML,
                                                    disable_notification=event.is_silent,
                                                    width=v_width,
                                                    height=v_height,
                                                    duration=v_dur,
                                                    thumbnail=v_thumb,
                                                    write_timeout=120,
                                                    has_spoiler=event.has_spoiler,
                                                    supports_streaming=True
                                                )
                                        except Exception as video_err:
                                            logger.warning(f"Video Player failed, falling back to Document: {video_err}")
                                            with open(img_path, 'rb') as v_file:
                                                posted_msg = await context.bot.send_document(
                                                    document=v_file,
                                                    chat_id=event.chat_id,
                                                    message_thread_id=topic_id_int,
                                                    caption=caption_text,
                                                    parse_mode=ParseMode.HTML,
                                                    disable_notification=event.is_silent
                                                )
                                        finally:
                                            # Close and delete thumbnail
                                            if v_thumb:
                                                v_thumb.close()
                                            if v_thumb_path and os.path.exists(v_thumb_path):
                                                os.remove(v_thumb_path)
                                    elif event.media_type == 'animation':
                                        posted_msg = await context.bot.send_animation(
                                            animation=media_input,
                                            chat_id=event.chat_id,
                                            message_thread_id=topic_id_int,
                                            caption=caption_text,
                                            parse_mode=ParseMode.HTML,
                                            disable_notification=event.is_silent
                                        )
                                    else:
                                        posted_msg = await context.bot.send_photo(
                                            photo=media_input,
                                            chat_id=event.chat_id,
                                            message_thread_id=topic_id_int,
                                            caption=caption_text,
                                            parse_mode=ParseMode.HTML,
                                            disable_notification=event.is_silent,
                                            has_spoiler=event.has_spoiler
                                        )
                            except Exception as e:
                                logger.error(f"Media send failed ({event.media_type}) for event {event.id}: {e}")
                                posted_msg = None 
                                
                            # If split, send the main text separately
                            if event.is_split and posted_msg:
                                await context.bot.send_message(
                                    chat_id=event.chat_id,
                                    message_thread_id=topic_id_int,
                                    text=text,
                                    parse_mode=ParseMode.HTML,
                                    reply_markup=get_event_markup(event, {}),
                                    disable_notification=event.is_silent
                                )
                    if not posted_msg:
                        posted_msg = await context.bot.send_message(
                            chat_id=event.chat_id,
                            message_thread_id=topic_id_int,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=get_event_markup(event, {}),
                            disable_notification=event.is_silent
                        )
                    
                    event.message_id = posted_msg.message_id
                    
                    # --- BUILD POLL OPTIONS ---
                    poll_options = []
                    is_multi = getattr(event, 'poll_multiple_choice', True)
                    
                    # Custom Labels parsing
                    cfg = {}
                    if event.poll_config_json:
                        try: cfg = json.loads(event.poll_config_json)
                        except: pass

                    if event.event_dates_json:
                        try:
                            dates = json.loads(event.event_dates_json)
                            if dates:
                                # 1. General YES
                                if getattr(event, 'poll_show_yes', True):
                                    label = cfg.get('yes') or "✅ Bin dabei"
                                    poll_options.append(label)

                                # 2. All Days
                                if getattr(event, 'poll_show_all_day', True):
                                    label = cfg.get('all_day') or "🌟 Bin an ALLEN Tagen dabei"
                                    poll_options.append(label)
                                
                                # 3. Specific Dates
                                if getattr(event, 'poll_show_dates', True):
                                    for d in dates:
                                        try:
                                            dt = datetime.fromisoformat(d['start'].replace('Z', ''))
                                            date_str = dt.strftime('%d.%m. %H:%M')
                                            poll_options.append(f"📅 {d['label']} ({date_str})")
                                        except:
                                            poll_options.append(f"📅 {d['label']}")
                        except: pass
                    
                    if not poll_options:
                        # Fallback if no dates or dates hidden
                        if getattr(event, 'poll_show_yes', True):
                            label = cfg.get('yes') or "✅ Bin dabei"
                            poll_options.append(label)
                    
                    # 4. Maybe
                    if getattr(event, 'poll_show_maybe', True):
                        label = cfg.get('maybe') or "🤔 Vielleicht"
                        poll_options.append(label)

                    # 5. No
                    if getattr(event, 'poll_show_no', True):
                        label = cfg.get('no') or "❌ Bin gar nicht dabei"
                        poll_options.append(label)

                    if event.interaction_type == 'poll' and poll_options:
                        poll_msg = await context.bot.send_poll(
                            chat_id=event.chat_id,
                            message_thread_id=topic_id_int,
                            question=f"Teilnahme: {event.title}",
                            options=poll_options,
                            is_anonymous=False,
                            allows_multiple_answers=is_multi,
                            disable_notification=event.is_silent
                        )
                        event.poll_id = str(poll_msg.poll.id)
                    else:
                        event.poll_id = None
                    db.session.commit()
                    
                    if event.should_pin:
                        try:
                            await context.bot.pin_chat_message(chat_id=event.chat_id, message_id=posted_msg.message_id)
                        except: pass

                except Exception as e:
                    logger.error(f"Failed to post event {event.id}: {e}")

            # 2. Update existing events (Edited in Dashboard)
            to_update = [e for e in all_events if e.message_id and e.needs_update]
            for event in to_update:
                try:
                    # Get current RSVP counts
                    counts = {
                        'dabei': EventRSVP.query.filter_by(event_id=event.id, status='dabei').count(),
                        'vielleicht': EventRSVP.query.filter_by(event_id=event.id, status='vielleicht').count(),
                        'nicht_dabei': EventRSVP.query.filter_by(event_id=event.id, status='nicht_dabei').count()
                    }
                    limit = 1024 if (event.image_path and not event.is_split) else 4000
                    new_text = format_event_text(event.title, event.description, counts, event=event, max_chars=limit)
                    
                    try:
                        # Try editing caption (photo/video/animation)
                        await context.bot.edit_message_caption(
                            chat_id=event.chat_id,
                            message_id=event.message_id,
                            caption=new_text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=get_event_markup(event, counts)
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "Message is not modified" in error_str: 
                            pass
                        elif "Message to edit not found" in error_str or "Message_id_invalid" in error_str:
                            logger.warning(f"Message for event {event.id} not found in Telegram. Clearing ID to allow repost.")
                            event.message_id = None # Set to None so it gets reposted in the next block
                        else:
                            # Try editing as text if caption fails
                            try:
                                await context.bot.edit_message_text(
                                    chat_id=event.chat_id,
                                    message_id=event.message_id,
                                    text=new_text,
                                    parse_mode=ParseMode.HTML,
                                    reply_markup=get_event_markup(event, counts)
                                )
                            except Exception as e2:
                                if "Message to edit not found" in str(e2) or "Message_id_invalid" in str(e2):
                                    event.message_id = None
                                else:
                                    logger.error(f"Failed to update event {event.id} in Telegram: {e2}")
                    
                    event.needs_update = False
                    db.session.commit()
                    logger.info(f"✅ Event {event.id} updated in Telegram.")
                except Exception as e:
                    logger.error(f"Failed to update event {event.id} in Telegram: {e}")

    except Exception as e:
        logger.error(f"Error in check_pending_events job: {e}")

async def rsvp_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button-based RSVPs."""
    query = update.callback_query
    data = query.data
    if not data.startswith("event_rsvp_"): return
    
    parts = data.split("_")
    if len(parts) < 4: return
    
    event_id = int(parts[2])
    status = parts[3]
    user = query.from_user
    
    try:
        with flask_app.app_context():
            event = GroupEvent.query.get(event_id)
            if not event:
                await query.answer("Event nicht gefunden.")
                return
            
            # Update RSVP
            rsvp = EventRSVP.query.filter_by(event_id=event.id, telegram_user_id=user.id).first()
            if rsvp:
                if rsvp.status == status:
                    await query.answer("Du hast bereits diesen Status.")
                    return
                rsvp.status = status
                rsvp.username = user.username or user.first_name
            else:
                rsvp = EventRSVP(
                    event_id=event.id,
                    telegram_user_id=user.id,
                    username=user.username or user.first_name,
                    status=status
                )
                db.session.add(rsvp)
            
            db.session.commit()
            
            # Trigger confirmation if joined
            if status == "dabei" and event.send_confirmation:
                await send_private_confirmation(context.bot, event, user, rsvp)
                db.session.commit()
                
            await query.answer(f"Status aktualisiert: {status}")
            
            # Update the message to show new counts
            counts = {
                'dabei': EventRSVP.query.filter_by(event_id=event.id, status='dabei').count(),
                'vielleicht': EventRSVP.query.filter_by(event_id=event.id, status='vielleicht').count(),
                'nicht_dabei': EventRSVP.query.filter_by(event_id=event.id, status='nicht_dabei').count()
            }
            limit = 1024 if (event.image_path and not event.is_split) else 4000
            new_text = format_event_text(event.title, event.description, counts, event=event, max_chars=limit)
            
            try:
                if query.message.caption:
                    await query.edit_message_caption(caption=new_text, parse_mode=ParseMode.HTML, reply_markup=get_event_markup(event, counts))
                else:
                    await query.edit_message_text(text=new_text, parse_mode=ParseMode.HTML, reply_markup=get_event_markup(event, counts))
            except Exception as e:
                if "Message is not modified" not in str(e):
                    logger.error(f"Failed to update RSVP message: {e}")
                    
    except Exception as e:
        logger.error(f"Error in rsvp_button_handler: {e}")
        await query.answer("Fehler beim Speichern.")

def setup_jobs(job_queue):
    """Register the polling job."""
    job_queue.run_repeating(check_pending_events, interval=10, first=5)
    logger.info("✅ Event polling job registered (10s interval).")

def get_handlers():
    return [
        PollAnswerHandler(poll_answer_handler),
        CallbackQueryHandler(rsvp_button_handler, pattern="^event_rsvp_")
    ]

if __name__ == "__main__":
    logger.error("Dieses Modul läuft nur via main_bot.py")

if __name__ == "__main__":
    logger.error("Dieses Modul läuft nur via main_bot.py")
