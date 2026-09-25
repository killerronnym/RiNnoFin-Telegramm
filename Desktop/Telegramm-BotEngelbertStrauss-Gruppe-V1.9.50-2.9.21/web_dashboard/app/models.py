from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(20), default='moderator')
    must_change_password = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    permissions_json = db.Column(db.Text, default='{}')
    profile_picture = db.Column(db.String(255), default='default_avatar.png')
    totp_secret = db.Column(db.String(32), nullable=True)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_login_enabled = db.Column(db.Boolean, default=True)
    two_factor_reset_enabled = db.Column(db.Boolean, default=False)

    @property
    def permissions(self):
        try:
            return json.loads(self.permissions_json) if self.permissions_json else {}
        except:
            return {}

    @permissions.setter
    def permissions(self, value):
        self.permissions_json = json.dumps(value)

    def has_permission(self, permission_name):
        if self.role == 'admin':
            return True
        if self.role not in ('moderator', 'user'):
            return False
        
        perms = self.permissions
        if permission_name in perms:
            return bool(perms[permission_name])
        
        # Default fallback permissions for moderators
        defaults = {
            'view_analytics': True,
            'manage_users': True,
            'use_live_moderation': True,
            'manage_polls': True,
            'manage_quizzes': True,
            'manage_events': True,
            'manage_reports': True,
            'manage_broadcasts': True,
            'view_id_finder_registry': True,
            'edit_poll_config': False,
            'edit_quiz_config': False,
            'edit_event_chat_id': False,
            'edit_report_chat_id': False,
            'edit_broadcast_chat_id': False,
            'edit_id_finder_registry': False
        }
        return defaults.get(permission_name, False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class PasskeyCredential(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    credential_id = db.Column(db.String(255), unique=True, nullable=False)
    public_key = db.Column(db.Text, nullable=False)
    sign_count = db.Column(db.Integer, default=0)
    name = db.Column(db.String(100), default='Passkey')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LoginTracker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), unique=True, nullable=False)
    attempts = db.Column(db.Integer, default=0)
    blocked_until = db.Column(db.DateTime, nullable=True)
    is_permanently_blocked = db.Column(db.Boolean, default=False)
    last_attempt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LoginAudit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(80), nullable=False)
    ip_address = db.Column(db.String(50), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    logout_time = db.Column(db.DateTime, nullable=True)

    @property
    def duration_string(self):
        end_time = self.logout_time or self.last_activity
        if self.login_time and end_time:
            diff = end_time - self.login_time
            seconds = int(diff.total_seconds())
            if seconds < 60:
                return f"{seconds} Sek."
            minutes = seconds // 60
            if minutes < 60:
                return f"{minutes} Min. {seconds % 60} Sek."
            hours = minutes // 60
            return f"{hours} Std. {minutes % 60} Min."
        return "-"

class BotSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_name = db.Column(db.String(50), unique=True, nullable=False)
    config_json = db.Column(db.Text, nullable=False)  # JSON-String speichern
    is_active = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(80), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Broadcast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text)
    topic_id = db.Column(db.String(50))
    send_mode = db.Column(db.String(20), default='standard')
    media_path = db.Column(db.String(255))  # legacy single-file
    media_type = db.Column(db.String(20))   # image, video
    media_files = db.Column(db.Text)        # JSON list of paths for multi-image
    spoiler = db.Column(db.Boolean, default=False)
    scheduled_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')  # pending, sent, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    pin_message = db.Column(db.Boolean, default=False)
    silent_send = db.Column(db.Boolean, default=False)

from sqlalchemy import UniqueConstraint

class TopicMapping(db.Model):
    __table_args__ = (UniqueConstraint('topic_id', 'chat_id', name='_topic_chat_uc'),)
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.BigInteger, nullable=False)
    chat_id = db.Column(db.BigInteger, nullable=True) # Parent group ID
    topic_name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_archived = db.Column(db.Boolean, default=False)
    is_hidden = db.Column(db.Boolean, default=False)
    is_pinned = db.Column(db.Boolean, default=False)
    is_closed = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(30), default='')  # hauptgruppe, admin, steckbriefe, or empty for auto

