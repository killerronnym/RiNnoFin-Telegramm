"""
Einmaliger RSS-Feed-Test mit detaillierter Fehlerausgabe
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import urllib.request, urllib.error
import xml.etree.ElementTree as ET
import html, re

from web_dashboard.app import create_app, db
from web_dashboard.app.models import RSSFeedConfig, RSSFeedItem, BotSettings

NS = {"a": "http://www.w3.org/2005/Atom"}
UA = {"User-Agent": "Mozilla/5.0 (StraussFeedBot)"}

def http_get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def strip_html(s):
    s = re.sub(r"<(br|/p|/div|/li)[^>]*>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n\n", s).strip()

def tg_send(token, method, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=data, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  HTTP {e.code}: {body}")
        return {"ok": False, "error": body}

def main():
    flask_app = create_app()
    with flask_app.app_context():
        s = BotSettings.query.filter_by(bot_name='invite').first()
        cfg = json.loads(s.config_json) if s else {}
        token = cfg.get('bot_token') or os.environ.get('TELEGRAM_BOT_TOKEN', '')

        if not token:
            print("ERROR: Kein Bot-Token!")
            return
        print(f"Token: {token[:10]}...")

        # Test: Bot info abfragen
        me = tg_send(token, "getMe", {})
        if not me.get("ok"):
            print("ERROR: Token ungueltig oder Bot offline!")
            return
        print(f"Bot: @{me['result']['username']}")

        feeds = RSSFeedConfig.query.filter_by(is_active=True).all()

        for feed in feeds:
            print(f"\nFeed: ID={feed.id} | admin={feed.admin_chat_id} topic={feed.admin_topic_id}")
            try:
                root = ET.fromstring(http_get(feed.url))
            except Exception as e:
                print(f"  Feed-Fehler: {e}")
                continue

            entry = root.findall("a:entry", NS)[0]
            link = ""
            for l in entry.findall("a:link", NS):
                if l.get("rel", "alternate") == "alternate":
                    link = l.get("href", "")
            guid = (entry.findtext("a:id", "", NS) or link).strip()
            title = (entry.findtext("a:title", "", NS) or "").strip()
            date_str = (entry.findtext("a:published", "", NS) or entry.findtext("a:updated", "", NS) or "")[:10]

            # DB-Eintrag
            existing = RSSFeedItem.query.filter_by(feed_id=feed.id, guid=guid).first()
            if existing:
                existing.status = 'pending_approval'
                existing.admin_message_id = None
                db.session.commit()
                item = existing
            else:
                from datetime import datetime
                item = RSSFeedItem(feed_id=feed.id, guid=guid, title=title, link=link,
                                   pub_date=datetime.utcnow(), status='pending_approval')
                db.session.add(item)
                db.session.flush()

            # Proper HTML caption
            if len(date_str) == 10:
                date_de = f"{date_str[8:10]}.{date_str[5:7]}.{date_str[0:4]}"
            else:
                date_de = date_str
            import html as html_mod
            caption = (
                f"\U0001f514 <b>Neuer RSS Artikel zur Genehmigung</b>\n\n"
                f"<b>{html_mod.escape(title)}</b>\n"
                f"<i>{html_mod.escape(feed.name)} \u00b7 {date_de}</i>\n\n"
                f"<a href=\"{html_mod.escape(link)}\">\u27a1\ufe0f Zum Artikel</a>\n\n"
                f"\u23f0 Bitte genehmigen oder ablehnen. Ohne Aktion wird der Artikel nach {feed.auto_post_timeout_hours}h automatisch gepostet."
            )

            keyboard = {"inline_keyboard": [[
                {"text": "\u2705 Genehmigen & Posten", "callback_data": f"rss_approve_{item.id}"},
                {"text": "\u274c Ablehnen",            "callback_data": f"rss_reject_{item.id}"}
            ]]}

            payload = {
                "chat_id": feed.admin_chat_id,
                "text": caption,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
                "reply_markup": keyboard
            }
            if feed.admin_topic_id:
                payload["message_thread_id"] = int(feed.admin_topic_id)

            print(f"  Sende an chat={feed.admin_chat_id} topic={feed.admin_topic_id}...")
            result = tg_send(token, "sendMessage", payload)
            if result.get("ok"):
                item.admin_message_id = result["result"]["message_id"]
                db.session.commit()
                print(f"  GESENDET! msg_id={item.admin_message_id}")
            else:
                print(f"  FEHLGESCHLAGEN: {result}")

if __name__ == "__main__":
    main()
