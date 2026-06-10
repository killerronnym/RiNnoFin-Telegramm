const LinkPrefix = "l:";

const tgConfigPage = {
    pluginUniqueId: "9e1d84f2-901d-44a6-ba92-7fcf1a5598ba",

    modifiedGroups: new Map(),
    currentGroup: null,

    loadConfiguration: (page) => {
        ApiClient.getPluginConfiguration(tgConfigPage.pluginUniqueId).then(
            (config) => {
                tgConfigPage.config = config;
                tgConfigPage.populateConfiguration(page, config);
                tgConfigPage.populateGroups(page, config);
            }
        );
    },

    populateConfiguration: (page, config) => {
        if (config.BotToken) {
            tgTokenHelper.validateToken(page, config.BotToken);
        }

        const botUserName = config.BotUsername || tgTokenHelper.currentUserName;

        page.querySelector("#TgBotToken").value = config.BotToken || tgTokenHelper.currentToken;
        page.querySelector("#TgBotUsername").innerHTML = botUserName;
        page.querySelector("#LoginBaseUrl").value = config.LoginBaseUrl ?? '';
        page.querySelector("#TgAdministrators").value = config.AdminUserNames?.join("\r\n") || "";
        page.querySelector("#ForcedUrlScheme").value = config.ForcedUrlScheme || "none";
        page.querySelector("#RegistrationTheme").value = config.RegistrationTheme || "jellyfin";
        page.querySelector("#EnableEmail").checked = config.EnableEmail ?? false;
        page.querySelector("#SmtpServer").value = config.SmtpServer ?? '';
        page.querySelector("#SmtpPort").value = config.SmtpPort ?? '587';
        page.querySelector("#SmtpUsername").value = config.SmtpUsername ?? '';
        page.querySelector("#SmtpPassword").value = config.SmtpPassword ?? '';
        page.querySelector("#EmailSenderAddress").value = config.EmailSenderAddress ?? '';
        page.querySelector("#EmailSenderName").value = config.EmailSenderName ?? '';
        page.querySelector("#SmtpUseSsl").checked = config.SmtpUseSsl ?? true;
        page.querySelector("#EnableBotService").checked = config.EnableBotService ?? true;
        page.querySelector("#EmailTemplateInvite").value = config.EmailTemplateInvite ?? '';
        page.querySelector("#EmailTemplateWelcome").value = config.EmailTemplateWelcome ?? '';
        page.querySelector("#EmailTemplatePasswordReset").value = config.EmailTemplatePasswordReset ?? '';
        page.querySelector("#EmailTemplatePasswordChanged").value = config.EmailTemplatePasswordChanged ?? '';
        page.querySelector("#EmailTemplateAccountEnabled").value = config.EmailTemplateAccountEnabled ?? '';
        page.querySelector("#EmailTemplateAccountDisabled").value = config.EmailTemplateAccountDisabled ?? '';

        const subjectInvite = page.querySelector("#EmailSubjectInvite");
        if (subjectInvite) subjectInvite.value = config.EmailSubjectInvite ?? '';

        const subjectWelcome = page.querySelector("#EmailSubjectWelcome");
        if (subjectWelcome) subjectWelcome.value = config.EmailSubjectWelcome ?? '';

        const subjectPasswordReset = page.querySelector("#EmailSubjectPasswordReset");
        if (subjectPasswordReset) subjectPasswordReset.value = config.EmailSubjectPasswordReset ?? '';

        const subjectPasswordChanged = page.querySelector("#EmailSubjectPasswordChanged");
        if (subjectPasswordChanged) subjectPasswordChanged.value = config.EmailSubjectPasswordChanged ?? '';

        const subjectAccountEnabled = page.querySelector("#EmailSubjectAccountEnabled");
        if (subjectAccountEnabled) subjectAccountEnabled.value = config.EmailSubjectAccountEnabled ?? '';

        const subjectAccountDisabled = page.querySelector("#EmailSubjectAccountDisabled");
        if (subjectAccountDisabled) subjectAccountDisabled.value = config.EmailSubjectAccountDisabled ?? '';

        const subjectAnnounce = page.querySelector("#EmailSubjectAnnounce");
        if (subjectAnnounce) subjectAnnounce.value = config.EmailSubjectAnnounce ?? '';
        
        page.querySelector("#EmailTemplateAnnounce").value = config.EmailTemplateAnnounce ?? '';
    },

    populateGroups: (page, config) => {
        const groupList = page.querySelector("#TgBotGroupList");
        groupList.innerHTML = '';

        config.TelegramGroups?.forEach((group) => {
            const groupItem = document.createElement('div');
            groupItem.className = 'group-item';
            groupItem.setAttribute('data-group-name', group.GroupName);
            groupItem.textContent = group.GroupName;
            groupItem.addEventListener('click', () => tgConfigPage.selectGroup(page, group.GroupName));
            groupList.appendChild(groupItem);
        });

        if (tgConfigPage.currentGroup) {
            tgConfigPage.selectGroup(page, tgConfigPage.currentGroup);
        } else {
            tgConfigPage.updateGroupEditingState(page);
        }
    },

    loadRequests: (page) => {
        window.ApiClient.ajax({
            url: window.ApiClient.getUrl("/api/RiNnoFinConfig/GetRequests"),
            type: "GET",
            dataType: "json"
        }).then((requests) => {
            tgConfigPage.populateRequests(page, requests);
        });
    },

    populateRequests: (page, requests) => {
        const listContainer = page.querySelector("#RequestList");
        listContainer.innerHTML = "";

        if (!requests || requests.length === 0) {
            listContainer.innerHTML = '<div class="listItem" style="padding:10px;">Keine aktiven Anfragen.</div>';
            return;
        }

        requests.forEach(req => {
            const item = document.createElement("div");
            item.className = "listItem listItem-border";
            item.style.display = "flex";
            item.style.alignItems = "center";
            item.style.justifyContent = "space-between";
            item.style.padding = "0.5em";

            const info = document.createElement("div");
            info.style.display = "flex";
            info.style.flexDirection = "column";

            const title = document.createElement("div");
            title.style.fontWeight = "bold";
            title.textContent = `${req.Title || "Unbekannt"} (${req.Year || "?"})`;

            const details = document.createElement("div");
            details.style.opacity = "0.7";
            details.style.fontSize = "0.9em";
            details.textContent = `IMDb: ${req.ImdbId} | Von: ${req.UserDisplayName} | Datum: ${new Date(req.RequestedAtUtc).toLocaleDateString()}`;

            info.appendChild(title);
            info.appendChild(details);
            item.appendChild(info);

            const delBtn = document.createElement("button");
            delBtn.is = "emby-button";
            delBtn.type = "button";
            delBtn.className = "raised button-delete emby-button";
            delBtn.textContent = "Entfernen";
            delBtn.style.marginLeft = "1em";
            delBtn.onclick = () => tgConfigPage.deleteRequest(page, req.ImdbId);

            item.appendChild(delBtn);
            listContainer.appendChild(item);
        });
    },

    loadUsers: (page) => {
        const url = window.ApiClient.getUrl("/api/RiNnoFinConfig/GetUsers");
        
        window.ApiClient.ajax({
            url: url,
            type: "GET",
            dataType: "json"
        })
        .then((users) => {
            tgConfigPage.populateUsers(page, users);
        })
        .catch((err) => {
            console.error("RiNnoFin GetUsers Error:", err);
            const profileSelect = page.querySelector("#InviteProfile");
            if(profileSelect) {
                profileSelect.innerHTML = '<option value="">Fehler beim Laden der Profile</option>';
            }
            const tbody = page.querySelector("#UserListTbody");
            if(tbody) {
                const msg = err.message || JSON.stringify(err) || "Unbekannter Fehler";
                tbody.innerHTML = `<tr><td colspan="6" style="padding:10px;text-align:center;color:#ef4444;word-break:break-all;">Fehler beim Laden: ${msg}</td></tr>`;
            }
        });
    },

    loadLogs: (page) => {
        window.ApiClient.ajax({
            url: window.ApiClient.getUrl("/api/RiNnoFinConfig/GetLogs"),
            type: "GET",
            dataType: "json"
        }).then((logs) => {
            const logsArea = page.querySelector("#PluginLogsArea");
            if (logsArea) {
                logsArea.value = (logs && logs.length > 0) ? logs.join("\n") : "Keine Log-Einträge vorhanden.";
                logsArea.scrollTop = logsArea.scrollHeight;
            }
        }).catch(() => {
            const logsArea = page.querySelector("#PluginLogsArea");
            if (logsArea) logsArea.value = "Fehler beim Laden der Logs.";
        });
    },

    populateUsers: (page, users) => {
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
            checkboxTd.innerHTML = `<input type="checkbox" class="user-checkbox" data-userid="${user.Id}" data-botadmin="${user.IsBotAdmin ? 'true' : 'false'}" style="width: 18px; height: 18px; cursor: pointer; accent-color: #3b82f6;"/>`;
            
            const nameTd = document.createElement("td");
            nameTd.style.padding = "10px";
            // Check if admin
            if (user.IsAdmin) {
                nameTd.innerHTML = `<strong>${user.Username || 'Unbekannt'}</strong> <span style="color: gold;" title="Administrator">👑</span>`;
            } else {
                nameTd.textContent = user.Username || 'Unbekannt';
            }

            const statusTd = document.createElement("td");
            statusTd.style.padding = "10px";
            statusTd.textContent = user.IsDisabled ? 'Deaktiviert' : 'Aktiv';
            if(user.IsDisabled) statusTd.style.color = '#ef4444';

            const emailTd = document.createElement("td");
            emailTd.style.padding = "10px";
            emailTd.textContent = user.Email ? user.Email : '-'; 

            const telegramTd = document.createElement("td");
            telegramTd.style.padding = "10px";
            telegramTd.textContent = user.TelegramUsername ? '@' + user.TelegramUsername : '-';

            const expirationTd = document.createElement("td");
            expirationTd.style.padding = "10px";
            expirationTd.textContent = user.ExpirationDate ? new Date(user.ExpirationDate).toLocaleString('de-DE') : 'Niemals';

            const lastAccessTd = document.createElement("td");
            lastAccessTd.style.padding = "10px";
            lastAccessTd.textContent = user.LastActivityDate ? new Date(user.LastActivityDate).toLocaleString('de-DE') : 'Niemals';

            tr.appendChild(checkboxTd);
            tr.appendChild(nameTd);
            tr.appendChild(statusTd);
            tr.appendChild(emailTd);
            tr.appendChild(telegramTd);
            tr.appendChild(expirationTd);
            tr.appendChild(lastAccessTd);

            tbody.appendChild(tr);
        });
    },

    adminActionUsers: (page, actionName, confirmMsg) => {
        const userIds = tgConfigPage.getSelectedUserIds(page);
        if (userIds.length === 0) {
            window.Dashboard.alert("Bitte wähle mindestens einen Benutzer aus.");
            return;
        }

        if (confirmMsg && !confirm(confirmMsg)) return;

        let reason = "";
        let requestData = userIds;

        if (actionName === "AdminDisableUser" || actionName === "AdminDeleteUser") {
            reason = prompt("Bitte gib einen Grund für diese Aktion an (wird in der E-Mail an den Benutzer gesendet):", "");
            if (reason === null) return; // User cancelled
            requestData = {
                UserIds: userIds,
                Reason: reason
            };
        }

        window.Dashboard.showLoadingMsg();
        window.ApiClient.ajax({
            url: window.ApiClient.getUrl(`/api/RiNnoFinConfig/${actionName}`),
            type: "POST",
            data: JSON.stringify(requestData),
            contentType: "application/json"
        }).then((res) => {
            window.Dashboard.hideLoadingMsg();
            window.Dashboard.alert(res.message || "Aktion erfolgreich.");
            tgConfigPage.loadUsers(page);
        }).catch(err => {
            window.Dashboard.hideLoadingMsg();
            window.Dashboard.alert("Fehler bei der Aktion: " + (err.responseJSON?.message || err.message || ""));
        });
    },

    getSelectedUserIds: (page) => {
        const checkboxes = page.querySelectorAll(".user-checkbox:checked");
        return Array.from(checkboxes).map(cb => cb.dataset.userid);
    },

    createInvite: (page) => {
        const email = page.querySelector("#InviteEmail").value.trim();
        const profileId = page.querySelector("#InviteProfile").value;
        const username = page.querySelector("#InviteUsername").value.trim();

        if (!email) {
            window.Dashboard.alert("Bitte eine E-Mail-Adresse eingeben.");
            return;
        }

        window.Dashboard.showLoadingMsg();
        window.ApiClient.ajax({
            url: window.ApiClient.getUrl("/api/RiNnoFinConfig/AdminCreateInvite"),
            type: "POST",
            data: JSON.stringify({ Email: email, ProfileUserId: profileId, Username: username }),
            contentType: "application/json"
        }).then((res) => {
            window.Dashboard.hideLoadingMsg();
            window.Dashboard.alert("Einladung erfolgreich versendet!");
            page.querySelector("#InviteEmail").value = "";
            page.querySelector("#InviteUsername").value = "";
        }).catch(err => {
            window.Dashboard.hideLoadingMsg();
            window.Dashboard.alert("Fehler: " + (err.responseJSON?.message || err.message || ""));
        });
    },

    addRequest: (page) => {
        const input = page.querySelector("#NewRequestImdbId");
        const imdbId = input.value.trim();

        if (!imdbId) return;

        window.ApiClient.ajax({
            url: window.ApiClient.getUrl("/api/RiNnoFinConfig/AddRequest"),
            type: "POST",
            data: JSON.stringify({imdbId}),
            contentType: "application/json",
            dataType: "json"
        }).then(() => {
            input.value = "";
            tgConfigPage.loadRequests(page);
            window.Dashboard.alert('Medienanfrage erfolgreich hinzugefügt.');
        }).catch((err) => {
            if (err?.status === 404) {
                window.Dashboard.alert("Keine Metadaten für die angegebene IMDb-ID gefunden.");
            } else if (err?.status === 409) {
                window.Dashboard.alert("Diese Medienanfrage existiert bereits.");
            } else {
                window.Dashboard.alert("Fehler beim Hinzufügen der Medienanfrage.");
            }
        });
    },

    saveConfig: (page) => {
        return new Promise((resolve) => {
            window.ApiClient.getPluginConfiguration(
                tgConfigPage.pluginUniqueId
            ).then((config) => {
                const baseUrlValue = (page.querySelector("#LoginBaseUrl").value ?? "").trim();
                const finalBaseUrl = baseUrlValue.length ? baseUrlValue : undefined;

                config.BotToken = tgTokenHelper.currentToken;
                config.BotUsername = tgTokenHelper.currentUserName;
                config.LoginBaseUrl = finalBaseUrl;
                config.AdminUserNames = tgConfigPage.parseTextList(page.querySelector("#TgAdministrators"));
                config.ForcedUrlScheme = page.querySelector("#ForcedUrlScheme").value || "none";
                config.DefaultProfileUserId = page.querySelector("#DefaultProfileUserId").value || undefined;
                config.RegistrationTheme = page.querySelector("#RegistrationTheme").value || "jellyfin";
                config.EnableEmail = page.querySelector("#EnableEmail").checked;
                config.SmtpServer = (page.querySelector("#SmtpServer").value ?? "").trim();
                config.SmtpPort = parseInt(page.querySelector("#SmtpPort").value) || 587;
                config.SmtpUsername = (page.querySelector("#SmtpUsername").value ?? "").trim();
                config.SmtpPassword = (page.querySelector("#SmtpPassword").value ?? "").trim();
                config.EmailSenderAddress = (page.querySelector("#EmailSenderAddress").value ?? "").trim();
                config.EmailSenderName = (page.querySelector("#EmailSenderName").value ?? "").trim();
                config.SmtpUseSsl = page.querySelector("#SmtpUseSsl").checked;
                config.EnableBotService = page.querySelector("#EnableBotService").checked;
                config.EmailTemplateInvite = (page.querySelector("#EmailTemplateInvite").value ?? "").trim() || undefined;
                config.EmailTemplateWelcome = (page.querySelector("#EmailTemplateWelcome").value ?? "").trim() || undefined;
                config.EmailTemplatePasswordReset = (page.querySelector("#EmailTemplatePasswordReset").value ?? "").trim() || undefined;
                config.EmailTemplatePasswordChanged = (page.querySelector("#EmailTemplatePasswordChanged").value ?? "").trim() || undefined;
                config.EmailTemplateAccountEnabled = (page.querySelector("#EmailTemplateAccountEnabled").value ?? "").trim() || undefined;
                config.EmailTemplateAccountDisabled = (page.querySelector("#EmailTemplateAccountDisabled").value ?? "").trim() || undefined;

                config.EmailSubjectInvite = (page.querySelector("#EmailSubjectInvite")?.value ?? "").trim() || undefined;
                config.EmailSubjectWelcome = (page.querySelector("#EmailSubjectWelcome")?.value ?? "").trim() || undefined;
                config.EmailSubjectPasswordReset = (page.querySelector("#EmailSubjectPasswordReset")?.value ?? "").trim() || undefined;
                config.EmailSubjectPasswordChanged = (page.querySelector("#EmailSubjectPasswordChanged")?.value ?? "").trim() || undefined;
                config.EmailSubjectAccountEnabled = (page.querySelector("#EmailSubjectAccountEnabled")?.value ?? "").trim() || undefined;
                config.EmailSubjectAccountDisabled = (page.querySelector("#EmailSubjectAccountDisabled")?.value ?? "").trim() || undefined;
                config.EmailSubjectAnnounce = (page.querySelector("#EmailSubjectAnnounce")?.value ?? "").trim() || undefined;

                config.EmailTemplateAnnounce = (page.querySelector("#EmailTemplateAnnounce").value ?? "").trim() || undefined;

                window.ApiClient.updatePluginConfiguration(
                    tgConfigPage.pluginUniqueId,
                    config
                ).then(function (result) {
                    window.Dashboard.processPluginConfigurationUpdateResult(result);
                    tgConfigPage.loadConfiguration(page);
                    resolve();
                });
            });
        });
    },

    addGroup: (page) => {
        const newGroupName = page.querySelector("#TgGroupName").value.trim();
        if (!newGroupName) {
            window.Dashboard.alert('Bitte gib einen Gruppennamen ein.');
            return;
        }

        if (newGroupName.length < 3 || newGroupName.length > 32) {
            window.Dashboard.alert('Der Gruppenname muss zwischen 3 und 32 Zeichen lang sein.');
            return;
        }

        const validCharsRegex = /^[a-zA-Z0-9_\-]+$/;
        if (!validCharsRegex.test(newGroupName)) {
            window.Dashboard.alert('Der Gruppenname darf nur Buchstaben, Zahlen, Unterstriche und Bindestriche enthalten.');
            return;
        }

        ApiClient.getPluginConfiguration(tgConfigPage.pluginUniqueId).then((config) => {
            if (!config.TelegramGroups) {
                config.TelegramGroups = [];
            }

            if (config.TelegramGroups.some(g => g.GroupName === newGroupName)) {
                window.Dashboard.alert('Eine Gruppe mit diesem Namen existiert bereits.');
                return;
            }

            config.TelegramGroups.push({
                GroupName: newGroupName,
                EnableAllFolders: false,
                EnabledFolders: [],
                LinkedTelegramGroupId: null,
                UserNames: [],
            });

            ApiClient.updatePluginConfiguration(
                tgConfigPage.pluginUniqueId,
                config
            ).then(function (result) {
                window.Dashboard.processPluginConfigurationUpdateResult(result);
                tgConfigPage.currentGroup = newGroupName;
                tgConfigPage.populateGroups(page, config);
                page.querySelector("#TgGroupName").value = '';
            });
        });
    },

    updateGroupEditingState: (page) => {
        const hasSelectedGroup = !!tgConfigPage.currentGroup;
        const enableAllChecked = page.querySelector("#EnableAllFolders")?.checked || false;

        const userNamesList = page.querySelector("#UserNames");
        const enableAllFolders = page.querySelector("#EnableAllFolders");
        const folderList = page.querySelector("#EnabledFolders");
        const delGroupBtn = page.querySelector("#DeleteGroup");
        const chatIdInput = page.querySelector("#LinkedTelegramGroupIdInput");
        const contentTopic = page.querySelector("#ContentTopicId");
        const quizTopic = page.querySelector("#QuizTopicId");
        const syncUser = page.querySelector("#SyncUserNames");
        const notifyNew = page.querySelector("#NotifyNewContent");
        const allowReq = page.querySelector("#AllowRequests");
        const enableQuiz = page.querySelector("#EnableQuiz");
        const triggerQuizBtn = page.querySelector("#TriggerGroupQuiz");

        [userNamesList, enableAllFolders, delGroupBtn, chatIdInput, contentTopic, quizTopic, syncUser, notifyNew, allowReq, enableQuiz, triggerQuizBtn].forEach(element => {
            if (element) {
                element.disabled = !hasSelectedGroup;
                element.title = hasSelectedGroup ? "" : "Bitte wähle zuerst eine Gruppe aus.";
            }
        });

        if (folderList) {
            const checkboxes = folderList.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                checkbox.disabled = !hasSelectedGroup || enableAllChecked;
                checkbox.parentElement.title = hasSelectedGroup ? "" : "Bitte wähle zuerst eine Gruppe aus.";
            });
        }

        if (userNamesList) {
            userNamesList.style.opacity = hasSelectedGroup ? "1" : "0.6";
        }
        if (folderList) {
            folderList.style.opacity = hasSelectedGroup ? "1" : "0.6";
        }
    },

    updateGroupData: (page) => {
        if (!tgConfigPage.currentGroup) return;

        const linkedText = (page.querySelector("#LinkedTelegramGroupIdInput")?.value || "").trim();
        const linkedId = linkedText ? Number(linkedText) : 0;
        const hasLinkedChat = !!linkedId;

        const contentTopicVal = (page.querySelector("#ContentTopicId")?.value || "").trim();
        const quizTopicVal = (page.querySelector("#QuizTopicId")?.value || "").trim();

        const groupData = {
            GroupName: tgConfigPage.currentGroup,
            EnableAllFolders: page.querySelector("#EnableAllFolders").checked,
            EnabledFolders: tgConfigPage.serializeEnabledFolders(page),
            UserNames: tgConfigPage.parseTextList(page.querySelector("#UserNames")),
            TelegramGroupChat: hasLinkedChat ? {
                TelegramChatId: linkedId,
                SyncUserNames: page.querySelector("#SyncUserNames").checked,
                NotifyNewContent: page.querySelector("#NotifyNewContent").checked,
                AllowRequests: (page.querySelector("#AllowRequests")?.checked) ?? true,
                ContentTopicId: contentTopicVal ? Number(contentTopicVal) : null,
                QuizTopicId: quizTopicVal ? Number(quizTopicVal) : null,
                EnableQuiz: page.querySelector("#EnableQuiz").checked
            } : undefined
        };

        tgConfigPage.modifiedGroups.set(tgConfigPage.currentGroup, groupData);
    },

    selectGroup: (page, groupName) => {
        tgConfigPage.currentGroup = groupName;

        const encodedText = btoa(`${LinkPrefix}${groupName}`);
        page.querySelector("#BotLinkCommandUrl").href = `https://t.me/${tgTokenHelper.currentUserName}?startgroup=${encodedText}`;

        page.querySelectorAll('.group-item').forEach(item => {
            item.classList.toggle('selected', item.getAttribute('data-group-name') === groupName);
        });

        let groupData = tgConfigPage.modifiedGroups.get(groupName);

        if (!groupData) {
            ApiClient.getPluginConfiguration(tgConfigPage.pluginUniqueId).then((config) => {
                groupData = config.TelegramGroups?.find(group => group.GroupName === groupName);
                if (groupData) {
                    tgConfigPage.populateGroupData(page, groupData);
                }
            });
        } else {
            tgConfigPage.populateGroupData(page, groupData);
        }

        tgConfigPage.updateGroupEditingState(page);
    },

    populateGroupData: (page, groupData) => {
        if (groupData) {
            tgConfigPage.populateEnabledFolders(groupData.EnabledFolders || [], page.querySelector("#EnabledFolders"));

            const folderCheckboxes = page.querySelectorAll('.folder-checkbox');
            folderCheckboxes.forEach(cb => {
                cb.disabled = groupData.EnableAllFolders;
                if (groupData.EnableAllFolders) {
                    cb.checked = true;
                }
            });

            const enableAllCheckbox = page.querySelector("#EnableAllFolders");
            enableAllCheckbox.checked = groupData.EnableAllFolders;

            page.querySelector("#LinkedTelegramGroupIdInput").value = groupData.TelegramGroupChat?.TelegramChatId ?? "";
            page.querySelector("#ContentTopicId").value = groupData.TelegramGroupChat?.ContentTopicId ?? "";
            page.querySelector("#QuizTopicId").value = groupData.TelegramGroupChat?.QuizTopicId ?? "";
            page.querySelector("#UserNames").value = groupData.UserNames.join("\r\n");
            page.querySelector("#SyncUserNames").checked = groupData.TelegramGroupChat?.SyncUserNames ?? true;
            page.querySelector("#NotifyNewContent").checked = groupData.TelegramGroupChat?.NotifyNewContent ?? true;
            page.querySelector("#EnableQuiz").checked = groupData.TelegramGroupChat?.EnableQuiz ?? true;
            const allowReq = page.querySelector("#AllowRequests");
            if (allowReq) allowReq.checked = groupData.TelegramGroupChat?.AllowRequests ?? true;

            tgConfigPage.updateTelegramSettingsUI(page, groupData);
        }
    },

    updateTelegramSettingsUI: (page, groupData) => {
        const linkedId = groupData.TelegramGroupChat?.TelegramChatId ?? 0;
        const hasLinked = !!linkedId;
        const isModified = tgConfigPage.modifiedGroups.has(groupData.GroupName);

        const sync = page.querySelector('#SyncUserNames');
        const notify = page.querySelector('#NotifyNewContent');
        const allowReq = page.querySelector('#AllowRequests');
        const enableQuiz = page.querySelector('#EnableQuiz');
        const triggerQuizBtn = page.querySelector('#TriggerGroupQuiz');
        const contentTopic = page.querySelector('#ContentTopicId');
        const quizTopic = page.querySelector('#QuizTopicId');
        const linkBtn = page.querySelector('#BotLinkCommandUrl');

        if (linkBtn) {
            if (isModified) {
                linkBtn.classList.add('hide');
                linkBtn.title = 'Bitte speichere die Gruppenänderungen vor dem Verknüpfen.';
            } else if (hasLinked) {
                linkBtn.classList.add('hide');
                linkBtn.title = 'Gruppe ist bereits verknüpft.';
            } else {
                linkBtn.classList.remove('hide');
                linkBtn.title = '';
            }
        }

        // Toggles und Quiz-Button nur aktiv wenn Chat verknüpft
        [sync, notify, allowReq, enableQuiz, triggerQuizBtn].forEach(el => {
            if (el) {
                el.disabled = !hasLinked;
                if (el.parentElement) el.parentElement.title = hasLinked ? '' : 'Trage zuerst eine Telegram Chat ID ein.';
            }
        });

        // Topic-Felder immer editierbar wenn Gruppe ausgewählt (damit man Chat ID + Topics gleichzeitig eintragen kann)
        [contentTopic, quizTopic].forEach(el => {
            if (el) {
                el.disabled = false;
                if (el.parentElement) el.parentElement.title = '';
            }
        });

        if (triggerQuizBtn && hasLinked) {
            triggerQuizBtn.disabled = !(enableQuiz && enableQuiz.checked);
        }

        const chatType = groupData.TelegramGroupChat?.ChatType;
        const isUnsupportedSync = chatType === 'Channel' || chatType === 'Private' || chatType === 2 || chatType === 3;
        if (sync) {
            sync.disabled = sync.disabled || isUnsupportedSync;
            if (isUnsupportedSync) {
                sync.checked = false;
                sync.parentElement.title = 'Die Synchronisierung von Benutzernamen ist für Kanäle oder private Chats nicht verfügbar.';
            }
        }
    },

    deleteGroup: (page) => {
        if (!tgConfigPage.currentGroup) {
            window.Dashboard.alert('Bitte wähle eine Gruppe zum Löschen aus.');
            return Promise.resolve();
        }

        if (!confirm(`Möchtest du die Gruppe "${tgConfigPage.currentGroup}" wirklich löschen?`)) {
            return Promise.resolve();
        }

        return new Promise((resolve) => {
            ApiClient.getPluginConfiguration(tgConfigPage.pluginUniqueId).then((config) => {
                config.TelegramGroups = config.TelegramGroups?.filter(
                    group => group.GroupName !== tgConfigPage.currentGroup
                ) || [];

                ApiClient.updatePluginConfiguration(
                    tgConfigPage.pluginUniqueId,
                    config
                ).then(function (result) {
                    window.Dashboard.processPluginConfigurationUpdateResult(result);
                    tgConfigPage.currentGroup = null;
                    tgConfigPage.populateGroups(page, config);
                    page.querySelector("#EnableAllFolders").checked = false;
                    page.querySelector("#UserNames").value = '';
                    page.querySelectorAll('.folder-checkbox').forEach(cb => cb.checked = false);
                    page.querySelector("#LinkedTelegramGroupIdInput").value = "";
                    page.querySelector("#ContentTopicId").value = "";
                    page.querySelector("#QuizTopicId").value = "";
                    page.querySelector("#EnableQuiz").checked = true;
                    page.querySelector("#BotLinkCommandUrl").href = `https://t.me/${tgTokenHelper.currentUserName}?startgroup`;
                    resolve();
                });
            });
        });
    },

    saveGroupConfig: (page) => {
        tgConfigPage.updateGroupData(page);

        return new Promise((resolve) => {
            ApiClient.getPluginConfiguration(tgConfigPage.pluginUniqueId).then((config) => {
                if (!config.TelegramGroups) {
                    config.TelegramGroups = [];
                }

                for (let [groupName, groupData] of tgConfigPage.modifiedGroups) {
                    const groupIndex = config.TelegramGroups.findIndex(g => g.GroupName === groupName);
                    if (groupIndex !== -1) {
                        const current = config.TelegramGroups[groupIndex];
                        const updated = {...current, ...groupData};

                        if (groupData.TelegramGroupChat !== undefined) {
                            updated.TelegramGroupChat = {
                                ...(current.TelegramGroupChat || {}),
                                ...groupData.TelegramGroupChat
                            };
                        }

                        config.TelegramGroups[groupIndex] = updated;
                    }
                }

                ApiClient.updatePluginConfiguration(
                    tgConfigPage.pluginUniqueId,
                    config
                ).then(function (result) {
                    window.Dashboard.processPluginConfigurationUpdateResult(result);
                    tgConfigPage.modifiedGroups.clear();
                    resolve();
                });
            });
        });
    },

    populateFolders: (container) => {
        const folderContainer = container.querySelector("#EnabledFolders");

        return window.ApiClient.getJSON(
            window.ApiClient.getUrl("Library/MediaFolders", {
                IsHidden: false
            })
        ).then((folders) => {
            tgConfigPage.populateFolderElements(folderContainer, folders.Items);
        });
    },

    populateEnabledFolders: (folderList, container) => {
        container.querySelectorAll(".folder-checkbox").forEach((e) => {
            e.checked = folderList.includes(e.getAttribute("data-id"));
        });
    },

    serializeEnabledFolders: (container) => {
        return [...container.querySelectorAll(".folder-checkbox")]
            .filter((e) => e.checked)
            .map((e) => {
                return e.getAttribute("data-id");
            });
    },

    populateFolderElements: (container, folderItems) => {
        container
            .querySelectorAll(".emby-checkbox-label")
            .forEach((e) => e.remove());

        const checkboxes = folderItems.map((folder) => {
            const out = document.createElement("label");
            out.innerHTML = `
                <input
                    is="emby-checkbox"
                    class="folder-checkbox chkFolder"
                    data-id="${folder.Id}"
                    type="checkbox"
                />
                <span>${folder.Name}</span>
            `;
            return out;
        });

        if (checkboxes.length === 0 && container.children.length === 0) {
            const missing = document.createElement("label");
            missing.innerHTML = "<span>Keine Medienbibliotheken konfiguriert.</span>";
            checkboxes.push(missing);
        }

        checkboxes.forEach((e) => {
            container.appendChild(e);
        });
    },

    parseTextList: (element) => {
        return element.value
            .split("\n")
            .map((e) => e.trim())
            .filter((e) => e);
    },

    addTextAreaStyle: (view) => {
        const style = document.createElement("link");
        style.rel = "stylesheet";
        style.href = window.ApiClient.getUrl("web/configurationpage") + "?name=RiNnoFinTelegramm.css";
        view.appendChild(style);
    },

    toggleTokenFunction: (e) => {
        const tokenField = document.getElementById("TgBotToken");
        if (tokenField.type === "password") {
            tokenField.type = "text";
        } else {
            tokenField.type = "password";
        }
    }
};

