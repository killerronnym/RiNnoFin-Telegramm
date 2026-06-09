import re

file_path = 'c:/Users/Ronny M PC/Documents/Jellyfin  Telegramm/RiNnoFin Telegramm/RiNnoFinTelegramm/Assets/Config/config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

style = '''
<style>
  .rinnofin-layout { display: flex; flex-direction: row; min-height: 80vh; margin-top: 10px; }
  .rinnofin-sidebar { width: 250px; border-right: 1px solid rgba(255,255,255,0.1); padding-right: 15px; flex-shrink: 0; }
  .rinnofin-content { flex: 1; padding-left: 20px; overflow-x: auto; }
  .rinnofin-tab { display: none; }
  .rinnofin-tab.active { display: block; }
  .rinnofin-menu-item { padding: 10px 15px; margin-bottom: 5px; cursor: pointer; border-radius: 4px; transition: background 0.2s; }
  .rinnofin-menu-item:hover { background: rgba(255,255,255,0.05); }
  .rinnofin-menu-item.active { background: #00a4dc; color: #fff; font-weight: bold; }
  .action-btn-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 15px; background: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px; }
  .action-btn { background: #374151; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
  .action-btn:hover { background: #4b5563; }
  .action-btn.btn-green { background: #10b981; } .action-btn.btn-green:hover { background: #059669; }
  .action-btn.btn-red { background: #ef4444; } .action-btn.btn-red:hover { background: #dc2626; }
  .action-btn.btn-blue { background: #3b82f6; } .action-btn.btn-blue:hover { background: #2563eb; }
  .action-btn.btn-yellow { background: #f59e0b; } .action-btn.btn-yellow:hover { background: #d97706; }
  .action-btn.btn-purple { background: #8b5cf6; } .action-btn.btn-purple:hover { background: #7c3aed; }
</style>
'''

layout_start = style + '''
<div class="rinnofin-layout">
    <div class="rinnofin-sidebar" id="rinnofin-sidebar-menu">
        <div class="rinnofin-menu-item active" data-tab="tab-general">🔌 Telegram & Allgemein</div>
        <div class="rinnofin-menu-item" data-tab="tab-groups">👥 Gruppenverwaltung</div>
        <div class="rinnofin-menu-item" data-tab="tab-users">👥 Benutzerverwaltung</div>
        <div class="rinnofin-menu-item" data-tab="tab-user-settings">⚙️ Benutzereinstellungen</div>
        <div class="rinnofin-menu-item" data-tab="tab-email">📧 E-Mail-Einstellungen</div>
        <div class="rinnofin-menu-item" data-tab="tab-messages">✉️ Verlauf & Anfragen</div>
        <div class="rinnofin-menu-item" data-tab="tab-logs">📋 Protokoll (Logs)</div>
    </div>
    
    <div class="rinnofin-content">
'''

layout_end = '''
    </div>
</div>
'''

def extract_block(form_id):
    pattern = r'<div class="block">\s*<form id="' + form_id + r'".*?</form>\s*</div>'
    match = re.search(pattern, content, re.DOTALL)
    return match.group(0) if match else ''

info_block = extract_block('InfoSectionForm')
branding_block = extract_block('BrandingSectionForm')
basic_config_block = extract_block('BasicConfigForm')
group_management_block = extract_block('GroupManagementForm')
request_management_block = extract_block('RequestManagementForm')
user_management_block = extract_block('UserManagementForm')

