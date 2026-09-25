from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, current_app, send_from_directory
from flask_login import login_required, current_user
from ..decorators import admin_required, permission_required
import os
import json
import subprocess
import sys
import signal
from datetime import datetime, timedelta
from sqlalchemy import func, extract, case, text, true
import traceback
import time
import logging
from werkzeug.utils import secure_filename
from ..models import db, BotSettings, Broadcast, TopicMapping, User, IDFinderAdmin, IDFinderUser, IDFinderMessage, AuditLog, AVAILABLE_PERMISSIONS, AutoReplyRule

# Wir definieren den Blueprint explizit
bp = Blueprint('dashboard', __name__)
logger = logging.getLogger(__name__)
AVATAR_CACHE = {}

# Pfade berechnen
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_FILE_DIR, '../../..'))
BASE_DIR = os.path.join(PROJECT_ROOT, 'web_dashboard')

# Bot PID Files
INVITE_BOT_PID_FILE = os.path.join(PROJECT_ROOT, "logs", "invite_bot.pid")
ID_FINDER_BOT_PID_FILE = os.path.join(PROJECT_ROOT, "logs", "id_finder_bot.pid")
TIKTOK_BOT_PID_FILE = os.path.join(PROJECT_ROOT, "logs", "tiktok_bot.pid")
QUIZ_BOT_PID_FILE = os.path.join(PROJECT_ROOT, "logs", "quiz_bot.pid")
UMFRAGE_BOT_PID_FILE = os.path.join(PROJECT_ROOT, "logs", "umfrage_bot.pid")
OUTFIT_BOT_PID_FILE = os.path.join(PROJECT_ROOT, "logs", "outfit_bot.pid")

# Log Files
INVITE_BOT_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "invite_bot.log")
ID_FINDER_BOT_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "id_finder_bot.log")
TIKTOK_BOT_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "tiktok_bot.log")
QUIZ_BOT_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "quiz_bot.log")
UMFRAGE_BOT_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "umfrage_bot.log")
OUTFIT_BOT_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "outfit_bot.log")

def is_process_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def safe_clear_log(filepath):
    if not os.path.exists(filepath): return True
    try:
        # Versuch 1: LÃƒÆ’Ã‚Â¶schen
        os.remove(filepath)
        return True
    except Exception as e:
        # Versuch 2: Leeren (Truncate), falls LÃƒÆ’Ã‚Â¶schen fehlschlÃƒÆ’Ã‚Â¤gt (File In Use)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.truncate(0)
            return True
        except Exception as e2:
            print(f"Error clearing log {filepath}: {e}, Truncate error: {e2}")
            return False

def get_master_pid():
    pfile = os.path.join(PROJECT_ROOT, "logs", "main_bot.pid")
    if os.path.exists(pfile):
        try:
            with open(pfile, 'r') as f: return int(f.read().strip())
        except: return None
    return None

def fmt_dt(d):
    """Helper for date formatting (Handles mysql date objects vs sqlite strings)"""
    if not d: return 'Unknown'
    if hasattr(d, 'strftime'): return d.strftime('%d.%m')
    try:
        s = str(d)
        if '-' in s:
            parts = s.split('-')
            if len(parts) >= 3: return f"{parts[2][:2]}.{parts[1]}"
        return s
    except: return 'Err'

def get_bot_status_simple():
    status = {
        "invite": {"running": False}, "quiz": {"running": False}, 
        "umfrage": {"running": False}, "outfit": {"running": False}, 
        "id_finder": {"running": False}, "tiktok": {"running": False},
        "auto_responder": {"running": False}, "profanity_filter": {"running": False},
        "birthday": {"running": False}, "report_bot": {"running": False}, 
        "event_bot": {"running": False}, "reaction_bot": {"running": False}
    }
    
    # ID Finder (Master Bot) ist der einzige echte Prozess
    pid = get_master_pid()
    if pid and is_process_running(pid):
        status["id_finder"]["running"] = True
    
    # Alle anderen Module lesen ihren "Aktiv" Status aus der Datenbank
    try:
        settings = BotSettings.query.all()
        for s in settings:
            if s.bot_name in status: # Check if bot_name is in status dict
                if s.config_json:
                    c = json.loads(s.config_json)
                    status[s.bot_name]["config"] = c
                    if s.bot_name == 'id_finder':
                        if 'last_heartbeat' in c:
                            status['id_finder']['last_heartbeat'] = c['last_heartbeat']
                    else: # For other bots, check 'is_active'
                        if c.get('is_active'):
                            status[s.bot_name]["running"] = True
    except Exception as e:
        print(f"Fehler beim Lesen des Bot-Status: {e}")
        
    return status

@bp.context_processor
def inject_globals():
    has_crit = False
    lpath = os.path.join(PROJECT_ROOT, "logs", "critical_errors.log")
    if os.path.exists(lpath) and os.path.getsize(lpath) > 0:
        has_crit = True
    return {"bot_status": get_bot_status_simple(), "has_critical_errors": has_crit}

@bp.route('/')
@bp.route('/dashboard')
@login_required
def index():
    version_path = os.path.join(PROJECT_ROOT, 'version.json')
    version = {"version": "1.0.0"}
    if os.path.exists(version_path):
        try:
            with open(version_path, 'r') as f: version = json.load(f)
        except: pass
    layout_settings = BotSettings.query.filter_by(bot_name='dashboard_layout').first()
    layout = json.loads(layout_settings.config_json) if layout_settings else None
    
    backup_settings = BotSettings.query.filter_by(bot_name='backup_bot').first()
    backup_config = json.loads(backup_settings.config_json) if backup_settings else {'enabled': False, 'nas_path': '', 'backup_time': '06:55', 'local_retention': 7}
    
    return render_template('index.html', version=version, layout=layout, backup_config=backup_config)

@bp.route('/wiki')
@login_required
def wiki():
    return render_template('wiki.html')

@bp.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@bp.route('/profile/upload', methods=['POST'])
@login_required
def profile_upload():
    if 'profile_picture' not in request.files:
        flash('Keine Datei ausgewÃƒÆ’Ã‚Â¤hlt', 'danger')
        return redirect(url_for('dashboard.profile'))
    
    file = request.files['profile_picture']
    if file.filename == '':
        flash('Keine Datei ausgewÃƒÆ’Ã‚Â¤hlt', 'danger')
        return redirect(url_for('dashboard.profile'))
        
    if file:
        fdir = os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'profiles')
        os.makedirs(fdir, exist_ok=True)
        fname = secure_filename(file.filename)
        import time
        fname = f"{int(time.time())}_{fname}"
        file.save(os.path.join(fdir, fname))
        
        current_user.profile_picture = fname
        db.session.commit()
        
        try:
            from ..utils import log_audit
            log_audit("Profilbild geÃƒÆ’Ã‚Â¤ndert", f"Benutzer '{current_user.username}' hat ein neues Profilbild hochgeladen.")
        except: pass
        
        flash('Profilbild erfolgreich aktualisiert', 'success')
        
    return redirect(url_for('dashboard.profile'))

@bp.route('/profile/password', methods=['POST'])
@login_required
def profile_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not current_user.check_password(current_password):
        flash('Das aktuelle Passwort ist falsch.', 'danger')
        return redirect(url_for('dashboard.profile'))
        
    if new_password != confirm_password:
        flash('Die neuen PasswÃƒÆ’Ã‚Â¶rter stimmen nicht ÃƒÆ’Ã‚Â¼berein.', 'danger')
        return redirect(url_for('dashboard.profile'))
        
    import re
    if len(new_password) < 8:
        flash('Das neue Passwort muss mindestens 8 Zeichen lang sein.', 'danger')
        return redirect(url_for('dashboard.profile'))
        
    if not re.search(r'[A-Z]', new_password):
        flash('Das neue Passwort muss mindestens einen GroÃƒÆ’Ã…Â¸buchstaben enthalten.', 'danger')
        return redirect(url_for('dashboard.profile'))
        
    if not re.search(r'[0-9]', new_password):
        flash('Das neue Passwort muss mindestens eine Zahl enthalten.', 'danger')
        return redirect(url_for('dashboard.profile'))
        
    if not re.search(r'[^a-zA-Z0-9]', new_password):
        flash('Das neue Passwort muss mindestens ein Sonderzeichen enthalten.', 'danger')
        return redirect(url_for('dashboard.profile'))
        
    current_user.set_password(new_password)
    db.session.commit()
    
    try:
        from ..utils import log_audit
        log_audit("Passwort geÃƒÆ’Ã‚Â¤ndert", f"Benutzer '{current_user.username}' hat sein Passwort ÃƒÆ’Ã‚Â¼ber das Profil geÃƒÆ’Ã‚Â¤ndert.")
    except: pass
    
    flash('Passwort erfolgreich geÃƒÆ’Ã‚Â¤ndert.', 'success')
    return redirect(url_for('dashboard.profile'))

@bp.route('/profile/2fa/generate', methods=['POST'])
@login_required
def profile_2fa_generate():
    import pyotp
    import qrcode
    from io import BytesIO
    import base64
    
    # Generate a new random secret
    secret = pyotp.random_base32()
    
    # Save it temporarily (we won't enable 2fa until verified)
    current_user.totp_secret = secret
    db.session.commit()
    
    # Generate provisioning URI
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user.username, issuer_name="BotSteuerung")
    
    # Generate QR code
    qr = qrcode.make(uri)
    buffered = BytesIO()
    qr.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({
        "success": True, 
        "secret": secret,
        "qr_code": f"data:image/png;base64,{img_str}"
    })

@bp.route('/profile/2fa/verify', methods=['POST'])
@login_required
def profile_2fa_verify():
    import pyotp
    
    code = request.form.get('totp_code')
    if not current_user.totp_secret:
        flash('Fehler: Bitte generiere zuerst einen QR Code.', 'danger')
        return redirect(url_for('dashboard.profile'))
        
    totp = pyotp.TOTP(current_user.totp_secret)
    if totp.verify(code):
        current_user.two_factor_enabled = True
        db.session.commit()
        flash('Zwei-Faktor-Authentifizierung wurde erfolgreich aktiviert!', 'success')
        try:
            from ..utils import log_audit
            log_audit("2FA Aktiviert", f"Benutzer '{current_user.username}' hat 2FA aktiviert.")
        except: pass
    else:
        flash('UngÃƒÆ’Ã‚Â¼ltiger Code. Bitte versuche es erneut.', 'danger')
        
    return redirect(url_for('dashboard.profile'))

@bp.route('/profile/2fa/disable', methods=['POST'])
@login_required
def profile_2fa_disable():
    password = request.form.get('password')
    
    if not current_user.check_password(password):
        flash('Das Passwort ist falsch.', 'danger')
        return redirect(url_for('dashboard.profile'))
        
    current_user.two_factor_enabled = False
    current_user.totp_secret = None
    db.session.commit()
    
    flash('Zwei-Faktor-Authentifizierung wurde deaktiviert.', 'warning')
    try:
        from ..utils import log_audit
        log_audit("2FA Deaktiviert", f"Benutzer '{current_user.username}' hat 2FA deaktiviert.")
    except: pass
    
    return redirect(url_for('dashboard.profile'))

@bp.route('/profile/2fa/settings', methods=['POST'])
@login_required
def profile_2fa_settings():
    if not current_user.two_factor_enabled:
        flash('Bitte aktiviere zuerst 2FA.', 'danger')
        return redirect(url_for('dashboard.profile'))
        
    login_enabled = request.form.get('two_factor_login_enabled') == 'on'
    reset_enabled = request.form.get('two_factor_reset_enabled') == 'on'
    
    current_user.two_factor_login_enabled = login_enabled
    current_user.two_factor_reset_enabled = reset_enabled
    db.session.commit()
    
    flash('2FA Einstellungen erfolgreich gespeichert.', 'success')
    return redirect(url_for('dashboard.profile'))

@bp.route('/cleanup-settings')
@admin_required
def cleanup_settings():
    from ..models import TopicCleanupConfig, AutoCleanupTask
    configs = TopicCleanupConfig.query.all()
    queue = AutoCleanupTask.query.filter_by(status='pending').order_by(AutoCleanupTask.cleanup_at.asc()).all()
    return render_template('cleanup_settings.html', configs=configs, queue=queue)

@bp.route('/user-management')
@permission_required('manage_users')
def user_management():
    from ..models import TopicMapping
    topics = TopicMapping.query.all()
    return render_template('user_management.html', topics=topics)

@bp.route('/analytics')
@permission_required('view_analytics')
def analytics():
    return id_finder_analytics()

@bp.route('/team-management', methods=['GET', 'POST'])
@admin_required
def team_management():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role', 'user')
            
            if User.query.filter_by(username=username).first():
                flash("Benutzername existiert bereits.", "danger")
            else:
                user = User(username=username, role=role, must_change_password=True)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash(f"Benutzer {username} erstellt.", "success")
                
        elif action == 'delete':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                if user.id == current_user.id:
                    flash("Du kannst dich nicht selbst lÃƒÆ’Ã‚Â¶schen.", "danger")
                else:
                    db.session.delete(user)
                    db.session.commit()
                    flash("Benutzer gelÃƒÆ’Ã‚Â¶scht.", "success")
                    
        elif action == 'change_password':
            user_id = request.form.get('user_id')
            new_password = request.form.get('new_password')
            user = User.query.get(user_id)
            if user:
                user.set_password(new_password)
                user.must_change_password = True
                db.session.commit()
                flash(f"Passwort fÃƒÆ’Ã‚Â¼r {user.username} geÃƒÆ’Ã‚Â¤ndert.", "success")
                
        elif action == 'save_permissions':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user and user.role in ('moderator', 'user'):
                perms_list = [
                    'view_analytics', 'manage_users', 'use_live_moderation',
                    'manage_polls', 'edit_poll_config', 'manage_quizzes', 'edit_quiz_config',
                    'manage_events', 'edit_event_chat_id', 'manage_reports', 'edit_report_chat_id',
                    'manage_broadcasts', 'edit_broadcast_chat_id', 'view_id_finder_registry', 'edit_id_finder_registry'
                ]
                new_perms = {}
                for perm in perms_list:
                    new_perms[perm] = request.form.get(f'perm_{perm}') == 'on'
                user.permissions = new_perms
                db.session.commit()
                flash(f"Berechtigungen fÃƒÆ’Ã‚Â¼r {user.username} erfolgreich aktualisiert! ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦", "success")
                
        return redirect(url_for('dashboard.team_management'))
        
    from ..models import AuditLog, PasskeyCredential
    users = User.query.all()
    audit_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    passkeys = PasskeyCredential.query.all()
    user_passkey_counts = {}
    for p in passkeys:
        user_passkey_counts[p.user_id] = user_passkey_counts.get(p.user_id, 0) + 1
    return render_template('team_management.html', users=users, audit_logs=audit_logs, user_passkey_counts=user_passkey_counts)

@bp.route('/api/dashboard/save-layout', methods=['POST'])
@admin_required
def save_dashboard_layout():
    data = request.json
    s = BotSettings.query.filter_by(bot_name='dashboard_layout').first()
    if not s: s = BotSettings(bot_name='dashboard_layout', config_json=json.dumps(data)); db.session.add(s)
    else: s.config_json = json.dumps(data)
    db.session.commit()
    return jsonify({"success": True})

# --- AUTO RESPONDER ROUTE ---
@bp.route('/auto-responder')
@login_required
def auto_responder():
    rules = AutoReplyRule.query.order_by(AutoReplyRule.id.desc()).all()
    # Check if the auto_responder bot is toggled 'on' in the main settings
    s = BotSettings.query.filter_by(bot_name='auto_responder').first()
    is_running = False
    if s and s.config_json:
        try:
            cfg = json.loads(s.config_json)
            is_running = cfg.get('is_active', False)
        except:
            pass
    return render_template('auto_responder.html', rules=rules, is_running=is_running)

# --- INVITE BOT ROUTES ---
@bp.route('/bot-settings', methods=["GET", "POST"])
@admin_required
def bot_settings():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    if not s:
        cfg = {'is_enabled': False, 'bot_token': '', 'main_chat_id': '', 'topic_id': '', 'link_ttl_minutes': 15, 'start_message': 'Willkommen!', 'rules_message': 'Bitte beachte die Regeln.', 'blocked_message': 'Du bist gesperrt.', 'privacy_policy': 'Datenschutz...', 'form_fields': [], 'whitelist_enabled': False, 'whitelist_approval_chat_id': '', 'whitelist_approval_topic_id': '', 'whitelist_pending_message': 'Wird geprÃƒÆ’Ã‚Â¼ft.', 'whitelist_rejection_message': 'Abgelehnt.'}
        s = BotSettings(bot_name='invite', config_json=json.dumps(cfg)); db.session.add(s); db.session.commit()
    
    if request.method == 'POST':
        action = request.form.get('action')
        config = json.loads(s.config_json)
        if action == 'save_reminder_config':
            config.update({
                'incomplete_rem_days': request.form.get('incomplete_rem_days', 0, type=int),
                'incomplete_rem_hours': request.form.get('incomplete_rem_hours', 0, type=int),
                'incomplete_rem_minutes': request.form.get('incomplete_rem_minutes', 0, type=int),
                'incomplete_rem_max': request.form.get('incomplete_rem_max', 1, type=int),
                'incomplete_rem_message': request.form.get('incomplete_rem_message', ''),
                'incomplete_admin_message': request.form.get('incomplete_admin_message', '')
            })
            s.config_json = json.dumps(config)
            db.session.commit()
            flash('Erinnerungs-Einstellungen gespeichert.', 'success')
            return redirect(url_for('dashboard.bot_settings'))

        if action == 'save_base_config':
            old_enabled = config.get('is_enabled', False)
            new_enabled = 'is_enabled' in request.form
            config.update({
                'is_enabled': new_enabled, 
                'bot_token': request.form.get('bot_token', ''), 
                'main_chat_id': request.form.get('main_chat_id', ''), 
                'topic_id': request.form.get('topic_id', ''), 
                'link_ttl_minutes': request.form.get('link_ttl_minutes', 15, type=int), 
                'whitelist_enabled': 'whitelist_enabled' in request.form, 
                'whitelist_approval_chat_id': request.form.get('whitelist_approval_chat_id', ''), 
                'whitelist_approval_topic_id': request.form.get('whitelist_approval_topic_id', ''),
                'incomplete_rem_days': request.form.get('incomplete_rem_days', 0, type=int),
                'incomplete_rem_hours': request.form.get('incomplete_rem_hours', 0, type=int),
                'incomplete_rem_minutes': request.form.get('incomplete_rem_minutes', 0, type=int),
                'incomplete_rem_max': request.form.get('incomplete_rem_max', 1, type=int)
            })
            s.config_json = json.dumps(config)
            db.session.commit()
            
            # --- AUDIT LOG ---
            from ..utils import log_audit
            log_audit("Invite-Bot Konfiguration gespeichert", f"Status geÃƒÆ’Ã‚Â¤ndert von {old_enabled} zu {new_enabled}. Token & Gruppenkonfiguration aktualisiert.")
            
            flash('Gespeichert.', 'success')
        return redirect(url_for('dashboard.bot_settings'))

    logs = []
    if os.path.exists(INVITE_BOT_LOG_FILE):
        with open(INVITE_BOT_LOG_FILE, 'r') as f: logs = f.readlines()[-50:]
        
    user_logs = []
    profiles = []
    try:
        from ..models import InviteLog, InviteApplication, RSSFeedConfig
        db_logs = InviteLog.query.order_by(InviteLog.timestamp.desc()).all()
        for log in db_logs:
            user_logs.append(f"{log.timestamp.strftime('%d.%m.%Y %H:%M:%S')} - ID: {log.telegram_user_id} - @{log.username or 'NoUser'} - {log.action}")
            
        profiles = InviteApplication.query.order_by(InviteApplication.updated_at.desc()).all()
        rss_feeds = RSSFeedConfig.query.all()
    except Exception as e:
        rss_feeds = []
        pass
        
    return render_template("bot_settings.html", config=json.loads(s.config_json), is_invite_running=get_bot_status_simple()['invite']['running'], user_interaction_logs=user_logs, invite_bot_logs=logs, profiles=profiles, rss_feeds=rss_feeds)

@bp.route('/bot-settings/save-content', methods=['POST'])
@admin_required
def save_invite_content():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json)
    fields_to_update = [
        'start_message', 'rules_message', 'blocked_message', 'fc_blocked_message', 'privacy_policy', 
        'whitelist_pending_message', 'whitelist_rejection_message', 'profile_posted_message',
        'leave_pm_voluntary', 'leave_pm_kicked', 'welcome_pm_message',
        'fc_request_message', 'fc_received_message', 'fc_rejection_message'
    ]
    for k in fields_to_update:
        if k in request.form:
            cfg[k] = request.form.get(k, '')
    s.config_json = json.dumps(cfg, ensure_ascii=True)
    db.session.commit()
    flash('Texte gespeichert.', 'success')
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/add-field', methods=['POST'])
@login_required
def add_field():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json); fields = cfg.setdefault('form_fields', [])
    min_age = request.form.get('min_age')
    fid = request.form.get('field_id', 'field').strip().lower()
    if not fid: fid = "field"
    
    # Ensure ID is unique
    existing_ids = [f['id'] for f in cfg.get('form_fields', [])]
    base_id = fid
    counter = 1
    while fid in existing_ids:
        fid = f"{base_id}_{counter}"
        counter += 1

    cfg.setdefault('form_fields', []).append({
        'id': fid,
        'emoji': request.form.get('emoji', 'ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â¹'), 
        'display_name': request.form.get('display_name', 'Neues Feld'), 
        'label': request.form.get('label', ''), 
        'type': request.form.get('type', 'text'), 
        'required': 'required' in request.form, 
        'enabled': True,
        'is_internal': 'is_internal' in request.form,
        'min_age': int(min_age) if min_age and min_age.isdigit() else None,
        'min_age_error_msg': request.form.get('min_age_error_msg', '')
    })
    s.config_json = json.dumps(cfg, ensure_ascii=True); db.session.commit(); return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/edit-field', methods=['POST'])
@login_required
def edit_field():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json); fid = request.form.get('field_id')
    for f in cfg.get('form_fields', []):
        if f['id'] == fid:
            min_age = request.form.get('min_age')
            f.update({
                'emoji': request.form.get('emoji'), 
                'display_name': request.form.get('display_name'), 
                'label': request.form.get('label'), 
                'type': request.form.get('type'), 
                'required': 'required' in request.form, 
                'enabled': 'enabled' in request.form,
                'is_internal': 'is_internal' in request.form,
                'min_age': int(min_age) if min_age and min_age.isdigit() else None,
                'min_age_error_msg': request.form.get('min_age_error_msg', '')
            })
    s.config_json = json.dumps(cfg, ensure_ascii=True); db.session.commit(); return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/delete-field', methods=['POST'])
