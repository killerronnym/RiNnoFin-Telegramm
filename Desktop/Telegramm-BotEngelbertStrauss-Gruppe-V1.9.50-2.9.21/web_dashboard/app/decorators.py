from functools import wraps
from flask import flash, redirect, url_for, request, abort
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if current_user.role != 'admin':
            if request.path.startswith('/api/'):
                abort(403)
            flash("Zugriff verweigert. Diese Aktion erfordert Admin-Rechte.", "danger")
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            if current_user.has_permission(permission_name):
                return f(*args, **kwargs)
            
            if request.path.startswith('/api/'):
                abort(403)
            flash(f"Zugriff verweigert. Dir fehlt das Recht: {permission_name}", "danger")
            return redirect(url_for('dashboard.index'))
        return decorated_function
    return decorator
