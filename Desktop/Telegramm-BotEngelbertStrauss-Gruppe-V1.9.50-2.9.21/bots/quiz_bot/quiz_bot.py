import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
import json
import time
import random
import asyncio
import logging
import hashlib
from datetime import datetime, time as dt_time, timedelta
from telegram import Bot, InputMediaPhoto, InputMediaVideo
from telegram.error import TelegramError

# ----------------- Setup -----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
TRIGGER_FILE = os.path.join(BASE_DIR, "send_now.tmp")
TRIGGER_FILE = os.path.join(BASE_DIR, "send_now.tmp")
STATE_FILE = os.path.join(PROJECT_ROOT, "instance", "quiz_bot_state.json")

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
QUIZ_FILE = os.path.join(DATA_DIR, "quizfragen.json")
QUIZ_FILE = os.path.join(DATA_DIR, "quizfragen.json")
USED_FILE = os.path.join(PROJECT_ROOT, "instance", "quizfragen_gestellt.json")

# Navigating to project root
sys.path.append(PROJECT_ROOT)
from shared_bot_utils import get_bot_config, is_bot_active, get_bot_token

# logging.basicConfig is handled by main_bot.py
log = logging.getLogger(__name__)

def load_config_from_db():
    return get_bot_config("quiz")


# ----------------- Helpers -----------------
def load_json(path, default):
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Error loading JSON from {path}: {e}")
        return default

def save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"Error saving JSON to {path}: {e}")

def get_last_sent_slot():
    """Returns the last sent date+time slot string, e.g. '2026-07-10_12:00'"""
    state = load_json(STATE_FILE, {})
    return state.get("last_sent_slot", "")

def set_last_sent_slot(date_obj, time_str):
    """Saves date+scheduled_time so changing the time in dashboard forces a new send."""
    state = load_json(STATE_FILE, {})
    state["last_sent_slot"] = f"{date_obj.strftime('%Y-%m-%d')}_{time_str}"
    save_json(STATE_FILE, state)

def question_fingerprint(q: dict) -> str:
    frage = str(q.get("frage", "")).strip()
    optionen = q.get("optionen", [])
    if not isinstance(optionen, list):
        optionen = []
    opt_strs = []
    for opt in optionen:
        if isinstance(opt, dict):
            opt_strs.append(str(opt.get("text", "")).strip())
        else:
            opt_strs.append(str(opt).strip())
    payload = frage + "||" + "||".join(sorted(opt_strs))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()

