from flask import Blueprint, jsonify, request, send_file, redirect, url_for, abort
from flask_login import login_required, current_user
from ..decorators import admin_required, permission_required
from ..models import db, BotSettings, IDFinderMessage, IDFinderUser, TopicMapping, IDFinderWarning, AutoCleanupTask, AutoReplyRule, IDFinderAdmin
# Absolute import to avoid ModuleNotFoundError
from web_dashboard.updater import Updater
from sqlalchemy import func
import os
import re
from datetime import datetime, timedelta
import requests
import json
import io
import traceback

bp = Blueprint('api', __name__, url_prefix='/api')

# Pfade
WEB_DASHBOARD_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.dirname(WEB_DASHBOARD_DIR)
USER_INTERACTION_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "user_interactions.log") 
AVATAR_CACHE_DIR = os.path.join(WEB_DASHBOARD_DIR, "app", "static", "avatars")
MEDIA_CACHE_DIR = os.path.join(WEB_DASHBOARD_DIR, "app", "static", "media")
VERSION_FILE = os.path.join(PROJECT_ROOT, "version.json")
os.makedirs(AVATAR_CACHE_DIR, exist_ok=True)
os.makedirs(MEDIA_CACHE_DIR, exist_ok=True)

# Helper um Updater mit aktuellen Settings zu bekommen
def get_updater_instance():
    settings = BotSettings.query.filter_by(bot_name='system').first()
    config = json.loads(settings.config_json) if settings else {}
    
    return Updater(
        repo_owner=config.get('github_repo_owner') or os.environ.get('GITHUB_REPO_OWNER', 'killerronnym'),
        repo_name=config.get('github_repo_name') or os.environ.get('GITHUB_REPO_NAME', 'Telegramm-BotEngelbertStrauss-Gruppe-V1.9.50'),
        current_version_file=VERSION_FILE,
        project_root=PROJECT_ROOT,
        github_token=config.get('github_token') or os.environ.get('GITHUB_TOKEN')
    )

@bp.route('/update/check')
@admin_required
def update_check():
    updater = get_updater_instance()
    info = updater.check_for_update()
    return jsonify(info)

@bp.route('/events/delete/<int:event_id>', methods=['GET', 'POST'])
def delete_event_direct(event_id):
    from ..models import GroupEvent
    event = GroupEvent.query.get(event_id)
    if event:
        db.session.delete(event)
        db.session.commit()
    return redirect(url_for('dashboard.event_settings'))

@bp.route('/events/<int:event_id>', methods=['GET'])
@login_required
def get_event_details(event_id):
    from ..models import GroupEvent
    event = GroupEvent.query.get(event_id)
    if not event:
        return jsonify({"success": False, "error": "Not found"}), 404
    
    # Simple event serialization
    e_data = {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "chat_id": event.chat_id,
        "topic_id": event.topic_id,
        "poll_type": event.poll_type,
        "interaction_type": event.interaction_type,
        "send_confirmation": event.send_confirmation,
        "confirmation_text": event.confirmation_text,
        "poll_show_all_day": event.poll_show_all_day,
        "poll_show_maybe": event.poll_show_maybe,
        "poll_show_no": event.poll_show_no,
        "poll_show_yes": event.poll_show_yes,
        "poll_show_dates": event.poll_show_dates,
        "poll_multiple_choice": event.poll_multiple_choice,
        "poll_config_json": event.poll_config_json,
        "event_dates_json": event.event_dates_json,
        "event_start": event.event_start.isoformat() if event.event_start else None,
        "image_path": event.image_path,
        "media_type": event.media_type,
        "send_as_document": event.send_as_document,
        "confirmation_image_path": event.confirmation_image_path,
        "calendar_title": event.calendar_title,
        "calendar_filename": event.calendar_filename,
        "dm_website_url": event.dm_website_url,
        "dm_website_label": event.dm_website_label,
        "dm_tickets_url": event.dm_tickets_url,
        "dm_tickets_label": event.dm_tickets_label,
        "website_url": event.website_url,
        "website_label": event.website_label,
        "tickets_url": event.tickets_url,
        "tickets_label": event.tickets_label,
        "location_in_group": event.location_in_group,
        "location_in_dm": event.location_in_dm,
        "website_in_group": event.website_in_group,
        "website_in_dm": event.website_in_dm,
        "tickets_in_group": event.tickets_in_group,
        "tickets_in_dm": event.tickets_in_dm
    }
    return jsonify({"success": True, "event": e_data})

@bp.route('/update/install', methods=['POST'])
@admin_required
def update_install():
    data = request.json
    if not data or 'url' not in data:
        return jsonify({"success": False, "error": "No URL"}), 400
    updater = get_updater_instance()
    updater.install_update(data['url'], data['version'], data['published_at'])
    return jsonify({"success": True})

@bp.route('/update/status')
@admin_required
def update_status():
    updater = get_updater_instance()
    return jsonify(updater.get_status())

@bp.route('/update/releases')
@admin_required
def update_releases():
    updater = get_updater_instance()
    releases = updater.get_recent_releases()
    return jsonify(releases)

