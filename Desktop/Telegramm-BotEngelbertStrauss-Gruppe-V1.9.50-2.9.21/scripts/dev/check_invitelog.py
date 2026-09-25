import os
import sys

# Add project root to path for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from web_dashboard.app import create_app
from web_dashboard.app.models import InviteLog

app = create_app()
with app.app_context():
    logs = InviteLog.query.all()
    print(f"Total InviteLog entries: {len(logs)}")
    for log in logs[:10]:
        print(f"ID={log.id} | Action={log.action} | User={log.username}")
