import os
import shutil
import logging
import json
import zipfile
import html
from datetime import datetime, time
from telegram.ext import ContextTypes, Application
from shared_bot_utils import DB_PATH, PROJECT_ROOT, get_bot_config, get_shared_flask_app

logger = logging.getLogger(__name__)

# Backup directories
LOCAL_BACKUP_DIR = os.path.join(PROJECT_ROOT, "instance", "backups")

async def perform_backup(context: ContextTypes.DEFAULT_TYPE = None):
    """Main backup logic with ZIP compression for 'Everything' safety."""
    if context:
        await notify_admin(context, "🔄 <b>Automatisches Voll-Backup gestartet...</b>\nDatenbank und Bilder werden gesichert.")
    
    logger.info("Starting automated full backup...")
    
    config = get_bot_config('backup_bot')
    if not config or not config.get('enabled'):
        logger.info("Backup is disabled in settings.")
        return

    nas_path = config.get('nas_path')
    local_retention = config.get('local_retention', 7)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename = f"FULL_BACKUP_{timestamp}.zip"
    
    # Temporäres ZIP erstellen
    temp_zip = os.path.join(PROJECT_ROOT, "instance", "tmp_auto_backup.zip")
    
    try:
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as z:
            # 1. DB
            if os.path.exists(DB_PATH):
                z.write(DB_PATH, arcname="database/app.db")
            # 2. .env
            env_path = os.path.join(PROJECT_ROOT, ".env")
            if os.path.exists(env_path):
                z.write(env_path, arcname=".env")
            # 3. Media
            media_dir = os.path.join(PROJECT_ROOT, "web_dashboard", "app", "static", "uploads")
            if os.path.exists(media_dir):
                for root, _, files in os.walk(media_dir):
                    for file in files:
                        f_path = os.path.join(root, file)
                        rel = os.path.relpath(f_path, os.path.join(PROJECT_ROOT, "web_dashboard", "app", "static"))
                        z.write(f_path, arcname=f"media/{rel}")
    except Exception as e:
        logger.error(f"Error zipping backup: {e}")
        if context: await notify_admin(context, f"❌ Fehler beim Zippen des Backups: {html.escape(str(e))}")
        return

    # 1. Local Backup
    try:
        os.makedirs(LOCAL_BACKUP_DIR, exist_ok=True)
        local_path = os.path.join(LOCAL_BACKUP_DIR, backup_filename)
        shutil.copy2(temp_zip, local_path)
        logger.info(f"Local full backup created: {local_path}")
        
        # Cleanup
        if local_retention > 0:
            all_b = sorted([f for f in os.listdir(LOCAL_BACKUP_DIR) if f.startswith("FULL_BACKUP_")])
            if len(all_b) > local_retention:
                for old in all_b[:-local_retention]: os.remove(os.path.join(LOCAL_BACKUP_DIR, old))
    except Exception as e:
        logger.error(f"Error during local backup: {e}")

    # 2. NAS Backup
    if nas_path:
        try:
            if not os.path.exists(nas_path): os.makedirs(nas_path, exist_ok=True)
            nas_file_path = os.path.join(nas_path, backup_filename)
            shutil.copy2(temp_zip, nas_file_path)
            if context: await notify_admin(context, f"✅ Voll-Backup erfolgreich an NAS übertragen: <code>{html.escape(backup_filename)}</code>")
        except Exception as e:
            logger.error(f"Error during NAS backup: {e}")
            
    # 3. Google Drive Backup
    gdrive_enabled = config.get('gdrive_enabled', False)
    gdrive_folder_id = config.get('gdrive_folder_id')
    gdrive_retention = config.get('gdrive_retention', 7)
    
    if gdrive_enabled and gdrive_folder_id:
        try:
            drive_file_id = upload_to_gdrive(temp_zip, backup_filename, gdrive_folder_id, config=config)
            logger.info(f"Google Drive backup uploaded successfully. File ID: {drive_file_id}")
            if context:
                await notify_admin(context, f"☁️ Voll-Backup erfolgreich an Google Drive übertragen: <code>{html.escape(backup_filename)}</code>")
            
            # Retention Cleanup
            cleanup_gdrive_backups(gdrive_folder_id, gdrive_retention, config=config)
        except Exception as e:
            logger.error(f"Error during Google Drive backup: {e}")
            if context:
                await notify_admin(context, f"❌ Fehler beim Übertragen an Google Drive: {html.escape(str(e))}")
            
    if os.path.exists(temp_zip): os.remove(temp_zip)