@bp.route('/topics')
@permission_required('use_live_moderation')
def get_topics():
    try:
        show_hidden = request.args.get('show_hidden', 'false') == 'true'
        # 1. Alle echten Topics aus der Datenbank holen
        query = TopicMapping.query.order_by(TopicMapping.topic_id.asc())
        if not show_hidden:
            query = query.filter(TopicMapping.is_hidden == False)
            
        mappings = query.all()
        topics_map = {} # Wir nutzen ein Map für schnellen Zugriff
        
        # 2. Letzte Aktivität pro Topic ermitteln (für Sortierung)
        from sqlalchemy import func
        last_activities = db.session.query(
            IDFinderMessage.message_thread_id,
            IDFinderMessage.chat_id,
            func.max(IDFinderMessage.timestamp).label('latest')
        ).group_by(IDFinderMessage.message_thread_id, IDFinderMessage.chat_id).all()
        
        activity_map = {}
        for tid, cid, latest in last_activities:
            # Key ist (topic_id, chat_id)
            # Behandle tid=None/0 als 1 (Allgemein)
            effective_tid = tid if tid and tid > 0 else 1
            activity_map[(str(effective_tid), cid)] = latest.isoformat() if latest else None

        # 3. Topics aufbereiten
        topics = []
        for m in mappings:
            tid_str = str(m.topic_id)
            latest_ts = activity_map.get((tid_str, m.chat_id))
            
            topics.append({
                'id': m.topic_id,
                'chat_id': m.chat_id,
                'name': m.topic_name,
                'is_active': bool(m.is_active),
                'is_archived': bool(m.is_archived),
                'is_hidden': bool(m.is_hidden),
                'is_pinned': bool(m.is_pinned),
                'is_closed': bool(m.is_closed),
                'is_deleted': bool(m.is_deleted),
                'category': str(m.category or 'Hauptgruppe'),
                'last_activity': latest_ts
            })
            
        # 4. Virtual Topics für Privat-DMs (DMs sind immer eigene Chat-IDs)
        try:
            # Finde alle privaten Chat-IDs
            dm_activities = db.session.query(
                IDFinderMessage.chat_id,
                func.max(IDFinderMessage.timestamp).label('latest')
            ).filter(IDFinderMessage.chat_type == 'private')\
             .group_by(IDFinderMessage.chat_id).all()
            
            for cid, latest in dm_activities:
                user = IDFinderUser.query.filter_by(telegram_id=cid).first()
                if not user: continue
                
                name = user.custom_name or f"{user.first_name} {user.last_name or ''}".strip() or f"User {cid}"
                is_archived = bool(user.is_sidebar_archived)
                
                topics.append({
                    'id': f"dm_{cid}",
                    'chat_id': cid,
                    'name': name,
                    'is_active': True,
                    'is_archived': is_archived,
                    'is_hidden': False,
                    'is_pinned': False,
                    'is_closed': False,
                    'is_deleted': False,
                    'category': 'Bot & Privat (DMs)',
                    'icon': 'bi-person-fill',
                    'last_activity': latest.isoformat() if latest else None
                })
        except Exception as e:
            print(f"Error fetching DM topics: {e}")

        # 5. Global sortieren (Pinned zuerst, dann nach Aktivität)
        def sort_key(t):
            pinned = 1 if t.get('is_pinned') else 0
            ts = t.get('last_activity') or '1970-01-01T00:00:00'
            return (pinned, ts)

        topics.sort(key=sort_key, reverse=True)
        return jsonify(topics)
    except Exception as e:
        print(f"ERROR in get_topics API: {e}")
        import traceback
        traceback.print_exc()
        return jsonify([])

@bp.route('/moderation/topics/update', methods=['POST'])
@permission_required('use_live_moderation')
def update_topic():
    try:
        data = request.json
        tid = str(data.get('topic_id'))
        if not tid: return jsonify({"success": False, "error": "No topic_id"}), 400
        
        if tid.startswith('dm_'):
            # Update User Table
            uid = int(tid.replace('dm_', ''))
            user = IDFinderUser.query.filter_by(telegram_id=uid).first()
            if not user: return jsonify({"success": False, "error": "User not found"}), 404
            
            if 'name' in data: user.custom_name = data['name']
            if 'is_archived' in data: user.is_sidebar_archived = bool(data['is_archived'])
            db.session.commit()
            return jsonify({"success": True})
        
        # Original TopicMapping logic
        mapping = TopicMapping.query.filter_by(topic_id=tid).first()
        if not mapping:
            mapping = TopicMapping(topic_id=tid, topic_name=data.get('name', f"Topic {tid}"))
            db.session.add(mapping)
        
        if 'name' in data: mapping.topic_name = data['name']
        if 'is_active' in data: mapping.is_active = bool(data['is_active'])
        if 'is_hidden' in data: mapping.is_hidden = bool(data['is_hidden'])
        if 'is_pinned' in data: mapping.is_pinned = bool(data['is_pinned'])
        if 'is_archived' in data: mapping.is_archived = bool(data['is_archived'])
        if 'category' in data: mapping.category = str(data['category'] or '')
        
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/live-messages')
@permission_required('use_live_moderation')
def get_live_messages():
    try:
        topic_id = request.args.get('topic_id')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        query = IDFinderMessage.query
        if topic_id == 'private':
            query = query.filter(IDFinderMessage.chat_type == 'private')
        elif topic_id and str(topic_id).startswith('dm_'):
            try:
                target_chat_id = int(topic_id.split('_')[1])
                query = query.filter(IDFinderMessage.chat_id == target_chat_id).filter(IDFinderMessage.chat_type == 'private')
            except: pass
        elif topic_id and topic_id != 'all':
            try:
                tid = int(topic_id)
                if tid == 1:
                    from sqlalchemy import or_
                    query = query.filter(IDFinderMessage.chat_type != 'private').filter(or_(IDFinderMessage.message_thread_id == 1, IDFinderMessage.message_thread_id == None, IDFinderMessage.message_thread_id == 0))
                else:
                    query = query.filter(IDFinderMessage.message_thread_id == tid)
            except: pass
            
        from sqlalchemy import case, or_
        # Get messages
        db_messages = query.order_by(IDFinderMessage.timestamp.desc()).offset(offset).limit(limit).all()
        
        # Bot Detection Logic
        bot_id = 7520803994
        try:
            settings = BotSettings.query.filter_by(bot_name='id_finder').first()
            if settings:
                config = json.loads(settings.config_json)
                bot_id = int(config.get('bot_id', 7520803994))
        except: pass

        messages = []
        for m in db_messages:
            try:
                user = IDFinderUser.query.filter_by(telegram_id=m.telegram_user_id).first()
                t_id = m.message_thread_id
                if t_id is None and m.chat_type != 'private': t_id = 1
                
                topic = TopicMapping.query.filter_by(topic_id=t_id, chat_id=m.chat_id).first() if t_id else None
                
                # Warning Count
                warning_count = 0
                try:
                    uid_check = int(m.telegram_user_id) if m.telegram_user_id else 0
                    if uid_check > 0:
                        warning_count = db.session.query(IDFinderWarning).filter_by(telegram_user_id=uid_check).count()
                except Exception as e:
                    print(f"Warning Count Error for user {m.telegram_user_id}: {e}")
                
                ts_iso = m.timestamp.isoformat() if m.timestamp else ""
                display_topic_name = topic.topic_name if topic else (f"Topic {t_id}" if t_id else "Hauptchat")
                if m.chat_type == 'private': display_topic_name = "Privat"

                # Rank Detection
                rank = 'User'
                uid = int(m.telegram_user_id) if m.telegram_user_id else 0
                
                if (user and getattr(user, 'is_bot', False)) or uid == bot_id:
                    rank = 'Bot'
                elif uid == 5544098336: rank = 'Developer' 
                elif uid == 7386906637 or uid == 1032410054: rank = 'Inhaber'
                else:
                    try:
                        admin = IDFinderAdmin.query.filter_by(telegram_id=uid).first()
                        if admin:
                            perms = admin.permissions
                            if perms.get('is_superadmin'): rank = 'Inhaber'
                            elif perms.get('can_manage_admins'): rank = 'Admin'
                            else: rank = 'Moderator'
                    except: pass
                
                messages.append({
                    'id': m.id, 'message_id': m.message_id or 0, 'chat_id': m.chat_id or 0, 'thread_id': m.message_thread_id or 0,
                    'topic_name': display_topic_name,
                    'ts_str': ts_iso, 'user_id': uid,
                    'full_name': (f"{user.first_name or ''} {user.last_name or ''}").strip() or user.username or str(uid) if user else str(uid),
                    'text': str(m.text or ""), 'chat_type': str(m.chat_type or "unknown"),
                    'avatar_url': f"/api/avatar/{uid}" if user else f"https://ui-avatars.com/api/?name={uid}&background=random", 
                    'is_deleted': bool(m.is_deleted),
                    'deleted_by_name': str(m.deleted_by_name or m.deleted_by or "System"),
                    'is_edited': bool(getattr(m, 'is_edited', False)),
                    'warning_count': int(warning_count),
                    'content_type': str(m.content_type or 'text'),
                    'file_id': str(m.file_id or ''),
                    'user_rank': rank,
                    'reply_markup': str(m.reply_markup or '')
                })
            except Exception as e:
                print(f"ERROR processing msg {m.id}: {e}")
                continue
        return jsonify(messages)
    except Exception as e:
        print(f"CRITICAL ERROR in get_live_messages: {e}")
        traceback.print_exc()
        return jsonify([])