const tgTokenHelper = {
    currentToken: "12341234:xxxxxxxx",
    currentUserName: "INVALID_BOT_TOKEN",

    validateToken(page, token) {
        tgTokenHelper.currentToken = token.trim();
        return window.ApiClient.ajax(
            {
                url: window.ApiClient.getUrl("/api/RiNnoFinConfig/TestBotToken"),
                type: "POST",
                data: JSON.stringify({Token: token}),
                contentType: "application/json",
                dataType: "json"
            })
            .then(data => {
                tgTokenHelper.handleValidationResponse(page, data);
            })
            .catch(error => {
                tgTokenHelper.handleValidationResponse(page, {ErrorMessage: error.message || "Fehler beim Verbinden"});
            });
    },

    handleValidationResponse(page, data) {
        const tokenElement = page.querySelector("#TgBotToken");
        const nameElement = page.querySelector("#TgBotUsername");
        if (data?.Ok) {
            nameElement.style.color = "limegreen";
            tokenElement.style.borderColor = "limegreen";
            tgTokenHelper.currentUserName = data.BotUsername;
            nameElement.innerHTML = `✅ Verbunden als @${data.BotUsername}`;

            if (data.AdminMessageSent) {
                window.Dashboard.alert(`Erfolgreich verbunden! Testnachricht wurde an die Administratoren gesendet.`);
            } else {
                window.Dashboard.alert(`Erfolgreich verbunden als @${data.BotUsername}. (Keine Testnachricht gesendet, da keine Chat-IDs für die Admins gefunden wurden)`);
            }

            if (tgConfigPage.currentGroup) {
                const encodedText = btoa(`${LinkPrefix}${tgConfigPage.currentGroup}`);
                page.querySelector("#BotLinkCommandUrl").href = `https://t.me/${data.BotUsername}?startgroup=${encodedText}`;
            } else {
                page.querySelector("#BotLinkCommandUrl").href = `https://t.me/${data.BotUsername}?startgroup`;
            }
        } else {
            nameElement.style.color = "indianred";
            tokenElement.style.borderColor = "indianred";
            tgTokenHelper.currentUserName = "";
            nameElement.innerHTML = `❌ Nicht verbunden: ${data.ErrorMessage || "Ungültiger Token"}`;
            window.Dashboard.alert(`Fehler bei der Überprüfung: ${data.ErrorMessage || "Ungültiger Token"}`);
        }
    }
}

