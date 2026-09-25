import re

filepath = r'c:\Users\Ronny M PC\Desktop\Telegramm-BotEngelbertStrauss-Gruppe-V1.9.50-2.9.21\bots\invite_bot\invite_bot.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Update signature
content = re.sub(
    r'def generate_profile_text\(user: User, answers: Dict\[str, Any\], ordered_fields: List\[Dict\[str, Any\]\]\) -> tuple\[str, bool\]:',
    r'def generate_profile_text(user: User, answers: Dict[str, Any], ordered_fields: List[Dict[str, Any]], is_admin_view: bool = False) -> tuple[str, bool, list]:',
    content
)

# Replace all calls unpacking 2 values to unpack 3 values
content = re.sub(
    r'([a-zA-Z0-9_]+),\s*([a-zA-Z0-9_]+)\s*=\s*generate_profile_text\((.*?)\)',
    r'\1, \2, _buttons = generate_profile_text(\3)',
    content
)

# Update logic inside generate_profile_text
old_logic = '''        else:
            emoji = field.get('emoji', '🔹')
            name = field.get('display_name', fid.capitalize())
            
            is_social_field = fid == 'instagram' or 'social' in fid.lower() or 'social' in field.get('display_name', '').lower() or 'insta' in field.get('display_name', '').lower()
            if is_social_field:
                answers_list = answer if isinstance(answer, list) else [answer]
                formatted_socials = []
                for entry in answers_list:
                    if isinstance(entry, dict):
                        m_url = entry.get('url', '#')
                        m_name = entry.get('name', 'Link')
                        formatted_socials.append(f'<a href="{m_url}">{m_name}</a>')
                    else:
                        formatted_socials.append(str(entry))
                answer = ", ".join(formatted_socials)
            
            steckbrief_lines.append(f"{emoji} <b>{name}:</b> {answer}")
    
    # Header + optionaler Telegram-Username'''

new_logic = '''        else:
            if field.get('admin_only') and not is_admin_view:
                continue
                
            emoji = field.get('emoji', '🔹')
            name = field.get('display_name', fid.capitalize())
            
            is_social_field = fid == 'instagram' or 'social' in fid.lower() or 'social' in field.get('display_name', '').lower() or 'insta' in field.get('display_name', '').lower()
            if is_social_field:
                answers_list = answer if isinstance(answer, list) else [answer]
                for entry in answers_list:
                    if isinstance(entry, dict):
                        m_url = entry.get('url', '#')
                        m_name = entry.get('name', 'Link')
                        buttons_list.append([telegram.InlineKeyboardButton(m_name, url=m_url)])
                    else:
                        url = str(entry).strip()
                        if not url.startswith('http'):
                            if fid == 'instagram' or 'insta' in url.lower():
                                url = f"https://instagram.com/{url.replace('@', '')}"
                            else:
                                url = f"https://{url}"
                        buttons_list.append([telegram.InlineKeyboardButton(f"{emoji} {name}", url=url)])
                continue
            
            steckbrief_lines.append(f"{emoji} <b>{name}:</b> {answer}")
    
    # Header + optionaler Telegram-Username'''

content = content.replace("steckbrief_lines = []\n    pm_allowed_status = None", "steckbrief_lines = []\n    pm_allowed_status = None\n    buttons_list = []")
content = content.replace(old_logic, new_logic)
content = content.replace('final_text += f"\\n\\n{banner_emoji} <b>{banner_text}</b>"\n        \n    return final_text, has_actual_data', 'final_text += f"\\n\\n{banner_emoji} <b>{banner_text}</b>"\n        \n    return final_text, has_actual_data, buttons_list')
# In case pm banner isn't the exact end
content = re.sub(r'return final_text, has_actual_data\s*$', 'return final_text, has_actual_data, buttons_list\n', content, flags=re.MULTILINE)

# Now we need to patch post_profile to accept reply_markup
# find post_profile definition
post_profile_old = '''async def post_profile(bot, profile_data: Dict[str, Any], is_approval_post: bool = False):
    target_chat_id = profile_data['target_chat_id']
    kwargs = {"chat_id": target_chat_id}'''

post_profile_new = '''async def post_profile(bot, profile_data: Dict[str, Any], is_approval_post: bool = False):
    import telegram
    target_chat_id = profile_data['target_chat_id']
    kwargs = {"chat_id": target_chat_id}
    if profile_data.get('buttons'):
        kwargs['reply_markup'] = telegram.InlineKeyboardMarkup(profile_data['buttons'])'''

content = content.replace(post_profile_old, post_profile_new)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("File updated!")