@bp.route('/moderation/get-settings')
def get_mod_settings():
    try:
        settings = BotSettings.query.filter_by(bot_name='id_finder').first()
        if settings:
            config = json.loads(settings.config_json)
            return jsonify({'max_warnings': config.get('max_warnings', 3), 'cleanup_notification_seconds': config.get('cleanup_notification_seconds', 60), 'warning_bot_name': config.get('warning_bot_name', 'invite'), 'punishment_type': config.get('punishment_type', 'none'), 'mute_duration': config.get('mute_duration', 24)})
    except: pass
    return jsonify({'max_warnings': 3, 'cleanup_notification_seconds': 60, 'warning_bot_name': 'invite', 'punishment_type': 'none', 'mute_duration': 24})

@bp.route('/media/<file_id>')
def get_media(file_id):
    try:
        # Check if we have it in cache - look for any file starting with file_id
        if os.path.exists(MEDIA_CACHE_DIR):
            for filename in os.listdir(MEDIA_CACHE_DIR):
                if filename.startswith(file_id + "."):
                    file_path = os.path.join(MEDIA_CACHE_DIR, filename)
                    ext = filename.split('.')[-1].lower()
                    if ext == 'webp': mimetype = 'image/webp'
                    elif ext in ['jpg', 'jpeg']: mimetype = 'image/jpeg'
                    elif ext == 'png': mimetype = 'image/png'
                    elif ext == 'gif': mimetype = 'image/gif'
                    elif ext in ['mp4', 'm4v']: mimetype = 'video/mp4'
                    elif ext == 'webm': mimetype = 'video/webm'
                    elif ext in ['mov', 'qt']: mimetype = 'video/quicktime'
                    elif ext in ['avi']: mimetype = 'video/x-msvideo'
                    elif ext in ['mpeg', 'mpg']: mimetype = 'video/mpeg'
                    elif ext in ['ogg', 'oga', 'ogv']: mimetype = 'application/ogg'
                    elif ext in ['mp3']: mimetype = 'audio/mpeg'
                    elif ext in ['opus']: mimetype = 'audio/ogg'
                    elif ext in ['wav']: mimetype = 'audio/wav'
                    elif ext == 'tgs': mimetype = 'application/x-tgsticker'
                    else: mimetype = f'image/{ext}'
                    return send_file(file_path, mimetype=mimetype)
        
        # If not in cache, download from Telegram
        settings = BotSettings.query.filter_by(bot_name='id_finder').first()
        if not settings: return jsonify({'error': 'Master-Setting nicht gefunden'}), 404
        config = json.loads(settings.config_json); bot_token = config.get('bot_token')
        if not bot_token: return jsonify({'error': 'Master-Token fehlt in DB'}), 404
        
        # Get file info
        file_info_res = requests.get(f"https://api.telegram.org/bot{bot_token}/getFile", params={'file_id': file_id}, timeout=5)
        file_info = file_info_res.json()
        
        if file_info.get('ok'):
            remote_path = file_info['result']['file_path']
            # Extract extension
            ext = remote_path.split('.')[-1].lower() if '.' in remote_path else 'jpg'
            local_path = os.path.join(MEDIA_CACHE_DIR, f"{file_id}.{ext}")
            
            # Download file
            img_res = requests.get(f"https://api.telegram.org/file/bot{bot_token}/{remote_path}", timeout=10)
            if img_res.status_code == 200:
                with open(local_path, 'wb') as f: f.write(img_res.content)
                if ext == 'webp': mimetype = 'image/webp'
                elif ext in ['jpg', 'jpeg']: mimetype = 'image/jpeg'
                elif ext == 'png': mimetype = 'image/png'
                elif ext == 'gif': mimetype = 'image/gif'
                elif ext in ['mp4', 'm4v']: mimetype = 'video/mp4'
                elif ext == 'webm': mimetype = 'video/webm'
                elif ext in ['mov', 'qt']: mimetype = 'video/quicktime'
                elif ext in ['avi']: mimetype = 'video/x-msvideo'
                elif ext in ['mpeg', 'mpg']: mimetype = 'video/mpeg'
                elif ext in ['ogg', 'oga', 'ogv']: mimetype = 'application/ogg'
                elif ext in ['mp3']: mimetype = 'audio/mpeg'
                elif ext in ['opus']: mimetype = 'audio/ogg'
                elif ext in ['wav']: mimetype = 'audio/wav'
                elif ext == 'tgs': mimetype = 'application/x-tgsticker'
                else: mimetype = f'image/{ext}'
                return send_file(io.BytesIO(img_res.content), mimetype=mimetype)
    except Exception as e:
        print(f"Error in get_media: {e}")
    return jsonify({'error': 'Media not found'}), 404