# --- Auto-Responder Models ---
class AutoReplyRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trigger_type = db.Column(db.String(20), nullable=False) # 'command' or 'keyword'
    trigger_text = db.Column(db.String(255), nullable=False)
    response_text = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# --- ID Finder Bot Models ---

class IDFinderAdmin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    permissions_json = db.Column(db.Text, default='{}') # JSON string of permissions
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def permissions(self):
        try:
            return json.loads(self.permissions_json)
        except:
            return {}

    @permissions.setter
    def permissions(self, value):
        self.permissions_json = json.dumps(value)

class IDFinderUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(100))
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    language_code = db.Column(db.String(10))
    is_bot = db.Column(db.Boolean, default=False)
    avatar_file_id = db.Column(db.String(255))
    photo_file_id = db.Column(db.String(200), nullable=True)
    photo_url = db.Column(db.String(500), nullable=True)
    photo_cached_at = db.Column(db.DateTime, nullable=True)
    first_contact = db.Column(db.DateTime, default=datetime.utcnow)
    last_contact = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_in_group = db.Column(db.Boolean, default=True)  # Track if user is still in the main group
    is_steckbrief_paused = db.Column(db.Boolean, default=False) # Admin toggle to pause the bot
    steckbrief_paused_at = db.Column(db.DateTime, nullable=True) # When was it paused?
    custom_name = db.Column(db.String(200), nullable=True) # Admin-defined name
    is_sidebar_archived = db.Column(db.Boolean, default=False) # Move to archive folder
    # Relationship to messages
    messages = db.relationship('IDFinderMessage', backref='user', lazy=True, cascade="all, delete-orphan")
    # Relationship to warnings
    warnings = db.relationship('IDFinderWarning', backref='user', lazy=True, cascade="all, delete-orphan")

class IDFinderMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.BigInteger, db.ForeignKey('id_finder_user.telegram_id'), nullable=False)
    message_id = db.Column(db.BigInteger)
    chat_id = db.Column(db.BigInteger)
    message_thread_id = db.Column(db.BigInteger)
    chat_type = db.Column(db.String(50)) # private, group, supergroup, channel
    text = db.Column(db.Text)
    content_type = db.Column(db.String(50), default='text') # text, photo, video, etc.
    file_id = db.Column(db.String(255))
    is_command = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    deletion_reason = db.Column(db.Text)
    deleted_by = db.Column(db.String(100), nullable=True) # Username/Name
    deleted_by_id = db.Column(db.BigInteger, nullable=True) # ID des Admins/Users
    deleted_by_name = db.Column(db.String(100), nullable=True) # Voller Name
    is_edited = db.Column(db.Boolean, default=False)
    previous_text = db.Column(db.Text, nullable=True)
    edit_timestamp = db.Column(db.DateTime, nullable=True)
    edited_by = db.Column(db.String(100), nullable=True)
    text_preview = db.Column(db.String(200), nullable=True)
    reply_to_id = db.Column(db.BigInteger, nullable=True)
    reply_to_text = db.Column(db.Text, nullable=True)
    reply_markup = db.Column(db.Text, nullable=True) # JSON of the keyboard
    is_failed = db.Column(db.Boolean, default=False) # Delivery failure
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class IDFinderWarning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.BigInteger, db.ForeignKey('id_finder_user.telegram_id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    admin_id = db.Column(db.BigInteger)
    message_db_id = db.Column(db.Integer, db.ForeignKey('id_finder_message.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class AutoCleanupTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.BigInteger, nullable=False)
    message_id = db.Column(db.BigInteger, nullable=False)
    cleanup_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, done

class TopicCleanupConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.BigInteger, nullable=False)
    topic_name = db.Column(db.String(100)) # Nur für Anzeige im Dashboard
    chat_id = db.Column(db.BigInteger, nullable=True)
    delay_minutes = db.Column(db.Integer, default=1440) # Standard 24h = 1440min
    delete_admins = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- Birthday Bot Models ---
class Birthday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.BigInteger, unique=True, nullable=False)
    chat_id = db.Column(db.BigInteger) # The group where it was registered
    topic_id = db.Column(db.BigInteger, nullable=True) # The topic where it was registered
    username = db.Column(db.String(100))
    first_name = db.Column(db.String(100))
    day = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- Invite Bot Models ---

class InviteApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(100))
    full_name = db.Column(db.String(100))
    answers_json = db.Column(db.Text, default='{}')
    status = db.Column(db.String(20), default='pending') # pending, accepted, rejected, completed
    message_ids_json = db.Column(db.Text, default='[]') # Optional: um gesendete Bewerbungs-Nachrichten später editieren zu können
    profile_message_id = db.Column(db.BigInteger, nullable=True)  # message_id des geposteten Steckbriefs (für Auto-Löschen)
    profile_chat_id = db.Column(db.BigInteger, nullable=True)     # chat_id wo der Steckbrief gepostet wurde
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def answers(self):
        try: return json.loads(self.answers_json)
        except: return {}

    @answers.setter
    def answers(self, value):
        self.answers_json = json.dumps(value)

class InviteLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.BigInteger, nullable=False)
    username = db.Column(db.String(100))
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# --- Admin Permissions Definition ---
AVAILABLE_PERMISSIONS = {
    "Moderation": {
        "can_warn": "Nutzer verwarnen",
        "can_mute": "Nutzer stummschalten",
        "can_kick": "Nutzer kicken",
        "can_ban": "Nutzer bannen",
        "can_delete": "Nachrichten löschen"
    },
    "Management": {
        "can_broadcast": "Broadcasts senden",
        "can_manage_topics": "Topics verwalten",
        "can_view_logs": "Logs einsehen"
    },
    "System": {
        "is_superadmin": "Vollzugriff (Superadmin)",
        "can_manage_admins": "Andere Admins verwalten"
    }
}

# --- Profanity Filter Models ---
class ProfanityWord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), unique=True, nullable=False)
    language = db.Column(db.String(10), default='custom') # 'de', 'en', 'custom'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- Report Bot Models ---
class ReportedMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.BigInteger, nullable=False)
    reporter_name = db.Column(db.String(255))
    reported_user_id = db.Column(db.BigInteger, nullable=True)
    reported_user_name = db.Column(db.String(255))
    reported_message_id = db.Column(db.BigInteger, nullable=True)
    chat_id = db.Column(db.BigInteger, nullable=False)
    chat_type = db.Column(db.String(50), default='group') # group, private
    reason = db.Column(db.Text)
    content_preview = db.Column(db.Text) # Text content or media description
    status = db.Column(db.String(20), default='pending') # pending, processed, dismissed
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# --- Event Planner Models ---
class GroupEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    chat_id = db.Column(db.BigInteger, nullable=False)
    topic_id = db.Column(db.String(50), nullable=True)  # <-- Added Topic ID support
    message_id = db.Column(db.BigInteger, nullable=True)  # Setzt der Bot nach dem Posten
    poll_id = db.Column(db.String(100), unique=True, nullable=True) # ID der Umfrage für RSVP
    should_pin = db.Column(db.Boolean, default=False)
    image_path = db.Column(db.String(255), nullable=True)
    media_type = db.Column(db.String(20), default='photo') # photo, video, animation
    has_spoiler = db.Column(db.Boolean, default=False)
    is_silent = db.Column(db.Boolean, default=False)
    is_split = db.Column(db.Boolean, default=False)
    scheduled_time = db.Column(db.DateTime, nullable=True)
    
    # --- New fields for Calendar & Confirmation ---
    send_confirmation = db.Column(db.Boolean, default=False)
    confirmation_text = db.Column(db.Text, nullable=True)
    calendar_title = db.Column(db.String(255), nullable=True)
    calendar_filename = db.Column(db.String(100), nullable=True, default='termin.ics')
    calendar_url = db.Column(db.String(500))
    confirmation_image_path = db.Column(db.String(255))
    
    # Website & Ticket Links (Group)
    website_url = db.Column(db.String(500), nullable=True)
    website_label = db.Column(db.String(100), nullable=True)
    tickets_url = db.Column(db.String(500), nullable=True)
    tickets_label = db.Column(db.String(100), nullable=True)
    
    # Link Visibility Flags
    website_in_group = db.Column(db.Boolean, default=True)
    website_in_dm = db.Column(db.Boolean, default=True)
    tickets_in_group = db.Column(db.Boolean, default=True)
    tickets_in_dm = db.Column(db.Boolean, default=True)
    location_in_group = db.Column(db.Boolean, default=True)
    location_in_dm = db.Column(db.Boolean, default=True)

    # Website & Ticket Links (DM - Legacy fallback, we'll use flags instead)
    dm_website_url = db.Column(db.String(500), nullable=True)
    dm_website_label = db.Column(db.String(100), nullable=True)
    dm_tickets_url = db.Column(db.String(500), nullable=True)
    dm_tickets_label = db.Column(db.String(100), nullable=True)
    
    # Scheduling
    location = db.Column(db.String(255), nullable=True)
    event_start = db.Column(db.DateTime, nullable=True)
    event_end = db.Column(db.DateTime, nullable=True)
    event_dates_json = db.Column(db.Text, nullable=True) # JSON list of {start, end, label}
    poll_type = db.Column(db.String(50), default='multi_day') # 'standard', 'multi_day', 'days_only'
    interaction_type = db.Column(db.String(20), default='poll') # 'poll', 'buttons'
    poll_show_all_day = db.Column(db.Boolean, default=True)
    poll_show_maybe = db.Column(db.Boolean, default=True)
    poll_show_no = db.Column(db.Boolean, default=True)
    poll_show_yes = db.Column(db.Boolean, default=True)
    poll_show_dates = db.Column(db.Boolean, default=True)
    poll_multiple_choice = db.Column(db.Boolean, default=True)
    poll_config_json = db.Column(db.Text, nullable=True) # Custom labels for options
    send_as_document = db.Column(db.Boolean, default=False) # New: Send media in original quality
    # ---------------------------------------------

    
    needs_update = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to RSVPs
    rsvps = db.relationship('EventRSVP', backref='event', lazy=True, cascade="all, delete-orphan")

