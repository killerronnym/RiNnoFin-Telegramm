import re

filepath = r'c:\Users\Ronny M PC\Desktop\Telegramm-BotEngelbertStrauss-Gruppe-V1.9.50-2.9.21\bots\invite_bot\invite_bot.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Make generate_profile_text pass is_admin_view=True when generating the approval post
content = content.replace(
    r'final_text, _, _buttons = generate_profile_text(user, answers, ordered_fields)',
    r'final_text, _, _buttons = generate_profile_text(user, answers, ordered_fields, is_admin_view=True)'
)

# And when saving `profile_data` or `approval_post_data` or `reconstructed_profile`
content = re.sub(
    r"'text':\s*final_text,",
    r"'text': final_text,\n                'buttons': _buttons,",
    content
)

# Wait! There's also `reconstructed` which uses `profile_text`
content = re.sub(
    r"'text':\s*profile_text,",
    r"'text': profile_text,\n                'buttons': _buttons,",
    content
)

# One place is:
#                     reconstructed_profile = {
#                         'text': final_text,
# ...

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixes applied.")