@login_required
def delete_field():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json)
    fid = request.form.get('field_id')
    # Use a more robust check: delete the first one that matches to handle existing duplicates
    fields = cfg.get('form_fields', [])
    for i, f in enumerate(fields):
        if f['id'] == fid:
            fields.pop(i)
            break
    s.config_json = json.dumps(cfg, ensure_ascii=True)
    db.session.commit()
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/move-field/<string:field_id>/<string:direction>', methods=['POST'])
@login_required
def invite_bot_move_field(field_id, direction):
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json); fs = cfg.get('form_fields', [])
    idx = next((i for i, f in enumerate(fs) if f['id'] == field_id), -1)
    if idx != -1:
        if direction == 'up' and idx > 0: fs[idx], fs[idx-1] = fs[idx-1], fs[idx]
        elif direction == 'down' and idx < len(fs)-1: fs[idx], fs[idx+1] = fs[idx+1], fs[idx]
    s.config_json = json.dumps(cfg); db.session.commit(); return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/reorder-fields', methods=['POST'])
@login_required
def invite_bot_reorder_fields():
    data = request.get_json()
    if not data or 'field_ids' not in data:
        return jsonify({"success": False, "error": "Invalid data"}), 400
    
    s = BotSettings.query.filter_by(bot_name='invite').first()
    if not s: return jsonify({"success": False, "error": "Settings not found"}), 404
    
    cfg = json.loads(s.config_json); fs = cfg.get('form_fields', [])
    existing_fields = {f.get('id'): f for f in fs}
    
    new_fields = []
    for fid in data['field_ids']:
        if fid in existing_fields:
            new_fields.append(existing_fields[fid])
            
    # Keep missing fields
    new_ids = set(data['field_ids'])
    for fid, f in existing_fields.items():
        if fid not in new_ids:
            new_fields.append(f)
            
    cfg['form_fields'] = new_fields
    s.config_json = json.dumps(cfg)
    db.session.commit()
    return jsonify({"success": True})

@bp.route('/bot-settings/add-command', methods=['POST'])
@login_required
def add_custom_command():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json)
    commands = cfg.setdefault('custom_commands', {})
    
    cmd = request.form.get('command_name', '').strip().lower().replace('/', '')
    resp = request.form.get('response_text', '').strip()
    
    if cmd and resp:
        commands[cmd] = resp
        s.config_json = json.dumps(cfg)
        db.session.commit()
        flash(f'Befehl /{cmd} hinzugefÃƒÆ’Ã‚Â¼gt.', 'success')
    else:
        flash('Befehl und Antwort sind erforderlich.', 'danger')
        
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/delete-command', methods=['POST'])
@login_required
def delete_custom_command():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json)
    commands = cfg.get('custom_commands', {})
    
    cmd = request.form.get('command_name')
    if cmd in commands:
        del commands[cmd]
        s.config_json = json.dumps(cfg)
        db.session.commit()
        flash(f'Befehl /{cmd} gelÃƒÆ’Ã‚Â¶scht.', 'info')
        
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/save-puppy-config', methods=['POST'])
@login_required
def save_puppy_config():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json)
    
    cfg['puppy_config'] = {
        'enabled': 'enabled' in request.form,
        'label': request.form.get('label', '').strip(),
        'min_age': int(request.form.get('min_age', 1)),
        'required': 'required' in request.form,
        'error_msg': request.form.get('error_msg', '').strip()
    }
    
    s.config_json = json.dumps(cfg)
    db.session.commit()
    flash('Puppy-Alter Einstellungen gespeichert.', 'success')
    return redirect(url_for('dashboard.bot_settings', _anchor='puppy-panel'))

@bp.route('/bot-settings/clear-logs/user', methods=['POST'])
@admin_required
def clear_user_logs():
    from ..models import InviteLog
    try:
        InviteLog.query.delete()
        db.session.commit()
    except:
        db.session.rollback()
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/clear-logs/system', methods=['POST'])
@admin_required
def clear_system_logs():
    if not safe_clear_log(INVITE_BOT_LOG_FILE):
        flash('System-Logs konnten nicht gelÃƒÆ’Ã‚Â¶scht werden (File In Use).', 'warning')
    else:
        flash('System-Logs erfolgreich gelÃƒÆ’Ã‚Â¶scht.', 'success')
    return redirect(url_for('dashboard.bot_settings'))

# --- BROADCAST ROUTES ---
@bp.route('/broadcast_manager')
@permission_required('manage_broadcasts')
def broadcast_manager():
    ts = TopicMapping.query.all(); bs = Broadcast.query.order_by(Broadcast.created_at.desc()).all()
    return render_template('broadcast_manager.html', known_topics={str(t.topic_id): t.topic_name for t in ts}, broadcasts=bs, now=datetime.utcnow())

@bp.route('/broadcast_manager/save', methods=['POST'])
@permission_required('manage_broadcasts')
def save_broadcast():
    action = request.form.get('action', 'send_now')
    fdir = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    os.makedirs(fdir, exist_ok=True)

    # Handle multiple file uploads
    uploaded = request.files.getlist('media')
    saved_paths = []
    first_mtype = None
    for m in uploaded:
        if m and m.filename:
            fname = secure_filename(m.filename)
            m.save(os.path.join(fdir, fname))
            rel = f'uploads/{fname}'
            saved_paths.append(rel)
            if first_mtype is None:
                first_mtype = 'image' if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')) else 'video'

    # Determine send time
    if action == 'schedule':
        raw_dt = request.form.get('scheduled_at')
        try:
            scheduled_at = datetime.strptime(raw_dt, '%Y-%m-%dT%H:%M') if raw_dt else datetime.utcnow()
        except ValueError:
            scheduled_at = datetime.utcnow()
    else:
        scheduled_at = datetime.utcnow()

    # Single-file: media_path; multi-file: media_files as JSON list
    mpath = saved_paths[0] if len(saved_paths) == 1 else None
    mtype = first_mtype if len(saved_paths) == 1 else None
    mfiles_json = json.dumps(saved_paths) if len(saved_paths) > 1 else None

    b = Broadcast(
        text=request.form.get('text'),
        topic_id=request.form.get('topic_id') or None,
        send_mode=request.form.get('send_mode', 'standard'),
        scheduled_at=scheduled_at,
        status='pending',
        media_path=mpath,
        media_type=mtype,
        media_files=mfiles_json,
        spoiler='spoiler' in request.form,
        pin_message='pin_message' in request.form,
        silent_send='silent_send' in request.form,
    )
    db.session.add(b)
    db.session.commit()

    if action == 'send_now':
        flash('Nachricht in die Warteschlange eingestellt. Wird in Kuerze gesendet.', 'success')
    else:
        flash(f'Nachricht geplant fuer {scheduled_at.strftime("%d.%m.%Y %H:%M")} UTC.', 'success')

    return redirect(url_for('dashboard.broadcast_manager'))