class EventRSVP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('group_event.id'), nullable=False)
    telegram_user_id = db.Column(db.BigInteger, nullable=False)
    username = db.Column(db.String(100))
    status = db.Column(db.String(20)) # 'dabei', 'vielleicht', 'nicht_dabei'
    dm_sent_status = db.Column(db.String(20), nullable=True) # 'success', 'failed'
    dm_error = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# --- User Restriction Models ---
class UserRestriction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(100))
    full_name = db.Column(db.String(100))
    is_globally_muted = db.Column(db.Boolean, default=False)
    restricted_topics_json = db.Column(db.Text, default='[]') # JSON list of topic IDs
    reason = db.Column(db.String(255))
    expires_at = db.Column(db.DateTime, nullable=True) # None = Permanent
    
    # Advanced Restrictions
    no_media = db.Column(db.Boolean, default=False)
    no_links = db.Column(db.Boolean, default=False)
    no_stickers = db.Column(db.Boolean, default=False)
    slow_mode_seconds = db.Column(db.Integer, default=0) # 0 = Off
    is_shadow_banned = db.Column(db.Boolean, default=False)
    
    # Tracking
    last_message_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def restricted_topics(self):
        try: return json.loads(self.restricted_topics_json)
        except: return []

    @restricted_topics.setter
    def restricted_topics(self, value):
        self.restricted_topics_json = json.dumps(value)

# --- RSS Feed Models ---
class RSSFeedConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    target_chat_id = db.Column(db.String(50), nullable=False)
    target_topic_id = db.Column(db.String(50), nullable=True)
    admin_chat_id = db.Column(db.String(50), nullable=False)
    admin_topic_id = db.Column(db.String(50), nullable=True)
    auto_post_timeout_hours = db.Column(db.Integer, default=24)
    include_images = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    check_interval_minutes = db.Column(db.Integer, default=30)   # Wie oft prüfen (in Minuten)
    post_time = db.Column(db.String(5), nullable=True)            # z.B. "09:00" - Uhrzeit für automatischen Post (None = sofort)
    
    items = db.relationship('RSSFeedItem', backref='feed', lazy=True, cascade="all, delete-orphan")


class RSSFeedItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    feed_id = db.Column(db.Integer, db.ForeignKey('rss_feed_config.id'), nullable=False)
    guid = db.Column(db.String(255), nullable=False) # Unique identifier from RSS
    title = db.Column(db.String(500))
    link = db.Column(db.String(500))
    pub_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pending_approval') # pending_approval, approved, rejected, posted, timeout_posted
    admin_message_id = db.Column(db.BigInteger, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