@bp.route('/avatar/<int:user_id>')
def get_avatar(user_id):
    avatar_path = os.path.join(AVATAR_CACHE_DIR, f"{user_id}.jpg")
    try:
        if os.path.exists(avatar_path): 
            return send_file(avatar_path, mimetype='image/jpeg')
        
        user = IDFinderUser.query.filter_by(telegram_id=user_id).first()
        if user and user.photo_url:
            return redirect(user.photo_url)
        if user and user.photo_file_id:
            return redirect(url_for('dashboard.telegram_image', file_id=user.photo_file_id))
        
        # Try to fetch from Telegram
        settings = BotSettings.query.filter_by(bot_name='id_finder').first()
        if settings:
            config = json.loads(settings.config_json)
            bot_token = config.get('bot_token')
            if bot_token:
                res = requests.get(f"https://api.telegram.org/bot{bot_token}/getUserProfilePhotos", params={'user_id': user_id, 'limit': 1}, timeout=2); data = res.json()
                if data.get('ok') and data['result']['total_count'] > 0:
                    file_id = data['result']['photos'][0][-1]['file_id']
                    file_info = requests.get(f"https://api.telegram.org/bot{bot_token}/getFile", params={'file_id': file_id}, timeout=2).json()
                    if file_info.get('ok'):
                        file_path = file_info['result']['file_path']
                        img_res = requests.get(f"https://api.telegram.org/file/bot{bot_token}/{file_path}", timeout=3)
                        if img_res.status_code == 200:
                            os.makedirs(AVATAR_CACHE_DIR, exist_ok=True)
                            with open(avatar_path, 'wb') as f: f.write(img_res.content)
                            return send_file(io.BytesIO(img_res.content), mimetype='image/jpeg')
    except: pass

    # Fallback to UI-Avatars
    user = IDFinderUser.query.filter_by(telegram_id=user_id).first()
    name = user.first_name if user and user.first_name else str(user_id)
    import urllib.parse
    return redirect(f"https://ui-avatars.com/api/?name={urllib.parse.quote(name)}&background=random&color=fff")


# --- AUTO RESPONDER API ---
@bp.route('/auto-responder/add', methods=['POST'])
def add_auto_reply():
    data = request.json
    if not data or 'trigger_type' not in data or 'trigger_text' not in data or 'response_text' not in data:
        return jsonify({"success": False, "error": "Fehlende Daten"}), 400
    
    try:
        rule = AutoReplyRule(
            trigger_type=data['trigger_type'],
            trigger_text=data['trigger_text'],
            response_text=data['response_text'],
            is_active=True
        )
        db.session.add(rule)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/auto-responder/delete/<int:rule_id>', methods=['POST'])
def delete_auto_reply(rule_id):
    try:
        rule = AutoReplyRule.query.get(rule_id)
        if rule:
            db.session.delete(rule)
            db.session.commit()
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Regel nicht gefunden"}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/auto-responder/toggle/<int:rule_id>', methods=['POST'])
def toggle_auto_reply(rule_id):
    try:
        rule = AutoReplyRule.query.get(rule_id)
        if rule:
            rule.is_active = not rule.is_active
            db.session.commit()
            return jsonify({"success": True, "is_active": rule.is_active})
        return jsonify({"success": False, "error": "Regel nicht gefunden"}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/moderation/delete', methods=['POST'])
def delete_message():
    try:
        data = request.json
        msg_db_id = data.get('id')
        reason = data.get('reason') # Only warn if reason is provided
        send_public = data.get('send_public', False) if not reason else data.get('send_public', True)
        send_private = data.get('send_private', False) if not reason else data.get('send_private', True)
        
        if msg_db_id:
            msg = IDFinderMessage.query.get(msg_db_id)
        else:
            chat_id = data.get('chat_id')
            message_id = data.get('message_id')
            msg = IDFinderMessage.query.filter_by(chat_id=chat_id, message_id=message_id).first()
        
        if not msg:
            print(f"DEBUG: Message not found for deletion. ID: {msg_db_id}, Chat: {data.get('chat_id')}, Msg: {data.get('message_id')}")
            return jsonify({'success': False, 'error': 'Nachricht nicht gefunden'}), 404
            
        settings = BotSettings.query.filter_by(bot_name='id_finder').first()
        config = json.loads(settings.config_json) if settings else {}
        bot_token = config.get('bot_token')
        if not bot_token: return jsonify({'success': False, 'error': 'Bot Token fehlt'}), 500
        
        # 1. DELETE from Telegram
        res_del = requests.post(f"https://api.telegram.org/bot{bot_token}/deleteMessage", 
                               json={'chat_id': msg.chat_id, 'message_id': msg.message_id}, timeout=5).json()
        
        if not res_del.get('ok'):
            desc = res_del.get('description', '').lower()
            print(f"DEBUG: Telegram deleteMessage failed: {res_del}")
            # Falls die Nachricht schon weg ist (z.B. manuell gelöscht), ignorieren wir den Fehler
            if "message to delete not found" in desc or "message can't be deleted" in desc:
                pass 
            elif not reason: # Nur bei Schnelllöschung Fehlermeldung zeigen, wenn es ein echtes Problem ist
                 return jsonify({'success': False, 'error': f"Telegram Fehler: {res_del.get('description')}"}), 400

        # 2. WARNING LOGIC (only if reason is provided)
        action_taken_text = ""
        if reason:
            user = IDFinderUser.query.filter_by(telegram_id=msg.telegram_user_id).first()
            new_warning = IDFinderWarning(telegram_user_id=msg.telegram_user_id, reason=reason, message_db_id=msg.id)
            db.session.add(new_warning)
            db.session.commit()
            
            warning_count = IDFinderWarning.query.filter_by(telegram_user_id=msg.telegram_user_id).count()
            max_warnings = int(config.get('max_warnings', 3))
            punishment_type = config.get('punishment_type', 'none')
            mute_duration = int(config.get('mute_duration', 24))
            
            if warning_count >= max_warnings:
                if punishment_type == 'mute':
                    until_date = int((datetime.utcnow() + timedelta(hours=mute_duration)).timestamp())
                    requests.post(f"https://api.telegram.org/bot{bot_token}/restrictChatMember", 
                                 json={'chat_id': msg.chat_id, 'user_id': msg.telegram_user_id, 'permissions': {'can_send_messages': False}, 'until_date': until_date}, timeout=5)
                    action_taken_text = f"\n🔇 <b>Nutzer für {mute_duration}h stummgeschaltet.</b>"
                elif punishment_type == 'kick':
                    requests.post(f"https://api.telegram.org/bot{bot_token}/banChatMember", json={'chat_id': msg.chat_id, 'user_id': msg.telegram_user_id}, timeout=5)
                    requests.post(f"https://api.telegram.org/bot{bot_token}/unbanChatMember", json={'chat_id': msg.chat_id, 'user_id': msg.telegram_user_id, 'only_if_banned': True}, timeout=5)
                    action_taken_text = f"\n👞 <b>Nutzer aus der Gruppe geworfen.</b>"
                elif punishment_type == 'ban':
                    requests.post(f"https://api.telegram.org/bot{bot_token}/banChatMember", json={'chat_id': msg.chat_id, 'user_id': msg.telegram_user_id}, timeout=5)
                    action_taken_text = f"\n🔨 <b>Nutzer permanent gebannt.</b>"

            # Send warning log to administrator group topic 3
            try:
                admin_name = current_user.username if current_user and hasattr(current_user, 'username') else "Dashboard Admin"
                admin_log_group = -1003372573784
                admin_log_thread = 3
                warned_user_mention = f"@{user.username}" if user and user.username else f"<b>{user.first_name if user else msg.telegram_user_id}</b>"
                admin_mention = f"Dashboard Admin ({admin_name})"
                
                admin_log_text = (
                    f"⚠️ <b>Neue Verwarnung erteilt (Dashboard)</b>\n\n"
                    f"👤 <b>Nutzer:</b> {warned_user_mention} (ID: {msg.telegram_user_id})\n"
                    f"🛡️ <b>Verwarnt durch:</b> {admin_mention}\n"
                    f"⚖️ <b>Grund:</b> {reason}\n"
                    f"📊 <b>Status:</b> {warning_count}/{max_warnings}{action_taken_text}"
                )
                requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", 
                              json={'chat_id': admin_log_group, 'message_thread_id': admin_log_thread, 'text': admin_log_text, 'parse_mode': 'HTML'}, timeout=5)
            except Exception as log_e:
                print(f"Error sending warning log to admin group: {log_e}")
            
            if send_public:
                user_mention = f"@{user.username}" if user and user.username else f"<b>{user.first_name if user else msg.telegram_user_id}</b>"
                public_text = (f"🚫 <b>Nachricht gelöscht</b>\n\n👤 Nutzer: {user_mention}\n⚖️ Grund: {reason}\n⚠️ Verwarnung: {warning_count}/{max_warnings}{action_taken_text}")
                res = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", 
                                   json={'chat_id': msg.chat_id, 'message_thread_id': msg.message_thread_id, 'text': public_text, 'parse_mode': 'HTML'}, timeout=5).json()
                cleanup_seconds = int(config.get('cleanup_notification_seconds', 60))
                if cleanup_seconds > 0 and res.get('ok'):
                    db.session.add(AutoCleanupTask(chat_id=msg.chat_id, message_id=res['result']['message_id'], cleanup_at=datetime.utcnow() + timedelta(seconds=cleanup_seconds)))
            
            if send_private:
                private_text = (f"Hallo, deine Nachricht in der Gruppe wurde gelöscht.\n\nGrund: {reason}\nDu hast nun {warning_count} von {max_warnings} Verwarnungen.")
                if action_taken_text: private_text += f"\nKonsequenz: {action_taken_text.replace('<b>', '').replace('</b>', '')}"
                requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={'chat_id': msg.telegram_user_id, 'text': private_text}, timeout=5)

        # 3. MARK in DB
        msg.is_deleted = True
        msg.deletion_reason = reason or "Schnelllöschung"
        msg.deleted_by = "Dashboard Admin"
        msg.deleted_by_name = "Dashboard Admin"
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/moderation/settings', methods=['POST'])
def save_mod_settings():
    try:
        data = request.json; settings = BotSettings.query.filter_by(bot_name='id_finder').first()
        if settings:
            config = json.loads(settings.config_json); config['max_warnings'] = int(data.get('max_warnings', 3)); config['cleanup_notification_seconds'] = int(data.get('cleanup_notification_seconds', 60)); config['warning_bot_name'] = data.get('warning_bot_name', 'invite'); config['punishment_type'] = data.get('punishment_type', 'none'); config['mute_duration'] = int(data.get('mute_duration', 24)); settings.config_json = json.dumps(config); db.session.commit()
            return jsonify({'success': True})
    except: pass
    return jsonify({'success': False}), 400

