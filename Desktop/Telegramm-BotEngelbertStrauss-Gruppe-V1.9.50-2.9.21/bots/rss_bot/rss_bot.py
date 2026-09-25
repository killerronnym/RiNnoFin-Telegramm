import logging
import os
import urllib.request
import xml.etree.ElementTree as ET
import re
import html
import urllib.parse
import json
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import ContextTypes, CallbackQueryHandler

from shared_bot_utils import get_shared_flask_app
try:
    from web_dashboard.app.models import db, RSSFeedConfig, RSSFeedItem
except ImportError:
    db = None
    RSSFeedConfig = None
    RSSFeedItem = None

logger = logging.getLogger("RSSBot")
logger.setLevel(logging.INFO)

NS = {"a": "http://www.w3.org/2005/Atom"}
UA = {"User-Agent": "Mozilla/5.0 (StraussFeedBot)"}

def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def strip_html(s: str) -> str:
    s = re.sub(r"<(br|/p|/div|/li)[^>]*>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n\n", s).strip()

def clean_img(u: str) -> str:
    u = html.unescape(u)
    if u.startswith("//"):
        u = "https:" + u
    u = re.sub(r"^http://", "https://", u)
    base, _, q = u.partition("?")
    params = urllib.parse.parse_qs(q)
    v = params.get("v", [""])[0]
    return f"{base}?width=1600" + (f"&v={v}" if v else "")

def get_images(article_url: str) -> list:
    try:
        page = http_get(article_url)
    except Exception:
        return []
    imgs = []
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', page) or \
        re.search(r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"', page)
    if m:
        imgs.append(clean_img(m.group(1)))
    a = page.find("<article")
    body = page[a:page.find("</article>", a)] if a != -1 else ""
    for u in re.findall(r'(?:src|srcset)="([^"\s]*?/cdn/shop/(?:articles|files)/[^"\s]+?\.(?:jpe?g|png|webp)[^"\s]*)', body, flags=re.I):
        if re.search(r"logo|icon|favicon", u, re.I):
            continue
        c = clean_img(u)
        if c.split("?")[0] not in [i.split("?")[0] for i in imgs]:
            imgs.append(c)
    return imgs

def build_caption(feed_name, title, link, date_str, summary) -> str:
    esc = lambda s: html.escape(s, quote=False)
    if len(date_str) == 10:
        date_de = f"{date_str[8:10]}.{date_str[5:7]}.{date_str[0:4]}"
    else:
        date_de = date_str
    
    # Use blockquote for the feed name/date header to make it look premium
    head = f"<blockquote><b>{esc(feed_name)}</b>\n<i>{date_de}</i></blockquote>\n\n"
    
    # Main Title
    head += f"<b>{esc(title)}</b>\n\n"
    
    # Body text - telegram allows up to 32,768 chars now (or 1024 historically, but expanded recently)
    # We will preserve paragraph formatting by using double newlines
    body = esc(summary)
    
    # Clean up excessive newlines
    body = re.sub(r'\n{3,}', '\n\n', body)
    
    # Footer link
    foot = f'\n\n<a href="{esc(link)}">âž¡ï¸ Zur Pressemitteilung</a>'
    
    return head + body + foot

def abs_url(u: str, base: str) -> str:
    u = html.unescape(u.strip())
    if u.startswith("//"):
        u = "https:" + u
    u = urllib.parse.urljoin(base, u)
    return re.sub(r"^http://", "https://", u)

def haix_full_img(u: str) -> str:
    return re.sub(r"-\d{2,4}x\d{2,4}(\.(?:jpe?g|png|webp))$", r"\1", u, flags=re.I)

