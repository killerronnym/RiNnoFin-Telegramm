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