# ----------------- Core Logic -----------------
async def send_quiz(context=None, force=False, specific_question_data=None):
    if not force and not is_bot_active('quiz'):
        log.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Quiz Bot ist inaktiv (kein force). Abbruch.")
        return False
        
    log.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Attempting to send quiz...")
    cfg = load_config_from_db()
    token = cfg.get("bot_token", "").strip() or get_bot_token()
    chat_id = cfg.get("channel_id", "").strip()
    topic_id = cfg.get("topic_id", "")

    if not token:
        log.warning("No bot token found.")
        return False
    if not chat_id:
        log.warning("No channel_id/chat_id found in Quiz config.")
        return False

    if specific_question_data:
        question_data = specific_question_data
    else:
        all_questions = load_json(QUIZ_FILE, [])
        if not all_questions:
            log.error(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No questions found in quizfragen.json")
            # Continue so the admin notification gets triggered below

        used_hashes = set(load_json(USED_FILE, []))
        available_questions = [q for q in all_questions if question_fingerprint(q) not in used_hashes]

        if not available_questions:
            log.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] All questions have been asked. Sending admin notification.")
            try:
                bot = Bot(token=token)
                try:
                    await bot.send_message(
                        chat_id="-1003372573784", 
                        text="⚠️ **Achtung (Quiz-Bot):** Es sind **keine** Quizfragen mehr verfügbar! Bitte lade neue im Dashboard hoch.",
                        message_thread_id=1,
                        parse_mode="Markdown"
                    )
                except Exception as ex:
                    log.warning(f"Failed with thread_id=1, trying without: {ex}")
                    await bot.send_message(
                        chat_id="-1003372573784", 
                        text="⚠️ **Achtung (Quiz-Bot):** Es sind **keine** Quizfragen mehr verfügbar! Bitte lade neue im Dashboard hoch.",
                        parse_mode="Markdown"
                    )
            except Exception as e:
                log.error(f"Failed to send admin notification: {e}")
            # Return True so the scheduler marks today as 'done' and doesn't spam every minute
            return True

        question_data = random.choice(available_questions)
    
    frage = question_data.get("frage", "").strip()
    optionen_raw = question_data.get("optionen", [])
    optionen = []
    for opt in optionen_raw:
        if isinstance(opt, dict):
            optionen.append(opt.get("text", ""))
        else:
            optionen.append(str(opt))
    antwort_idx = int(question_data.get("antwort", 0))
    is_anonymous = question_data.get("is_anonymous", True)
    shuffle_options = question_data.get("shuffle_options", False)
    open_period = question_data.get("open_period")
    
    # NEU: Mighty Polls Parameter (Erklärung und Medien)
    erklaerung = question_data.get("erklaerung", "").strip()
    frage_media_url = question_data.get("frage_media_url", "").strip()
    frage_media_type = question_data.get("frage_media_type", "photo").strip()

    # --- Validation for Telegram API Limits ---
    if len(frage) > 300:
        log.warning(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Question too long ({len(frage)} chars). Skipping.")
        return False
    
    if len(optionen) < 2 or len(optionen) > 10:
        log.warning(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Invalid number of options ({len(optionen)}). Skipping.")
        return False
        
    if antwort_idx < 0 or antwort_idx >= len(optionen):
        log.warning(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Invalid correct option index {antwort_idx}. Skipping.")
        return False

    if shuffle_options:
        # Keep track of the correct option text
        correct_text = optionen[antwort_idx]
        random.shuffle(optionen)
        # Find new index of correct option
        antwort_idx = optionen.index(correct_text)

    for opt in optionen:
        if len(str(opt)) > 100:
             log.warning(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Option too long ({len(str(opt))} chars). Skipping.")
             return False

    try:
        bot = Bot(token=token)
        
        # Handle Topic ID
        message_thread_id = None
        if topic_id and str(topic_id).strip().lower() != "null":
             if str(topic_id).isdigit():
                 message_thread_id = int(topic_id)
        
        log.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sending quiz to {chat_id} (Topic: {message_thread_id}): {frage}")
        
        poll_kwargs = {
            "chat_id": chat_id,
            "question": frage,
            "options": optionen,
            "type": 'quiz',
            "correct_option_id": antwort_idx,
            "is_anonymous": is_anonymous,
            "message_thread_id": message_thread_id
        }

        if open_period and str(open_period).isdigit():
            poll_kwargs["open_period"] = int(open_period)

        # Detaillierte Erklärungen hinzufügen (für falsch beantwortete Fragen)
        if erklaerung:
            poll_kwargs["explanation"] = erklaerung
            
        # Integration der neuen Parameter zum Anhängen von Medien (InputMedia Objekte)
        if frage_media_url:
            if frage_media_type.lower() == "video":
                poll_kwargs["question_media"] = InputMediaVideo(media=frage_media_url)
            else:
                poll_kwargs["question_media"] = InputMediaPhoto(media=frage_media_url)

        await bot.send_poll(**poll_kwargs)
        
        # Mark as used
        used_hashes.add(question_fingerprint(question_data))
        save_json(USED_FILE, list(used_hashes))
        
        log.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Quiz sent successfully.")
        return True

    except TelegramError as e:
        log.error(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Telegram API Error: {e}")
        return False
    except Exception as e:
        log.error(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unexpected error sending quiz: {e}")
        return False

# ----------------- Scheduler and Trigger -----------------
async def process_trigger(context=None):
    # Debug: Logge den Pfad einmalig/gelegentlich oder bei Fund
    if not hasattr(process_trigger, "last_debug"): process_trigger.last_debug = 0
    if time.time() - process_trigger.last_debug > 60:
        log.info(f"Checking for manual trigger at: {os.path.abspath(TRIGGER_FILE)}")
        process_trigger.last_debug = time.time()

    specific_file = os.path.join(os.path.dirname(TRIGGER_FILE), "send_specific.json")
    if os.path.exists(specific_file):
        log.info(f"Specific trigger detected at {os.path.abspath(specific_file)}.")
        try:
            with open(specific_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            os.remove(specific_file)
            await send_quiz(force=True, specific_question_data=data)
        except Exception as e:
            log.error(f"Error processing specific trigger: {e}")

    if os.path.exists(TRIGGER_FILE):
        log.info(f"Manual trigger detected at {os.path.abspath(TRIGGER_FILE)}.")
        try:
            os.remove(TRIGGER_FILE)
            await send_quiz(force=True)
        except Exception as e:
            log.error(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error processing trigger: {e}")

async def check_schedule():
    cfg = load_config_from_db()
    schedule = cfg.get("schedule", {})
    
    if not schedule.get("enabled"):
        return

    time_str = schedule.get("time")
    if not time_str: return

    try:
        scheduled_time = datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        log.error(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Invalid schedule time format: {time_str}")
        return

    now = datetime.now()
    today_date = now.date()

    # Check if already sent today for THIS specific time slot
    current_slot = f"{today_date.strftime('%Y-%m-%d')}_{time_str}"
    if get_last_sent_slot() == current_slot:
        return

    # Check correct day of week
    allowed_days = schedule.get("days", [])
    if now.weekday() not in allowed_days:
        return

    # Check time window: send if we are within 5 min of the scheduled time
    import datetime as dt_module
    sched_dt = dt_module.datetime.combine(today_date, scheduled_time)
    diff_minutes = (now - sched_dt).total_seconds() / 60
    if 0 <= diff_minutes < 5:
        log.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduled time reached ({time_str}). Sending quiz...")
        success = await send_quiz()
        if success:
            set_last_sent_slot(today_date, time_str)
            log.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Schedule slot '{current_slot}' marked as done.")

async def check_schedule_job(context=None):
    try:
        if not is_bot_active('quiz'): return
        await check_schedule()
    except Exception as e:
        log.exception(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Exception in check_schedule_job: {e}")

# ----------------- Master Bot Setup -----------------
def setup_jobs(job_queue):
    log.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Quiz Bot registriert Jobs...")
    # Trigger-Check alle 10 Sekunden
    job_queue.run_repeating(process_trigger, interval=10)
    # Schedule-Check minutlich
    job_queue.run_repeating(check_schedule_job, interval=60)

if __name__ == "__main__":
    print("Bitte starte den Bot über main_bot.py")
