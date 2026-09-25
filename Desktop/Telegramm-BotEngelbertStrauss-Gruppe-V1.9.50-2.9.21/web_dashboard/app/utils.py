from datetime import datetime

def datetimeformat(value, format='%H:%M:%S | %d.%m.%Y'):
    if isinstance(value, (int, float)):
        value = datetime.fromtimestamp(value)
    return value.strftime(format)

def get_client_ip():
    from flask import request, has_request_context
    if not has_request_context():
        return None
        
    # Standard header fields sent by Synology and other reverse proxies
    for header in ['X-Forwarded-For', 'X-Real-IP', 'CF-Connecting-IP', 'Proxy-Client-IP', 'WL-Proxy-Client-IP']:
        ip_val = request.headers.get(header)
        if ip_val:
            # X-Forwarded-For can contain multiple IPs separated by commas
            if ',' in ip_val:
                ip_val = ip_val.split(',')[0].strip()
            return ip_val
            
    return request.remote_addr

def log_audit(action, details=None):
    from flask import has_request_context
    from .models import db, AuditLog
    
    user_id = None
    username = "System"
    ip = None
    
    if has_request_context():
        try:
            from flask_login import current_user
            if current_user and current_user.is_authenticated:
                user_id = current_user.id
                username = current_user.username
            ip = get_client_ip()
        except Exception as e:
            print(f"Error extracting request context for log_audit: {e}")
            
    try:
        log = AuditLog(user_id=user_id, username=username, ip_address=ip, action=action, details=details)
        db.session.add(log)
        db.session.commit()
        print(f"AuditLog: logged '{action}' by {username} ({ip})")
    except Exception as e:
        db.session.rollback()
        import sys
        sys.stderr.write(f"ERROR: log_audit failed: {e}\n")