export default function (view) {

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
            url: window.ApiClient.getUrl('/api/RiNnoFinConfig/AdminCreateInvite'),
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
        const userIds = tgConfigPage.getSelectedUserIds(view);
        if (userIds.length === 0) {
            window.Dashboard.alert('Bitte wähle mindestens einen Benutzer für die Ankündigung aus.');
            return;
        }
        
        const panel = view.querySelector('#AnnouncePanel');
        if(panel) panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    });

    view.querySelector('#CancelAnnounceBtn')?.addEventListener('click', (e) => {
        e.preventDefault();
        const panel = view.querySelector('#AnnouncePanel');
        if(panel) panel.style.display = 'none';
    });

    view.querySelector('#SendAnnounceBtn')?.addEventListener('click', (e) => {
        e.preventDefault();
        const userIds = tgConfigPage.getSelectedUserIds(view);
        if (userIds.length === 0) {
            window.Dashboard.alert('Bitte wähle mindestens einen Benutzer für die Ankündigung aus.');
            return;
        }

        const subject = view.querySelector('#AnnounceSubject').value.trim();
        const message = view.querySelector('#AnnounceMessage').value.trim();
        const viaEmail = view.querySelector('#AnnounceViaEmail').checked;
        const viaTelegram = view.querySelector('#AnnounceViaTelegram').checked;

        if (!viaEmail && !viaTelegram) {
            window.Dashboard.alert('Bitte wähle mindestens einen Kanal (E-Mail oder Telegram) aus.');
            return;
        }

        if (!message) {
            window.Dashboard.alert('Bitte gib eine Nachricht ein.');
            return;
        }
        
        if (viaEmail && !subject) {
            window.Dashboard.alert('Bitte gib einen Betreff für die E-Mail ein.');
            return;
        }

        window.Dashboard.showLoadingMsg();
        window.ApiClient.ajax({
            url: window.ApiClient.getUrl('/api/RiNnoFinConfig/SendAnnouncement'),
            type: 'POST',
            data: JSON.stringify({ 
                UserIds: userIds, 
                Subject: subject, 
                Message: message,
                ViaEmail: viaEmail,
                ViaTelegram: viaTelegram
            }),
            contentType: 'application/json'
        }).then((res) => {
            window.Dashboard.hideLoadingMsg();
            window.Dashboard.alert(res.message || 'Ankündigung erfolgreich gesendet!');
            view.querySelector('#AnnouncePanel').style.display = 'none';
            view.querySelector('#AnnounceSubject').value = '';
            view.querySelector('#AnnounceMessage').value = '';
        }).catch(err => {
            window.Dashboard.hideLoadingMsg();
            window.Dashboard.alert('Fehler: ' + (err.responseJSON?.message || err.message || ''));
        });
    });

    view.querySelector('#ActionSettings')?.addEventListener('click', (e) => {
        e.preventDefault();
        const userIds = tgConfigPage.getSelectedUserIds(view);
        if (userIds.length !== 1) {
            window.Dashboard.alert('Bitte wähle genau EINEN Benutzer zum Bearbeiten aus.');
            return;
        }

        const userId = userIds[0];
        
        // Find row to extract current email and telegram
        const row = view.querySelector(`.user-checkbox[data-userid="${userId}"]`).closest('tr');
        const email = row.children[3].textContent.trim() === '-' ? '' : row.children[3].textContent.trim();
        let telegram = row.children[4].textContent.trim();
        telegram = telegram.startsWith('@') ? telegram.substring(1) : (telegram === 'Nein' ? '' : telegram);

        view.querySelector('#EditUserId').value = userId;
        view.querySelector('#EditUserEmail').value = email;
        view.querySelector('#EditUserTelegram').value = telegram;
        
        view.querySelector('#EditUserPanel').style.display = 'block';
    });

    view.querySelector('#CancelEditUserBtn')?.addEventListener('click', (e) => {
        e.preventDefault();
        view.querySelector('#EditUserPanel').style.display = 'none';
    });

    view.querySelector('#SaveEditUserBtn')?.addEventListener('click', (e) => {
        e.preventDefault();
        const userId = view.querySelector('#EditUserId').value;
        const email = view.querySelector('#EditUserEmail').value.trim();
        let telegram = view.querySelector('#EditUserTelegram').value.trim();
        if (telegram.startsWith('@')) telegram = telegram.substring(1);

        window.Dashboard.showLoadingMsg();
        window.ApiClient.ajax({
            url: window.ApiClient.getUrl('/api/RiNnoFinConfig/AdminUpdateUser'),
            type: 'POST',
            data: JSON.stringify({ UserId: userId, Email: email, TelegramUsername: telegram }),
            contentType: 'application/json'
        }).then((res) => {
            window.Dashboard.hideLoadingMsg();
            window.Dashboard.alert(res.message || 'Benutzer erfolgreich aktualisiert.');
            view.querySelector('#EditUserPanel').style.display = 'none';
            tgConfigPage.loadUsers(view);
        }).catch(err => {
            window.Dashboard.hideLoadingMsg();
            window.Dashboard.alert('Fehler beim Speichern: ' + (err.responseJSON?.message || err.message || ''));
        });
    });

    view.querySelector('#ActionRecommendations')?.addEventListener('click', (e) => {
        e.preventDefault();
        window.Dashboard.alert('Empfehlungen aktivieren ist in Entwicklung.');
    });

    view.querySelector('#ActionExpiry')?.addEventListener('click', (e) => {
        e.preventDefault();
        window.Dashboard.alert('Ablaufdatum-Funktion ist in Entwicklung.');
    });

    window.Dashboard.showLoadingMsg();

    tgConfigPage.addTextAreaStyle(view);
    tgConfigPage.loadConfiguration(view);
    tgConfigPage.loadRequests(view);
    tgConfigPage.loadUsers(view);
    tgConfigPage.loadLogs(view);

    tgConfigPage.populateFolders(view).then(() => {
        const inputs = [
            "#EnableAllFolders",
            "#UserNames",
            ".folder-checkbox",
            "#SyncUserNames",
            "#NotifyNewContent",
            "#AllowRequests",
            "#LinkedTelegramGroupIdInput",
            "#ContentTopicId",
            "#QuizTopicId",
            "#EnableQuiz"
        ];

        inputs.forEach(selector => {
            const elements = view.querySelectorAll(selector);
            elements.forEach(element => {
                element.addEventListener('change', () => tgConfigPage.updateGroupData(view));
            });
        });
    });

    view.querySelector("#LinkedTelegramGroupIdInput")?.addEventListener("input", () => {
        tgConfigPage.updateGroupData(view);
        const linkedVal = Number(view.querySelector("#LinkedTelegramGroupIdInput").value) || 0;
        const groupData = {
            GroupName: tgConfigPage.currentGroup,
            TelegramGroupChat: {
                TelegramChatId: linkedVal
            }
        };
        tgConfigPage.updateTelegramSettingsUI(view, groupData);
    });

    view.querySelector("#EnableQuiz")?.addEventListener("change", () => {
        tgConfigPage.updateGroupData(view);
        const linkedVal = Number(view.querySelector("#LinkedTelegramGroupIdInput").value) || 0;
        const groupData = {
            GroupName: tgConfigPage.currentGroup,
            TelegramGroupChat: {
                TelegramChatId: linkedVal,
                EnableQuiz: view.querySelector("#EnableQuiz").checked
            }
        };
        tgConfigPage.updateTelegramSettingsUI(view, groupData);
    });

    view.querySelector("#TriggerGroupQuiz")?.addEventListener("click", (e) => {
        e.preventDefault();
        const groupName = tgConfigPage.currentGroup;
        if (!groupName) {
            window.Dashboard.alert("Bitte wähle zuerst eine Gruppe aus.");
            return;
        }

        window.Dashboard.showLoadingMsg();
        window.ApiClient.ajax({
            url: window.ApiClient.getUrl(`/api/RiNnoFinConfig/TriggerQuiz/${encodeURIComponent(groupName)}`),
            type: "POST"
        }).then(() => {
            window.Dashboard.hideLoadingMsg();
            window.Dashboard.alert("✅ Quizfrage wurde erfolgreich an Telegram gesendet!");
        }).catch(err => {
            window.Dashboard.hideLoadingMsg();
            // Try to extract the actual error message from the response body
            const msg = err?.responseJSON?.message || err?.responseText || err?.message || "Unbekannter Fehler";
            window.Dashboard.alert("❌ Fehler beim Senden der Quizfrage:\n" + msg);
        });
    });

    view.querySelector("#show-hide-token")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.toggleTokenFunction(e);
    });

    view.querySelector("#LoginBaseUrl")?.addEventListener("change", (e) => {
        const ref = view.querySelector('#LoginBaseUrl');
        const inputValue = ref?.value;
        if (inputValue?.endsWith("/")) {
            ref.value = inputValue.substring(0, inputValue.length - 1);
        }
    });

    view.querySelector("#SaveConfig")?.addEventListener("click", async (e) => {
        e.preventDefault();
        await tgConfigPage.saveConfig(view);
    });

    view.querySelector("#SaveConfigEmail")?.addEventListener("click", async (e) => {
        e.preventDefault();
        await tgConfigPage.saveConfig(view);
    });

    view.querySelector("#SaveConfigUsers")?.addEventListener("click", async (e) => {
        e.preventDefault();
        await tgConfigPage.saveConfig(view);
    });

    view.querySelector("#EnableAllFolders")?.addEventListener("change", (e) => {
        const checkboxes = view.querySelectorAll('.folder-checkbox');
        checkboxes.forEach(cb => {
            cb.disabled = e.target.checked;
            if (e.target.checked) {
                cb.checked = true;
            }
        });
        tgConfigPage.updateGroupData(view);
        tgConfigPage.updateGroupEditingState(view);
    });

    view.querySelector("#AddGroup")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.addGroup(view);
    });

    view.querySelector("#SaveGroupConfig")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.saveGroupConfig(view);
    });

    view.querySelector("#DeleteGroup")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.deleteGroup(view);
    });

    view.querySelector("#TriggerGroupAnnounce")?.addEventListener("click", (e) => {
        e.preventDefault();
        if (!tgConfigPage.currentGroup) {
            window.Dashboard.alert('Bitte wähle zuerst eine Gruppe aus.');
            return;
        }
        view.querySelector("#GroupAnnounceMessage").value = "";
        view.querySelector("#GroupAnnouncePanel").style.display = "block";
    });

    view.querySelector("#CancelGroupAnnounceBtn")?.addEventListener("click", (e) => {
        e.preventDefault();
        view.querySelector("#GroupAnnouncePanel").style.display = "none";
    });

    view.querySelector("#SendGroupAnnounceBtn")?.addEventListener("click", async (e) => {
        e.preventDefault();
        if (!tgConfigPage.currentGroup) return;

        const message = view.querySelector("#GroupAnnounceMessage").value.trim();
        if (!message) {
            window.Dashboard.alert('Bitte gib eine Nachricht ein.');
            return;
        }

        view.querySelector("#SendGroupAnnounceBtn").disabled = true;

        try {
            const url = window.ApiClient.getUrl('/api/RiNnoFinConfig/SendGroupAnnouncement?groupName=' + encodeURIComponent(tgConfigPage.currentGroup));
            window.ApiClient.ajax({
                url: url,
                type: 'POST',
                data: JSON.stringify({ Message: message }),
                contentType: 'application/json'
            }).then(() => {
                window.Dashboard.alert('Gruppen-Ankündigung erfolgreich gesendet.');
                view.querySelector("#GroupAnnouncePanel").style.display = "none";
            }).catch(err => {
                const msg = err?.responseJSON?.message || err?.responseText || err?.message || "Unbekannter Fehler";
                window.Dashboard.alert('Fehler: ' + msg);
            });
        } catch (err) {
            window.Dashboard.alert('Netzwerkfehler: ' + err.message);
        } finally {
            view.querySelector("#SendGroupAnnounceBtn").disabled = false;
        }
    });

    view.querySelector("#RefreshRequests")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.loadRequests(view);
        window.Dashboard.alert('Wunschliste aktualisiert.');
    });

    view.querySelector("#AddManualRequest")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.addRequest(view);
    });

    view.querySelector("#CreateInviteBtn")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.createInvite(view);
    });

    view.querySelector("#SelectAllUsers")?.addEventListener("change", (e) => {
        const checked = e.target.checked;
        const checkboxes = view.querySelectorAll(".user-checkbox");
        checkboxes.forEach(cb => cb.checked = checked);
    });

    view.querySelector("#AdminEnableUser")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.adminActionUsers(view, "AdminEnableUser", "Möchtest du die ausgewählten Benutzer wirklich aktivieren?");
    });

    view.querySelector("#AdminDisableUser")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.adminActionUsers(view, "AdminDisableUser", "Möchtest du die ausgewählten Benutzer wirklich DEAKTIVIEREN?");
    });

    view.querySelector("#AdminDeleteUser")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.adminActionUsers(view, "AdminDeleteUser", "ACHTUNG: Möchtest du die ausgewählten Benutzer WIRKLICH LÖSCHEN? Dies kann nicht rückgängig gemacht werden!");
    });

    view.querySelector("#AdminSendPasswordReset")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.adminActionUsers(view, "AdminSendPasswordReset", "Möchtest du den ausgewählten Benutzern eine E-Mail zum Zurücksetzen des Passworts senden?");
    });

    view.querySelector("#RefreshUsersBtn")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.loadUsers(view);
    });



    view.querySelector("#ActionSettings")?.addEventListener("click", (e) => {
        e.preventDefault();
        const userIds = tgConfigPage.getSelectedUserIds(view);
        if (userIds.length !== 1) {
            window.Dashboard.alert('Bitte wähle genau EINEN Benutzer aus, um ihn zu bearbeiten.');
            return;
        }
        
        const userId = userIds[0];
        const cb = view.querySelector(`.user-checkbox[data-userid="${userId}"]`);
        if (!cb) return;

        const tr = cb.closest('tr');
        const email = tr.children[3].textContent;
        const telegram = tr.children[4].textContent.replace('@', '');
        const expirationStr = tr.children[5].textContent;

        view.querySelector("#EditUserId").value = userId;
        view.querySelector("#EditUserEmail").value = email === 'Nein' ? '' : email;
        view.querySelector("#EditUserTelegram").value = telegram === 'Nein' ? '' : telegram;
        
        if (expirationStr && expirationStr !== '-' && expirationStr !== 'Niemals') {
            const parts = expirationStr.split(',')[0].trim().split('.');
            if (parts.length === 3) {
                view.querySelector("#EditUserExpiration").value = `${parts[2]}-${parts[1]}-${parts[0]}`;
            } else {
                view.querySelector("#EditUserExpiration").value = '';
            }
        } else {
            view.querySelector("#EditUserExpiration").value = '';
        }
        
        view.querySelector("#EditUserIsBotAdmin").checked = cb.dataset.botadmin === 'true';

        view.querySelector("#EditUserPanel").style.display = "block";
    });

    view.querySelector("#CancelEditUserBtn")?.addEventListener("click", (e) => {
        e.preventDefault();
        view.querySelector("#EditUserPanel").style.display = "none";
    });

    view.querySelector("#SaveEditUserBtn")?.addEventListener("click", async (e) => {
        e.preventDefault();
        const userId = view.querySelector("#EditUserId").value;
        const email = view.querySelector("#EditUserEmail").value.trim();
        const telegram = view.querySelector("#EditUserTelegram").value.trim();
        const expiration = view.querySelector("#EditUserExpiration").value; // YYYY-MM-DD
        const isBotAdmin = view.querySelector("#EditUserIsBotAdmin").checked;

        try {
            window.ApiClient.ajax({
                url: window.ApiClient.getUrl('/api/RiNnoFinConfig/UpdateUserLink'),
                type: 'POST',
                data: JSON.stringify({
                    UserId: userId,
                    Email: email,
                    TelegramUsername: telegram,
                    ExpirationDate: expiration ? new Date(expiration).toISOString() : null,
                    IsBotAdmin: isBotAdmin
                }),
                contentType: 'application/json'
            }).then(() => {
                window.Dashboard.alert('Benutzer erfolgreich aktualisiert.');
                view.querySelector("#EditUserPanel").style.display = "none";
                tgConfigPage.loadUsers(view);
            }).catch(err => {
                window.Dashboard.alert('Fehler beim Aktualisieren des Benutzers.');
            });
        } catch (err) {
            window.Dashboard.alert('Netzwerkfehler: ' + err.message);
        }
    });

    view.querySelector("#RefreshLogsBtn")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.loadLogs(view);
    });

    const inputElement = view.querySelector("#TgBotToken");
    const saveBtn = view.querySelector("#SaveConfig");
    saveBtn.addEventListener("click", () => {
        tgConfigPage.saveConfig(view);
    });

    const btnUploadLogo = view.querySelector("#btnUploadLogo");
    if(btnUploadLogo) {
        btnUploadLogo.addEventListener("click", async () => {
            const fileInput = view.querySelector("#logoUpload");
            if(!fileInput.files || fileInput.files.length === 0) {
                window.Dashboard.alert("Bitte wähle zuerst ein Bild aus.");
                return;
            }
            const formData = new FormData();
            formData.append("file", fileInput.files[0]);
            
            window.Dashboard.showLoadingMsg();
            try {
                // fetch works for FormData, but we need full auth headers
                const response = await fetch(window.ApiClient.getUrl('/api/RiNnoFinConfig/UploadLogo'), {
                    method: 'POST',
                    headers: {
                        'Authorization': window.ApiClient.getAuthorizationHeader()
                    },
                    body: formData
                });
                if(response.ok) {
                    window.Dashboard.alert("Logo erfolgreich hochgeladen! Die Änderungen sind sofort sichtbar.");
                    fileInput.value = "";
                } else {
                    throw new Error("Fehler beim Hochladen.");
                }
            } catch(e) {
                window.Dashboard.alert("Fehler beim Hochladen des Logos.");
            } finally {
                window.Dashboard.hideLoadingMsg();
            }
        });
    }

    const btnResetLogo = view.querySelector("#btnResetLogo");
    if(btnResetLogo) {
        btnResetLogo.addEventListener("click", async () => {
            window.Dashboard.showLoadingMsg();
            try {
                window.ApiClient.ajax({
                    url: window.ApiClient.getUrl('/api/RiNnoFinConfig/ResetLogo'),
                    type: 'POST'
                }).then(() => {
                    window.Dashboard.alert("Logo wurde erfolgreich auf den Standard zurückgesetzt.");
                }).catch(() => {
                    throw new Error("Fehler");
                });
            } catch(e) {
                window.Dashboard.alert("Fehler beim Zurücksetzen des Logos.");
            } finally {
                window.Dashboard.hideLoadingMsg();
            }
        });
    }

    view.querySelector("#TestSmtpBtn")?.addEventListener("click", async (e) => {
        e.preventDefault();
        window.Dashboard.showLoadingMsg();
        
        const payload = {
            SmtpServer: (view.querySelector("#SmtpServer").value ?? "").trim(),
            SmtpPort: parseInt(view.querySelector("#SmtpPort").value) || 587,
            SmtpUsername: (view.querySelector("#SmtpUsername").value ?? "").trim(),
            SmtpPassword: (view.querySelector("#SmtpPassword").value ?? "").trim(),
            EmailSenderAddress: (view.querySelector("#EmailSenderAddress").value ?? "").trim(),
            EmailSenderName: (view.querySelector("#EmailSenderName").value ?? "").trim(),
            TestEmailAddress: (view.querySelector("#TestEmailAddress").value ?? "").trim(),
            SmtpUseSsl: view.querySelector("#SmtpUseSsl").checked
        };
        
        window.ApiClient.ajax({
            url: window.ApiClient.getUrl("/api/RiNnoFinConfig/TestSmtp"),
            type: "POST",
            data: JSON.stringify(payload),
            contentType: "application/json"
        }).then(() => {
            window.Dashboard.hideLoadingMsg();
            window.Dashboard.alert("✅ Test E-Mail wurde erfolgreich versendet! Bitte überprüfe dein Postfach.");
        }).catch(err => {
            window.Dashboard.hideLoadingMsg();
            const msg = err?.responseJSON?.message || err?.responseText || err?.message || "Unbekannter Fehler beim Senden.";
            window.Dashboard.alert("❌ Fehler beim Versenden der Test-E-Mail:\n" + msg);
        });
    });

    view.querySelector("#TestTokenBtn")?.addEventListener("click", (e) => {
        e.preventDefault();
        const token = view.querySelector("#TgBotToken").value;
        if (!token) {
            window.Dashboard.alert("Bitte gib zuerst einen Token ein.");
            return;
        }
        tgTokenHelper.validateToken(view, token);
    });

    const loginUrl = window.ApiClient.getUrl("/sso/Telegram");
    view.querySelector("#SSOTelegramLoginUrl").href = loginUrl;
    view.querySelector("#SSOTelegramLoginUrl").innerText = loginUrl;

    const brandingWidget = `
<form action="${loginUrl}">
<button is="emby-button" style="display:flex;flex-direction:row;width:auto;" class="block emby-button raised button-submit">
Mit Telegram anmelden
<svg viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg" style="max-height:4.20em;">
    <defs>
        <linearGradient gradientUnits="userSpaceOnUse" x2="120" y1="240" x1="120" id="linear-gradient">
            <stop stop-color="#1d93d2" offset="0"></stop>
            <stop stop-color="#38b0e3" offset="1"></stop>
        </linearGradient>
    </defs>
    <title>Telegram_logo</title>
    <circle fill="url(#linear-gradient)" r="120" cy="120" cx="120"></circle>
    <path fill="#fff" d="M81.486,130.178,52.2,120.636s-3.5-1.42-2.373-4.64c.232-.664.7-1.229,2.1-2.2,6.489-4.523,120.106-45.36,120.106-45.36s3.208-1.081,5.1-.362a2.766,2.766,0,0,1,1.885,2.055,9.357,9.357,0,0,1,.254,2.585c-.009.752-.1,1.449-.169,2.542-.692,11.165-21.4,94.493-21.4,94.493s-1.239,4.876-5.678,5.043A8.13,8.13,0,0,1,146.1,172.5c-8.711-7.493-38.819-27.727-45.472-32.177a1.27,1.27,0,0,1-.546-.9c-.093-.469.417-1.05.417-1.05s52.426-46.6,53.821-51.492c.108-.379-.3-.566-.848-.4-3.482,1.281-63.844,39.4-70.506,43.607A3.21,3.21,0,0,1,81.486,130.178Z"></path>
</svg>
</button>
</form>`;

    view.querySelector("#ExampleBranding").innerHTML = brandingWidget;
    view.querySelector("#ExampleBrandingCode").innerHTML = brandingWidget.replace(/>/g, "&gt;").replace(/</g, "&lt;").replace(/"/g, "&quot;");

    window.Dashboard.hideLoadingMsg();
}
