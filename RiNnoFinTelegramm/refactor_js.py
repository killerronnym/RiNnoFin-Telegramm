import re

file_path = 'c:/Users/Ronny M PC/Documents/Jellyfin  Telegramm/RiNnoFin Telegramm/RiNnoFinTelegramm/Assets/Config/config.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_populate = '''populateUsers: (page, users) => {
        const tbody = page.querySelector("#UserListTbody");
        tbody.innerHTML = "";
        
        const profileSelect = page.querySelector("#InviteProfile");
        if(profileSelect) {
            profileSelect.innerHTML = '<option value="">Lade Profile...</option>';
        }

        if (!users || users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="padding:10px;text-align:center;">Keine Benutzer gefunden.</td></tr>';
            return;
        }

        if(profileSelect) {
            profileSelect.innerHTML = '<option value="">Kein Profil (Leer)</option>';
        }

        users.forEach(user => {
            if(profileSelect) {
                const opt = document.createElement("option");
                opt.value = user.Id;
                opt.textContent = user.Name || user.Username;
                profileSelect.appendChild(opt);
            }

            const tr = document.createElement("tr");
            tr.style.borderBottom = "1px solid rgba(255,255,255,0.1)";
            
            const checkboxTd = document.createElement("td");
            checkboxTd.style.padding = "10px";
            checkboxTd.innerHTML = `<input type="checkbox" class="user-checkbox emby-checkbox" data-userid="${user.Id}" is="emby-checkbox"/>`;
            
            const nameTd = document.createElement("td");
            nameTd.style.padding = "10px";
            nameTd.textContent = user.Name || user.Username || 'Unbekannt';

            const statusTd = document.createElement("td");
            statusTd.style.padding = "10px";
            statusTd.textContent = user.Policy && user.Policy.IsDisabled ? 'Deaktiviert' : 'Aktiv';
            if(user.Policy && user.Policy.IsDisabled) statusTd.style.color = '#ef4444';

            const emailTd = document.createElement("td");
            emailTd.style.padding = "10px";
            emailTd.textContent = user.HasConfiguredPassword ? '?' : '-'; 

            const telegramTd = document.createElement("td");
            telegramTd.style.padding = "10px";
            telegramTd.textContent = '-';

            const lastAccessTd = document.createElement("td");
            lastAccessTd.style.padding = "10px";
            lastAccessTd.textContent = user.LastActivityDate ? new Date(user.LastActivityDate).toLocaleString('de-DE') : 'Niemals';

            tr.appendChild(checkboxTd);
            tr.appendChild(nameTd);
            tr.appendChild(statusTd);
            tr.appendChild(emailTd);
            tr.appendChild(telegramTd);
            tr.appendChild(lastAccessTd);

            tbody.appendChild(tr);
        });
    },'''

content = re.sub(r'populateUsers: \(page, users\) => \{.*?\},\s*adminActionUsers:', new_populate + '\n\n    adminActionUsers:', content, flags=re.DOTALL)

init_logic = '''
    const tabItems = view.querySelectorAll('.rinnofin-menu-item');
    tabItems.forEach(item => {
        item.addEventListener('click', (e) => {
            const tabId = e.currentTarget.getAttribute('data-tab');
            view.querySelectorAll('.rinnofin-menu-item').forEach(el => el.classList.remove('active'));
            view.querySelectorAll('.rinnofin-tab').forEach(el => el.classList.remove('active'));
            e.currentTarget.classList.add('active');
            const targetTab = view.querySelector('#' + tabId);
            if(targetTab) targetTab.classList.add('active');
        });
    });

    view.querySelector('#ActionLoadAll')?.addEventListener('click', (e) => {
        e.preventDefault();
        tgConfigPage.loadUsers(view);
    });

    view.querySelector('#ActionAddUser')?.addEventListener('click', (e) => {
        e.preventDefault();
        const panel = view.querySelector('#InviteUserPanel');
        if(panel) panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    });

    view.querySelector('#CancelInviteBtn')?.addEventListener('click', (e) => {
        e.preventDefault();
        const panel = view.querySelector('#InviteUserPanel');
        if(panel) panel.style.display = 'none';
    });

    view.querySelector('#CreateInviteBtn')?.addEventListener('click', (e) => {
        e.preventDefault();
        const email = view.querySelector('#InviteEmail').value;
        const profileId = view.querySelector('#InviteProfile').value;
        
        if (!email) {
            window.Dashboard.alert('Bitte eine E-Mail Adresse eingeben.');
            return;
        }

        window.Dashboard.showLoadingMsg();
        window.ApiClient.ajax({
            url: window.ApiClient.getUrl('/api/RiNnoFinConfig/AdminInviteUser'),
            type: 'POST',
            data: JSON.stringify({ Email: email, ProfileUserId: profileId }),
            contentType: 'application/json'
        }).then(() => {
            window.Dashboard.hideLoadingMsg();
            window.Dashboard.alert('Einladung erfolgreich gesendet!');
            view.querySelector('#InviteUserPanel').style.display = 'none';
            view.querySelector('#InviteEmail').value = '';
            tgConfigPage.loadUsers(view);
        }).catch(err => {
            window.Dashboard.hideLoadingMsg();
            const msg = err?.responseJSON?.message || 'Unbekannter Fehler';
            window.Dashboard.alert('Fehler beim Senden der Einladung: ' + msg);
        });
    });

    view.querySelector('#ActionAnnounce')?.addEventListener('click', (e) => {
        e.preventDefault();
        window.Dashboard.alert('Ankündigen-Funktion ist in Entwicklung.');
    });

    view.querySelector('#ActionSettings')?.addEventListener('click', (e) => {
        e.preventDefault();
        window.Dashboard.alert('Einstellungen ändern ist in Entwicklung.');
    });

    view.querySelector('#ActionRecommendations')?.addEventListener('click', (e) => {
        e.preventDefault();
        window.Dashboard.alert('Empfehlungen aktivieren ist in Entwicklung.');
    });

    view.querySelector('#ActionExpiry')?.addEventListener('click', (e) => {
        e.preventDefault();
        window.Dashboard.alert('Ablaufdatum-Funktion ist in Entwicklung.');
    });
'''

content = content.replace('export default function (view) {', 'export default function (view) {\n' + init_logic)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('JS updated successfully')