@bp.route('/moderation/warnings/delete/<int:warning_id>', methods=['POST'])
@permission_required('use_live_moderation')
def delete_warning(warning_id):
    try:
        data = request.json or {}
        chat_id = data.get('chat_id')
        thread_id = data.get('thread_id')
        send_public = data.get('send_public', False)
        send_private = data.get('send_private', False)
        
        warning = IDFinderWarning.query.get(warning_id)
        if not warning: return jsonify({'success': False}), 404
        
        user_id = warning.telegram_user_id
        user = IDFinderUser.query.filter_by(telegram_id=user_id).first()
        
        db.session.delete(warning)
        db.session.commit()
        
        # Notifications
        if send_public or send_private:
            settings = BotSettings.query.filter_by(bot_name='id_finder').first()
            config = json.loads(settings.config_json) if settings else {}
            bot_token = config.get('bot_token')
            
            if bot_token:
                user_name = f"@{user.username}" if user and user.username else f"<b>{user.first_name if user else user_id}</b>"
                
                if send_public and chat_id:
                    public_text = f"ℹ️ Eine Verwarnung für {user_name} wurde zurückgesetzt!"
                    res = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", 
                                  json={'chat_id': chat_id, 'message_thread_id': thread_id, 'text': public_text, 'parse_mode': 'HTML'}, timeout=5).json()
                    
                    cleanup_seconds = int(config.get('cleanup_notification_seconds', 60))
                    if cleanup_seconds > 0 and res.get('ok'):
                        db.session.add(AutoCleanupTask(
                            chat_id=chat_id, 
                            message_id=res['result']['message_id'], 
                            cleanup_at=datetime.utcnow() + timedelta(seconds=cleanup_seconds)
                        ))
                        db.session.commit()
                
                if send_private:
                    # SSoT: Nutze Master-Token
                    w_token = bot_token
                    if w_token:
                        private_text = "Hallo, eine deiner Verwarnungen wurde zurückgesetzt."
                        requests.post(f"https://api.telegram.org/bot{w_token}/sendMessage", 
                                      json={'chat_id': user_id, 'text': private_text}, timeout=5)

        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting warning: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/moderation/warnings/clear/<int:user_id>', methods=['POST'])