def fetch_haix_items(url: str):
    page = http_get(url)
    m = re.search(r"<main\b.*?</main>", page, flags=re.S | re.I)
    content = m.group(0) if m else page
    
    pdfs = list(re.finditer(r'href="([^"]+?\.pdf)"', content, flags=re.I))
    items, prev_end = [], 0
    for pm in pdfs:
        a_start = content.rfind("<a", prev_end, pm.start())
        seg = content[prev_end:a_start if a_start != -1 else pm.start()]
        prev_end = pm.end()
        pdf = abs_url(pm.group(1), url)

        heads = re.findall(r"<h1[^>]*>(.*?)</h1>", seg, flags=re.S | re.I)
        title = strip_html(heads[-1]) if heads else ""
        tpos = seg.rfind("<h1") if heads else -1
        if not title:
            h = re.search(r"<h[23][^>]*>(.*?)</h[23]>", seg, flags=re.S | re.I)
            title, tpos = (strip_html(h.group(1)), h.start()) if h else ("", -1)
        if not title:
            continue

        after = seg[tpos:] if tpos >= 0 else seg
        sub = re.search(r"<h[23][^>]*>(.*?)</h[23]>", after[4:], flags=re.S | re.I)
        subtitle = strip_html(sub.group(1)) if sub else ""
        text = strip_html(after)
        text = text.replace(title, "", 1).replace(subtitle, "", 1).strip()

        d = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text) or re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", seg)
        if d:
            date_str = f"{d.group(3)}-{int(d.group(2)):02d}-{int(d.group(1)):02d}"
        else:
            continue
            
        text = re.sub(r"^[^\n–-]{0,40}\d{1,2}\.\d{1,2}\.\d{4}\s*[–-]\s*", "", text)
        summary = (subtitle + "\n\n" + text).strip() if subtitle else text

        items.append({
            "guid": pdf,
            "title": title,
            "link": pdf,
            "date_str": date_str,
            "summary": summary
        })
    return items

def fetch_atom_items(url: str):
    root = ET.fromstring(http_get(url))
    entries = root.findall("a:entry", NS)
    items = []
    for e in entries:
        link = ""
        for l in e.findall("a:link", NS):
            if l.get("rel", "alternate") == "alternate":
                link = l.get("href", "")
        guid = (e.findtext("a:id", "", NS) or link).strip()
        title = (e.findtext("a:title", "", NS) or "").strip()
        date_str = (e.findtext("a:published", "", NS) or e.findtext("a:updated", "", NS) or "")[:10]
        summary = strip_html(e.findtext("a:summary", "", NS) or e.findtext("a:content", "", NS) or "")
        items.append({
            "guid": guid,
            "title": title,
            "link": link,
            "date_str": date_str,
            "summary": summary
        })
    return items

async def check_feeds_job(context: ContextTypes.DEFAULT_TYPE):
    app = get_shared_flask_app()
    if not app:
        return
        
    with app.app_context():
        feeds = RSSFeedConfig.query.filter_by(is_active=True).all()
        for feed in feeds:
            try:
                if "haix" in feed.url.lower():
                    parsed_items = fetch_haix_items(feed.url)
                else:
                    parsed_items = fetch_atom_items(feed.url)
            except Exception as e:
                logger.error(f"Error parsing feed {feed.url}: {e}")
                continue
                
            for p_item in reversed(parsed_items):
                guid = p_item['guid']
                title = p_item['title']
                link = p_item['link']
                date_str = p_item['date_str']
                summary = p_item['summary']
                
                existing = RSSFeedItem.query.filter_by(feed_id=feed.id, guid=guid).first()
                if existing:
                    continue
                
                logger.info(f"New RSS item found: {title}")
                
                new_item = RSSFeedItem(
                    feed_id=feed.id,
                    guid=guid,
                    title=title,
                    link=link,
                    pub_date=datetime.utcnow(),
                    status='pending_approval'
                )
                db.session.add(new_item)
                db.session.flush()
                
                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("âœ… Genehmigen & Posten", callback_data=f"rss_approve_{new_item.id}")],
                    [InlineKeyboardButton("â Œ Ablehnen", callback_data=f"rss_reject_{new_item.id}")]
                ])
                
                admin_caption = (
                    f"\U0001f514 <b>Neuer RSS Artikel zur Genehmigung</b>\n\n"
                    f"<b>{html.escape(title)}</b>\n"
                    f"<i>{html.escape(feed.name)}</i>\n\n"
                    f"<a href=\"{html.escape(link)}\">\u27a1\ufe0f Zum Artikel</a>\n\n"
                    f"\u23f0 Ohne Aktion wird nach <b>{feed.auto_post_timeout_hours}h</b> automatisch gepostet."
                )
                
                try:
                    kwargs = {"chat_id": feed.admin_chat_id, "text": admin_caption, "parse_mode": "HTML", "reply_markup": reply_markup, "disable_web_page_preview": False}
                    if feed.admin_topic_id:
                        kwargs["message_thread_id"] = int(feed.admin_topic_id)
                    
                    msg = await context.bot.send_message(**kwargs)
                    new_item.admin_message_id = msg.message_id
                except Exception as e:
                    logger.error(f"Failed to send RSS approval to admin: {e}")
                
                db.session.commit()