@bp.route('/api/upload-media', methods=['POST'])
@login_required
def api_upload_media():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No file selected"}), 400
        
    fdir = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    os.makedirs(fdir, exist_ok=True)
    
    import time
    fname = secure_filename(file.filename)
    fname = f"{int(time.time())}_{fname}"
    file_path = os.path.join(fdir, fname)
    
    try:
        file.save(file_path)
        media_type = 'video' if fname.lower().endswith(('.mp4', '.mov', '.avi')) else 'photo'
        media_url = f"{request.host_url}static/uploads/{fname}"
        return jsonify({
            "success": True, 
            "url": media_url,
            "type": media_type
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/broadcast_manager/topic/save', methods=['POST'])
@permission_required('edit_broadcast_chat_id')
def save_topic_mapping():
    tid, tname = request.form.get('topic_id'), request.form.get('topic_name')
    m = TopicMapping.query.filter_by(topic_id=tid).first()
    if m: m.topic_name = tname
    else: db.session.add(TopicMapping(topic_id=tid, topic_name=tname))
    db.session.commit(); return redirect(url_for('dashboard.broadcast_manager'))

@bp.route('/broadcast_manager/topic/delete/<topic_id>', methods=['POST'])
@permission_required('edit_broadcast_chat_id')
def delete_topic_mapping(topic_id):
    m = TopicMapping.query.filter_by(topic_id=topic_id).first()
    if m: db.session.delete(m); db.session.commit()
    return redirect(url_for('dashboard.broadcast_manager'))

@bp.route('/broadcast_manager/delete/<int:broadcast_id>', methods=['POST'])
@permission_required('manage_broadcasts')
def delete_broadcast(broadcast_id):
    b = Broadcast.query.get(broadcast_id)
    if b: db.session.delete(b); db.session.commit()
    return redirect(url_for('dashboard.broadcast_manager'))

# --- OTHER BOT ROUTES ---
@bp.route('/live-moderation')
@permission_required('use_live_moderation')
def live_moderation(): return render_template('live_moderation.html')

@bp.route('/quiz-settings', methods=['GET', 'POST'])
@permission_required('manage_quizzes')
def quiz_settings():
    s = BotSettings.query.filter_by(bot_name='quiz').first()
    if not s:
        cfg = {"bot_token": "", "channel_id": "", "topic_id": "", "schedule": {"enabled": False, "time": "12:00", "days": []}}
        s = BotSettings(bot_name='quiz', config_json=json.dumps(cfg))
        db.session.add(s); db.session.commit()
    
    cfg = json.loads(s.config_json)
    
    if request.method == 'POST':
        action = request.form.get('action')
        from ..utils import log_audit
        if action == 'save_settings':
            if not current_user.has_permission('edit_quiz_config'):
                flash("Zugriff verweigert. Du darfst die Quiz-Verbindung nicht ÃƒÆ’Ã‚Â¤ndern.", "danger")
                return redirect(url_for('dashboard.quiz_settings'))
            cfg['channel_id'] = request.form.get('channel_id')
            cfg['topic_id'] = request.form.get('topic_id')
            log_audit("Quiz-Bot Einstellungen", f"Kanal-ID: {cfg['channel_id']}, Topic-ID: {cfg['topic_id']}")
        elif action == 'save_schedule':
            cfg['schedule'] = {
                'enabled': 'schedule_enabled' in request.form,
                'time': request.form.get('schedule_time', '12:00'),
                'days': [int(d) for d in request.form.getlist('schedule_days')]
            }
            log_audit("Quiz-Bot Zeitplan", f"Aktiviert: {cfg['schedule']['enabled']}, Uhrzeit: {cfg['schedule']['time']}, Tage: {cfg['schedule']['days']}")
        elif action == 'save_questions':
            q_json = request.form.get('questions_json')
            try:
                data = json.loads(q_json)
                q_path = os.path.join(PROJECT_ROOT, "data", "quizfragen.json")
                os.makedirs(os.path.dirname(q_path), exist_ok=True)
                with open(q_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                log_audit("Quizfragen gespeichert", f"{len(data)} Quizfragen in der Liste gespeichert")
                flash('Fragen gespeichert.', 'success')
            except Exception as e:
                flash(f'Fehler beim Speichern der Fragen: {e}', 'danger')
        elif action == 'save_asked_questions':
            aq_json = request.form.get('asked_questions_json')
            try:
                data = json.loads(aq_json)
                aq_path = os.path.join(PROJECT_ROOT, "instance", "quizfragen_gestellt.json")
                os.makedirs(os.path.dirname(aq_path), exist_ok=True)
                with open(aq_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                log_audit("Gestellte Quizfragen gespeichert", f"{len(data)} gestellte Quizfragen gespeichert")
                flash('Protokoll gespeichert.', 'success')
            except Exception as e:
                flash(f'Fehler beim Speichern des Protokolls: {e}', 'danger')
        
        s.config_json = json.dumps(cfg)
        db.session.commit()
        if action in ['save_settings', 'save_schedule']: flash('Einstellungen gespeichert.', 'success')
        return redirect(url_for('dashboard.quiz_settings'))

    # Load Data for Template
    q_path = os.path.join(PROJECT_ROOT, "data", "quizfragen.json")
    aq_path = os.path.join(PROJECT_ROOT, "instance", "quizfragen_gestellt.json")
    
    questions = []
    if os.path.exists(q_path):
        try:
            with open(q_path, 'r', encoding='utf-8') as f: questions = json.load(f)
        except: pass
        
    asked_questions = []
    if os.path.exists(aq_path):
        try:
            with open(aq_path, 'r', encoding='utf-8') as f: asked_questions = json.load(f)
        except: pass

    logs = []
    if os.path.exists(QUIZ_BOT_LOG_FILE):
        try:
            with open(QUIZ_BOT_LOG_FILE, 'r', encoding='utf-8') as f: logs = f.readlines()[-50:]
        except: pass

    stats = {
        'total': len(questions),
        'asked': len(asked_questions),
        'remaining': max(0, len(questions) - len(asked_questions))
    }

    return render_template('quiz_settings.html', 
                          schedule=cfg.get('schedule', {}), 
                          stats=stats, 
                          config=cfg, 
                          questions_json=json.dumps(questions, indent=2, ensure_ascii=False), 
                          asked_questions_json=json.dumps(asked_questions, indent=2, ensure_ascii=False), 
                          logs=logs)

@bp.route('/quiz/send-random', methods=['POST'])
@login_required
def quiz_send_random():
    try:
        tfile = os.path.abspath(os.path.join(PROJECT_ROOT, "bots", "quiz_bot", "send_now.tmp"))
        os.makedirs(os.path.dirname(tfile), exist_ok=True)
        with open(tfile, 'w') as f: f.write('1')
        
        # Verbose Log to file
        trigger_log = os.path.join(PROJECT_ROOT, "logs", "trigger.log")
        with open(trigger_log, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] Quiz Trigger written to: {tfile}\n")
            
        # Audit Log
        from ..utils import log_audit
        details = f"Quiz-Trigger geschrieben nach: {tfile}"
        log_audit("Manuelles Quiz gesendet", details)
        
        flash('Trigger an Quiz-Bot gesendet. Die Nachricht sollte in ca. 10 Sekunden erscheinen.', 'success')
    except Exception as e:
        flash(f'Fehler beim Sende-Trigger: {e}', 'danger')
        print(f"Error in quiz_send_random: {e}")
        
    return redirect(url_for('dashboard.quiz_settings'))

@bp.route('/umfrage-settings', methods=['GET', 'POST'])
@permission_required('manage_polls')
def umfrage_settings():
    s = BotSettings.query.filter_by(bot_name='umfrage').first()
    if not s:
        cfg = {"bot_token": "", "channel_id": "", "topic_id": "", "schedule": {"enabled": False, "time": "12:00", "days": []}}
        s = BotSettings(bot_name='umfrage', config_json=json.dumps(cfg))
        db.session.add(s); db.session.commit()
    
    cfg = json.loads(s.config_json)
    
    if request.method == 'POST':
        action = request.form.get('action')
        from ..utils import log_audit
        if action == 'save_settings':
            if not current_user.has_permission('edit_poll_config'):
                flash("Zugriff verweigert. Du darfst die Umfrage-Verbindung nicht ÃƒÆ’Ã‚Â¤ndern.", "danger")
                return redirect(url_for('dashboard.umfrage_settings'))
            cfg['channel_id'] = request.form.get('channel_id')
            cfg['topic_id'] = request.form.get('topic_id')
            log_audit("Umfrage-Bot Einstellungen", f"Kanal-ID: {cfg['channel_id']}, Topic-ID: {cfg['topic_id']}")
        elif action == 'save_schedule':
            cfg['schedule'] = {
                'enabled': 'schedule_enabled' in request.form,
                'time': request.form.get('schedule_time', '12:00'),
                'days': [int(d) for d in request.form.getlist('schedule_days')]
            }
            log_audit("Umfrage-Bot Zeitplan", f"Aktiviert: {cfg['schedule']['enabled']}, Uhrzeit: {cfg['schedule']['time']}, Tage: {cfg['schedule']['days']}")
        elif action == 'save_polls':
            p_json = request.form.get('polls_json')
            try:
                data = json.loads(p_json)
                p_path = os.path.join(PROJECT_ROOT, "data", "umfragen.json")
                os.makedirs(os.path.dirname(p_path), exist_ok=True)
                with open(p_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                log_audit("Umfragen gespeichert", f"{len(data)} Umfragen in der Liste gespeichert")
                flash('Umfragen gespeichert.', 'success')
            except Exception as e:
                flash(f'Fehler beim Speichern der Umfragen: {e}', 'danger')
        elif action == 'save_asked_polls':
            up_json = request.form.get('asked_polls_json')
            try:
                data = json.loads(up_json)
                up_path = os.path.join(PROJECT_ROOT, "instance", "umfragen_gestellt.json")
                os.makedirs(os.path.dirname(up_path), exist_ok=True)
                with open(up_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                log_audit("Gestellte Umfragen gespeichert", f"{len(data)} gestellte Umfragen im Protokoll gespeichert")
                flash('Gestellte-Umfragen-Protokoll gespeichert.', 'success')
            except Exception as e:
                flash(f'Fehler beim Speichern des Protokolls: {e}', 'danger')

        s.config_json = json.dumps(cfg)
        db.session.commit()
        if action in ['save_settings', 'save_schedule']: flash('Einstellungen gespeichert.', 'success')
        return redirect(url_for('dashboard.umfrage_settings'))

    # Load Data
    p_path = os.path.join(PROJECT_ROOT, "data", "umfragen.json")
    up_path = os.path.join(PROJECT_ROOT, "instance", "umfragen_gestellt.json")
    
    polls = []
    if os.path.exists(p_path):
        try:
            with open(p_path, 'r', encoding='utf-8') as f: polls = json.load(f)
        except: pass
        
    used_polls = []
    if os.path.exists(up_path):
        try:
            with open(up_path, 'r', encoding='utf-8') as f: used_polls = json.load(f)
        except: pass

    logs = []
    if os.path.exists(UMFRAGE_BOT_LOG_FILE):
        try:
            with open(UMFRAGE_BOT_LOG_FILE, 'r', encoding='utf-8') as f: logs = f.readlines()[-50:]
        except: pass

    stats = {
        'total': len(polls),
        'asked': len(used_polls),
        'remaining': max(0, len(polls) - len(used_polls))
    }

    return render_template('umfrage_settings.html', 
                          config=cfg, 
                          schedule=cfg.get('schedule', {}), 
                          stats=stats, 
                          logs=logs,
                          polls_json=json.dumps(polls, indent=2, ensure_ascii=False),
                          asked_polls_json=json.dumps(used_polls, indent=2, ensure_ascii=False))

@bp.route('/umfrage/send-now', methods=['POST'])
@login_required
def umfrage_send_now():
    try:
        tfile = os.path.abspath(os.path.join(PROJECT_ROOT, "bots", "umfrage_bot", "send_now.tmp"))
        os.makedirs(os.path.dirname(tfile), exist_ok=True)
        with open(tfile, 'w') as f: f.write('1')
        
        # Verbose Log to file
        trigger_log = os.path.join(PROJECT_ROOT, "logs", "trigger.log")
        with open(trigger_log, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] Umfrage Trigger written to: {tfile}\n")
            
        # Audit Log
        from ..utils import log_audit
        details = f"Umfrage-Trigger geschrieben nach: {tfile}"
        log_audit("Manuelle Umfrage gesendet", details)
        
        flash('Trigger an Umfrage-Bot gesendet.', 'success')
    except Exception as e:
        flash(f'Fehler beim Sende-Trigger: {e}', 'danger')
        print(f"Error in umfrage_send_now: {e}")
        
    return redirect(url_for('dashboard.umfrage_settings'))


@bp.route('/outfit-bot', methods=['GET', 'POST'])
@admin_required
def outfit_bot_dashboard():
    s = BotSettings.query.filter_by(bot_name='outfit').first()
    if not s:
        cfg = {
            "CHAT_ID": "", "TOPIC_ID": "", "POST_TIME": "18:00", "WINNER_TIME": "22:00",
            "AUTO_POST_ENABLED": True, "ADMIN_USER_IDS": [], "DUEL_MODE": False,
            "DUEL_TYPE": "tie_breaker", "DUEL_DURATION_MINUTES": 60, "BOT_TOKEN": ""
        }
        s = BotSettings(bot_name='outfit', config_json=json.dumps(cfg))
        db.session.add(s); db.session.commit()
    
    cfg = json.loads(s.config_json)
    
    logs = []
    if os.path.exists(OUTFIT_BOT_LOG_FILE):
        try:
            with open(OUTFIT_BOT_LOG_FILE, 'r', encoding='utf-8') as f: logs = f.readlines()[-50:]
        except: pass
        
    # Load Duel Status from data file
    data_path = os.path.join(PROJECT_ROOT, "instance", "outfit_bot_data.json")
    duel_status = {'active': False}
    if os.path.exists(data_path):
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('contest_active'):
                    duel_status = {'active': True, 'contestants': f"{len(data.get('submissions', {}))} Teilnehmer"}
        except: pass

    return render_template('outfit_bot_dashboard.html', 
                          config=cfg, 
                          is_running=get_bot_status_simple()['outfit']['running'], 
                          logs=logs, 
                          duel_status=duel_status)

@bp.route('/outfit-bot/actions/<action>', methods=['POST'])
@login_required
def outfit_bot_actions(action):
    s = BotSettings.query.filter_by(bot_name='outfit').first()
    if not s:
        cfg = {"BOT_TOKEN": "", "CHAT_ID": "", "TOPIC_ID": "", "AUTO_POST_ENABLED": False}
        s = BotSettings(bot_name='outfit', config_json=json.dumps(cfg))
        db.session.add(s); db.session.commit()
    
    cfg = json.loads(s.config_json)
    
    if action == 'save_config':
        cfg.update({
            # 'BOT_TOKEN': request.form.get('BOT_TOKEN'),
            'CHAT_ID': request.form.get('CHAT_ID'),
            'TOPIC_ID': request.form.get('TOPIC_ID'),
            'AUTO_POST_ENABLED': 'AUTO_POST_ENABLED' in request.form,
            'POST_TIME': request.form.get('POST_TIME', '18:00'),
            'WINNER_TIME': request.form.get('WINNER_TIME', '22:00'),
            'DUEL_MODE': 'DUEL_MODE' in request.form,
            'DUEL_TYPE': request.form.get('DUEL_TYPE', 'tie_breaker'),
            'DUEL_DURATION_MINUTES': int(request.form.get('DUEL_DURATION_MINUTES', 60)),
            'ADMIN_USER_IDS': [uid.strip() for uid in request.form.get('ADMIN_USER_IDS', '').split(',') if uid.strip()]
        })
        s.config_json = json.dumps(cfg)
        db.session.commit()
        flash('Outfit-Konfiguration gespeichert.', 'success')
    
    elif action == 'start_contest':
        tfile = os.path.join(PROJECT_ROOT, "bots", "outfit_bot", "start_contest.tmp")
        # Ensure the bot can notice this file. We should probably use a standard trigger file name or mechanism.
        # Based on outfit_bot.py, it doesn't have a trigger file mechanism yet, only schedule.
        # Let's add it to outfit_bot.py or just use a message file system.
        with open(tfile, 'w') as f: f.write('1')
        flash('Befehl zum Starten des Wettbewerbs gesendet.', 'info')
    
    elif action == 'announce_winner':
        tfile = os.path.join(PROJECT_ROOT, "bots", "outfit_bot", "announce_winner.tmp")
        with open(tfile, 'w') as f: f.write('1')
        flash('Befehl zum Auslosen des Gewinners gesendet.', 'info')
        
    elif action == 'clear_logs':
        if not safe_clear_log(OUTFIT_BOT_LOG_FILE):
            flash('Logs konnten nicht gelÃƒÆ’Ã‚Â¶scht werden (File In Use).', 'warning')
        else:
            flash('Logs gelÃƒÆ’Ã‚Â¶scht.', 'success')
        
    return redirect(url_for('dashboard.outfit_bot_dashboard'))

@bp.route('/critical-errors')
@admin_required
def critical_errors():
    logs = []
    lpath = os.path.join(PROJECT_ROOT, "logs", "critical_errors.log")
    if os.path.exists(lpath):
        with open(lpath, 'r', encoding='utf-8', errors='replace') as f: 
            logs = f.readlines()
    logs.reverse()  # Neueste zuerst
    return render_template("critical_errors.html", critical_logs=logs)

@bp.route('/api/logs/<bot_name>')
@login_required
def get_bot_logs(bot_name):
    # Mapping von Bot-ID zu Log-Datei
    log_map = {
        'main': 'main_bot.log',
        'id_finder': 'id_finder_bot.log',
        'invite': 'invite_bot.log',
        'tiktok': 'tiktok_bot.log',
        'quiz': 'quiz_bot.log',
        'umfrage': 'umfrage_bot.log',
        'outfit': 'outfit_bot.log',
        'report': 'report_bot.log',
        'event': 'event_bot.log',
        'birthday': 'birthday_bot.log',
        'cleanup': 'cleanup_bot.log'
    }
    
    filename = log_map.get(bot_name)
    if not filename:
        return jsonify({"error": "Unbekannter Bot-Typ"}), 400
        
    lpath = os.path.join(PROJECT_ROOT, "logs", filename)
    
    # Fallback to main_bot.log if specific log file doesn't exist
    if not os.path.exists(lpath):
        main_log_path = os.path.join(PROJECT_ROOT, "logs", "main_bot.log")
        if os.path.exists(main_log_path):
            try:
                keyword = f"bots.{bot_name}_bot" if bot_name != 'main' else "main_bot"
                keyword_alt = f"{bot_name}_bot"
                
                filtered_lines = []
                with open(main_log_path, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if keyword in line or keyword_alt in line:
                            filtered_lines.append(line.strip())
                
                if filtered_lines:
                    return jsonify({"lines": filtered_lines[-50:]})
                else:
                    return jsonify({"lines": [f"Keine spezifischen Log-EintrÃƒÆ’Ã‚Â¤ge fÃƒÆ’Ã‚Â¼r '{bot_name}' in den System-Logs gefunden."]})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        return jsonify({"lines": ["Keine Log-Datei gefunden (Bot vielleicht noch nie gestartet?)."]})
        
    try:
        # Lese die letzten 50 Zeilen
        with open(lpath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            last_lines = lines[-50:] if len(lines) > 50 else lines
            return jsonify({"lines": [l.strip() for l in last_lines]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/critical-errors/clear', methods=['POST'])
@login_required
def clear_critical_errors():
    lpath = os.path.join(PROJECT_ROOT, "logs", "critical_errors.log")
    if safe_clear_log(lpath):
        flash('Fehlerprotokolle erfolgreich gelÃƒÆ’Ã‚Â¶scht.', 'info')
    else:
        flash('Fehlerprotokolle konnten nicht gelÃƒÆ’Ã‚Â¶scht werden.', 'warning')
    return redirect(url_for('dashboard.critical_errors'))

@bp.route('/critical-errors/test', methods=['POST'])
@login_required
def trigger_test_error():
    import logging
    logger = logging.getLogger('web_dashboard.test')
    logger.error("ÃƒÂ°Ã…Â¸Ã…Â¡Ã‚Â¨ TEST-FEHLER: Dies ist eine manuelle Test-Fehlermeldung, um die Anzeige zu prÃƒÆ’Ã‚Â¼fen.")
    flash('Ein kritischer Test-Fehler wurde im System registriert. Das Banner sollte nun erscheinen.', 'info')
    return redirect(url_for('dashboard.critical_errors'))

@bp.route('/id-finder')
@permission_required('view_id_finder_registry')
def id_finder_dashboard():
    s = BotSettings.query.filter_by(bot_name='id_finder').first()
    if not s:
        cfg = {'bot_token': '', 'admin_group_id': 0, 'main_group_id': 0}
        s = BotSettings(bot_name='id_finder', config_json=json.dumps(cfg))
        db.session.add(s)
        db.session.commit()
    
    cfg = json.loads(s.config_json)
    us = IDFinderUser.query.order_by(IDFinderUser.last_contact.desc()).all()
    return render_template('id_finder_dashboard.html', config=cfg, user_registry=us, is_running=get_bot_status_simple()['id_finder']['running'], logs=[])

@bp.route('/id-finder/save-config', methods=['POST'])
@admin_required
def id_finder_save_config():
    s = BotSettings.query.filter_by(bot_name='id_finder').first()
    cfg = json.loads(s.config_json)
    admin_group_id = request.form.get('admin_group_id', '').strip().replace('--', '-')
    main_group_id = request.form.get('main_group_id', '').strip().replace('--', '-')
    admin_log_topic_id = request.form.get('admin_log_topic_id', '').strip().replace('--', '-')
    cfg.update({
        'bot_token': request.form.get('bot_token', '').strip(),
        'admin_group_id': int(admin_group_id) if admin_group_id else 0,
        'main_group_id': int(main_group_id) if main_group_id else 0,
        'admin_log_topic_id': int(admin_log_topic_id) if admin_log_topic_id else 0,
        'delete_commands': 'delete_commands' in request.form,
        'bot_message_cleanup_seconds': int(request.form.get('bot_message_cleanup_seconds') or 0),
        'message_logging_enabled': 'message_logging_enabled' in request.form,
        'message_logging_ignore_commands': 'message_logging_ignore_commands' in request.form,
        'message_logging_groups_only': 'message_logging_groups_only' in request.form,
        'max_warnings': int(request.form.get('max_warnings') or 3),
        'punishment_type': request.form.get('punishment_type', 'none'),
        'mute_duration': int(request.form.get('mute_duration') or 24),
        'cleanup_notification_seconds': int(request.form.get('cleanup_notification_seconds') or 60),
        'warning_bot_name': request.form.get('warning_bot_name', 'id_finder')
    })
    s.config_json = json.dumps(cfg)
    db.session.commit()
    
    # Audit Log
    from ..utils import log_audit
    log_audit("Master-Konfiguration geÃƒÆ’Ã‚Â¤ndert", f"Gruppe Admin: {cfg['admin_group_id']}, Gruppe Haupt: {cfg['main_group_id']}. Token & Haupteinstellungen wurden aktualisiert.")
    
    flash('Einstellungen gespeichert.', 'success')
    return redirect(url_for('dashboard.id_finder_dashboard'))

@bp.route('/id-finder/user/<int:user_id>')
@permission_required('view_id_finder_registry')
def id_finder_user_detail(user_id):
    u = IDFinderUser.query.filter_by(telegram_id=user_id).first_or_404()
    ms = IDFinderMessage.query.filter_by(telegram_user_id=user_id).order_by(IDFinderMessage.timestamp.desc()).limit(100).all()
    
    topic_ids = list(set([m.message_thread_id for m in ms if m.message_thread_id]))
    topic_map = {}
    if topic_ids:
        mappings = TopicMapping.query.filter(TopicMapping.topic_id.in_(topic_ids)).all()
        topic_map = {m.topic_id: m.topic_name for m in mappings}
        
    return render_template('id_finder_user_detail.html', user=u, messages=ms, topic_map=topic_map)

@bp.route('/id-finder/user/<int:user_id>/toggle-pause', methods=['POST'])
@permission_required('edit_id_finder_registry')
def id_finder_toggle_pause(user_id):
    u = IDFinderUser.query.filter_by(telegram_id=user_id).first_or_404()
    u.is_steckbrief_paused = not u.is_steckbrief_paused
    if u.is_steckbrief_paused:
        u.steckbrief_paused_at = datetime.utcnow()
    else:
        u.steckbrief_paused_at = None
    db.session.commit()
    
    # Audit Log
    from ..utils import log_audit
    status_str = "pausiert" if u.is_steckbrief_paused else "fortgesetzt"
    log_audit("Steckbrief-Prozess geÃƒÆ’Ã‚Â¤ndert", f"Prozess fÃƒÆ’Ã‚Â¼r {u.first_name or u.telegram_id} ({user_id}) {status_str}.")
    
    flash(f'Steckbrief-Prozess fÃƒÆ’Ã‚Â¼r {u.first_name or u.telegram_id} {"pausiert" if u.is_steckbrief_paused else "fortgesetzt"}.', 'success')
    return redirect(url_for('dashboard.id_finder_user_detail', user_id=user_id))

@bp.route('/id-finder/delete-user/<int:user_id>', methods=['POST'])
@permission_required('edit_id_finder_registry')
def id_finder_delete_user(user_id):
    u = IDFinderUser.query.filter_by(telegram_id=user_id).first()
    if u:
        name = u.first_name or str(u.telegram_id)
        db.session.delete(u)
        db.session.commit()
        
        # Audit Log
        from ..utils import log_audit
        log_audit("Steckbrief-Benutzer gelÃƒÆ’Ã‚Â¶scht", f"Steckbrief-Benutzer '{name}' ({user_id}) gelÃƒÆ’Ã‚Â¶scht.")
    return redirect(url_for('dashboard.id_finder_dashboard'))

@bp.route('/id-finder/commands')
@permission_required('view_id_finder_registry')
def id_finder_commands(): return render_template('id_finder_commands.html')

@bp.route('/id-finder/admin-panel')
@admin_required
def id_finder_admin_panel():
    ads = IDFinderAdmin.query.all()
    admins_dict = {str(a.telegram_id): {'name': a.name, 'permissions': a.permissions} for a in ads}
    
    return render_template('id_finder_admin_panel.html', 
                          admins=admins_dict, 
                          available_permission_groups=AVAILABLE_PERMISSIONS, 
                          available_permissions={})

@bp.route('/id-finder/admin-panel/add', methods=['POST'])
@admin_required
def id_finder_add_admin():
    admin_id = request.form.get('admin_id')
    admin_name = request.form.get('admin_name')
    if admin_id and admin_name:
        existing = IDFinderAdmin.query.filter_by(telegram_id=int(admin_id)).first()
        if not existing:
            new_admin = IDFinderAdmin(telegram_id=int(admin_id), name=admin_name, permissions={})
            db.session.add(new_admin)
            db.session.commit()
            
            # Audit Log
            from ..utils import log_audit
            log_audit("Bot-Admin hinzugefÃƒÆ’Ã‚Â¼gt", f"Admin '{admin_name}' ({admin_id}) wurde hinzugefÃƒÆ’Ã‚Â¼gt.")
            
            flash('Admin erfolgreich hinzugefÃƒÆ’Ã‚Â¼gt.', 'success')
        else:
            flash('Admin existiert bereits.', 'warning')
    return redirect(url_for('dashboard.id_finder_admin_panel'))

@bp.route('/id-finder/admin-panel/delete', methods=['POST'])
@admin_required
def id_finder_delete_admin():
    admin_id = request.form.get('admin_id')
    if admin_id:
        admin = IDFinderAdmin.query.filter_by(telegram_id=int(admin_id)).first()
        if admin:
            name = admin.name or str(admin_id)
            db.session.delete(admin)
            db.session.commit()
            
            # Audit Log
            from ..utils import log_audit
            log_audit("Bot-Admin gelÃƒÆ’Ã‚Â¶scht", f"Admin '{name}' ({admin_id}) wurde gelÃƒÆ’Ã‚Â¶scht.")
            
            flash('Admin erfolgreich gelÃƒÆ’Ã‚Â¶scht.', 'success')
    return redirect(url_for('dashboard.id_finder_admin_panel'))

@bp.route('/id-finder/admin-panel/update-permissions', methods=['POST'])
@admin_required
def id_finder_update_admin_permissions():
    admin_id = request.form.get('admin_id')
    if admin_id:
        admin = IDFinderAdmin.query.filter_by(telegram_id=int(admin_id)).first()
        if admin:
            name = admin.name or str(admin_id)
            # All form fields except admin_id are considered permissions
            perms = {k: True for k in request.form.keys() if k != 'admin_id'}
            admin.permissions = perms
            db.session.commit()
            
            # Audit Log
            from ..utils import log_audit
            log_audit("Bot-Admin Rechte geÃƒÆ’Ã‚Â¤ndert", f"Rechte fÃƒÆ’Ã‚Â¼r Admin '{name}' ({admin_id}) wurden aktualisiert.")
            
            flash('Berechtigungen erfolgreich aktualisiert.', 'success')
    return redirect(url_for('dashboard.id_finder_admin_panel'))




@bp.route('/id-finder/analytics')
@permission_required('view_analytics')
def id_finder_analytics():
    import logging
    logger = logging.getLogger(__name__)
    logger.debug("--- [DEBUG] Entered new id_finder_analytics ---")
    try:
        from ..models import IDFinderMessage, IDFinderUser, IDFinderAdmin, InviteLog, TopicMapping, InviteApplication
        from sqlalchemy import or_

        PALETTE=['#4f8ef7','#a855f7','#ec4899','#22c55e','#f59e0b','#ef4444','#14b8a6','#8b5cf6','#f97316','#06b6d4']
        now = datetime.utcnow()

        # Ermittle das ÃƒÆ’Ã‚Â¤lteste Datum aus der DB fÃƒÆ’Ã‚Â¼r die Limits
        first_msg = IDFinderMessage.query.order_by(IDFinderMessage.timestamp.asc()).first()
        first_date_str = first_msg.timestamp.strftime('%Y-%m-%d') if first_msg and first_msg.timestamp else "2024-01-01"

        date_from_str = request.args.get('date_from')
        date_to_str = request.args.get('date_to')
        days = int(request.args.get('days') or 30)
        topic_ids_str = request.args.get('topic_ids') or ''

        if date_from_str:
            cutoff = datetime.strptime(date_from_str, '%Y-%m-%d')
            date_end = datetime.strptime(date_to_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59) if date_to_str else now
            days = max(1, (date_end - cutoff).days)
        else:
            cutoff = now - timedelta(days=days)
            date_end = now

        exclude_bots = (
            (IDFinderUser.is_bot == False) & 
            (IDFinderUser.telegram_id != 7520803994) &
            (IDFinderUser.username.is_(None) | ~IDFinderUser.username.ilike('%bot'))
        )

        base_query = db.session.query(IDFinderMessage).join(IDFinderUser, IDFinderMessage.telegram_user_id == IDFinderUser.telegram_id).filter(
            IDFinderMessage.timestamp >= cutoff,
            IDFinderMessage.timestamp <= date_end,
            exclude_bots
        )

        if topic_ids_str and topic_ids_str != 'all':
            topic_ids = [t.strip() for t in topic_ids_str.split(',') if t.strip()]
            conditions = []
            if 'main' in topic_ids:
                conditions.append((IDFinderMessage.message_thread_id.is_(None)) | (IDFinderMessage.message_thread_id == 0))
            if 'private' in topic_ids:
                conditions.append(IDFinderMessage.chat_id == IDFinderMessage.telegram_user_id)
            other_ids = [t for t in topic_ids if t not in ('main', 'private') and not t.startswith('dm_')]
            if other_ids:
                conditions.append(IDFinderMessage.message_thread_id.in_(other_ids))
            dm_ids = [t.replace('dm_', '') for t in topic_ids if t.startswith('dm_')]
            if dm_ids:
                conditions.append(IDFinderMessage.chat_id.in_(dm_ids))
            if conditions:
                base_query = base_query.filter(or_(*conditions))

        total_users = IDFinderUser.query.filter(exclude_bots).count()
        total_messages = base_query.count()
        total_media = base_query.filter(IDFinderMessage.content_type != 'text').count()
        
        active_users = base_query.with_entities(IDFinderMessage.telegram_user_id).distinct().count()

        leaderboard_raw = []
        if total_messages > 0:
            leaderboard_raw = base_query.with_entities(
                IDFinderUser.telegram_id,
                IDFinderUser.first_name,
                IDFinderUser.username,
                IDFinderUser.photo_url,
                IDFinderUser.created_at if hasattr(IDFinderUser, 'created_at') else getattr(IDFinderUser, 'first_contact', None),
                func.count(IDFinderMessage.id).label('msg_count'),
                func.sum(case((IDFinderMessage.content_type != 'text', 1), else_=0)).label('media_count')
            ).group_by(IDFinderUser.telegram_id, IDFinderUser.first_name,
                       IDFinderUser.username, IDFinderUser.photo_url,
                       IDFinderUser.created_at if hasattr(IDFinderUser, 'created_at') else getattr(IDFinderUser, 'first_contact', None)) \
             .order_by(text('msg_count DESC')).limit(100).all()

        admins = {str(a.telegram_id) for a in IDFinderAdmin.query.all()}
        leaderboard = []
        for i, row in enumerate(leaderboard_raw):
            c_date = row[4]
            leaderboard.append({
                "uid": str(row.telegram_id), "name": row.first_name or "Unbekannt", "username": f"@{row.username}" if row.username else "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â",
                "avatar_url": f"/api/avatar/{row.telegram_id}", "msgs": int(row.msg_count), "media": int(row.media_count or 0),
                "joined_at": c_date.strftime('%d.%m.%Y') if c_date and hasattr(c_date, 'strftime') else "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â",
                "rank": i + 1, "status": "admin" if str(row.telegram_id) in admins else "member",
            })

        if total_messages == 0 and total_users > 0:
            recent_users = IDFinderUser.query.filter(exclude_bots).order_by(IDFinderUser.last_contact.desc()).limit(10).all()
            for i, u in enumerate(recent_users):
                c_date = getattr(u, 'created_at', getattr(u, 'first_contact', None))
                leaderboard.append({
                    "uid": str(u.telegram_id), "name": u.first_name or "Unbekannt", "username": f"@{u.username}" if u.username else "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â",
                    "avatar_url": f"/api/avatar/{u.telegram_id}", "msgs": 0, "media": 0, "joined_at": c_date.strftime('%d.%m.%Y') if c_date and hasattr(c_date, 'strftime') else "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â",
                    "rank": i + 1, "status": "admin" if str(u.telegram_id) in admins else "member"
                })

        timeline_query = base_query.with_entities(func.date(IDFinderMessage.timestamp).label('date'), func.count(IDFinderMessage.id).label('count')).group_by('date').order_by('date').all()
        def fmt_dt(d):
            if not d: return ""
            try: return d.strftime('%d.%m') if hasattr(d, 'strftime') else d if isinstance(d, str) and '.' in d else f"{str(d).split('-')[2][:2]}.{str(d).split('-')[1]}"
            except: return str(d)

        date_map = {fmt_dt(row.date): row.count for row in timeline_query if row.date}
        timeline_labels, total_data = [], []
        if days <= 90:
            for i in range(days - 1, -1, -1):
                d = date_end - timedelta(days=i)
                d_str = d.strftime('%d.%m')
                timeline_labels.append(d_str)
                total_data.append(date_map.get(d_str, 0))
        else:
            for row in timeline_query:
                timeline_labels.append(fmt_dt(row.date))
                total_data.append(row.count)

        hours_query = base_query.with_entities(extract('hour', IDFinderMessage.timestamp).label('hour'), func.count(IDFinderMessage.id).label('count')).group_by('hour').all()
        busiest_hours = [0] * 24
        for row in hours_query:
            if row.hour is not None: busiest_hours[int(row.hour)] = int(row.count)

        engine_name = db.engine.dialect.name
        dow_expr = func.dayofweek(IDFinderMessage.timestamp) if engine_name == 'mysql' else extract('dow', IDFinderMessage.timestamp)
        dow_query = base_query.with_entities(dow_expr.label('dow'), func.count(IDFinderMessage.id).label('count')).group_by('dow').all()
        busiest_days = [0] * 7
        for row in dow_query:
            if row.dow is not None:
                py_dow = (int(row.dow) + 5) % 7 if engine_name == 'mysql' else (int(row.dow) + 6) % 7
                busiest_days[py_dow] = int(row.count)

        type_query = base_query.with_entities(IDFinderMessage.content_type, func.count(IDFinderMessage.id).label('count')).group_by(IDFinderMessage.content_type).all()
        msg_types_dict = {row.content_type: int(row.count) for row in type_query}
        msg_types = [{"type": k.capitalize() if k else "Unbekannt", "val": v, "color": PALETTE[i%10]} for i, (k,v) in enumerate(msg_types_dict.items())]

        heatmap_query = base_query.with_entities(dow_expr.label('dow'), extract('hour', IDFinderMessage.timestamp).label('hour'), func.count(IDFinderMessage.id).label('count')).group_by('dow', 'hour').all()
        heatmap_matrix = [[0] * 24 for _ in range(7)]
        for row in heatmap_query:
            if row.dow is not None and row.hour is not None:
                py_dow = (int(row.dow) + 5) % 7 if engine_name == 'mysql' else (int(row.dow) + 6) % 7
                heatmap_matrix[py_dow][int(row.hour)] = int(row.count)

        growth_query = db.session.query(
            func.date(InviteLog.timestamp).label('date'),
            func.sum(case(((InviteLog.action.ilike('%beigetreten%') | InviteLog.action.ilike('%beitritt%')) & ~InviteLog.action.ilike('%Musik%'), 1), else_=0)).label('joins'),
            func.sum(case(((InviteLog.action.ilike('%verlassen%') | InviteLog.action.ilike('%entfernt%') | InviteLog.action.ilike('%austritt%')) & ~InviteLog.action.ilike('%Musik%'), 1), else_=0)).label('leaves')
        ).filter(InviteLog.timestamp >= cutoff, InviteLog.timestamp <= date_end).group_by('date').order_by('date').all()

        growth_labels, growth_net = [], []
        g_joins = {fmt_dt(r.date): int(r.joins) for r in growth_query if r.date}
        g_leaves = {fmt_dt(r.date): int(r.leaves) for r in growth_query if r.date}
        if days <= 90:
            for i in range(days - 1, -1, -1):
                d = date_end - timedelta(days=i)
                d_str = d.strftime('%d.%m')
                growth_labels.append(d_str)
                growth_net.append(g_joins.get(d_str, 0) - g_leaves.get(d_str, 0))
        else:
            for row in growth_query:
                growth_labels.append(fmt_dt(row.date))
                growth_net.append(g_joins.get(fmt_dt(row.date), 0) - g_leaves.get(fmt_dt(row.date), 0))

        joins_leaves = InviteLog.query.filter(
            InviteLog.timestamp >= cutoff, InviteLog.timestamp <= date_end,
            (InviteLog.action.ilike('%beigetreten%') | InviteLog.action.ilike('%verlassen%') | InviteLog.action.ilike('%entfernt%') | InviteLog.action.ilike('%beitritt%') | InviteLog.action.ilike('%austritt%')),
            ~InviteLog.action.ilike('%Musik%')
        ).order_by(InviteLog.timestamp.desc()).all()
        
        events_list = []
        compressed_events = {}
        for e in joins_leaves:
            ts = e.timestamp.timestamp() if hasattr(e.timestamp, 'timestamp') else 0
            window = int(ts / 60)
            key = (e.telegram_user_id, window)
            if key not in compressed_events:
                compressed_events[key] = e
        
        sorted_compressed = sorted(compressed_events.values(), key=lambda x: x.timestamp, reverse=True)[:50]
        for e in sorted_compressed:
            u_info = IDFinderUser.query.filter_by(telegram_id=e.telegram_user_id).first()
            display_name = e.username or f"id{e.telegram_user_id}"
            if u_info:
                display_name = u_info.username or f"{u_info.first_name or ''} {u_info.last_name or ''}".strip() or display_name
            act = str(e.action).lower()
            is_join = any(x in act for x in ["beigetreten", "beitritt", "joined"])
            is_leave = any(x in act for x in ["verlassen", "austritt", "left", "kicked", "entfernt"])
            simple_action = "Beigetreten" if is_join else "Verlassen"
            if "kicked" in act or "entfernt" in act: simple_action = "Entfernt"
            event_type = "join" if is_join else "leave"
            events_list.append({
                "time": e.timestamp.strftime('%d.%m %H:%M') if hasattr(e.timestamp, 'strftime') else str(e.timestamp),
                "user": display_name, "uid": str(e.telegram_user_id), "type": event_type, "action": simple_action
            })

        # Steckbriefe
        raw_steckbriefe = InviteApplication.query.filter(InviteApplication.created_at >= cutoff, InviteApplication.created_at <= date_end).order_by(InviteApplication.created_at.desc()).all()
        steckbriefe = []
        s_stats = {'total': len(raw_steckbriefe), 'accepted': 0, 'rejected': 0, 'pending': 0}
        for s in raw_steckbriefe:
            if s.status == 'accepted': s_stats['accepted'] += 1
            elif s.status == 'rejected': s_stats['rejected'] += 1
            else: s_stats['pending'] += 1
            steckbriefe.append({
                'id': s.id, 'uid': s.telegram_user_id, 'name': s.full_name or s.username or f"User {s.telegram_user_id}",
                'username': f"@{s.username}" if s.username else "", 'status': s.status, 'date': s.created_at.strftime('%d.%m.%Y %H:%M'),
                'answers': s.answers
            })

        return render_template('id_finder_analytics.html',
            stats={'total_users': total_users, 'total_messages': total_messages, 'total_media': total_media, 'active_users': active_users, 'avg_per_day': round(total_messages / max(days, 1), 1)},
            activity={'timeline': {'labels': timeline_labels, 'total': total_data}, 'leaderboard': leaderboard, 'busiest_hours': busiest_hours, 'busiest_days': busiest_days, 'msg_types': msg_types, 'heatmap': heatmap_matrix, 'growth': {'labels': growth_labels, 'net': growth_net}, 'events': events_list},
            filter_days=days, date_from=date_from_str, date_to=date_to_str, first_date=first_date_str,
            topic_ids=topic_ids_str, steckbriefe=steckbriefe, steckbrief_stats=s_stats)
    except Exception as e:
        import traceback; sys.stderr.write(f"ERROR: {e}\n{traceback.format_exc()}\n")
        return f"Fehler: {e}", 500

@bp.route('/api/id-finder/user-detail/<int:uid>')
@permission_required('view_id_finder_registry')
def id_finder_user_detail_api(uid):
    try:
        from ..models import IDFinderUser, IDFinderMessage, TopicMapping, IDFinderAdmin, BotSettings
        user = IDFinderUser.query.filter_by(telegram_id=uid).first_or_404()
        total_msgs = IDFinderMessage.query.filter_by(telegram_user_id=uid).count()
        total_media = IDFinderMessage.query.filter(IDFinderMessage.telegram_user_id==uid, IDFinderMessage.content_type != 'text').count()
        active_days = db.session.query(func.count(func.distinct(func.date(IDFinderMessage.timestamp)))).filter_by(telegram_user_id=uid).scalar() or 0

        subq = db.session.query(IDFinderMessage.telegram_user_id, func.count(IDFinderMessage.id).label('cnt')).join(IDFinderUser, IDFinderMessage.telegram_user_id == IDFinderUser.telegram_id).filter(
            IDFinderUser.is_bot == False,
            IDFinderUser.telegram_id != 7520803994,
            (IDFinderUser.username.is_(None) | ~IDFinderUser.username.ilike('%bot'))
        ).group_by(IDFinderMessage.telegram_user_id).subquery()
        rank_result = db.session.query(func.count()).filter(subq.c.cnt > db.session.query(subq.c.cnt).filter(subq.c.telegram_user_id == uid).scalar_subquery()).scalar()
        rank = (rank_result or 0) + 1

        now = datetime.utcnow()
        cutoff_14 = now - timedelta(days=14)
        tl_query = db.session.query(func.date(IDFinderMessage.timestamp).label('date'), func.count(IDFinderMessage.id).label('count')).filter(IDFinderMessage.telegram_user_id == uid, IDFinderMessage.timestamp >= cutoff_14).group_by('date').order_by('date').all()
        tl_map = {r.date.strftime('%d.%m') if hasattr(r.date, 'strftime') else str(r.date)[:10].split('-')[2]+'.'+str(r.date)[:10].split('-')[1]: r.count for r in tl_query if r.date}
        timeline_labels, timeline_data = [], []
        for i in range(13, -1, -1):
            lbl = (now - timedelta(days=i)).strftime('%d.%m')
            timeline_labels.append(lbl); timeline_data.append(tl_map.get(lbl, 0))

        types_query = db.session.query(IDFinderMessage.content_type, func.count(IDFinderMessage.id).label('count')).filter_by(telegram_user_id=uid).group_by(IDFinderMessage.content_type).all()
        msg_types = {r.content_type: int(r.count) for r in types_query}

        topic_query = db.session.query(IDFinderMessage.message_thread_id, func.count(IDFinderMessage.id).label('count')).filter(IDFinderMessage.telegram_user_id == uid, IDFinderMessage.message_thread_id != None).group_by(IDFinderMessage.message_thread_id).order_by(text('count DESC')).limit(5).all()
        topic_map = {t.topic_id: t.topic_name for t in TopicMapping.query.all()}
        topics = [{"name": topic_map.get(str(r.message_thread_id), f"Topic {r.message_thread_id}"), "count": int(r.count)} for r in topic_query]

        recent = IDFinderMessage.query.filter_by(telegram_user_id=uid).order_by(IDFinderMessage.timestamp.desc()).limit(10).all()
        recent_msgs = [{"time": m.timestamp.strftime('%H:%M') if hasattr(m.timestamp, 'strftime') else 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', "type": m.content_type or 'text', "preview": m.text or m.text_preview or "", "file_id": m.file_id} for m in recent]

        is_admin = IDFinderAdmin.query.filter_by(telegram_id=uid).first() is not None
        c_date = getattr(user, 'created_at', getattr(user, 'first_contact', None))

        from ..models import IDFinderWarning
        warnings = IDFinderWarning.query.filter_by(telegram_user_id=uid).count()
        
        return jsonify({
            "uid": str(uid), "name": user.first_name or "Unbekannt", "username": f"@{user.username}" if user.username else "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â",
            "language": user.language_code or "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â", "status": "admin" if is_admin else "member", "avatar_url": f"/api/avatar/{uid}",
            "total_msgs": total_msgs, "total_media": total_media, "active_days": active_days,
            "joined_at": c_date.strftime('%d.%m.%Y') if c_date and hasattr(c_date, 'strftime') else "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â",
            "last_active": user.last_contact.strftime('%d.%m. %H:%M') if user.last_contact and hasattr(user.last_contact, 'strftime') else "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â",
            "avg_per_day": round(total_msgs / max(active_days, 1), 1),
            "rank": rank, "warnings": warnings, "timeline_14d": timeline_data, "timeline_labels": timeline_labels,
            "msg_types": msg_types, "topics": topics, "recent_messages": recent_msgs
        })
    except Exception as e:
        import traceback; sys.stderr.write(f"API Error {e}\n{traceback.format_exc()}\n"); return jsonify({'error': str(e)}), 500

@bp.route('/api/id-finder/user-messages/<int:uid>')
@permission_required('view_id_finder_registry')
def id_finder_user_messages_api(uid):
    try:
        from ..models import IDFinderMessage
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        recent = IDFinderMessage.query.filter_by(telegram_user_id=uid)\
            .order_by(IDFinderMessage.timestamp.desc())\
            .offset(offset).limit(limit).all()
        
        recent_msgs = []
        for m in recent:
            recent_msgs.append({
                "time": m.timestamp.strftime('%d.%m. %H:%M') if m.timestamp else 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â',
                "type": m.content_type or 'text',
                "preview": m.text or m.text_preview or "",
                "file_id": m.file_id
            })
        return jsonify({
            "messages": recent_msgs,
            "has_more": len(recent_msgs) == limit
        })
    except Exception as e:
        import traceback; sys.stderr.write(f"API Error {e}\n{traceback.format_exc()}\n"); return jsonify({'error': str(e)}), 500


@bp.route('/api/id-finder/export-messages')
@permission_required('view_analytics')
def id_finder_export_messages():
    try:
        from ..models import IDFinderMessage, IDFinderUser, InviteApplication
        from flask import Response, request
        import json
        from sqlalchemy import func
        from datetime import datetime, timedelta

        days = int(request.args.get('days') or 30)
        date_from_str = request.args.get('date_from')
        date_to_str   = request.args.get('date_to')
        topic_ids_str = request.args.get('topic_ids')
        include_steckbriefe = request.args.get('steckbriefe', 'true') == 'true'

        now = datetime.utcnow()

        if date_from_str:
            cutoff   = datetime.strptime(date_from_str, '%Y-%m-%d')
            date_end = datetime.strptime(date_to_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59) if date_to_str else now
        else:
            cutoff   = now - timedelta(days=days)
            date_end = now

        exclude_bots = (
            (IDFinderUser.is_bot == False) & 
            (IDFinderUser.telegram_id != 7520803994) &
            (IDFinderUser.username.is_(None) | ~IDFinderUser.username.ilike('%bot'))
        )
        
        query = db.session.query(
            IDFinderMessage.timestamp,
            IDFinderUser.telegram_id,
            IDFinderUser.first_name,
            IDFinderUser.username,
            IDFinderMessage.content_type,
            IDFinderMessage.text,
            IDFinderMessage.text_preview
        ).join(IDFinderUser, IDFinderMessage.telegram_user_id == IDFinderUser.telegram_id)\
         .filter(exclude_bots)\
         .filter(IDFinderMessage.timestamp >= cutoff)

        if topic_ids_str and topic_ids_str != 'all':
            from sqlalchemy import or_
            topic_ids = [t.strip() for t in topic_ids_str.split(',') if t.strip()]
            conditions = []
            
            if 'main' in topic_ids:
                # Hauptchat (message_thread_id is None or 0)
                conditions.append((IDFinderMessage.message_thread_id.is_(None)) | (IDFinderMessage.message_thread_id == 0))
            if 'private' in topic_ids:
                # Private chats (chat_id == telegram_user_id)
                conditions.append(IDFinderMessage.chat_id == IDFinderMessage.telegram_user_id)
                
            # Restliche konkrete Topic IDs
            other_ids = [t for t in topic_ids if t not in ('main', 'private') and not t.startswith('dm_')]
            if other_ids:
                conditions.append(IDFinderMessage.message_thread_id.in_(other_ids))
                
            # Spezifische DMs
            dm_ids = [t.replace('dm_', '') for t in topic_ids if t.startswith('dm_')]
            if dm_ids:
                conditions.append(IDFinderMessage.chat_id.in_(dm_ids))
                
            if conditions:
                query = query.filter(or_(*conditions))

        messages = query.order_by(IDFinderMessage.timestamp.asc()).all()
         
        export_data = {
            "metadata": {
                "generated_at": now.isoformat(),
                "filters": {
                    "days": days,
                    "topic_ids": topic_ids_str or "all",
                    "included_steckbriefe": include_steckbriefe
                },
                "total_messages": len(messages)
            },
            "messages": [],
            "steckbriefe": []
        }

        for m in messages:
            export_data["messages"].append({
                "timestamp": m[0].isoformat() if m[0] else None,
                "user_id": str(m[1]),
                "name": m[2] or "Unbekannt",
                "username": f"@{m[3]}" if m[3] else None,
                "type": m[4] or "text",
                "content": (m[5] or m[6] or "")[:500]
            })

        if include_steckbriefe:
            steckbriefe = InviteApplication.query.filter(InviteApplication.created_at >= cutoff).order_by(InviteApplication.created_at.desc()).all()
            for s in steckbriefe:
                export_data["steckbriefe"].append({
                    "id": s.id,
                    "user_id": str(s.telegram_user_id),
                    "name": s.full_name or s.username or "Unbekannt",
                    "status": s.status,
                    "submitted_at": s.created_at.isoformat() if hasattr(s.created_at, 'isoformat') else str(s.created_at),
                    "answers": s.answers
                })
            export_data["metadata"]["total_steckbriefe"] = len(steckbriefe)

        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        return Response(
            json_str,
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment;filename=analytics_export_{now.strftime("%Y%m%d")}.json'}
        )
    except Exception as e:
        import traceback
        sys.stderr.write(f"Export Error {e}\n{traceback.format_exc()}\n")
        from flask import flash, redirect, url_for
        flash(f"Fehler beim Exportieren: {e}", "danger")
        return redirect(url_for('dashboard.id_finder_analytics'))




@bp.route('/api/moderation/topics')
@permission_required('use_live_moderation')
def live_topics_api():
    try:
        from ..models import TopicMapping, IDFinderUser, IDFinderAdmin
        
        # Basis-Themen laden
        topics = TopicMapping.query.all()
        # DMs laden
        users = IDFinderUser.query.order_by(IDFinderUser.last_contact.desc()).limit(80).all()
        # Admins fÃƒÆ’Ã‚Â¼r Rank-Check
        admins = {a.telegram_id for a in IDFinderAdmin.query.all()}
        
        data = []
        # Virtuelle Topics
        data.append({'id': 'all', 'name': 'Zentrale (Alle)', 'category': 'Allgemein', 'is_active': True})
        data.append({'id': 'private', 'name': 'Alle Nutzer-DMs', 'category': 'Allgemein', 'is_active': True})
        
        for t in topics:
            data.append({
                'id': t.id,
                'chat_id': t.chat_id,
                'name': t.topic_name,
                'category': t.category or 'Hauptgruppe',
                'is_active': t.is_active,
                'is_archived': t.is_archived,
                'is_deleted': t.is_deleted,
                'is_pinned': t.is_pinned,
                'is_closed': t.is_closed,
                'last_activity': None
            })
            
        for u in users:
            # Rank bestimmen
            rank = 'User'
            if u.telegram_id in admins: rank = 'Admin'
            if u.telegram_id == 6271423455: rank = 'Inhaber' # Beispiel
            
            data.append({
                'id': f"dm_{u.telegram_id}",
                'chat_id': u.telegram_id,
                'name': u.custom_name or u.first_name or str(u.telegram_id),
                'category': 'Bot & Privat (DMs)',
                'is_active': True,
                'is_archived': u.is_sidebar_archived,
                'is_deleted': False,
                'is_pinned': False,
                'is_closed': False,
                'user_rank': rank,
                'last_activity': u.last_contact.isoformat() if u.last_contact else None
            })
            
        return jsonify(data)
    except Exception as e:
        import traceback
        print(f"ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â¥ TOPICS API ERROR: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/live-messages')
@permission_required('use_live_moderation')
def live_messages_api():
    try:
        from ..models import IDFinderMessage, IDFinderUser, IDFinderAdmin
        topic_id = request.args.get('topic_id', 'all')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Admin set fÃƒÆ’Ã‚Â¼r schnellen check
        admins = {a.telegram_id for a in IDFinderAdmin.query.all()}
        
        query = IDFinderMessage.query
        if topic_id.startswith('dm_'):
            uid = int(topic_id.replace('dm_', ''))
            query = query.filter(IDFinderMessage.chat_id == uid)
        elif topic_id == 'all':
            pass
        elif topic_id == 'private':
            query = query.filter(IDFinderMessage.chat_type == 'private')
        else:
            try: query = query.filter(IDFinderMessage.message_thread_id == int(topic_id))
            except: pass
            
        msgs = query.order_by(IDFinderMessage.timestamp.desc()).limit(limit).offset(offset).all()
        
        data = []
        for m in msgs:
            u = m.user
            # Rank Logik
            rank = 'User'
            if m.content_type == 'bot': rank = 'Bot'
            elif m.telegram_user_id in admins: rank = 'Admin'
            elif m.telegram_user_id == 6271423455: rank = 'Inhaber'
            
            data.append({
                'id': m.id,
                'message_id': m.message_id,
                'chat_id': m.chat_id,
                'user_id': m.telegram_user_id,
                'full_name': u.first_name if u else (m.deleted_by_name or "System"),
                'username': u.username if u else None,
                'avatar_url': f"/api/avatar/{m.telegram_user_id}",
                'text': m.text,
                'content_type': m.content_type,
                'file_id': m.file_id,
                'is_edited': m.is_edited,
                'is_deleted': m.is_deleted,
                'deleted_by_name': m.deleted_by_name,
                'previous_text': m.previous_text,
                'reply_to_id': m.reply_to_id,
                'reply_to_text': m.reply_to_text,
                'reply_markup': m.reply_markup,
                'ts_str': m.timestamp.isoformat() if m.timestamp else None,
                'time': m.timestamp.strftime('%H:%M') if m.timestamp else '--:--',
                'user_rank': rank
            })
            
        return jsonify(data)
    except Exception as e:
        import traceback
        print(f"ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â¥ MESSAGES API ERROR: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/moderation/topics/update', methods=['POST'])
@permission_required('use_live_moderation')
def update_topic_api():
    try:
        from ..models import TopicMapping, IDFinderUser
        data = request.json
        tid = str(data.get('topic_id'))
        
        if tid.startswith('dm_'):
            uid = int(tid.replace('dm_', ''))
            u = IDFinderUser.query.filter_by(telegram_id=uid).first()
            if u:
                if 'is_archived' in data: u.is_sidebar_archived = data['is_archived']
                db.session.commit()
                return jsonify({'success': True})
        else:
            t = TopicMapping.query.filter_by(id=int(tid)).first()
            if t:
                if 'is_archived' in data: t.is_archived = data['is_archived']
                if 'is_pinned' in data: t.is_pinned = data['is_pinned']
                if 'topic_name' in data: t.topic_name = data['topic_name']
                db.session.commit()
                return jsonify({'success': True})
                
        return jsonify({'success': False, 'error': 'Not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
@bp.route('/api/moderation/delete-message', methods=['POST'])
@permission_required('use_live_moderation')
def delete_message_api():
    try:
        from ..models import IDFinderMessage
        data = request.json
        chat_id = data.get('chat_id')
        message_id = data.get('message_id')
        
        if not chat_id or not message_id:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400
            
        # Try to delete via bot API
        from shared_bot_utils import get_bot_token
        token = get_bot_token()
        if token:
            import requests
            url = f"https://api.telegram.org/bot{token}/deleteMessage"
            payload = {'chat_id': chat_id, 'message_id': message_id}
            requests.post(url, json=payload, timeout=5)
            
        # Update DB
        msg = IDFinderMessage.query.filter_by(chat_id=chat_id, message_id=message_id).first()
        if msg:
            msg.is_deleted = True
            msg.deleted_by_name = current_user.username
            msg.deleted_by_id = 0 # Dashboard admin
            db.session.commit()
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
@bp.route('/api/id-finder/user-history/<int:uid>')
@permission_required('view_id_finder_registry')
def id_finder_user_history_api(uid):
    try:
        from ..models import IDFinderMessage
        from sqlalchemy import func
        from datetime import datetime, timedelta
        
        days = request.args.get('days', 30, type=int)
        now = datetime.utcnow()
        cutoff = now - timedelta(days=days)
        
        history_query = db.session.query(func.date(IDFinderMessage.timestamp).label('date'), func.count(IDFinderMessage.id).label('count')).filter(IDFinderMessage.telegram_user_id == uid, IDFinderMessage.timestamp >= cutoff).group_by('date').order_by('date').all()
        
        # Format labels consistency
        tl_map = {row.date.strftime('%d.%m') if hasattr(row.date, 'strftime') else f"{str(row.date).split('-')[2][:2]}.{str(row.date).split('-')[1]}": row.count for row in history_query if row.date}
        
        history_data = []
        for i in range(days - 1, -1, -1):
            lbl = (now - timedelta(days=i)).strftime('%d.%m')
            history_data.append(tl_map.get(lbl, 0))
            
        return jsonify({"history": history_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/id-finder/profiles')
@admin_required
def id_finder_profiles():
    from ..models import InviteApplication, InviteLog, ReportedMessage, IDFinderUser
    from sqlalchemy import func
    
    apps = InviteApplication.query.order_by(InviteApplication.created_at.desc()).all()
    
    # Report counts per user
    report_counts = db.session.query(
        ReportedMessage.reported_user_id, 
        func.count(ReportedMessage.id)
    ).group_by(ReportedMessage.reported_user_id).all()
    report_map = {r[0]: r[1] for r in report_counts if r[0]}
    
    # ID Finder users for accurate group membership
    id_users = IDFinderUser.query.all()
    id_user_map = {u.telegram_id: u for u in id_users}
    
    profiles = []
    for app in apps:
        answers = app.answers or {}
        # Find photo field
        photo_id = None
        for a_val in answers.values():
            if isinstance(a_val, str) and len(a_val) > 30 and (a_val.startswith('AgA') or a_val.startswith('file') or 'id' in str(a_val).lower()): 
                photo_id = a_val
                break
        
        id_user = id_user_map.get(app.telegram_user_id)
        joined = id_user.is_in_group if id_user else False
        
        profiles.append({
            'id': app.id,
            'telegram_id': app.telegram_user_id,
            'username': app.username,
            'name': app.full_name,
            'status': app.status,
            'photo_id': photo_id,
            'answers': answers, # Pass full answers for the modal
            'report_count': report_map.get(app.telegram_user_id, 0),
            'joined': joined,
            'created_at': app.created_at.strftime('%d.%m.%Y %H:%M') if app.created_at else "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â"
        })
    return render_template('id_finder_profiles.html', profiles=profiles)

@bp.route('/id-finder/profiles/delete/<int:pid>', methods=['POST'])
@permission_required('edit_id_finder_registry')
def delete_profile(pid):
    from ..models import InviteApplication
    app = InviteApplication.query.get(pid)
    if app:
        db.session.delete(app)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Not found'}), 404

@bp.route('/api/telegram-image/<file_id>')
@login_required
def telegram_image(file_id):
    # Proxy fÃƒÆ’Ã‚Â¼r Telegram-Bilder
    import requests
    from ..models import BotSettings
    settings = BotSettings.query.filter_by(bot_name='id_finder').first()
    if not settings: return "No Settings", 500
    config = json.loads(settings.config_json)
    token = config.get('bot_token')
    if not token: return "No Token", 500
    
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}", timeout=5)
        res_data = r.json()
        if not res_data.get('ok'): return "Telegram Error", 500
        path = res_data.get('result', {}).get('file_path')
        if not path: return "No Path", 404
        
        # Stream image
        img_resp = requests.get(f"https://api.telegram.org/file/bot{token}/{path}", stream=True, timeout=10)
        return (img_resp.content, 200, {'Content-Type': img_resp.headers.get('Content-Type', 'image/jpeg')})
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

# --- USER MANAGEMENT ---
@bp.route('/users')
@login_required
def manage_users():
    us = User.query.all(); ud = {u.username: {'role': u.role} for u in us}
    return render_template('manage_users.html', users=ud)

@bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    u, p, r = request.form.get('username'), request.form.get('password'), request.form.get('role', 'moderator')
    if not u or not p:
        flash('Benutzername und Passwort sind erforderlich.', 'danger')
        return redirect(url_for('dashboard.manage_users'))
        
    if User.query.filter_by(username=u).first():
        flash(f'Benutzername "{u}" existiert bereits.', 'danger')
        return redirect(url_for('dashboard.manage_users'))
        
    try:
        nu = User(username=u, role=r); nu.set_password(p); db.session.add(nu); db.session.commit()
        
        # --- AUDIT LOG ---
        from ..utils import log_audit
        log_audit("Benutzer erstellt", f"Ein neuer Benutzer '{u}' mit der Rolle '{r}' wurde angelegt.")
        
        flash(f'Benutzer "{u}" wurde angelegt.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim Anlegen des Benutzers: {e}', 'danger')
        
    return redirect(url_for('dashboard.manage_users'))

@bp.route('/users/delete/<username>', methods=['POST'])
@login_required
def delete_user(username):
    if username == current_user.username:
        flash('Du kannst dich nicht selbst lÃƒÆ’Ã‚Â¶schen.', 'danger')
        return redirect(url_for('dashboard.manage_users'))
        
    u = User.query.filter_by(username=username).first()
    if not u:
        flash('Benutzer nicht gefunden.', 'danger')
        return redirect(url_for('dashboard.manage_users'))
        
    try:
        db.session.delete(u)
        db.session.commit()
        
        # --- AUDIT LOG ---
        from ..utils import log_audit
        log_audit("Benutzer gelÃƒÆ’Ã‚Â¶scht", f"Der Benutzer '{username}' wurde dauerhaft gelÃƒÆ’Ã‚Â¶scht.")
        
        flash(f'Benutzer "{username}" wurde gelÃƒÆ’Ã‚Â¶scht.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim LÃƒÆ’Ã‚Â¶schen des Benutzers: {e}', 'danger')
        
    return redirect(url_for('dashboard.manage_users'))

@bp.route('/users/edit/<username>', methods=['POST'])
@login_required
def edit_user(username):
    u = User.query.filter_by(username=username).first()
    if not u:
        flash('Benutzer nicht gefunden.', 'danger')
        return redirect(url_for('dashboard.manage_users'))
        
    nu, np, nr = request.form.get('new_username'), request.form.get('new_password'), request.form.get('new_role')
    
    if nu and nu != username:
        if User.query.filter_by(username=nu).first():
            flash(f'Benutzername "{nu}" wird bereits verwendet.', 'danger')
            return redirect(url_for('dashboard.manage_users'))
        u.username = nu
        
    if np: u.set_password(np)
    if nr: u.role = nr
    
    try:
        db.session.commit()
        
        # --- AUDIT LOG ---
        from ..utils import log_audit
        log_audit("Benutzer bearbeitet", f"Der Benutzer '{username}' wurde aktualisiert (Rolle: {nr}, neuer Name: {nu}).")
        
        flash(f'Benutzer "{username}" wurde aktualisiert.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Interner Fehler: {e}', 'danger')
        
    return redirect(url_for('dashboard.manage_users'))

# --- MINECRAFT ---
@bp.route('/minecraft', methods=['GET', 'POST'])
@admin_required
def minecraft_status_page():
    s = BotSettings.query.filter_by(bot_name='minecraft').first()
    if not s:
        cfg = {
            "mc_host": "127.0.0.1", "mc_port": 25565, "display_host": "", "display_port": None,
            "chat_id": "", "topic_id": None, "update_seconds": 30, "delete_player_seconds": 8
        }
        s = BotSettings(bot_name='minecraft', config_json=json.dumps(cfg))
        db.session.add(s); db.session.commit()
    
    cfg = json.loads(s.config_json)
    
    if request.method == 'POST':
        # Update settings from form
        cfg['mc_host'] = request.form.get('mc_host', '127.0.0.1')
        cfg['mc_port'] = int(request.form.get('mc_port', 25565))
        cfg['display_host'] = request.form.get('display_host', '')
        cfg['display_port'] = int(request.form.get('display_port', 25565))
        cfg['chat_id'] = request.form.get('chat_id', '')
        cfg['topic_id'] = request.form.get('topic_id') or None
        cfg['update_seconds'] = int(request.form.get('update_seconds', 30))
        cfg['delete_player_seconds'] = int(request.form.get('delete_player_seconds', 8))
        
        s.config_json = json.dumps(cfg)
        db.session.commit()
        flash('Minecraft-Einstellungen gespeichert.', 'success')
        return redirect(url_for('dashboard.minecraft_status_page'))

    # Load Status Cache
    cache_path = os.path.join(PROJECT_ROOT, "bots", "data", "minecraft_status_cache.json")
    status = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                status = json.load(f)
        except: pass

    return render_template('minecraft_status.html', 
                          cfg=cfg, 
                          status=status, 
                          latency_ms=status.get('ping_ms'),
                          motd=status.get('motd'),
                          players_text=status.get('players'),
                          error=status.get('error'))

# --- TIKTOK BOT ---
@bp.route('/tiktok-settings', methods=['GET', 'POST'])
@login_required
def tiktok_settings():
    s = BotSettings.query.filter_by(bot_name='tiktok').first()
    if not s:
        cfg = {
            'target_unique_ids': [], 'watch_hosts': [], 'telegram_chat_id': '', 'telegram_topic_id': '',
            'retry_offline_seconds': 60, 'alert_cooldown_seconds': 1800, 'max_concurrent_lives': 3,
            'is_active': False, 'message_template_self': "ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â´ {target} ist LIVE!", 'message_template_presence': "ÃƒÂ°Ã…Â¸Ã¢â‚¬ËœÃ¢â€šÂ¬ {target} bei @{host}!"
        }
        s = BotSettings(bot_name='tiktok', config_json=json.dumps(cfg)); db.session.add(s); db.session.commit()
    
    cfg = json.loads(s.config_json)
    if request.method == 'POST':
        cfg.update({
            'telegram_chat_id': request.form.get('telegram_chat_id'),
            'telegram_topic_id': request.form.get('telegram_topic_id'),
            'target_unique_ids': [t.strip().lstrip('@') for t in request.form.getlist('target_unique_ids') if t.strip()],
            'watch_hosts': [h.strip().lstrip('@') for h in request.form.get('watch_hosts', '').split(',') if h.strip()],
            'message_template_self': request.form.get('message_template_self'),
            'message_template_presence': request.form.get('message_template_presence'),
            'alert_cooldown_seconds': int(request.form.get('alert_cooldown_seconds', 1800)),
            'max_concurrent_lives': int(request.form.get('max_concurrent_lives', 3))
        })
        s.is_active = cfg.get('is_active', False)
        s.config_json = json.dumps(cfg); db.session.commit(); flash('TikTok-Einstellungen gespeichert.', 'success'); return redirect(url_for('dashboard.tiktok_settings'))

    logs = []
    if os.path.exists(TIKTOK_BOT_LOG_FILE):
        with open(TIKTOK_BOT_LOG_FILE, 'r') as f: logs = f.readlines()[-100:]
    
    ids = BotSettings.query.filter_by(bot_name='id_finder').first()
    cfg['api_token_display'] = json.loads(ids.config_json).get('bot_token', 'Nicht gesetzt') if ids and ids.config_json else 'Nicht gesetzt'
    return render_template('tiktok_settings.html', config=cfg, logs=logs)

@bp.route('/tiktok/clear-logs', methods=['POST'])
@login_required
def tiktok_clear_logs():
    if not safe_clear_log(TIKTOK_BOT_LOG_FILE):
        flash('Logs konnten nicht gelÃƒÆ’Ã‚Â¶scht werden (File In Use).', 'warning')
    else:
        flash('Logs erfolgreich gelÃƒÆ’Ã‚Â¶scht.', 'success')
    return redirect(url_for('dashboard.tiktok_settings'))

# --- BOT ACTIONS ---
@bp.route('/bot-action/<bot_name>/<action>', methods=['POST'])
@login_required
def bot_action_route(bot_name, action):
    # Master-Bot (ID-Finder) hat als einziges noch echte Prozess-Steuerung
    if bot_name == 'id_finder':
        return master_bot_action(action)

    # Alle anderen Bots (Module) toggeln nur noch ihr "is_active" Flag in der DB
    s = BotSettings.query.filter_by(bot_name=bot_name).first()
    
    # Auto-create if not exists (e.g. for new modules like auto_responder)
    if not s:
        s = BotSettings(bot_name=bot_name, config_json=json.dumps({"is_active": False}), is_active=False)
        db.session.add(s)
        db.session.commit()

    try:
        c = json.loads(s.config_json) if s.config_json else {}
        if action == 'start':
            c['is_active'] = True
            s.is_active = True
            
            # --- AUDIT LOG ---
            from ..utils import log_audit
            log_audit("Modul aktiviert", f"Das Modul '{bot_name}' wurde gestartet/aktiviert.")
            
            flash(f'{bot_name.capitalize()} Modul aktiviert.', 'success')
        elif action == 'stop':
            c['is_active'] = False
            s.is_active = False
            
            # --- AUDIT LOG ---
            from ..utils import log_audit
            log_audit("Modul deaktiviert", f"Das Modul '{bot_name}' wurde gestoppt/deaktiviert.")
            
            flash(f'{bot_name.capitalize()} Modul deaktiviert.', 'warning')
        
        s.config_json = json.dumps(c)
        db.session.commit()
    except Exception as e:
        flash(f'Fehler beim ÃƒÆ’Ã¢â‚¬Å¾ndern des Modul-Status: {e}', 'danger')
        
    return redirect(request.referrer or url_for('dashboard.index'))

def manage_master_bot_logic(action, is_auto_start=False):
    """
    Kapselt die Logik zum Starten/Stoppen des Master-Bots.
    Kann sowohl aus einer Web-Route als auch beim App-Start (Auto-Start) aufgerufen werden.
    """
    pfile = os.path.join(PROJECT_ROOT, "logs", "main_bot.pid")
    script = os.path.join(PROJECT_ROOT, "bots", "main_bot.py")
    lpath = os.path.join(PROJECT_ROOT, "logs", "main_bot.log")

    def _flash(msg, cat):
        if not is_auto_start:
            try: flash(msg, cat)
            except: pass

    if action == 'start':
        if os.path.exists(pfile):
            try:
                with open(pfile, 'r') as f: pid = int(f.read().strip())
                if is_process_running(pid):
                    print(f"Master-Bot lÃƒÆ’Ã‚Â¤uft bereits (PID: {pid}). Kein Neustart erforderlich.")
                    _flash('Master-Bot lÃƒÆ’Ã‚Â¤uft bereits.', 'info')
                    return
            except Exception as e:
                print(f"Fehler beim PrÃƒÆ’Ã‚Â¼fen der PID-Datei: {e}")
        
        # Falls Datei existiert aber Prozess NICHT lÃƒÆ’Ã‚Â¤uft -> Datei lÃƒÆ’Ã‚Â¶schen fÃƒÆ’Ã‚Â¼r sauberen Start
        if os.path.exists(pfile):
            try: os.remove(pfile)
            except: pass
        
        exe = sys.executable
        venv_win = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
        venv_lin = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
        if os.path.exists(venv_win): exe = venv_win
        elif os.path.exists(venv_lin): exe = venv_lin

        os.makedirs(os.path.dirname(lpath), exist_ok=True)
        
        from dotenv import load_dotenv as load_env_file
        load_env_file(os.path.join(PROJECT_ROOT, '.env'))
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["BOT_PROCESS"] = "1"  # Markierung fÃƒÆ’Ã‚Â¼r Unterprozesse
        
        creationflags = 0
        if os.name == 'nt': creationflags = 0x00000008
            
        with open(lpath, 'a', encoding='utf-8') as lf: 
            proc = subprocess.Popen([exe, script], start_new_session=(os.name != 'nt'), creationflags=creationflags, stdout=lf, stderr=lf, env=env)
        
        with open(pfile, 'w') as f: f.write(str(proc.pid))
        _flash('Master-Bot gestartet.', 'success')
        print(f"Master-Bot gestartet (PID: {proc.pid})")
        
    elif action == 'stop' and os.path.exists(pfile):
        try:
            with open(pfile, 'r') as f: pid = int(f.read().strip())
            if os.name == 'nt':
                # Force kill process tree to avoid ghost processes
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Also kill any leftover main_bot.py processes just in case
                subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE eq Bot-Master*'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.kill(pid, signal.SIGTERM)
            if os.path.exists(pfile): os.remove(pfile)
            _flash('Master-Bot gestoppt.', 'success')

        except Exception as e:
            print(f"Fehler beim Stoppen vom Master Bot: {e}")
            _flash('Fehler beim Stoppen des Master-Bots.', 'danger')

def master_bot_action(action):
    manage_master_bot_logic(action)
    
    # --- AUDIT LOG ---
    from ..utils import log_audit
    status_text = "gestartet" if action == "start" else "gestoppt"
    log_audit("Master-Bot gesteuert", f"Der Master-Bot (ID-Finder) wurde manuell {status_text}.")
    
    return redirect(request.referrer or url_for('dashboard.index'))

@bp.route('/api/bot-status')
@login_required
def bot_status_api(): return jsonify(get_bot_status_simple())

# --- PROFANITY FILTER ---
@bp.route('/profanity-filter')
@login_required
def profanity_filter():
    from ..models import ProfanityWord
    words = ProfanityWord.query.order_by(ProfanityWord.word).all()
    s = BotSettings.query.filter_by(bot_name='profanity_filter').first()
    is_running = False
    if s and s.config_json:
        try:
            cfg = json.loads(s.config_json)
            is_running = cfg.get('is_active', False)
        except:
            pass
    return render_template('profanity_filter.html', words=words, is_running=is_running)

@bp.route('/profanity-filter/add', methods=['POST'])
@login_required
def profanity_filter_add():
    from ..models import ProfanityWord
    
    # Check if this is a bulk import from the new textarea
    bulk_words = request.form.get('words_bulk', '')
    if not bulk_words:
        # Fallback to single word input if used
        bulk_words = request.form.get('word', '')
        
    if bulk_words:
        import re
        # Split by commas or newlines
        words_list = re.split(r'[,\n\r]+', bulk_words)
        
        added_count = 0
        skipped_count = 0
        
        for w in words_list:
            clean_word = w.strip().lower()
            if not clean_word:
                continue
                
            if len(clean_word) > 100:
                skipped_count += 1
                continue
                
            exists = ProfanityWord.query.filter_by(word=clean_word).first()
            if not exists:
                db.session.add(ProfanityWord(word=clean_word))
                added_count += 1
            else:
                skipped_count += 1
                
        if added_count > 0:
            db.session.commit()
            flash(f'{added_count} neue(s) Wort/WÃƒÆ’Ã‚Â¶rter erfolgreich hinzugefÃƒÆ’Ã‚Â¼gt.', 'success')
            if skipped_count > 0:
                flash(f'{skipped_count} Wort/WÃƒÆ’Ã‚Â¶rter wurden ÃƒÆ’Ã‚Â¼bersprungen (bereits vorhanden oder zu lang).', 'warning')
        elif skipped_count > 0:
            flash(f'Alle eingegebenen WÃƒÆ’Ã‚Â¶rter existieren bereits oder sind zu lang.', 'warning')
        else:
            flash('Keine gÃƒÆ’Ã‚Â¼ltigen WÃƒÆ’Ã‚Â¶rter gefunden.', 'warning')
            
    return redirect(url_for('dashboard.profanity_filter'))

@bp.route('/profanity-filter/delete/<int:word_id>', methods=['POST'])
@login_required
def profanity_filter_delete(word_id):
    from ..models import ProfanityWord
    w = ProfanityWord.query.get(word_id)
    if w:
        db.session.delete(w)
        db.session.commit()
        flash('Wort gelÃƒÆ’Ã‚Â¶scht.', 'info')
    return redirect(url_for('dashboard.profanity_filter'))

@bp.route('/profanity-filter/import-google', methods=['POST'])
@login_required
def profanity_filter_import_google():
    from ..models import ProfanityWord
    import urllib.request
    try:
        url = "https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/de"
        response = urllib.request.urlopen(url)
        content = response.read().decode('utf-8')
        lines = content.splitlines()
        
        added = 0
        for line in lines:
            w = line.strip().lower()
            if w and len(w) <= 100:
                if not ProfanityWord.query.filter_by(word=w).first():
                    db.session.add(ProfanityWord(word=w, language='de'))
                    added += 1
        db.session.commit()
        flash(f'{added} neue WÃƒÆ’Ã‚Â¶rter aus der Google-Liste importiert.', 'success')
    except Exception as e:
        flash(f'Fehler beim Importieren: {e}', 'danger')
        
    return redirect(url_for('dashboard.profanity_filter'))

# --- BIRTHDAY BOT ---
@bp.route('/birthday-settings', methods=['GET', 'POST'])
@admin_required
def birthday_settings():
    from ..models import Birthday, BotSettings, IDFinderUser, TopicMapping
    
    s = BotSettings.query.filter_by(bot_name='birthday').first()
    if not s:
        cfg = {
            'registration_text': 'Dein Geburtstag ({day}.{month}.) wurde erfolgreich eingetragen!',
            'congratulation_text': 'Herzlichen GlÃƒÆ’Ã‚Â¼ckwunsch zum Geburtstag, {user}!',
            'prompt_text': 'ÃƒÂ°Ã…Â¸Ã…Â½Ã¢â‚¬Å¡ <b>Geburtstags-Bot</b>\n\nWann hast du Geburtstag?\nBitte schreibe es im Format <code>Tag.Monat</code> oder <code>Tag.Monat.Jahr</code>.\n<i>(Beispiel: 15.08. oder 15.08.1990 - das Jahr ist komplett freiwillig!)</i>\n\nWenn du abbrechen mÃƒÆ’Ã‚Â¶chtest, tippe /cancel.',
            'error_format_text': 'Das war leider das falsche Format.\nBeispiele: `15.08.` oder `15 08 1990`\nVersuche es nochmal oder tippe /cancel.',
            'error_date_text': 'Das ist leider kein echtes Kalenderdatum. Bitte versuche es noch einmal:',
            'cancel_text': 'Geburtstags-Eintragung abgebrochen.',
            'announce_time': '00:01',
            'target_chat_id': '',
            'target_topic_id': '',
            'auto_delete_registration': False,
            'auto_delete_wishes': True,
            'auto_delete_wishes_days': 2,
            'auto_delete_wishes_hours': 0,
            'auto_delete_wishes_minutes': 0
        }
        s = BotSettings(bot_name='birthday', config_json=json.dumps(cfg))
        db.session.add(s)
        db.session.commit()
        
    cfg = json.loads(s.config_json)
    # Self-healing default population
    if 'auto_delete_wishes' not in cfg:
        cfg['auto_delete_wishes'] = True
    if 'auto_delete_wishes_days' not in cfg:
        cfg['auto_delete_wishes_days'] = 2
    if 'auto_delete_wishes_hours' not in cfg:
        cfg['auto_delete_wishes_hours'] = 0
    if 'auto_delete_wishes_minutes' not in cfg:
        cfg['auto_delete_wishes_minutes'] = 0
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_settings':
            cfg['registration_text'] = request.form.get('registration_text')
            cfg['congratulation_text'] = request.form.get('congratulation_text')
            cfg['prompt_text'] = request.form.get('prompt_text')
            cfg['error_format_text'] = request.form.get('error_format_text')
            cfg['error_date_text'] = request.form.get('error_date_text')
            cfg['cancel_text'] = request.form.get('cancel_text')
            cfg['announce_time'] = request.form.get('announce_time')
            cfg['target_chat_id'] = request.form.get('target_chat_id', '').strip()
            cfg['target_topic_id'] = request.form.get('target_topic_id', '').strip()
            cfg['auto_delete_registration'] = request.form.get('auto_delete_registration') == 'on'
            cfg['auto_delete_wishes'] = request.form.get('auto_delete_wishes') == 'on'
            try:
                cfg['auto_delete_wishes_days'] = int(request.form.get('auto_delete_wishes_days') or 0)
            except ValueError:
                cfg['auto_delete_wishes_days'] = 2
            try:
                cfg['auto_delete_wishes_hours'] = int(request.form.get('auto_delete_wishes_hours') or 0)
            except ValueError:
                cfg['auto_delete_wishes_hours'] = 0
            try:
                cfg['auto_delete_wishes_minutes'] = int(request.form.get('auto_delete_wishes_minutes') or 0)
            except ValueError:
                cfg['auto_delete_wishes_minutes'] = 0
            s.config_json = json.dumps(cfg)
            db.session.commit()
            flash('Geburtstags-Einstellungen gespeichert.', 'success')
            
        elif action == 'add_birthday':
            uid = request.form.get('telegram_user_id')
            day = request.form.get('day')
            month = request.form.get('month')
            year = request.form.get('year')
            if uid and day and month:
                existing = Birthday.query.filter_by(telegram_user_id=int(uid)).first()
                if not existing:
                    u = IDFinderUser.query.filter_by(telegram_id=int(uid)).first()
                    name = u.first_name if u else "Unbekannt"
                    username = u.username if u else ""
                    b = Birthday(telegram_user_id=int(uid), day=int(day), month=int(month), year=int(year) if year else None, first_name=name, username=username)
                    db.session.add(b)
                    db.session.commit()
                    flash('Geburtstag hinzugefÃƒÆ’Ã‚Â¼gt.', 'success')
                else:
                    flash('User hat bereits einen Geburtstag eingetragen.', 'warning')
                    
        elif action == 'update_birthday':
            bid = request.form.get('birthday_id')
            day = request.form.get('day')
            month = request.form.get('month')
            year = request.form.get('year')
            if bid and day and month:
                b = Birthday.query.get(int(bid))
                if b:
                    b.day = int(day)
                    b.month = int(month)
                    b.year = int(year) if year else None
                    db.session.commit()
                    flash('Geburtstag aktualisiert.', 'success')
                    
        elif action == 'delete_birthday':
            bid = request.form.get('birthday_id')
            if bid:
                b = Birthday.query.get(int(bid))
                if b:
                    db.session.delete(b)
                    db.session.commit()
                    flash('Geburtstag gelÃƒÆ’Ã‚Â¶scht.', 'success')
                    
        return redirect(url_for('dashboard.birthday_settings'))
        
    birthdays = Birthday.query.order_by(Birthday.month, Birthday.day).all()
    
    # Load topics
    topics = TopicMapping.query.all()
    
    # Load master bot config
    master_bot = BotSettings.query.filter_by(bot_name='id_finder').first()
    master_cfg = json.loads(master_bot.config_json) if master_bot else {}

    return render_template('birthday.html', settings=cfg, birthdays=birthdays, topics=topics, master_cfg=master_cfg)

@bp.route('/birthday/gratulieren/<int:birthday_id>', methods=['POST'])
@login_required
def birthday_gratulieren(birthday_id):
    from ..models import Birthday, BotSettings
    from bots.birthday_bot.birthday_bot import send_birthday_wish
    from shared_bot_utils import get_bot_token
    import asyncio
    from telegram import Bot
    
    b = Birthday.query.get(birthday_id)
    if not b:
        flash('Geburtstag nicht gefunden.', 'danger')
        return redirect(url_for('dashboard.birthday_settings'))
    
    s = BotSettings.query.filter_by(bot_name='birthday').first()
    cfg = json.loads(s.config_json) if s else {}
    
    # Load master bot config for fallback
    master_bot = BotSettings.query.filter_by(bot_name='id_finder').first()
    master_cfg = json.loads(master_bot.config_json) if master_bot else {}
    
    target_chat = cfg.get('target_chat_id') or str(master_cfg.get('main_group_id')) or str(b.chat_id)
    target_topic = cfg.get('target_topic_id') or b.topic_id
    
    token = get_bot_token()
    if not token:
        flash('Bot Token nicht gefunden.', 'danger')
        return redirect(url_for('dashboard.birthday_settings'))
    
    try:
        bot = Bot(token=token)
        # Wir mÃƒÆ’Ã‚Â¼ssen den async Aufruf in ein Event-Loop packen
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(send_birthday_wish(bot, b.telegram_user_id, target_chat, target_topic))
        loop.close()
        
        if success:
            flash(f'Gratulation an {b.first_name} wurde gesendet!', 'success')
        else:
            flash('Senden fehlgeschlagen. PrÃƒÆ’Ã‚Â¼fe die Logs.', 'warning')
    except Exception as e:
        flash(f'Fehler beim Senden: {e}', 'danger')
        
    return redirect(url_for('dashboard.birthday_settings'))

@bp.route('/api/backup/download')
@login_required
def download_backup():
    import os
    from flask import send_file, flash, redirect, url_for
    from flask_login import current_user
    
    if getattr(current_user, 'role', 'user') != 'admin':
        flash('Keine Berechtigung. Nur Administratoren kÃƒÆ’Ã‚Â¶nnen Backups herunterladen.', 'danger')
        return redirect(url_for('dashboard.index'))
        
    from shared_bot_utils import DB_PATH
    
    if os.path.exists(DB_PATH):
        return send_file(DB_PATH, as_attachment=True, download_name='app_backup.db')
    else:
        flash('Datenbank-Datei nicht gefunden. Nutzen Sie ggf. eine externe MariaDB?', 'danger')
        return redirect(url_for('dashboard.index'))

@bp.route('/api/backup/list-nas')
@login_required
def list_nas_backups():
    s = BotSettings.query.filter_by(bot_name='backup_bot').first()
    if not s or not s.config_json:
        return jsonify([])
    
    cfg = json.loads(s.config_json)
    nas_path = cfg.get('nas_path')
    if not nas_path or not os.path.exists(nas_path):
        return jsonify([])
    
    backups = []
    try:
        from datetime import datetime
        for f in os.listdir(nas_path):
            if f.endswith('.db'):
                path = os.path.join(nas_path, f)
                stats = os.stat(path)
                backups.append({
                    "filename": f,
                    "size": round(stats.st_size / 1024, 1), # KB
                    "date": datetime.fromtimestamp(stats.st_mtime).strftime('%d.%m.%Y %H:%M')
                })
        # Sortieren nach Datum (neueste zuerst)
        backups.sort(key=lambda x: x['date'], reverse=True)
    except Exception as e:
        print(f"Fehler beim Auflisten der NAS-Backups: {e}")
        
    return jsonify(backups)

@bp.route('/api/backup/restore-nas', methods=['POST'])
@login_required
def restore_from_nas():
    if getattr(current_user, 'role', 'user') != 'admin':
        return jsonify({"success": False, "error": "Keine Berechtigung."}), 403
        
    filename = request.json.get('filename')
    if not filename:
        return jsonify({"success": False, "error": "Keine Datei angegeben."}), 400
        
    from shared_bot_utils import DB_PATH
    import shutil
    s = BotSettings.query.filter_by(bot_name='backup_bot').first()
    cfg = json.loads(s.config_json)
    nas_path = cfg.get('nas_path')
    
    source_path = os.path.join(nas_path, filename)
    if not os.path.exists(source_path):
        return jsonify({"success": False, "error": "Datei auf NAS nicht gefunden."}), 404
        
    RESTORE_PENDING_PATH = DB_PATH + ".restore_pending"
    
    try:
        # Falls alte Pending-Datei existiert
        if os.path.exists(RESTORE_PENDING_PATH): os.remove(RESTORE_PENDING_PATH)
        
        # 1. Von NAS in Pending-Pfad kopieren
        shutil.copy2(source_path, RESTORE_PENDING_PATH)
        
        # 2. Neustart triggern - Monitor erledigt den Rest
        import threading
        import time
        def restart_task():
            time.sleep(2)
            os._exit(0)
        threading.Thread(target=restart_task).start()
        
        return jsonify({"success": True, "message": f"Backup '{filename}' wird vorbereitet. Das System startet gleich neu und fÃƒÆ’Ã‚Â¼hrt den Restore durch."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/api/send-specific-poll', methods=['POST'])
@login_required
def api_send_specific_poll():
    data = request.json
    if not data: return jsonify({"success": False, "error": "No data"}), 400
    try:
        tfile = os.path.abspath(os.path.join(PROJECT_ROOT, "bots", "umfrage_bot", "send_specific.json"))
        os.makedirs(os.path.dirname(tfile), exist_ok=True)
        with open(tfile, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/api/send-specific-quiz', methods=['POST'])
@login_required
def api_send_specific_quiz():
    data = request.json
    if not data: return jsonify({"success": False, "error": "No data"}), 400
    try:
        tfile = os.path.abspath(os.path.join(PROJECT_ROOT, "bots", "quiz_bot", "send_specific.json"))
        os.makedirs(os.path.dirname(tfile), exist_ok=True)
        with open(tfile, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/api/backup/validate', methods=['POST'])
@login_required
def validate_backup_file():
    if 'backup_file' not in request.files:
        return jsonify({"success": False, "error": "Keine Datei hochgeladen."}), 400
    
    file = request.files['backup_file']
    from shared_bot_utils import DB_PATH
    temp_path = DB_PATH + ".validate_tmp"
    
    try:
        # Falls alte Temp-Datei existiert, lÃƒÆ’Ã‚Â¶schen
        if os.path.exists(temp_path): os.remove(temp_path)
        
        file.save(temp_path)
        
        # SQLite Check
        with open(temp_path, 'rb') as f:
            header = f.read(16)
            if header != b'SQLite format 3\x00':
                if os.path.exists(temp_path): os.remove(temp_path)
                return jsonify({"success": False, "error": "Die Datei ist keine gÃƒÆ’Ã‚Â¼ltige SQLite-Datenbank."})

        from sqlalchemy import create_engine, text
        engine = create_engine(f"sqlite:///{temp_path}")
        
        stats = {"admins": 0, "users": 0, "bots": 0, "profiles": 0, "messages": 0, "tokens": [], "groups": [], "created_at": None, "age_str": ""}
        
        try:
            with engine.connect() as conn:
                # 1. Admins
                try: stats["admins"] = conn.execute(text("SELECT COUNT(*) FROM user")).scalar() or 0
                except: pass
                
                # 2. Bot Settings
                try: 
                    rows = conn.execute(text("SELECT bot_name, config_json FROM bot_settings")).fetchall()
                    stats["bots"] = len(rows)
                    for row in rows:
                        try:
                            if row[0] == 'dashboard_layout': continue
                            cfg = json.loads(row[1])
                            tk = cfg.get('bot_token') or cfg.get('token') or cfg.get('BOT_TOKEN')
                            if tk: stats["tokens"].append(row[0])
                            gid = cfg.get('main_group_id') or cfg.get('main_chat_id') or \
                                  cfg.get('telegram_chat_id') or cfg.get('channel_id') or \
                                  cfg.get('CHAT_ID') or cfg.get('chat_id')
                            if gid: stats["groups"].append(f"{row[0]}: {gid}")
                        except: pass
                except: pass

                # 3. Bot Users
                try: stats["users"] = conn.execute(text("SELECT COUNT(*) FROM id_finder_user")).scalar() or 0
                except: pass
                
                # 4. Profiles
                try: stats["profiles"] = conn.execute(text("SELECT COUNT(*) FROM invite_application")).scalar() or 0
                except: pass

                # 5. Messages & Age Estimation
                try: 
                    msg_res = conn.execute(text("SELECT COUNT(*), MAX(timestamp) FROM id_finder_message")).fetchone()
                    stats["messages"] = msg_res[0] or 0
                    latest_ts_str = msg_res[1]
                    
                    if latest_ts_str:
                        # SQLite timestamps can be varied, try common formats
                        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                            try:
                                dt = datetime.strptime(latest_ts_str.split('.')[0] if '.' in latest_ts_str and fmt=="%Y-%m-%d %H:%M:%S" else latest_ts_str, fmt)
                                stats["created_at"] = dt.strftime("%d.%m.%Y %H:%M")
                                
                                diff = datetime.now() - dt
                                if diff.days > 0:
                                    stats["age_str"] = f"{diff.days} Tag(e) alt"
                                elif diff.seconds > 3600:
                                    stats["age_str"] = f"{diff.seconds // 3600} Stunde(n) alt"
                                else:
                                    stats["age_str"] = f"{diff.seconds // 60} Minute(n) alt"
                                break
                            except: continue
                except: pass
                
            engine.dispose()
            if os.path.exists(temp_path): os.remove(temp_path)
            
            return jsonify({
                "success": True, 
                "stats": stats
            })
        except Exception as e:
            engine.dispose()
            if os.path.exists(temp_path): os.remove(temp_path)
            return jsonify({"success": False, "error": f"Datenbank-Zugriffsfehler: {str(e)}"})
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        return jsonify({"success": False, "error": f"Dateifehler: {str(e)}"})

@bp.route('/api/backup/upload', methods=['POST'])
@login_required
def upload_backup():
    if getattr(current_user, 'role', 'user') != 'admin':
        return jsonify({"success": False, "error": "Keine Berechtigung."}), 403
        
    if 'backup_file' not in request.files:
        return jsonify({"success": False, "error": "Keine Datei."}), 400
        
    file = request.files['backup_file']
    from shared_bot_utils import DB_PATH, PROJECT_ROOT
    import zipfile
    import shutil
    
    RESTORE_PENDING_PATH = DB_PATH + ".restore_pending"
    is_zip = file.filename.lower().endswith('.zip')
    
    try:
        # Falls eine alte Pending-Datei existiert
        if os.path.exists(RESTORE_PENDING_PATH): os.remove(RESTORE_PENDING_PATH)
        
        if is_zip:
            # ZIP-Handling: Entpacke DB und Bilder
            temp_zip = RESTORE_PENDING_PATH + ".zip"
            file.save(temp_zip)
            
            with zipfile.ZipFile(temp_zip, 'r') as z:
                # 1. Datenbank wiederherstellen
                if 'database/app.db' in z.namelist():
                    with z.open('database/app.db') as db_src, open(RESTORE_PENDING_PATH, 'wb') as db_dst:
                        shutil.copyfileobj(db_src, db_dst)
                
                # 2. Bilder direkt wiederherstellen (static/uploads)
                target_base = os.path.join(PROJECT_ROOT, "web_dashboard", "app", "static")
                for member in z.namelist():
                    if member.startswith('media/'):
                        # Extrahiere nach target_base/uploads/...
                        # Der Pfad im ZIP ist 'media/uploads/filename.jpg'
                        rel_path = member.replace('media/', '') # result: 'uploads/f.jpg'
                        dest_path = os.path.join(target_base, rel_path)
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        with z.open(member) as f_src, open(dest_path, 'wb') as f_dst:
                            shutil.copyfileobj(f_src, f_dst)
            
            os.remove(temp_zip)
        else:
            # Normales DB-Handling
            file.save(RESTORE_PENDING_PATH)
            # SQLite Check
            with open(RESTORE_PENDING_PATH, 'rb') as f:
                if f.read(16) != b'SQLite format 3\x00':
                    os.remove(RESTORE_PENDING_PATH)
                    return jsonify({"success": False, "error": "Die Datei ist keine gÃƒÆ’Ã‚Â¼ltige SQLite-Datenbank."}), 400
        
        # Server Neustart triggern
        import threading
        import time
        import platform
        def restart_server():
            time.sleep(2)
            # Auf Linux/NAS (Docker) machen wir den Swap sofort, da kein Monitor-Skript lÃƒÆ’Ã‚Â¤uft.
            if platform.system() != 'Windows':
                try:
                    db.session.remove()
                    db.engine.dispose()
                    if os.path.exists(RESTORE_PENDING_PATH):
                        if os.path.exists(DB_PATH): shutil.move(DB_PATH, DB_PATH + ".bak")
                        shutil.move(RESTORE_PENDING_PATH, DB_PATH)
                except: pass
            os._exit(0)
            
        threading.Thread(target=restart_server, daemon=True).start()
        
        msg = "Voll-Backup (mit Bildern) geladen!" if is_zip else "Datenbank-Backup geladen!"
        return jsonify({"success": True, "message": f"{msg} Die Wiederherstellung wurde gestartet. Der Server wird nun neu geladen."})
        
    except Exception as e:
        logger.error(f"Error restoring backup: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/api/backup/settings/save', methods=['POST'])
@login_required
def save_backup_settings():
    if getattr(current_user, 'role', 'user') != 'admin':
        flash('Nur Administratoren kÃƒÆ’Ã‚Â¶nnen Backup-Einstellungen ÃƒÆ’Ã‚Â¤ndern.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    s = BotSettings.query.filter_by(bot_name='backup_bot').first()
    if not s:
        s = BotSettings(bot_name='backup_bot')
        db.session.add(s)
        
    cfg = {
        'enabled': 'enabled' in request.form,
        'nas_path': request.form.get('nas_path', '').strip(),
        'backup_time': request.form.get('backup_time', '06:55'),
        'local_retention': int(request.form.get('local_retention', 7)),
        'gdrive_enabled': 'gdrive_enabled' in request.form,
        'gdrive_folder_id': request.form.get('gdrive_folder_id', '').strip(),
        'gdrive_retention': int(request.form.get('gdrive_retention', 7)),
        'gdrive_credentials_json': request.form.get('gdrive_credentials_json', '').strip(),
        'silent_notifications': 'silent_notifications' in request.form,
        'backup_group_id': request.form.get('backup_group_id', '').strip()
    }
    
    s.config_json = json.dumps(cfg)
    db.session.commit()
    
    # Optional: Update the running job in the bot
    # This might require a bot restart or a dynamic job update mechanism
    # For now, a bot restart is simplest if they want immediate change, but usually they'll wait for the next day.
    
    flash('Backup-Einstellungen erfolgreich gespeichert.', 'success')
    return redirect(url_for('dashboard.index'))

@bp.route('/api/backup/test-gdrive', methods=['POST'])
@login_required
def test_gdrive_connection():
    if getattr(current_user, 'role', 'user') != 'admin':
        return jsonify({"success": False, "error": "Keine Berechtigung."}), 403
        
    data = request.json or {}
    folder_id = data.get('folder_id')
    creds_json = data.get('credentials_json')
    
    if not folder_id:
        return jsonify({"success": False, "error": "Google Drive Ordner-ID fehlt."}), 400
        
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        
        scopes = ["https://www.googleapis.com/auth/drive"]
        creds = None
        
        if creds_json and creds_json.strip():
            try:
                info = json.loads(creds_json)
                creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
            except Exception as parse_err:
                return jsonify({"success": False, "error": f"UngÃƒÆ’Ã‚Â¼ltiges JSON-Format bei den Zugangsdaten: {parse_err}"}), 400
        else:
            # Fallback directly to file google_drive_credentials.json
            from shared_bot_utils import PROJECT_ROOT
            creds_path = os.path.join(PROJECT_ROOT, "google_drive_credentials.json")
            if os.path.exists(creds_path):
                creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
            else:
                # Also check database configuration fallback
                s = BotSettings.query.filter_by(bot_name='backup_bot').first()
                if s and s.config_json:
                    cfg = json.loads(s.config_json)
                    db_creds_json = cfg.get('gdrive_credentials_json')
                    if db_creds_json and db_creds_json.strip():
                        try:
                            info = json.loads(db_creds_json)
                            creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
                        except:
                            pass
        
        if not creds:
            return jsonify({"success": False, "error": "Keine Google Drive Zugangsdaten (JSON-SchlÃƒÆ’Ã‚Â¼ssel) gefunden. Bitte fÃƒÆ’Ã‚Â¼ge den JSON-Inhalt ein."}), 400
            
        service = build("drive", "v3", credentials=creds)
        
        try:
            # Check metadata of the folder
            folder = service.files().get(fileId=folder_id, fields="id, name, mimeType").execute()
            if folder.get('mimeType') != 'application/vnd.google-apps.folder':
                return jsonify({"success": False, "error": f"Die angegebene ID gehÃƒÆ’Ã‚Â¶rt zu einer Datei, nicht zu einem Ordner (Typ: {folder.get('mimeType')})."})
            
            return jsonify({"success": True, "message": f"Erfolgreich! Ordner '{folder.get('name')}' gefunden und beschreibbar."})
        except Exception as api_err:
            error_str = str(api_err)
            if "Google Drive API has not been used" in error_str or "disabled" in error_str:
                return jsonify({"success": False, "error": "Google Drive API ist in deiner Google Cloud Platform Console deaktiviert. Bitte aktiviere sie fÃƒÆ’Ã‚Â¼r dein Projekt."})
            return jsonify({"success": False, "error": f"Google API Fehler: {error_str}"})
            
    except Exception as e:
        return jsonify({"success": False, "error": f"Fehler bei Verbindung: {str(e)}"}), 500

@bp.route('/api/backup/trigger', methods=['POST'])
@login_required
def manual_backup_trigger():
    if getattr(current_user, 'role', 'user') != 'admin':
        return jsonify({"success": False, "error": "Keine Berechtigung."}), 403
    
    from shared_bot_utils import PROJECT_ROOT
    import os
    import sys
    import json
    import subprocess
    
    s = BotSettings.query.filter_by(bot_name='backup_bot').first()
    if not s or not s.config_json:
        return jsonify({"success": False, "error": "Backup ist nicht konfiguriert."}), 400
        
    script_path = os.path.join(PROJECT_ROOT, "instance", "manual_backup_runner.py")
    if not os.path.exists(script_path):
        return jsonify({"success": False, "error": "Backup Runner Skript nicht gefunden."}), 500
        
    try:
        # Run the clean backup runner script as a subprocess
        res = subprocess.run([sys.executable, script_path], capture_output=True, text=True, check=False)
        
        status_line = None
        for line in res.stdout.splitlines():
            if line.startswith("JSON_STATUS: "):
                status_line = line[len("JSON_STATUS: "):]
                break
                
        if status_line:
            status_data = json.loads(status_line)
            success = status_data.get("success", False)
            gdrive = status_data.get("gdrive", "")
            nas = status_data.get("nas", "")
            local = status_data.get("local", "")
            
            # If Google Drive failed due to disabled API, provide a helpful explanation
            error_msg = None
            if "Google Drive API has not been used" in gdrive or "disabled" in gdrive:
                error_msg = "Google Drive API ist im Google Cloud Projekt deaktiviert. Bitte aktiviere sie."
                
            return jsonify({
                "success": success,
                "message": f"Voll-Backup abgeschlossen! (Lokal: {local}, NAS: {nas}, Google Drive: {gdrive})",
                "error": error_msg,
                "gdrive_status": gdrive,
                "nas_status": nas,
                "local_status": local
            })
        else:
            return jsonify({"success": False, "error": f"Das Backup-Skript lieferte keine Statusmeldung:\n{res.stderr or res.stdout}"}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": f"Fehler beim Starten des Backups: {str(e)}"}), 500

@bp.route('/api/id-finder/user-activity/<int:uid>')
@permission_required('view_id_finder_registry')
def id_finder_user_activity(uid):
    try:
        from ..models import IDFinderMessage
        from datetime import datetime, timedelta
        from sqlalchemy import func
        now = datetime.utcnow()
        try:
            days = int(request.args.get('days') or 7)
        except ValueError:
            days = 7
        cutoff = now - timedelta(days=days)
        
        timeline_query = db.session.query(
            func.date(IDFinderMessage.timestamp).label('date'),
            func.count(IDFinderMessage.id).label('count')
        ).filter(IDFinderMessage.telegram_user_id == uid, IDFinderMessage.timestamp >= cutoff) \
         .group_by('date').order_by('date').all()

        date_map = {row.date.strftime('%d.%m') if hasattr(row.date, 'strftime') else str(row.date): row.count for row in timeline_query if row.date}
        
        total_data = []
        for i in range(days-1, -1, -1):
            d_str = (now - timedelta(days=i)).strftime('%d.%m')
            total_data.append(date_map.get(d_str, 0))

        return jsonify({"timeline": total_data})
    except Exception as e:
        import sys
        sys.stderr.write(f"Error for user activity API: {e}\n")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/events/<int:event_id>', methods=['GET'])
@login_required
def get_event_api(event_id):
    from ..models import GroupEvent
    event = GroupEvent.query.get(event_id)
    if not event:
        return jsonify({"success": False, "error": "Event nicht gefunden."}), 404
    
    return jsonify({
        "success": True,
        "event": {
            "id": event.id,
            "title": event.title,
            "description": event.description,
            "chat_id": str(event.chat_id),
            "topic_id": event.topic_id or "",
            "should_pin": event.should_pin,
            "image_path": event.image_path,
            "message_id": event.message_id,
            "is_silent": event.is_silent,
            "is_split": event.is_split,
            "has_spoiler": event.has_spoiler,
                        "media_type": event.media_type,
            "scheduled_time": event.scheduled_time.isoformat() if event.scheduled_time else None,
            "send_confirmation": event.send_confirmation,
            "confirmation_text": event.confirmation_text,
            "calendar_title": event.calendar_title,
            "calendar_filename": event.calendar_filename,
            "calendar_url": event.calendar_url,
            "confirmation_image_path": event.confirmation_image_path,
            "location": event.location,
            "event_start": event.event_start.isoformat() if event.event_start else None,
            "event_end": event.event_end.isoformat() if event.event_end else None,
            "event_dates_json": event.event_dates_json,
            "poll_type": event.poll_type,
            "interaction_type": event.interaction_type,
            "website_url": event.website_url,
            "website_label": event.website_label,
            "website_in_group": event.website_in_group,
            "website_in_dm": event.website_in_dm,
            "tickets_url": event.tickets_url,
            "tickets_label": event.tickets_label,
            "tickets_in_group": event.tickets_in_group,
            "tickets_in_dm": event.tickets_in_dm,
            "dm_website_url": event.dm_website_url,
            "dm_website_label": event.dm_website_label,
            "dm_tickets_url": event.dm_tickets_url,
            "dm_tickets_label": event.dm_tickets_label,
            "location_in_group": event.location_in_group,
            "location_in_dm": event.location_in_dm,
            "poll_show_all_day": event.poll_show_all_day,
            "poll_show_maybe": event.poll_show_maybe,
            "poll_show_no": event.poll_show_no,
            "poll_show_yes": event.poll_show_yes,
            "poll_show_dates": event.poll_show_dates,
            "poll_multiple_choice": event.poll_multiple_choice,
            "poll_config_json": event.poll_config_json,
            "send_as_document": event.send_as_document
        }

    })

@bp.route('/api/create-event', methods=['POST'])
@permission_required('manage_events')
def create_event_api():
    event_id = request.form.get('event_id')
    title = request.form.get('title')
    description = request.form.get('description')
    chat_id = request.form.get('chat_id')
    
    # Secure Chat ID change if not allowed
    config_setting = BotSettings.query.filter_by(bot_name='event_bot').first()
    config = json.loads(config_setting.config_json) if config_setting and config_setting.config_json else {}
    default_chat_id = config.get('last_chat_id')
    if not default_chat_id:
        master_bot = BotSettings.query.filter_by(bot_name='id_finder').first()
        if master_bot and master_bot.config_json:
            try:
                m_cfg = json.loads(master_bot.config_json)
                if m_cfg.get('main_group_id'):
                    default_chat_id = str(m_cfg['main_group_id'])
            except:
                pass
    if default_chat_id and str(chat_id) != str(default_chat_id) and not current_user.has_permission('edit_event_chat_id'):
        chat_id = default_chat_id

    topic_id = request.form.get('topic_id')
    should_pin = request.form.get('pin') in ['true', 'on']
    is_silent = request.form.get('silent') in ['true', 'on']
    is_split = request.form.get('split') in ['true', 'on']
    has_spoiler = request.form.get('spoiler') in ['true', 'on']
    remove_image = request.form.get('remove_image') in ['true', 'on']
    scheduled_time_str = request.form.get('scheduled_time')
    image = request.files.get('image')
    
    send_confirmation = request.form.get('send_confirmation') == 'on'
    confirmation_text = request.form.get('confirmation_text')
    calendar_title = request.form.get('calendar_title')
    poll_type = request.form.get('poll_type', 'multi_day') # New multi-day JSON
    interaction_type = request.form.get('interaction_type', 'poll')
    
    # New Link Fields (Group)
    website_url = request.form.get('website_url')
    website_label = request.form.get('website_label')
    tickets_url = request.form.get('tickets_url')
    tickets_label = request.form.get('tickets_label')

    # New Link Fields (DM)
    dm_website_url = request.form.get('dm_website_url')
    dm_website_label = request.form.get('dm_website_label')
    dm_tickets_url = request.form.get('dm_tickets_url')
    dm_tickets_label = request.form.get('dm_tickets_label')
    
    # New Visibility Flags
    website_in_group = request.form.get('website_in_group') == 'on'
    website_in_dm = request.form.get('website_in_dm') == 'on'
    tickets_in_group = request.form.get('tickets_in_group') == 'on'
    tickets_in_dm = request.form.get('tickets_in_dm') == 'on'
    
    # Auto-fix .ics extension
    calendar_filename = request.form.get('calendar_filename', 'termin.ics')
    if calendar_filename and not calendar_filename.lower().endswith('.ics'):
        calendar_filename += '.ics'
    
    # Legacy fields (might still come from old copies or simple single-date posts)
    event_start_str = request.form.get('event_start')
    event_end_str = request.form.get('event_end')
    
    event_start = None
    if event_start_str:
        try: event_start = datetime.fromisoformat(event_start_str.replace('Z', ''))
        except: pass
        
    event_end = None
    if event_end_str:
        try: event_end = datetime.fromisoformat(event_end_str.replace('Z', ''))
        except: pass

    # --- New Fields Extraction ---
    location = request.form.get('location')
    event_dates_json = request.form.get('event_dates')
    poll_config_json = request.form.get('poll_config_json')
    calendar_url = request.form.get('calendar_url')
    send_as_document = request.form.get('send_as_document') == 'on'


    # Poll Visibility Flags
    poll_show_all_day = request.form.get('poll_show_all_day') == 'on'
    poll_show_maybe = request.form.get('poll_show_maybe') == 'on'
    poll_show_no = request.form.get('poll_show_no') == 'on'
    poll_show_yes = request.form.get('poll_show_yes') == 'on'
    poll_show_dates = request.form.get('poll_show_dates') == 'on'
    poll_multiple_choice = request.form.get('poll_multiple_choice') == 'on'

    # Location Visibility Flags
    location_in_group = request.form.get('location_in_group') == 'on'
    location_in_dm = request.form.get('location_in_dm') == 'on'
    
    # Scheduling logic
    scheduled_time = None
    if scheduled_time_str:
        try:
            scheduled_time = datetime.fromisoformat(scheduled_time_str.replace('Z', ''))
        except Exception as e:
            logger.error(f"Error parsing scheduled_time '{scheduled_time_str}': {e}")
            
    # Auto-populate event_start/end from dates JSON if empty
    if event_dates_json and not event_start:
        try:
            dates = json.loads(event_dates_json)
            if dates:
                first = dates[0]
                if first.get('start'):
                    event_start = datetime.fromisoformat(first['start'].replace('Z', ''))
                if first.get('end'):
                    event_end = datetime.fromisoformat(first['end'].replace('Z', ''))
        except: pass

    if not chat_id:
        # Fallback to Master-Bot config
        try:
            config_setting = BotSettings.query.filter_by(bot_name='id_finder').first()
            if config_setting and config_setting.config_json:
                cfg = json.loads(config_setting.config_json)
                chat_id = str(cfg.get('main_group_id') or cfg.get('group_id') or '')
                if chat_id:
                    logger.info(f"EVENT-FIX: Using fallback Chat ID from id_finder settings: {chat_id}")
        except Exception as e:
            logger.error(f"Error in chat_id fallback: {e}")

    if not title or not chat_id:
        err_msg = f"Titel oder Chat-ID fehlt (Titel: {title}, ChatID: {chat_id})"
        logger.warning(f"400 Error in create_event_api: {err_msg}")
        return jsonify({"success": False, "error": "Titel und Chat-ID sind erforderlich."}), 400
    
    try:
        int_chat_id = int(chat_id)
    except:
        return jsonify({"success": False, "error": f"UngÃƒÆ’Ã‚Â¼ltige Chat-ID Format: {chat_id}"}), 400
        
    image_path = None
    media_type = 'photo'
    
    if image and image.filename:
        # Check extension for media type
        ext = image.filename.lower().split('.')[-1]
        if ext == 'svg':
            return jsonify({"success": False, "message": "SVG-Dateien werden von Telegram nicht als Bild unterstÃƒÆ’Ã‚Â¼tzt. Bitte nutze JPG, PNG oder MP4."}), 400
            
        media_type = 'photo'
        if ext in ['mp4', 'mov', 'avi', 'mkv', 'webm']:
            media_type = 'video'
        elif ext in ['gif']:
            media_type = 'animation'
        elif ext not in ['jpg', 'jpeg', 'jfif', 'png', 'webp', 'bmp']:
            return jsonify({"success": False, "message": f"Dateiformat .{ext} wird nicht unterstÃƒÆ’Ã‚Â¼tzt."}), 400
            
        target_dir = os.path.join(PROJECT_ROOT, 'web_dashboard', 'app', 'static', 'uploads', 'events')
        os.makedirs(target_dir, exist_ok=True)
        filename = f"{int(time.time())}_{secure_filename(image.filename)}"
        image.save(os.path.join(target_dir, filename))
        image_path = f"/static/uploads/events/{filename}"
        
    # --- Confirmation Image Handling ---
    confirmation_image = request.files.get('confirmation_image')
    confirmation_image_path = None
    if confirmation_image and confirmation_image.filename:
        ext = confirmation_image.filename.lower().split('.')[-1]
        if ext in ['jpg', 'jpeg', 'jfif', 'png', 'webp', 'bmp']:
            target_dir = os.path.join(PROJECT_ROOT, 'web_dashboard', 'app', 'static', 'uploads', 'events')
            os.makedirs(target_dir, exist_ok=True)
            filename = f"conf_{int(time.time())}_{secure_filename(confirmation_image.filename)}"
            confirmation_image.save(os.path.join(target_dir, filename))
            confirmation_image_path = f"/static/uploads/events/{filename}"
        else:
            return jsonify({"success": False, "message": f"BestÃƒÆ’Ã‚Â¤tigungs-Bild: Format .{ext} wird nicht unterstÃƒÆ’Ã‚Â¼tzt."}), 400
        
    topic_id = request.form.get('topic_id')
    topic_id = topic_id.strip() if topic_id else None
        
    try:
        from ..models import GroupEvent
        
        msg = "Event wurde gespeichert."
        
        if event_id:
            event = GroupEvent.query.get(event_id)
            if not event:
                return jsonify({"success": False, "error": "Event zum Bearbeiten nicht gefunden."}), 404
            
            event.title = title
            event.description = description
            event.chat_id = int_chat_id
            event.topic_id = topic_id
            event.should_pin = should_pin
            event.is_silent = is_silent
            event.is_split = is_split
            event.has_spoiler = has_spoiler
            event.scheduled_time = scheduled_time
            
            event.chat_id = int_chat_id
            event.topic_id = topic_id
            # New fields
            event.send_confirmation = send_confirmation
            event.confirmation_text = confirmation_text
            event.calendar_title = calendar_title
            event.calendar_filename = calendar_filename
            event.calendar_url = calendar_url
            event.location = location
            event.event_start = event_start
            event.event_end = event_end
            event.event_dates_json = event_dates_json
            event.poll_type = poll_type
            event.interaction_type = interaction_type
            event.poll_show_all_day = poll_show_all_day
            event.poll_show_maybe = poll_show_maybe
            event.poll_show_no = poll_show_no
            event.poll_show_yes = poll_show_yes
            event.poll_show_dates = poll_show_dates
            event.poll_multiple_choice = poll_multiple_choice
            event.poll_config_json = poll_config_json
            event.send_as_document = send_as_document

            
            # New fields for links
            event.website_url = website_url
            event.website_label = website_label
            event.tickets_url = tickets_url
            event.tickets_label = tickets_label
            event.dm_website_url = dm_website_url
            event.dm_website_label = dm_website_label
            event.dm_tickets_url = dm_tickets_url
            event.dm_tickets_label = dm_tickets_label

            # Visibility Flags
            event.website_in_group = website_in_group
            event.website_in_dm = website_in_dm
            event.tickets_in_group = tickets_in_group
            event.tickets_in_dm = tickets_in_dm
            event.location_in_group = location_in_group
            event.location_in_dm = location_in_dm

            event.needs_update = True
            
            if remove_image:
                event.image_path = None
                event.media_type = 'photo'
            elif image_path:
                event.image_path = image_path
                event.media_type = media_type
            
            if confirmation_image_path:
                event.confirmation_image_path = confirmation_image_path
            
            # Mark for update in Telegram
            event.needs_update = True
            msg = "Event wurde aktualisiert."
        else:
            new_event = GroupEvent(
                title=title,
                description=description,
                chat_id=int_chat_id,
                topic_id=topic_id,
                should_pin=should_pin,
                is_silent=is_silent,
                is_split=is_split,
                has_spoiler=has_spoiler,
                scheduled_time=scheduled_time,
                image_path=image_path,
                media_type=media_type,
                send_confirmation=send_confirmation,
                confirmation_text=confirmation_text,
                calendar_title=calendar_title,
                calendar_filename=calendar_filename,
                calendar_url=calendar_url,
                confirmation_image_path=confirmation_image_path,
                location=location,
                event_start=event_start,
                event_end=event_end,
                event_dates_json=event_dates_json,
                poll_type=poll_type,
                interaction_type=interaction_type,
                website_url=website_url,
                website_label=website_label,
                tickets_url=tickets_url,
                tickets_label=tickets_label,
                dm_website_url=dm_website_url,
                dm_website_label=dm_website_label,
                dm_tickets_url=dm_tickets_url,
                dm_tickets_label=dm_tickets_label,
                website_in_group=website_in_group,
                website_in_dm=website_in_dm,
                tickets_in_group=tickets_in_group,
                tickets_in_dm=tickets_in_dm,
                location_in_group=location_in_group,
                location_in_dm=location_in_dm,
                poll_show_all_day=poll_show_all_day,
                poll_show_maybe=poll_show_maybe,
                poll_show_no=poll_show_no,
                poll_show_yes=poll_show_yes,
                poll_show_dates=poll_show_dates,
                poll_multiple_choice=poll_multiple_choice,
                poll_config_json=poll_config_json,
                send_as_document=send_as_document
            )
            db.session.add(new_event)
        
        # Save last used IDs
        s = BotSettings.query.filter_by(bot_name='event_bot').first()
        if not s:
            s = BotSettings(bot_name='event_bot', config_json=json.dumps({"is_active": True}))
            db.session.add(s)
        try:
            cfg = json.loads(s.config_json) if s.config_json else {}
        except:
            cfg = {}
        cfg['last_chat_id'] = str(int_chat_id)
        cfg['last_topic_id'] = str(topic_id) if topic_id else ""
        s.config_json = json.dumps(cfg)
        
        db.session.commit()
        
        logger.info(f"Event '{title}' processed in database. Mode: {'Update' if event_id else 'New'}")
        return jsonify({"success": True, "message": msg})
                             
    except Exception as e:
        logger.error(f"Error processing event in database: {e}")
        return jsonify({"success": False, "error": f"Datenbankfehler: {str(e)}"}), 500

@bp.route('/debug/db-path')
@login_required
def debug_db_path():
    from shared_bot_utils import get_db_url
    from ..models import GroupEvent
    events = GroupEvent.query.all()
    ev_list = [{"id": e.id, "title": e.title, "chat": e.chat_id, "msg": e.message_id} for e in events]
    return jsonify({
        "db_url": get_db_url(),
        "event_count": len(events),
        "events": ev_list,
        "env_db": os.environ.get('DATABASE_URL')
    })

# --- BOT API ROUTES ---
@bp.route('/api/bot/save-config', methods=['POST'])
@login_required
def save_bot_config_api():
    data = request.json
    bot_name = data.get('bot_name')
    config_update = data.get('config')
    
    if not bot_name or config_update is None:
        return jsonify({"success": False, "error": "Missing data"}), 400
        
    s = BotSettings.query.filter_by(bot_name=bot_name).first()
    if not s:
        s = BotSettings(bot_name=bot_name, config_json=json.dumps(config_update))
        db.session.add(s)
    else:
        try:
            current_cfg = json.loads(s.config_json)
        except:
            current_cfg = {}
        current_cfg.update(config_update)
        s.config_json = json.dumps(current_cfg)
        
    db.session.commit()
    
    # --- AUDIT LOG ---
    from ..utils import log_audit
    clean_config = config_update.copy() if isinstance(config_update, dict) else {}
    for token_key in ['bot_token', 'token', 'BOT_TOKEN', 'api_token']:
        if token_key in clean_config:
            clean_config[token_key] = "********"
    log_audit("Bot-Konfiguration gespeichert", f"Die Einstellungen fÃƒÆ’Ã‚Â¼r das Modul '{bot_name}' wurden geÃƒÆ’Ã‚Â¤ndert. GeÃƒÆ’Ã‚Â¤nderte Felder: {list(clean_config.keys())}")
    
    return jsonify({"success": True})

@bp.route('/api/bot/stats/<bot_name>', methods=['GET'])
@login_required
def get_bot_stats(bot_name):
    if bot_name == 'report_bot':
        try:
            from ..models import ReportedMessage
            count = ReportedMessage.query.count()
            return jsonify({"success": True, "count": count})
        except:
            return jsonify({"success": False, "error": "Table not found"}), 404
            
    elif bot_name == 'event_bot':
        try:
            from ..models import GroupEvent
            count = GroupEvent.query.count()
            return jsonify({"success": True, "count": count})
        except:
            return jsonify({"success": False, "error": "Table not found"}), 404
            
    return jsonify({"success": False, "error": "Unknown bot"}), 400

@bp.route('/api/bot/toggle', methods=['POST'])
@login_required
def toggle_bot_api():
    data = request.json
    bot_name = data.get('bot_name')
    active = data.get('active', False)
    
    s = BotSettings.query.filter_by(bot_name=bot_name).first()
    if not s:
        cfg = {"is_active": active}
        s = BotSettings(bot_name=bot_name, config_json=json.dumps(cfg))
        db.session.add(s)
    else:
        try:
            cfg = json.loads(s.config_json)
        except:
            cfg = {}
        cfg['is_active'] = active
        s.config_json = json.dumps(cfg)
        
    db.session.commit()
    
    # --- AUDIT LOG ---
    from ..utils import log_audit
    status_text = "aktiviert" if active else "deaktiviert"
    log_audit("Modul toggeln", f"Das Modul '{bot_name}' wurde ÃƒÆ’Ã‚Â¼ber die API {status_text}.")
    
    return jsonify({"success": True})

# --- REPORT BOT SETTINGS ---

@bp.route('/report-settings', methods=['GET', 'POST'])
@permission_required('manage_reports')
def report_settings():
    from ..models import ReportedMessage
    config_setting = BotSettings.query.filter_by(bot_name='report_bot').first()
    config = json.loads(config_setting.config_json) if config_setting and config_setting.config_json else {}
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_config':
            target_chat_id = request.form.get('target_chat_id')
            target_topic_id = request.form.get('target_topic_id')
            
            if not current_user.has_permission('edit_report_chat_id'):
                # Silently ignore attempts to modify, or fallback if fields were disabled/omitted by the browser
                target_chat_id = config.get('target_chat_id')
                target_topic_id = config.get('target_topic_id')
                
            new_config = {
                "target_chat_id": target_chat_id,
                "target_topic_id": target_topic_id,
                "is_active": config.get('is_active', False)
            }
            if not config_setting:
                config_setting = BotSettings(bot_name='report_bot')
                db.session.add(config_setting)
            config_setting.config_json = json.dumps(new_config)
            db.session.commit()
            flash('Konfiguration gespeichert!', 'success')
            return redirect(url_for('dashboard.report_settings'))
            
        elif action == 'dismiss_report':
            report_id = request.form.get('report_id')
            report = ReportedMessage.query.get(report_id)
            if report:
                report.status = 'dismissed'
                db.session.commit()
                flash('Bericht als erledigt markiert.', 'success')
            return redirect(url_for('dashboard.report_settings'))
            
        elif action == 'process_report':
            report_id = request.form.get('report_id')
            report = ReportedMessage.query.get(report_id)
            if report:
                report.status = 'processed'
                db.session.commit()
                flash('Bericht in Bearbeitung.', 'info')
            return redirect(url_for('dashboard.report_settings'))

        elif action == 'clear_reports':
            ReportedMessage.query.delete()
            db.session.commit()
            flash('Alle Berichte wurden gelÃƒÆ’Ã‚Â¶scht.', 'info')
            return redirect(url_for('dashboard.report_settings'))

    reports = ReportedMessage.query.order_by(ReportedMessage.timestamp.desc()).all()
    return render_template('report_settings.html', config=config, reports=reports)

# --- EVENT PLANNER SETTINGS ---

@bp.route('/event-settings', methods=['GET', 'POST'])
@permission_required('manage_events')
def event_settings():
    from ..models import GroupEvent
    config_setting = BotSettings.query.filter_by(bot_name='event_bot').first()
    config = json.loads(config_setting.config_json) if config_setting and config_setting.config_json else {}
    
    # Fallback to Master-Bot Chat-ID if not set yet (first use)
    if not config.get('last_chat_id'):
        master_bot = BotSettings.query.filter_by(bot_name='id_finder').first()
        if master_bot and master_bot.config_json:
            try:
                m_cfg = json.loads(master_bot.config_json)
                if m_cfg.get('main_group_id'):
                    config['last_chat_id'] = str(m_cfg['main_group_id'])
            except:
                pass
    
    if request.method == 'POST':
        action = request.form.get('action')
        logger.info(f"Event Settings POST: action={action}, event_id={request.form.get('event_id')}")
        if action == 'delete_event':
            event_id = request.form.get('event_id')
            try:
                event_id_int = int(event_id)
                event = GroupEvent.query.get(event_id_int)
                if event:
                    logger.info(f"Deleting event {event_id_int}: {event.title}")
                    db.session.delete(event)
                    db.session.commit()
                    flash('Event wurde gelÃƒÆ’Ã‚Â¶scht.', 'info')
                else:
                    logger.warning(f"Event {event_id_int} not found for deletion.")
            except Exception as e:
                logger.error(f"Error during event deletion: {e}")
            return redirect(url_for('dashboard.event_settings'))

    events = GroupEvent.query.order_by(GroupEvent.created_at.desc()).all()
    
    from ..models import TopicMapping, IDFinderUser, InviteApplication
    ts = TopicMapping.query.all()
    known_topics = {str(t.topic_id): t.topic_name for t in ts}
    
    # 1. Start with Profile-Images from IDFinderUser
    user_photos = {u.telegram_id: u.photo_url for u in IDFinderUser.query.filter(IDFinderUser.photo_url != None).all()}
    
    # 2. Add fallback from IDFinderUser file_ids (cached Telegram pics)
    for u in IDFinderUser.query.filter(IDFinderUser.photo_file_id != None).all():
        if u.telegram_id not in user_photos:
            user_photos[u.telegram_id] = url_for('dashboard.telegram_image', file_id=u.photo_file_id)

    # 3. Last fallback: Check Steckbrief (InviteApplication) for uploaded photos
    apps = InviteApplication.query.all()
    for app in apps:
        if app.telegram_user_id not in user_photos:
            answers = app.answers
            # Look for common photo keys in answers_json
            for key in ['photo_id', 'photo', 'profilbild', 'bild', 'Steckbrief Bild']:
                if key in answers and answers[key]:
                    # If it's a path or file_id, we try to map it
                    val = str(answers[key])
                    if val.startswith('http'):
                        user_photos[app.telegram_user_id] = val
                    elif '.' in val: # Likely a path like 'uploads/...'
                        user_photos[app.telegram_user_id] = url_for('static', filename=val.replace('static/',''))
                    else: # Likely a file_id
                        user_photos[app.telegram_user_id] = url_for('dashboard.telegram_image', file_id=val)
                    break

    # 4. Get all uploaded event media
    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'events')
    upload_images = []
    if os.path.exists(upload_dir):
        for f in os.listdir(upload_dir):
            if os.path.isfile(os.path.join(upload_dir, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mov', '.svg')):
                upload_images.append(f)

    return render_template('event_settings.html', config=config, events=events, known_topics=known_topics, user_photos=user_photos, upload_images=upload_images)

@bp.route('/api/event-logs')
@login_required
def get_event_logs():
    import os
    from flask import jsonify
    
    # Try reading event_bot.log first
    log_path = os.path.join(current_app.root_path, '..', 'bots', 'event_bot', 'event_bot.log')
    if not os.path.exists(log_path):
        # Fallback: check central logs folder
        log_path = os.path.join(current_app.root_path, '..', 'logs', 'event_bot.log')
        
    if not os.path.exists(log_path):
        # Fallback 2: read from main_bot.log and filter for 'event_bot'
        main_log = os.path.join(current_app.root_path, '..', 'logs', 'main_bot.log')
        if os.path.exists(main_log):
            try:
                filtered = []
                with open(main_log, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if 'event_bot' in line:
                            filtered.append(line)
                if filtered:
                    return jsonify({"logs": "".join(filtered[-100:])})
            except Exception as e:
                return jsonify({"logs": f"Fehler beim Filtern der Logs: {e}"})
        return jsonify({"logs": "Keine Log-Datei gefunden."})
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            return jsonify({"logs": "".join(lines[-100:])})
    except Exception as e:
        return jsonify({"logs": f"Fehler beim Lesen der Logs: {e}"})

@bp.route('/bot-settings/profile/repost/<int:profile_id>', methods=['POST'])
@login_required
def profile_repost(profile_id):
    from ..models import InviteApplication
    app = InviteApplication.query.get(profile_id)
    if app:
        # Create a trigger file so the background process can pick it up, or we can just send it manually.
        # But invite_bot doesn't have a background process for reposts. We must just trigger it somehow.
        # Actually it's easier to set its status to a special 'repost_pending' and let the updater loop handle it,
        # OR we can just write a file that a new bot function will check.
        # For simplicity, let's write a file and the bot checking it will handle it.
        tfile = os.path.join(PROJECT_ROOT, 'instance', f'repost_{profile_id}.tmp')
        with open(tfile, 'w') as f: f.write('1')
        flash('Befehl zum erneuten Posten des Steckbriefs gesendet.', 'success')
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/profile/edit/<int:profile_id>', methods=['POST'])
@login_required
def profile_edit(profile_id):
    from ..models import InviteApplication
    app = InviteApplication.query.get(profile_id)
    if app:
        new_answers = request.form.get('answers_json')
        try:
            app.answers = json.loads(new_answers)
            # wir setzen das updated_at Datum damit es oben steht
            app.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Steckbrief erfolgreich bearbeitet! Vergiss nicht, ihn neu zu posten, damit die ÃƒÆ’Ã¢â‚¬Å¾nderungen live gehen!', 'success')
        except Exception as e:
            flash(f'Fehler beim Speichern der Antworten: {e}', 'danger')
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/profile/delete/<int:profile_id>', methods=['POST'])
@login_required
def profile_delete(profile_id):
    from ..models import InviteApplication
    app = InviteApplication.query.get(profile_id)
    if app:
        try:
            db.session.delete(app)
            db.session.commit()
            flash('Steckbrief erfolgreich gelÃƒÆ’Ã‚Â¶scht.', 'success')
        except Exception as e:
            flash(f'Fehler beim LÃƒÆ’Ã‚Â¶schen des Steckbriefs: {e}', 'danger')
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/profile/unblock/<int:profile_id>', methods=['POST'])
@login_required
def profile_unblock(profile_id):
    from ..models import InviteApplication
    app = InviteApplication.query.get(profile_id)
    if app:
        try:
            app.status = 'rejected'
            db.session.commit()
            flash(f'Nutzer {app.full_name or app.username or app.telegram_user_id} wurde erfolgreich entsperrt.', 'success')
        except Exception as e:
            flash(f'Fehler beim Entsperren des Nutzers: {e}', 'danger')
    return redirect(url_for('dashboard.bot_settings') + '#blocklist-panel')

@bp.route('/api/events/export/<int:event_id>')
@login_required
def export_event_participants(event_id):
    from ..models import GroupEvent
    import csv
    import io
    from flask import Response
    
    event = GroupEvent.query.get_or_404(event_id)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    
    # Header
    writer.writerow(['Name/Username', 'Telegram ID', 'Status', 'Gemeldet am'])
    
    for rsvp in event.rsvps:
        writer.writerow([
            rsvp.username or 'Unbekannt',
            rsvp.telegram_user_id,
            rsvp.status.upper(),
            rsvp.updated_at.strftime('%Y-%m-%d %H:%M') if rsvp.updated_at else '-'
        ])
    
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=event_{event_id}_participants.csv'
    return response

@bp.route('/api/avatar/<int:user_id>')
@login_required
def get_user_avatar(user_id):
    """Liefert das Profilbild eines Users aus der Datenbank oder einen Platzhalter."""
    global AVATAR_CACHE
    import time
    now = time.time()
    
    # Check cache (valid for 300 seconds / 5 minutes)
    if user_id in AVATAR_CACHE:
        cached_val, cached_time = AVATAR_CACHE[user_id]
        if now - cached_time < 300:
            if isinstance(cached_val, dict):
                photo_url = cached_val.get('photo_url')
                photo_file_id = cached_val.get('photo_file_id')
                username = cached_val.get('username')
                custom_name = cached_val.get('custom_name')
                
                if photo_url:
                    return redirect(photo_url)
                if photo_file_id:
                    return redirect(url_for('dashboard.telegram_image', file_id=photo_file_id))
                
                name = custom_name if custom_name else (username if username else "U")
                return redirect(f'https://ui-avatars.com/api/?name={name}&background=random')

    # If not in cache or expired, query database
    from ..models import IDFinderUser
    try:
        user = IDFinderUser.query.filter_by(telegram_id=user_id).first()
        if user:
            cache_entry = {
                'photo_url': user.photo_url,
                'photo_file_id': user.photo_file_id,
                'username': user.username,
                'custom_name': user.custom_name
            }
            AVATAR_CACHE[user_id] = (cache_entry, now)
            
            if user.photo_url:
                return redirect(user.photo_url)
            if user.photo_file_id:
                return redirect(url_for('dashboard.telegram_image', file_id=user.photo_file_id))
            
            name = user.custom_name if user.custom_name else (user.username if user else "U")
            return redirect(f'https://ui-avatars.com/api/?name={name}&background=random')
        else:
            # User not found in DB
            AVATAR_CACHE[user_id] = (None, now)
    except Exception as e:
        # On DB error, don't crash, try to fallback to a placeholder
        pass
        
    return redirect(f'https://ui-avatars.com/api/?name=U&background=random')

@bp.route('/ip-locks')
@admin_required
def ip_locks():
    from ..models import LoginTracker, LoginAudit, AuditLog
    trackers = LoginTracker.query.order_by(LoginTracker.last_attempt.desc()).all()
    login_audits = LoginAudit.query.order_by(LoginAudit.login_time.desc()).all()
    audit_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    return render_template('ip_locks.html', trackers=trackers, login_audits=login_audits, audit_logs=audit_logs, now=datetime.utcnow())

@bp.route('/ip-locks/delete/<int:tracker_id>', methods=['POST'])
@admin_required
def delete_ip_lock(tracker_id):
    from ..models import LoginTracker
    tracker = LoginTracker.query.get_or_404(tracker_id)
    ip = tracker.ip_address
    try:
        db.session.delete(tracker)
        db.session.commit()
        
        # --- AUDIT LOG ---
        from ..utils import log_audit
        log_audit("IP-Adresse freigegeben", f"Die blockierte IP-Adresse {ip} wurde manuell entsperrt.")
        
        flash(f'Die IP-Adresse {ip} wurde erfolgreich entsperrt.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim Entsperren der IP-Adresse: {e}', 'danger')
    return redirect(url_for('dashboard.ip_locks'))
# --- REACTION BOT ROUTES ---
@bp.route('/reaction-settings')
@login_required
def reaction_settings():
    s = BotSettings.query.filter_by(bot_name='reaction_bot').first()
    if not s:
        cfg = {"is_active": False, "rules": []}
        s = BotSettings(bot_name='reaction_bot', config_json=json.dumps(cfg))
        db.session.add(s)
        db.session.commit()
    
    cfg = json.loads(s.config_json) if s.config_json else {"is_active": False, "rules": []}
    return render_template('reaction_settings.html', rules=cfg.get('rules', []), is_running=cfg.get('is_active', False))

@bp.route('/api/reaction-bot/add', methods=['POST'])
@login_required
def reaction_add():
    data = request.json
    s = BotSettings.query.filter_by(bot_name='reaction_bot').first()
    cfg = json.loads(s.config_json) if s.config_json else {"is_active": False, "rules": []}
    
    chat_type = data.get('chat_type', 'all')
    
    # Check for duplicates
    for rule in cfg.get('rules', []):
        if rule.get('trigger_type') == data.get('trigger_type') and \
           rule.get('trigger_text', '').lower() == data.get('trigger_text', '').lower() and \
           rule.get('chat_type', 'all') == chat_type:
            return jsonify({"success": False, "error": "Eine Regel fÃƒÆ’Ã‚Â¼r diesen AuslÃƒÆ’Ã‚Â¶ser und Chat-Typ existiert bereits."})
            
    cfg.setdefault('rules', []).append({
        'trigger_type': data.get('trigger_type'),
        'trigger_text': data.get('trigger_text', ''),
        'reaction_type': data.get('reaction_type'),
        'reaction_emoji': data.get('reaction_emoji'),
        'secondary_emoji': data.get('secondary_emoji', ''),
        'chat_type': chat_type,
        'is_active': True
    })
    s.config_json = json.dumps(cfg)
    db.session.commit()
    
    from ..utils import log_audit
    log_audit("Reaktion/Effekt hinzugefÃƒÂ¯Ã‚Â¿Ã‚Â½gt", f"Typ: {data.get('trigger_type')}, Aktion: {data.get('reaction_emoji')}")
    
    return jsonify({"success": True})

@bp.route('/api/reaction-bot/edit/<int:idx>', methods=['POST'])
@login_required
def reaction_edit(idx):
    data = request.json
    s = BotSettings.query.filter_by(bot_name='reaction_bot').first()
    cfg = json.loads(s.config_json)
    
    if 'rules' in cfg and 0 <= idx < len(cfg['rules']):
        # Check for duplicates excluding current rule
        chat_type = data.get('chat_type', 'all')
        for i, rule in enumerate(cfg['rules']):
            if i != idx and \
               rule.get('trigger_type') == data.get('trigger_type') and \
               rule.get('trigger_text', '').lower() == data.get('trigger_text', '').lower() and \
               rule.get('chat_type', 'all') == chat_type:
                return jsonify({"success": False, "error": "Eine andere Regel fÃƒÆ’Ã‚Â¼r diesen AuslÃƒÆ’Ã‚Â¶ser und Chat-Typ existiert bereits."})
        
        cfg['rules'][idx].update({
            'trigger_type': data.get('trigger_type'),
            'trigger_text': data.get('trigger_text', ''),
            'reaction_type': data.get('reaction_type'),
            'reaction_emoji': data.get('reaction_emoji'),
            'secondary_emoji': data.get('secondary_emoji', ''),
            'chat_type': chat_type
        })
        s.config_json = json.dumps(cfg)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Regel nicht gefunden."})

@bp.route('/api/reaction-bot/delete/<int:idx>', methods=['POST'])
@login_required
def reaction_delete(idx):
    s = BotSettings.query.filter_by(bot_name='reaction_bot').first()
    cfg = json.loads(s.config_json)
    
    if 0 <= idx < len(cfg.get('rules', [])):
        cfg['rules'].pop(idx)
        s.config_json = json.dumps(cfg)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Index out of range"})

@bp.route('/api/reaction-bot/toggle/<int:idx>', methods=['POST'])
@login_required
def reaction_toggle(idx):
    s = BotSettings.query.filter_by(bot_name='reaction_bot').first()
    cfg = json.loads(s.config_json)
    
    if 0 <= idx < len(cfg.get('rules', [])):
        cfg['rules'][idx]['is_active'] = not cfg['rules'][idx]['is_active']
        s.config_json = json.dumps(cfg)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Index out of range"})










# --- RSS Feed Routes ---
@bp.route('/bot-settings/rss-feed/add', methods=['POST'])
@admin_required
def add_rss_feed():
    from ..models import RSSFeedConfig
    name = request.form.get('name')
    url = request.form.get('url')
    admin_chat_id = request.form.get('admin_chat_id')
    admin_topic_id = request.form.get('admin_topic_id')
    target_chat_id = request.form.get('target_chat_id')
    target_topic_id = request.form.get('target_topic_id')
    auto_post_timeout_hours = request.form.get('auto_post_timeout_hours', 24, type=int)
    include_images = 'include_images' in request.form
    
    if name and url and admin_chat_id and target_chat_id:
        new_feed = RSSFeedConfig(
            name=name,
            url=url,
            admin_chat_id=admin_chat_id,
            admin_topic_id=admin_topic_id,
            target_chat_id=target_chat_id,
            target_topic_id=target_topic_id,
            auto_post_timeout_hours=auto_post_timeout_hours,
            include_images=include_images
        )
        db.session.add(new_feed)
        db.session.commit()
        flash('RSS Feed erfolgreich hinzugefÃ¼gt.', 'success')
    else:
        flash('Bitte alle Pflichtfelder ausfÃ¼llen.', 'danger')
        
    return redirect(url_for('dashboard.rss_feeds_dashboard'))

@bp.route('/bot-settings/rss-feed/toggle', methods=['POST'])
@admin_required
def toggle_rss_feed():
    from ..models import RSSFeedConfig
    feed_id = request.form.get('feed_id')
    feed = RSSFeedConfig.query.get(feed_id)
    if feed:
        feed.is_active = not feed.is_active
        db.session.commit()
        flash(f'RSS Feed "{feed.name}" wurde {"aktiviert" if feed.is_active else "deaktiviert"}.', 'success')
    return redirect(url_for('dashboard.rss_feeds_dashboard'))

@bp.route('/bot-settings/rss-feed/delete', methods=['POST'])
@admin_required
def delete_rss_feed():
    from ..models import RSSFeedConfig
    feed_id = request.form.get('feed_id')
    feed = RSSFeedConfig.query.get(feed_id)
    if feed:
        db.session.delete(feed)
        db.session.commit()
        flash('RSS Feed gelÃ¶scht.', 'success')
    return redirect(url_for('dashboard.rss_feeds_dashboard'))

@bp.route('/rss-feed')
@admin_required
def rss_feeds_dashboard():
    from ..models import RSSFeedConfig, RSSFeedItem
    rss_feeds = RSSFeedConfig.query.all()
    rss_items = RSSFeedItem.query.order_by(RSSFeedItem.created_at.desc()).limit(100).all()
    return render_template('rss_feeds.html', rss_feeds=rss_feeds, rss_items=rss_items)


@bp.route('/rss-feed/update', methods=['POST'])
@admin_required
def update_rss_feed():
    from ..models import RSSFeedConfig
    feed_id = request.form.get('feed_id')
    feed = RSSFeedConfig.query.get(feed_id)
    if feed:
        feed.name = request.form.get('name', feed.name)
        feed.url = request.form.get('url', feed.url)
        feed.admin_chat_id = request.form.get('admin_chat_id', feed.admin_chat_id)
        feed.admin_topic_id = request.form.get('admin_topic_id') or None
        feed.target_chat_id = request.form.get('target_chat_id', feed.target_chat_id)
        feed.target_topic_id = request.form.get('target_topic_id') or None
        feed.auto_post_timeout_hours = request.form.get('auto_post_timeout_hours', 24, type=int)
        feed.include_images = 'include_images' in request.form
        feed.check_interval_minutes = request.form.get('check_interval_minutes', 30, type=int)
        feed.post_time = request.form.get('post_time') or None
        db.session.commit()
        flash(f'RSS Feed "{feed.name}" gespeichert.', 'success')
    return redirect(url_for('dashboard.rss_feeds_dashboard'))

@bp.route('/rss-feed/manual-post', methods=['POST'])
@admin_required
def manual_post_rss():
    from ..models import RSSFeedItem
    item_id = request.form.get('item_id')
    item = RSSFeedItem.query.get(item_id)
    if item:
        item.status = 'approved'
        db.session.commit()
        flash(f'Artikel "{item.title}" wurde genehmigt und wird in Kuerze gepostet.', 'success')
    return redirect(url_for('dashboard.rss_feeds_dashboard'))

@bp.route('/rss-feed/reject', methods=['POST'])
@admin_required
def reject_rss_item():
    from ..models import RSSFeedItem
    item_id = request.form.get('item_id')
    item = RSSFeedItem.query.get(item_id)
    if item:
        item.status = 'rejected'
        db.session.commit()
        flash(f'Artikel "{item.title}" wurde manuell abgelehnt.', 'warning')
    return redirect(url_for('dashboard.rss_feeds_dashboard'))


@bp.route('/rss-feed/preview/<int:item_id>')
@admin_required
def preview_rss_item(item_id):
    from ..models import RSSFeedItem
    item = RSSFeedItem.query.get_or_404(item_id)
    
    import urllib.request
    import xml.etree.ElementTree as ET
    import html, re
    import sys
    sys.path.insert(0, r'c:\Users\Ronny M PC\Desktop\Telegramm-BotEngelbertStrauss-Gruppe-V1.9.50-2.9.21')
    try:
        from bots.rss_bot.rss_bot import get_images
    except:
        get_images = lambda url: []
    
    NS = {"a": "http://www.w3.org/2005/Atom"}
    summary = "Keine Zusammenfassung gefunden."
    
    try:
        req = urllib.request.Request(item.feed.url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            xml_data = r.read().decode("utf-8", "replace")
        root = ET.fromstring(xml_data)
        for e in root.findall("a:entry", NS):
            link = ""
            for l in e.findall("a:link", NS):
                if l.get("rel", "alternate") == "alternate":
                    link = l.get("href", "")
            guid = (e.findtext("a:id", "", NS) or link).strip()
            if guid == item.guid:
                raw_summary = e.findtext("a:summary", "", NS) or e.findtext("a:content", "", NS) or ""
                s = re.sub(r"<(br|/p|/div|/li)[^>]*>", "\n", raw_summary or "", flags=re.I)
                s = re.sub(r"<[^>]+>", "", s)
                s = html.unescape(s)
                s = re.sub(r"[ \t\xa0]+", " ", s)
                summary = re.sub(r"\n\s*\n+", "\n\n", s).strip()
                break
    except Exception as e:
        summary = f"Fehler beim Laden der Vorschau: {e}"

    images = get_images(item.link)
    first_image = images[0] if images else None

    date_str = item.pub_date.strftime("%Y-%m-%d") if item.pub_date else ""
    if len(date_str) == 10:
        date_de = f"{date_str[8:10]}.{date_str[5:7]}.{date_str[0:4]}"
    else:
        date_de = date_str
        
    head = f"<blockquote><b>{html.escape(item.feed.name)}</b>\n<i>{date_de}</i></blockquote>\n\n"
    head += f"<b>{html.escape(item.title)}</b>\n\n"
    
    body = html.escape(summary)
    body = re.sub(r'\n{3,}', '\n\n', body)
    
    foot = f'\n\n<a href="{html.escape(item.link)}">➡️ Zur Pressemitteilung</a>'
    
    telegram_text = head + body + foot
    
    # Telegram-like HTML formatting
    web_html = telegram_text.replace('\n', '<br>')
    
    # Convert blockquote to look like Telegram's native quote
    web_html = web_html.replace('<blockquote>', '<div style="border-left: 3px solid #3b82f6; background: rgba(59,130,246,0.1); padding: 4px 10px; margin-bottom: 8px; border-radius: 0 6px 6px 0;">')
    web_html = web_html.replace('</blockquote>', '</div>')
    
    # Wrap in Telegram bubble layout
    final_html = '<div style="background-color: #2b5278; border-radius: 12px; max-width: 450px; margin: 0 auto; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.3);">'
    
    if first_image:
        final_html += f'<img src="{first_image}" style="width: 100%; height: auto; max-height: 250px; object-fit: cover; display: block;">'
        
    final_html += f'<div style="padding: 12px 14px; color: #fff; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, Helvetica, Arial, sans-serif; font-size: 15px; line-height: 1.4;">{web_html}</div></div>'
    
    return {'html': final_html}