@permission_required('use_live_moderation')
def clear_all_warnings(user_id):
    try:
        data = request.json or {}
        chat_id = data.get('chat_id')
        thread_id = data.get('thread_id')
        send_public = data.get('send_public', False)
        send_private = data.get('send_private', False)
        
        user = IDFinderUser.query.filter_by(telegram_id=user_id).first()
        
        IDFinderWarning.query.filter_by(telegram_user_id=user_id).delete()
        db.session.commit()
        
        # Notifications
        if send_public or send_private:
            settings = BotSettings.query.filter_by(bot_name='id_finder').first()
            config = json.loads(settings.config_json) if settings else {}
            bot_token = config.get('bot_token')
            
            if bot_token:
                user_name = f"@{user.username}" if user and user.username else f"<b>{user.first_name if user else user_id}</b>"
                
                if send_public and chat_id:
                    public_text = f"✅ Alle Verwarnungen für {user_name} wurden zurückgesetzt!"
                    res = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", 
                                  json={'chat_id': chat_id, 'message_thread_id': thread_id, 'text': public_text, 'parse_mode': 'HTML'}, timeout=5).json()
                    
                    cleanup_seconds = int(config.get('cleanup_notification_seconds', 60))
                    if cleanup_seconds > 0 and res.get('ok'):
                        db.session.add(AutoCleanupTask(
                            chat_id=chat_id, 
                            message_id=res['result']['message_id'], 
                            cleanup_at=datetime.utcnow() + timedelta(seconds=cleanup_seconds)
                        ))
                        db.session.commit()
                
                if send_private:
                    # SSoT: Nutze Master-Token
                    w_token = bot_token
                    if w_token:
                        private_text = "Hallo, deine Verwarnungen wurden alle zurückgesetzt."
                        requests.post(f"https://api.telegram.org/bot{w_token}/sendMessage", 
                                      json={'chat_id': user_id, 'text': private_text}, timeout=5)

        return jsonify({'success': True})
    except Exception as e:
        print(f"Error clearing warnings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/system/settings')
@admin_required
def get_system_settings():
    try:
        settings = BotSettings.query.filter_by(bot_name='system').first()
        if settings:
            return jsonify(json.loads(settings.config_json))
    except: pass
    return jsonify({'auto_update_enabled': False, 'last_check_at': None})

@bp.route('/system/settings/save', methods=['POST'])
@admin_required
def save_system_settings():
    try:
        data = request.json
        settings = BotSettings.query.filter_by(bot_name='system').first()
        if not settings:
            settings = BotSettings(bot_name='system', config_json='{}')
            db.session.add(settings)
        
        config = json.loads(settings.config_json) if settings.config_json else {}
        
        if 'auto_update_enabled' in data:
            config['auto_update_enabled'] = bool(data['auto_update_enabled'])
        
        # New Settings for Private GitHub Updates
        if 'github_token' in data:
            config['github_token'] = data['github_token'].strip()
        if 'github_repo_owner' in data:
            config['github_repo_owner'] = data['github_repo_owner'].strip()
        if 'github_repo_name' in data:
            config['github_repo_name'] = data['github_repo_name'].strip()
            
        settings.config_json = json.dumps(config)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# --- Topic Cleanup Routes ---
@bp.route('/cleanup/configs')
def get_cleanup_configs():
    from ..models import TopicCleanupConfig
    configs = TopicCleanupConfig.query.all()
    return jsonify([{
        'id': c.id,
        'topic_id': str(c.topic_id),
        'topic_name': c.topic_name,
        'delay_minutes': c.delay_minutes,
        'delete_admins': c.delete_admins,
        'is_active': c.is_active
    } for c in configs])

@bp.route('/cleanup/config/save', methods=['POST'])
def save_cleanup_config():
    from ..models import TopicCleanupConfig
    data = request.json
    cid = data.get('id')
    try:
        if cid:
            config = TopicCleanupConfig.query.get(cid)
        else:
            config = TopicCleanupConfig()
            db.session.add(config)
        
        config.topic_id = int(data['topic_id'])
        config.topic_name = data.get('topic_name', '')
        config.delay_minutes = int(data.get('delay_minutes', 1440))
        config.delete_admins = bool(data.get('delete_admins', False))
        config.is_active = bool(data.get('is_active', True))
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@bp.route('/cleanup/config/delete/<int:cid>', methods=['POST'])
def delete_cleanup_config(cid):
    from ..models import TopicCleanupConfig
    config = TopicCleanupConfig.query.get(cid)
    if config:
        db.session.delete(config)
        db.session.commit()
    return jsonify({'success': True})

@bp.route('/cleanup/queue')
def get_cleanup_queue():
    from ..models import AutoCleanupTask
    from datetime import datetime
    now = datetime.utcnow()
    tasks = AutoCleanupTask.query.filter_by(status='pending').order_by(AutoCleanupTask.cleanup_at.asc()).limit(5).all()
    return jsonify([{
        'message_id': t.message_id,
        'chat_id': t.chat_id,
        'seconds_left': int((t.cleanup_at - now).total_seconds())
    } for t in tasks])

@bp.route('/cleanup/history')
def get_cleanup_history():
    from ..models import AutoCleanupTask
    tasks = AutoCleanupTask.query.filter_by(status='done').order_by(AutoCleanupTask.cleanup_at.desc()).limit(10).all()
    return jsonify([{
        'message_id': t.message_id,
        'chat_id': t.chat_id,
        'cleaned_at': t.cleanup_at.isoformat()
    } for t in tasks])

@bp.route('/cleanup/discovered-topics')
def get_discovered_topics():
    from ..models import TopicMapping, TopicCleanupConfig
    configs = TopicCleanupConfig.query.all()
    configured_ids = [c.topic_id for c in configs]
    mappings = TopicMapping.query.filter(~TopicMapping.topic_id.in_(configured_ids)).all()
    return jsonify([{
        'topic_id': m.topic_id,
        'topic_name': m.topic_name
    } for m in mappings])

# --- User Management API ---
@bp.route('/users/search')
@login_required
def search_users():
    from ..models import IDFinderUser
    q = request.args.get('q', '')
    if len(q) < 2: return jsonify([])
    
    users = IDFinderUser.query.filter(
        (IDFinderUser.username.ilike(f'%{q}%')) | 
        (IDFinderUser.first_name.ilike(f'%{q}%')) |
        (db.cast(IDFinderUser.telegram_id, db.String).ilike(f'%{q}%'))
    ).limit(20).all()
    
    return jsonify([{
        'telegram_id': u.telegram_id,
        'username': u.username,
        'first_name': u.first_name,
        'last_name': u.last_name,
        'photo_url': u.photo_url
    } for u in users])

@bp.route('/users/restricted/list')
@login_required
def get_restricted_users():
    from ..models import UserRestriction, IDFinderUser
    users = UserRestriction.query.all()
    
    result = []
    for u in users:
        try:
            # User-Avatar aus IDFinderUser holen
            t_user = IDFinderUser.query.filter_by(telegram_id=u.telegram_id).first()
            
            # Datum sicher formatieren
            iso_date = None
            if u.expires_at:
                try: iso_date = u.expires_at.isoformat()
                except: iso_date = str(u.expires_at)

            result.append({
                'id': u.id,
                'telegram_id': u.telegram_id,
                'username': u.username,
                'full_name': u.full_name,
                'is_globally_muted': u.is_globally_muted,
                'restricted_topics': u.restricted_topics,
                'no_media': u.no_media,
                'no_links': u.no_links,
                'no_stickers': u.no_stickers,
                'slow_mode_seconds': u.slow_mode_seconds,
                'is_shadow_banned': u.is_shadow_banned,
                'reason': u.reason,
                'expires_at': iso_date,
                'photo_url': t_user.photo_url if t_user else None
            })
        except Exception as e:
            print(f"Error processing restricted user {u.telegram_id}: {e}")
            continue
    return jsonify(result)
    
def send_bot_message(chat_id, text):
    try:
        from flask import current_app
        import requests
        import os
        
        token = None
        if current_app:
            token = current_app.config.get('BOT_TOKEN')
        if not token:
            token = os.environ.get('TELEGRAM_BOT_TOKEN') or os.environ.get('BOT_TOKEN')
            
        if not token: 
            print("ERROR: No bot token found for sending DM.")
            return False
        
        print(f"DEBUG: Sending DM to {chat_id} using token {token[:10]}...")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        res = requests.post(url, json=payload, timeout=5)
        if not res.ok:
            print(f"ERROR: Telegram API returned {res.status_code}: {res.text}")
            return False
        return True
    except Exception as e:
        print(f"CRITICAL Error sending bot message: {e}")
        return False

@bp.route('/users/restrict/save', methods=['POST'])
@login_required
def save_user_restriction():
    from ..models import UserRestriction
    from datetime import timedelta
    data = request.json
    tid = data.get('telegram_id')
    if not tid: return jsonify({'success': False, 'error': 'No Telegram ID'}), 400
    
    res = UserRestriction.query.filter_by(telegram_id=tid).first()
    if not res:
        res = UserRestriction(telegram_id=tid)
        db.session.add(res)
    
    res.username = data.get('username')
    res.full_name = data.get('full_name')
    res.is_globally_muted = bool(data.get('is_globally_muted', False))
    res.restricted_topics = data.get('restricted_topics', [])
    res.no_media = bool(data.get('no_media', False))
    res.no_links = bool(data.get('no_links', False))
    res.no_stickers = bool(data.get('no_stickers', False))
    res.slow_mode_seconds = int(data.get('slow_mode_seconds', 0))
    res.is_shadow_banned = bool(data.get('is_shadow_banned', False))
    res.reason = data.get('reason', '')
    
    # Expiration logic
    expire_hours = data.get('expire_hours')
    if expire_hours and float(expire_hours) > 0:
        res.expires_at = datetime.utcnow() + timedelta(hours=float(expire_hours))
    else:
        res.expires_at = None
    
    db.session.commit()

    # Notify user via DM (ONLY if not shadow banned)
    if not res.is_shadow_banned:
        try:
            duration_text = "Unbefristet"
            if expire_hours and float(expire_hours) > 0:
                h = float(expire_hours)
                if h < 1: duration_text = f"{int(h*60)} Minuten"
                elif h == 1: duration_text = "1 Stunde"
                elif h < 24: duration_text = f"{int(h)} Stunden"
                elif h == 24: duration_text = "24 Stunden (1 Tag)"
                else: duration_text = f"{int(h/24)} Tage"

            reason_raw = data.get('reason', '').strip()
            reason = reason_raw if reason_raw else "Verstoß gegen die Gruppenregeln / Moderations-Entscheidung."
            
            restriction_type = "<b>vollständige Schreibsperre (Nur-Lese-Modus)</b>" if res.is_globally_muted else "<b>Einschränkung in bestimmten Topics / Medien</b>"
            
            extra_info = ""
            if res.no_media: extra_info += "• Bilder/Videos gesperrt\n"
            if res.no_links: extra_info += "• Links gesperrt\n"
            if res.no_stickers: extra_info += "• Sticker/GIFs gesperrt\n"
            if res.slow_mode_seconds > 0: extra_info += f"• Slow-Mode aktiv ({res.slow_mode_seconds}s Pause zwischen Nachrichten)\n"

            msg = (
                f"⚠️ <b>Information zur Moderation</b>\n\n"
                f"Hallo {res.full_name or 'Nutzer'},\n\n"
                f"deine Schreibrechte in der Gruppe wurden angepasst.\n\n"
                f"• <b>Art der Sperre:</b> {restriction_type}\n"
                f"{extra_info}"
                f"• <b>Dauer:</b> {duration_text}\n"
                f"• <b>Grund:</b> {reason}\n\n"
                f"<i>Hinweis: Diese Nachricht wurde automatisch vom System versendet.</i>"
            )
            send_bot_message(res.telegram_id, msg)
        except Exception as e:
            print(f"Notification error: {e}")

@bp.route('/users/restrict/delete/<int:rid>', methods=['POST'])
@login_required
def delete_user_restriction(rid):
    from ..models import UserRestriction
    res = UserRestriction.query.get(rid)
    if res:
        db.session.delete(res)
        db.session.commit()
    return jsonify({'success': True})

@bp.route('/send-interactive-bot-message', methods=['POST'])
def send_interactive_bot_message():
    try:
        topic_id = request.form.get('topic_id')
        text = request.form.get('text', '')
        media = request.files.get('media')
        
        from flask import current_app
        import os
        
        s = BotSettings.query.filter_by(bot_name='id_finder').first()
        if not s: return jsonify({'success': False, 'error': 'Bot config not found'})
        cfg = json.loads(s.config_json)
        token = cfg.get('bot_token')
        main_chat_id = cfg.get('main_group_id')
        
        if not token or not main_chat_id:
            return jsonify({'success': False, 'error': 'Token or Group ID missing'})

        base_url = f'https://api.telegram.org/bot{token}/'
        target_chat = main_chat_id
        thread_id = None
        
        if topic_id:
            if topic_id.startswith('dm_'):
                # Sende direkt an den User (DM)
                target_chat = int(topic_id.replace('dm_', ''))
                thread_id = None
            elif topic_id.isdigit():
                # Sende an ein spezifisches Topic in der Gruppe
                target_chat = main_chat_id
                thread_id = int(topic_id)
        
        pin = request.form.get('pin') == 'true'
        silent = request.form.get('silent') == 'true'
        
        msg_id = None
        if media:
            fdir = os.path.join(current_app.root_path, 'static', 'uploads')
            os.makedirs(fdir, exist_ok=True)
            fname = media.filename
            fpath = os.path.join(fdir, fname)
            media.save(fpath)
            
            with open(fpath, 'rb') as f:
                payload = {'chat_id': target_chat, 'caption': text, 'parse_mode': 'HTML', 'disable_notification': silent}
                if thread_id: payload['message_thread_id'] = thread_id
                
                mtype = 'sendPhoto' if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')) else 'sendVideo'
                files = {'photo' if mtype == 'sendPhoto' else 'video': f}
                resp = requests.post(base_url + mtype, data=payload, files=files)
        else:
            payload = {'chat_id': target_chat, 'text': text, 'parse_mode': 'HTML', 'disable_notification': silent}
            if thread_id: payload['message_thread_id'] = thread_id
            resp = requests.post(base_url + 'sendMessage', json=payload)
            
        rjson = resp.json()
        bot_id = int(token.split(':')[0])

        if not rjson.get('ok'):
            error_desc = rjson.get('description', 'Unbekannter Fehler')
            # Log failure as a regular message but marked as FAILED
            try:
                from ..models import IDFinderMessage, IDFinderUser
                from datetime import datetime
                
                # Ensure bot exists in user table
                if not IDFinderUser.query.filter_by(telegram_id=bot_id).first():
                    db.session.add(IDFinderUser(telegram_id=bot_id, first_name="Bot Agent", is_bot=True))
                
                fail_msg = IDFinderMessage(
                    telegram_user_id=bot_id,
                    chat_id=target_chat,
                    message_id=0, # Mark as unique/service-like for grouping
                    message_thread_id=thread_id,
                    chat_type='private' if target_chat > 0 else 'supergroup',
                    text=text or (media.filename if media else ""),
                    content_type='photo' if media and mtype == 'sendPhoto' else ('video' if media else 'text'),
                    is_failed=True,
                    timestamp=datetime.utcnow()
                )
                db.session.add(fail_msg)
                db.session.commit()
            except Exception as e:
                print(f"Error logging failed message: {e}")
                
            return jsonify({'success': False, 'error': error_desc})
            
        # Log the bot's own message to the database so it appears in the feed
        try:
            tg_msg = rjson.get('result', {})
            bot_id = int(token.split(':')[0])
            from ..models import IDFinderMessage, IDFinderUser
            from datetime import datetime
            
            # Ensure bot exists in user table if needed
            if not IDFinderUser.query.filter_by(telegram_id=bot_id).first():
                db.session.add(IDFinderUser(telegram_id=bot_id, first_name="Bot Agent", is_bot=True))
            
            file_id = None
            if tg_msg.get('photo'): file_id = tg_msg['photo'][-1].get('file_id')
            elif tg_msg.get('video'): file_id = tg_msg['video'].get('file_id')
            elif tg_msg.get('document'): file_id = tg_msg['document'].get('file_id')
            elif tg_msg.get('animation'): file_id = tg_msg['animation'].get('file_id')

            new_msg = IDFinderMessage(
                telegram_user_id=bot_id,
                message_id=tg_msg.get('message_id'),
                chat_id=target_chat,
                message_thread_id=thread_id,
                chat_type='private' if target_chat > 0 else 'supergroup',
                text=text or (fname if media else ""),
                content_type='photo' if media and mtype == 'sendPhoto' else ('video' if media else 'text'),
                file_id=file_id,
                timestamp=datetime.utcnow()
            )
            db.session.add(new_msg)
            db.session.commit()
        except Exception as log_err:
            print(f"Error logging bot's own message: {log_err}")
        
        # Handle Pinning
        if pin:
            msg_id = rjson.get('result', {}).get('message_id')
            if msg_id:
                requests.post(base_url + 'pinChatMessage', json={'chat_id': target_chat, 'message_id': msg_id})

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/toggle-bot-pause', methods=['POST'])
@admin_required
def toggle_bot_pause():
    try:
        data = request.json
        user_id = data.get('user_id')
        paused = data.get('paused', False)
        
        if not user_id: return jsonify({'success': False, 'error': 'User ID missing'})
        
        from ..models import IDFinderUser, BotSettings
        from datetime import datetime
        import requests
        
        user = IDFinderUser.query.filter_by(telegram_id=user_id).first()
        if not user: return jsonify({'success': False, 'error': 'User not found'})
        
        user.is_steckbrief_paused = paused
        user.steckbrief_paused_at = datetime.utcnow() if paused else None
        db.session.commit()
        
        # Sende Nachricht an User
        s = BotSettings.query.filter_by(bot_name='id_finder').first()
        if s:
            cfg = json.loads(s.config_json)
            token = cfg.get('bot_token')
            if token:
                if paused:
                    msg = "ℹ️ Der Bot wurde vorübergehend deaktiviert. Es befindet sich ein Supporter im Chat, um dir zu helfen oder dir zu schreiben."
                else:
                    msg = "✅ Der Support-Chat wurde beendet. Du kannst nun wieder mit deinem Steckbrief fortfahren."
                
                requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                              json={'chat_id': user_id, 'text': msg}, timeout=5)
        
        return jsonify({'success': True, 'paused': user.is_steckbrief_paused})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