async def auto_post_job(context: ContextTypes.DEFAULT_TYPE):
    app = get_shared_flask_app()
    if not app:
        return
        
    with app.app_context():
        # Find all pending that have timed out AND explicitly 'approved'
        items_to_check = RSSFeedItem.query.filter(RSSFeedItem.status.in_(['pending_approval', 'approved'])).all()
        now = datetime.utcnow()
        for item in items_to_check:
            feed = item.feed
            if not feed or not feed.is_active:
                continue
                
            if item.status == 'approved':
                # Force immediate post if approved from web interface
                await post_feed_item(context, item, feed, auto=False)
            else:
                timeout_hours = feed.auto_post_timeout_hours
                if timeout_hours > 0 and (now - item.created_at) > timedelta(hours=timeout_hours):
                    # Auto-post!
                    await post_feed_item(context, item, feed, auto=True)

async def post_feed_item(context: ContextTypes.DEFAULT_TYPE, item: RSSFeedItem, feed: RSSFeedConfig, auto=False):
    caption = build_caption(feed.name, item.title, item.link, item.pub_date.strftime("%Y-%m-%d") if item.pub_date else "", "")
    
    # Needs re-fetching summary for clean caption (since we didn't save summary to DB)
    # Actually, we can fetch from live link or just use a minimal caption
    # Let's fetch page again to get images anyway
    imgs = []
    if feed.include_images:
        imgs = get_images(item.link)
    
    imgs = imgs[:10] # Max 10 for album
    
    kwargs = {"chat_id": feed.target_chat_id, "parse_mode": "HTML"}
    if feed.target_topic_id:
        kwargs["message_thread_id"] = int(feed.target_topic_id)
        
    try:
        if len(imgs) >= 2:
            media = [InputMediaPhoto(media=u) for u in imgs]
            media[0].caption = caption
            media[0].parse_mode = "HTML"
            await context.bot.send_media_group(media=media, **kwargs)
        elif len(imgs) == 1:
            await context.bot.send_photo(photo=imgs[0], caption=caption, **kwargs)
        else:
            kwargs["text"] = caption
            kwargs["link_preview_options"] = {"url": item.link, "prefer_large_media": True, "show_above_text": True}
            await context.bot.send_message(**kwargs)
            
        item.status = 'timeout_posted' if auto else 'posted'
        
        # Update admin message to remove buttons
        if item.admin_message_id:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=feed.admin_chat_id,
                    message_id=item.admin_message_id,
                    reply_markup=None
                )
                text = "â³ <i>Automatisch gepostet (Timeout)</i>" if auto else "âœ… <i>Von Admin genehmigt</i>"
                await context.bot.send_message(
                    chat_id=feed.admin_chat_id,
                    reply_to_message_id=item.admin_message_id,
                    text=text,
                    parse_mode="HTML"
                )
            except Exception:
                pass
                
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to post RSS item {item.id}: {e}")

async def handle_rss_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    app = get_shared_flask_app()
    with app.app_context():
        if data.startswith("rss_approve_"):
            item_id = int(data.split("_")[2])
            item = RSSFeedItem.query.get(item_id)
            if item and item.status == 'pending_approval':
                await post_feed_item(context, item, item.feed, auto=False)
                await query.answer("Gepostet!")
            else:
                await query.answer("Schon bearbeitet.", show_alert=True)
                
        elif data.startswith("rss_reject_"):
            item_id = int(data.split("_")[2])
            item = RSSFeedItem.query.get(item_id)
            if item and item.status == 'pending_approval':
                item.status = 'rejected'
                db.session.commit()
                await query.answer("Abgelehnt.")
                try:
                    await query.edit_message_reply_markup(reply_markup=None)
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        reply_to_message_id=query.message.message_id,
                        text="âŒ <i>Wurde abgelehnt und wird nicht gepostet.</i>",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            else:
                await query.answer("Schon bearbeitet.", show_alert=True)

def get_handlers():
    return [
        CallbackQueryHandler(handle_rss_callback, pattern="^rss_(approve|reject)_")
    ]

def get_fallback_handlers():
    return []

def setup_jobs(application):
    application.job_queue.run_repeating(check_feeds_job, interval=300, first=10) # Every 5 mins
    application.job_queue.run_repeating(auto_post_job, interval=300, first=30) # Every 5 mins


