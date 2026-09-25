import json
import logging
import asyncio
from telegram import Update
from telegram.ext import MessageHandler, filters, ContextTypes, TypeHandler
from shared_bot_utils import get_bot_config, is_bot_active

logger = logging.getLogger(__name__)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Reaction Bot: handle_message TRIGGERED! update.message: {bool(update.message)}")
    # Check if bot is active globally
    if not is_bot_active('reaction_bot'):
        logger.info("Reaction Bot is NOT active globally.")
        return

    config = get_bot_config('reaction_bot')
    rules = config.get('rules', [])
    if not rules:
        return

    # Check if message exists
    if not update.message:
        logger.info("Reaction Bot: No message in update.")
        return

    message = update.message
    text = message.text or message.caption or ""
    
    # Determine media type of the incoming message
    is_image = bool(message.photo)
    is_audio = bool(message.audio or message.voice)
    is_video = bool(message.video or message.animation or message.document)
    
    for rule in rules:
        if not rule.get('is_active', False):
            continue
            
        # 1. Check chat type constraint
        rule_chat_type = rule.get('chat_type', 'all')
        is_private = message.chat.type == "private"
        if rule_chat_type == 'group' and is_private:
            continue
        if rule_chat_type == 'private' and not is_private:
            continue

        trigger_type = rule.get('trigger_type')
        trigger_text = rule.get('trigger_text', '').lower().strip()
        reaction_type = rule.get('reaction_type')
        reaction_emoji = rule.get('reaction_emoji')
        
        if not reaction_emoji:
            continue

        match_found = False
        logger.info(f"Checking rule: {rule}, Text: {text}, is_image: {is_image}")
        
        if trigger_type == 'keyword':
            if trigger_text and trigger_text.strip() in text.lower():
                match_found = True
        elif trigger_type == 'all_text' and text.strip():
            match_found = True
        elif trigger_type == 'media_image' and is_image:
            match_found = True
        elif trigger_type == 'media_audio' and is_audio:
            match_found = True
        elif trigger_type == 'media_video' and is_video:
            match_found = True
            
        if match_found:
            logger.info(f"Reaction Bot: Match found! Reaction type: {reaction_type}, Emoji: {reaction_emoji}")
            if reaction_type == 'reaction':
                try:
                    await message.set_reaction(reaction=reaction_emoji)
                except Exception as e:
                    logger.error(f"Reaction Bot Error (Normal Reaction): {e}")
                    
            elif reaction_type == 'effect':
                try:
                    # Use the user-defined secondary emoji, or default to a thumbs up if not set
                    fallback_emoji = rule.get('secondary_emoji')
                    if not fallback_emoji:
                        fallback_emoji = "👍"
                    
                    # 1. First, set a normal reaction on the user's actual message
                    try:
                        await message.set_reaction(reaction=fallback_emoji)
                    except:
                        pass # Ignore if this fails

                    # 2. Store the effect to be attached to the bot's actual response message
                    # instead of sending an intrusive "." carrier message.
                    from shared_bot_utils import PENDING_EFFECTS
                    import time
                    PENDING_EFFECTS[message.chat_id] = (reaction_emoji, time.time())
                except Exception as e:
                    if "Can't use message effects in the chat" in str(e):
                        logger.warning("Premium effect blocked by Telegram in this chat type. Falling back to normal reaction.")
                        # Fallback mapping from effect ID to standard emoji
                        fallback_map = {
                            "5104841245755180586": "🔥",
                            "5107584321108051014": "👍",
                            "5104858069142078462": "🎉",
                            "5044134455711629726": "❤️",
                            "5046509860389126442": "😂",
                            "5046589136895476101": "😭"
                        }
                        fallback_emoji = fallback_map.get(str(reaction_emoji), "👍")
                        try:
                            await message.set_reaction(reaction=fallback_emoji)
                        except Exception as fallback_err:
                            logger.error(f"Reaction Bot Error (Fallback Reaction): {fallback_err}")
                    else:
                        logger.error(f"Reaction Bot Error (Premium Effect): {e}")

def get_handlers():
    return [
        (TypeHandler(Update, handle_message), -2) 
    ]