@bp.route('/get-user-status/<int:user_id>')
def get_user_status(user_id):
    try:
        from ..models import IDFinderUser
        user = IDFinderUser.query.filter_by(telegram_id=user_id).first()
        if not user: return jsonify({'success': False, 'error': 'User not found'})
        return jsonify({'success': True, 'is_steckbrief_paused': bool(user.is_steckbrief_paused)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
@bp.route('/export/event/<int:event_id>')
def export_event(event_id):
    from ..models import GroupEvent, EventRSVP
    event = GroupEvent.query.get_or_404(event_id)
    rsvps = EventRSVP.query.filter_by(event_id=event_id).all()
    
    output = io.StringIO()
    output.write(f"==================================================\n")
    output.write(f"   EVENT STATISTIK: {event.title.upper()}\n")
    output.write(f"==================================================\n")
    output.write(f"ID: #{event.id}\n")
    output.write(f"Erstellt am: {event.created_at.strftime('%d.%m.%Y %H:%M')} Uhr\n")
    output.write(f"Gesamt-Teilnehmer: {len(rsvps)}\n")
    output.write("-" * 50 + "\n\n")
    
    # Gruppieren nach Status
    groups = {
        'Alle Tage': [],
        'dabei': [],
        'vielleicht': [],
        'nicht_dabei': []
    }
    
    for r in rsvps:
        if r.status in groups:
            groups[r.status].append(r)
        else:
            if 'Andere' not in groups: groups['Andere'] = []
            groups['Andere'].append(r)
        
    for status, members in groups.items():
        if not members: continue
        
        display_status = status.upper()
        if status == 'dabei': display_status = "🔥 DABEI (EINZELN)"
        elif status == 'Alle Tage': display_status = "🌟 DABEI (ALLE TAGE)"
        elif status == 'vielleicht': display_status = "🤔 EVENTUELL"
        elif status == 'nicht_dabei': display_status = "💤 ABSAGEN"
        
        output.write(f"{display_status} — ({len(members)} Personen)\n")
        for m in members:
            dm_info = f"[DM: {m.dm_sent_status}]" if m.dm_sent_status else "[DM: -]"
            output.write(f" • {m.username or 'User'[:15]:<15} (ID: {m.telegram_user_id}) {dm_info}\n")
        output.write("\n")
        
    output.seek(0)
    # Rückgabe als Text-Datei (UTF-8 mit BOM für Windows/Excel Kompatibilität)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/plain',
        as_attachment=True,
        download_name=f"statistik_event_{event_id}.txt"
    )