new_user_management = '''
        <div id="tab-users" class="rinnofin-tab block">
            <form id="UserManagementForm">
                <fieldset class="verticalSection">
                    <legend><h3>Benutzerverwaltung</h3></legend>
                    
                    <div class="action-btn-bar">
                        <button class="action-btn" id="ActionLoadAll" type="button">Load All</button>
                        <button class="action-btn btn-green" id="ActionAddUser" type="button">Benutzer hinzufügen</button>
                        <button class="action-btn" id="ActionAnnounce" type="button">Ankündigen</button>
                        <button class="action-btn" id="ActionSettings" type="button">Einstellungen ändern</button>
                        <button class="action-btn" id="ActionRecommendations" type="button">Empfehlungen aktivieren</button>
                        <button class="action-btn" id="ActionExpiry" type="button">Ablaufdatum</button>
                        <button class="action-btn btn-yellow" id="AdminDisableUser" type="button">Deaktivieren / Aktivieren</button>
                        <button class="action-btn btn-purple" id="AdminSendPasswordReset" type="button">Sende Passwortrücksetzung</button>
                        <button class="action-btn btn-red" id="AdminDeleteUser" type="button">Benutzer löschen</button>
                    </div>

                    <div id="InviteUserPanel" style="display:none; background: rgba(0,0,0,0.1); padding: 15px; margin-bottom: 15px; border-radius: 6px;">
                        <h3>Neuen Benutzer einladen</h3>
                        <div style="display: flex; gap: 10px; margin-bottom: 10px;">
                            <div style="flex: 1;">
                                <label class="inputLabel" for="InviteEmail">E-Mail Adresse:</label>
                                <input class="sso-text" id="InviteEmail" is="emby-input" type="email" placeholder="example@example.com"/>
                            </div>
                            <div style="flex: 1;">
                                <label class="inputLabel" for="InviteProfile">Profil-Vorlage (Rechte klonen):</label>
                                <select class="emby-select-withcolor emby-select" id="InviteProfile" is="emby-select">
                                    <option value="">Lade Profile...</option>
                                </select>
                            </div>
                        </div>
                        <button class="action-btn btn-green" id="CreateInviteBtn" type="button">Einladung Senden</button>
                        <button class="action-btn" id="CancelInviteBtn" type="button">Abbrechen</button>
                    </div>

                    <div class="tableScrollSlider" style="overflow-x: auto;">
                        <table class="tableDetail" style="width: 100%; text-align: left; border-collapse: collapse;">
                            <thead>
                                <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
                                    <th style="padding: 10px; width: 40px;"><input type="checkbox" id="SelectAllUsers" is="emby-checkbox"/></th>
                                    <th style="padding: 10px;">Benutzername</th>
                                    <th style="padding: 10px;">Status</th>
                                    <th style="padding: 10px;">E-Mail</th>
                                    <th style="padding: 10px;">Telegram</th>
                                    <th style="padding: 10px;">Letzter Zugriff</th>
                                </tr>
                            </thead>
                            <tbody id="UserListTbody">
                            </tbody>
                        </table>
                    </div>
                </fieldset>
            </form>
        </div>
'''

tabs_html = layout_start + f'''
        <div id="tab-general" class="rinnofin-tab active block">
            {info_block}
            {branding_block}
            {basic_config_block}
        </div>
        <div id="tab-groups" class="rinnofin-tab block">
            {group_management_block}
        </div>
        {new_user_management}
        <div id="tab-user-settings" class="rinnofin-tab block">
            <fieldset class="verticalSection">
                <legend><h3>Benutzereinstellungen</h3></legend>
                <p>Hier kommen künftig Standard-Ablaufdaten und globale Profil-Vorlagen hin.</p>
            </fieldset>
        </div>
        <div id="tab-email" class="rinnofin-tab block">
            <fieldset class="verticalSection">
                <legend><h3>E-Mail-Einstellungen</h3></legend>
                <p>Die SMTP-Einstellungen findest du aktuell noch im Reiter 'Telegram & Allgemein'. Sie werden in Zukunft hierher ausgelagert.</p>
            </fieldset>
        </div>
        <div id="tab-messages" class="rinnofin-tab block">
            {request_management_block}
        </div>
        <div id="tab-logs" class="rinnofin-tab block">
            <fieldset class="verticalSection">
                <legend><h3>Protokoll (Logs)</h3></legend>
                <p>Hier werden Fehler und Systemereignisse protokolliert.</p>
            </fieldset>
        </div>
''' + layout_end

new_content = re.sub(r'<div class="blocks">.*</div>\s*</div>\s*</div>\s*</div>\s*</body>', tabs_html + '\n        </div>\n    </div>\n</div>\n</body>', content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Done rewriting HTML')
