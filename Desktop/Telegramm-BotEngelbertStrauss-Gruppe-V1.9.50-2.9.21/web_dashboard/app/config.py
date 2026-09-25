import os
import sys

# Get absolute path to the project root so we can import shared_bot_utils
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from shared_bot_utils import get_db_url

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-me'
    SQLALCHEMY_DATABASE_URI = get_db_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'timeout': 30
        }
    }
    
    # Bot Settings
    BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or os.environ.get('BOT_TOKEN')
    OWNER_ID = os.environ.get('OWNER_ID')
    GROUP_ID = os.environ.get('GROUP_ID')
    TOPIC_ID = os.environ.get('TOPIC_ID')
    
    # GitHub Update Settings
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
    GITHUB_REPO_OWNER = os.environ.get('GITHUB_REPO_OWNER') or 'killerronnym'
    GITHUB_REPO_NAME = os.environ.get('GITHUB_REPO_NAME') or 'Telegramm-BotEngelbertStrauss-Gruppe-V1.9.50'
    
    # Dashboard Settings
    TITLE = "Bot Dashboard"
    
    # File Upload - allow up to 100MB for database restore
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB
