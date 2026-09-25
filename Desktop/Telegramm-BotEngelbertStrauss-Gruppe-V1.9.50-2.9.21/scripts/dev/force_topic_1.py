import os
import sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from web_dashboard.app import create_app
from web_dashboard.app.models import db, TopicMapping

app = create_app()
with app.app_context():
    # ID 1 (oder NULL) ist oft die Vorstellungsrunde/Hauptchat
    topic = TopicMapping.query.filter_by(topic_id=1).first()
    if not topic:
        new_topic = TopicMapping(topic_id=1, topic_name="Vorstellungsrunde", is_active=True)
        db.session.add(new_topic)
        db.session.commit()
        print("Vorstellungsrunde (ID 1) wurde erfolgreich angelegt.")
    else:
        topic.topic_name = "Vorstellungsrunde"
        topic.is_active = True
        db.session.commit()
        print("Vorstellungsrunde war bereits vorhanden und wurde aktualisiert.")
