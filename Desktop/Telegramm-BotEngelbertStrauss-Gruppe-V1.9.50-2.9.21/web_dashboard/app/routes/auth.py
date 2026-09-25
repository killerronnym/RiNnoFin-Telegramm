import os
import requests
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from ..models import db, User, LoginTracker, LoginAudit

bp = Blueprint('auth', __name__, url_prefix='/auth')

def send_telegram_security_alert(ip, username, attempts, status):
    try:
        from shared_bot_utils import get_bot_token
        token = get_bot_token()
    except Exception as e:
        print(f"Error importing shared_bot_utils: {e}")
        token = current_app.config.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN') or os.environ.get('BOT_TOKEN')
        
    group_id = "-1003372573784"
    topic_id = 3
    
    if not token or not group_id:
        print("Telegram warning failed: No token or group_id found.")
        return False
        
    msg = (
        "🚨 **SICHERHEITSALARM: DASHBOARD-ANGRIFF** 🚨\n\n"
        "Es wurde ein unbefugter Login-Versuch auf dem Dashboard registriert!\n\n"
        f"👤 **Eingegebener Benutzer:** `{username}`\n"
        f"🌐 **IP-Adresse:** `{ip}`\n"
        f"❌ **Fehlversuche:** `{attempts}`\n"
        f"🔒 **Status:** `{status}`\n"
        f"📅 **Server-Zeit:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    
    payload = {
        "chat_id": group_id,
        "text": msg,
        "parse_mode": "Markdown",
        "message_thread_id": int(topic_id)
    }
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"Telegram Alert sent. Status: {r.status_code}, Response: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error sending Telegram alert: {e}")
        return False

@bp.route('/login', methods=('GET', 'POST'))
def login():
    # IP-Adresse des Besuchers ermitteln (unterstützt Reverse Proxies)
    from ..utils import get_client_ip
    ip = get_client_ip()
        
    # IP-Status in der Datenbank prüfen
    tracker = LoginTracker.query.filter_by(ip_address=ip).first()
    now = datetime.utcnow()
    
    if tracker:
        # LOGIN-SPERRE TEMPORÄR DEAKTIVIERT FÜR TEST
        pass
        """
        # 1. Permanenter Ban
        if tracker.is_permanently_blocked:
            flash('Diese IP-Adresse wurde wegen wiederholter Fehlversuche dauerhaft gesperrt.', 'danger')
            return render_template('login.html')
            
        # 2. Temporärer Timeout
        if tracker.blocked_until and tracker.blocked_until > now:
            remaining_seconds = int((tracker.blocked_until - now).total_seconds())
            if remaining_seconds > 60:
                remaining_minutes = int(remaining_seconds / 60)
                flash(f'Zu viele Fehlversuche. Diese IP-Adresse ist für noch {remaining_minutes} Minuten gesperrt.', 'danger')
            else:
                flash(f'Zu viele Fehlversuche. Bitte warte noch {remaining_seconds} Sekunden.', 'danger')
            return render_template('login.html')
        """
 
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if user.two_factor_enabled and getattr(user, 'two_factor_login_enabled', True):
                session['pending_2fa_user_id'] = user.id
                return redirect(url_for('auth.login_2fa'))
                
            # Login erfolgreich! Tracker zurücksetzen
            if tracker:
                tracker.attempts = 0
                tracker.blocked_until = None
                tracker.is_permanently_blocked = False
                db.session.commit()
                
            login_user(user)
            
            # Successful Login Audit Log
            try:
                audit = LoginAudit(user_id=user.id, username=user.username, ip_address=ip)
                db.session.add(audit)
                db.session.commit()
                session['login_audit_id'] = audit.id
            except Exception as e:
                db.session.rollback()
                print(f"Error creating LoginAudit: {e}")
                
            # Write to central AuditLog
            try:
                from ..utils import log_audit
                log_audit("Dashboard Login", f"Benutzer '{user.username}' hat sich erfolgreich angemeldet.")
            except Exception as e:
                print(f"Error logging successful login to AuditLog: {e}")
                
            return redirect(url_for('dashboard.index'))
            
        # Login fehlgeschlagen!
        if not tracker:
            tracker = LoginTracker(ip_address=ip, attempts=0)
            db.session.add(tracker)
            
        tracker.attempts += 1
        tracker.last_attempt = now
        
        status_msg = "Keine Sperre"
        
        # Sperrstufen anwenden
        if tracker.attempts == 3:
            # 1. Stufe: 30 Sekunden sperren + Telegram-Alarm
            tracker.blocked_until = now + timedelta(seconds=30)
            status_msg = "30 Sekunden gesperrt (Temporär) ⏳"
            flash('Ungültiger Benutzername oder Passwort. Diese IP wurde für 30 Sekunden gesperrt.', 'danger')
            
            try:
                send_telegram_security_alert(ip, username, tracker.attempts, status_msg)
            except Exception as e:
                print(f"Failed to send Telegram alert: {e}")
        elif tracker.attempts == 4:
            # 2. Stufe: 30 Minuten sperren + Telegram-Alarm
            tracker.blocked_until = now + timedelta(minutes=30)
            status_msg = "30 Minuten gesperrt (Temporär) ⏳"
            flash('Ungültiger Benutzername oder Passwort. Diese IP wurde für 30 Minuten gesperrt.', 'danger')
            
            try:
                send_telegram_security_alert(ip, username, tracker.attempts, status_msg)
            except Exception as e:
                print(f"Failed to send Telegram alert: {e}")
        elif tracker.attempts >= 5:
            # 3. Stufe: Dauerhaft sperren + Telegram-Alarm
            tracker.is_permanently_blocked = True
            status_msg = "Dauerhaft gesperrt (Banned) 🚨"
            flash('Ungültiger Benutzername oder Passwort. Diese IP wurde dauerhaft gesperrt.', 'danger')
            
            try:
                send_telegram_security_alert(ip, username, tracker.attempts, status_msg)
            except Exception as e:
                print(f"Failed to send Telegram alert: {e}")
        else:
            flash('Ungültiger Benutzername oder Passwort.', 'danger')
            
        db.session.commit()
        return redirect(url_for('auth.login'))
        
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    # Update Logout Time
    audit_id = session.get('login_audit_id')
    if audit_id:
        try:
            audit = db.session.get(LoginAudit, audit_id)
            if audit:
                audit.logout_time = datetime.utcnow()
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error logging logout time: {e}")
            
    try:
        from ..utils import log_audit
        log_audit("Dashboard Logout", f"Benutzer '{current_user.username}' hat sich abgemeldet.")
    except Exception as e:
        print(f"Error logging logout to AuditLog: {e}")
        
    logout_user()
    flash('Du wurdest erfolgreich abgemeldet.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/change-password', methods=('GET', 'POST'))
@login_required
def change_password_required():
    if not current_user.must_change_password:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        
        if not password or not confirm:
            flash('Bitte fülle alle Felder aus.', 'danger')
            return render_template('change_password_required.html')
            
        if password != confirm:
            flash('Die Passwörter stimmen nicht überein.', 'danger')
            return render_template('change_password_required.html')
            
        import re
        if len(password) < 8:
            flash('Das Passwort muss mindestens 8 Zeichen lang sein.', 'danger')
            return render_template('change_password_required.html')
            
        if not re.search(r'[A-Z]', password):
            flash('Das Passwort muss mindestens einen Großbuchstaben enthalten.', 'danger')
            return render_template('change_password_required.html')
            
        if not re.search(r'[0-9]', password):
            flash('Das Passwort muss mindestens eine Zahl enthalten.', 'danger')
            return render_template('change_password_required.html')
            
        if not re.search(r'[^a-zA-Z0-9]', password):
            flash('Das Passwort muss mindestens ein Sonderzeichen enthalten.', 'danger')
            return render_template('change_password_required.html')
            
        try:
            current_user.set_password(password)
            current_user.must_change_password = False
            db.session.commit()
            
            # Audit log
            from ..utils import log_audit
            log_audit("Passwort initialisiert", f"Benutzer '{current_user.username}' hat sein Initialpasswort erfolgreich geändert.")
            
            flash('Dein Passwort wurde erfolgreich aktualisiert! Du bist nun vollständig angemeldet.', 'success')
            return redirect(url_for('dashboard.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler beim Aktualisieren des Passworts: {e}', 'danger')
            
    return render_template('change_password_required.html')

@bp.route('/login/2fa', methods=('GET', 'POST'))
def login_2fa():
    if 'pending_2fa_user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user = db.session.get(User, session['pending_2fa_user_id'])
    if not user:
        session.pop('pending_2fa_user_id', None)
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        code = request.form.get('totp_code')
        import pyotp
        totp = pyotp.TOTP(user.totp_secret)
        
        if totp.verify(code):
            session.pop('pending_2fa_user_id', None)
            
            from ..utils import get_client_ip
            ip = get_client_ip()
            tracker = LoginTracker.query.filter_by(ip_address=ip).first()
            if tracker:
                tracker.attempts = 0
                tracker.blocked_until = None
                tracker.is_permanently_blocked = False
                db.session.commit()
                
            login_user(user)
            
            try:
                audit = LoginAudit(user_id=user.id, username=user.username, ip_address=ip)
                db.session.add(audit)
                db.session.commit()
                session['login_audit_id'] = audit.id
            except: pass
            
            try:
                from ..utils import log_audit
                log_audit("Dashboard Login", f"Benutzer '{user.username}' hat sich erfolgreich (2FA) angemeldet.")
            except: pass
            
            return redirect(url_for('dashboard.index'))
        else:
            flash('Ungültiger 2FA Code.', 'danger')
            
    return render_template('login_2fa.html')
