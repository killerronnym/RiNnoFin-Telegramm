import json
from datetime import datetime, timezone

file_path = r'C:\Users\Ronny M PC\Documents\RiNnoFin-Telegramm\manifest.json'
with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

new_version = {
    'version': '1.0.4.56',
    'changelog': 'Bugfixes: Telegram-Bot Endlosschleife behoben (Inaktivitaetsschwelle auf 1 Woche erhoeht, sauberes Zuruecksetzen, weniger Log-Spam).',
    'targetAbi': '10.9.0.0',
    'sourceUrl': 'https://raw.githubusercontent.com/killerronnym/RiNnoFin-Telegramm/master/publish_release/RiNnoFinTelegramm_1.0.4.56.zip',
    'checksum': 'd48c68956216d7be005ef97d934f33e6',
    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
}

data[0]['versions'].insert(0, new_version)

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('manifest.json updated successfully.')