def get_gdrive_service(config):
    """Creates a Google Drive API client using either DB config or file credentials."""
    import json
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_json = config.get('gdrive_credentials_json')
    scopes = ["https://www.googleapis.com/auth/drive"]

    if creds_json:
        try:
            info = json.loads(creds_json)
            creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
            return build("drive", "v3", credentials=creds)
        except Exception as e:
            logger.error(f"Error parsing credentials from database: {e}")
            
    # Fallback to file
    creds_path = os.path.join(PROJECT_ROOT, "google_drive_credentials.json")
    if os.path.exists(creds_path):
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
        return build("drive", "v3", credentials=creds)
        
    raise FileNotFoundError("Keine Google Drive Zugangsdaten in Datenbank oder Datei gefunden.")

def upload_to_gdrive(filepath, filename, folder_id, config=None):
    """Uploads a file to Google Drive using database or file credentials."""
    from googleapiclient.http import MediaFileUpload
    if config is None:
        config = get_bot_config('backup_bot') or {}
        
    service = get_gdrive_service(config)
    
    file_metadata = {
        "name": filename,
        "parents": [folder_id]
    }
    media = MediaFileUpload(filepath, mimetype="application/zip", resumable=True)
    
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return file.get("id")

def cleanup_gdrive_backups(folder_id, retention_days, config=None):
    """Deletes older backup files in Google Drive matching the naming pattern."""
    if retention_days <= 0:
        return # Keep all
        
    if config is None:
        config = get_bot_config('backup_bot') or {}
        
    try:
        service = get_gdrive_service(config)
    except Exception as e:
        logger.error(f"Error initializing Google Drive client for cleanup: {e}")
        return
    
    # Query files in folder
    query = f"'{folder_id}' in parents and name contains 'FULL_BACKUP_' and mimeType = 'application/zip' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)", orderBy="createdTime desc").execute()
    files = results.get("files", [])
    
    if len(files) > retention_days:
        for old_file in files[retention_days:]:
            try:
                service.files().delete(fileId=old_file["id"]).execute()
                logger.info(f"Deleted old Google Drive backup: {old_file['name']}")
            except Exception as delete_err:
                logger.error(f"Error deleting Google Drive file {old_file['name']}: {delete_err}")

async def notify_admin(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Sends a notification to the admin group or owner."""
    try:
        id_config = get_bot_config('id_finder')
        backup_config = get_bot_config('backup_bot') or {}
        
        # Backup-Gruppe priorisieren, falls gesetzt. Ansonsten Standard Admin-Gruppe.
        admin_chat_id = backup_config.get('backup_group_id')
        if not admin_chat_id:
            admin_chat_id = id_config.get('admin_group_id')
            
        topic_id = id_config.get('admin_log_topic_id')
        
        # Standardmäßig stumm, außer in den Settings deaktiviert
        silent = backup_config.get('silent_notifications', True)
        
        if admin_chat_id:
            kwargs = {"chat_id": admin_chat_id, "text": f"💾 <b>BACKUP-SYSTEM</b>\n\n{message}", "parse_mode": "HTML", "disable_notification": silent}
            if topic_id:
                kwargs["message_thread_id"] = topic_id
            await context.bot.send_message(**kwargs)
    except Exception as e:
        logger.error(f"Could not notify admin about backup: {e}")

def setup_jobs(job_queue):
    """Registers the daily backup job."""
    config = get_bot_config('backup_bot')
    if not config: return
    backup_time_str = config.get('backup_time', '06:55')
    try:
        h, m = map(int, backup_time_str.split(':'))
        backup_time = time(hour=h, minute=m)
    except: backup_time = time(hour=6, minute=55)
    job_queue.run_daily(perform_backup, time=backup_time, name="daily_database_backup")

def get_handlers(): return []
