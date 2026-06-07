const LinkPrefix = "l:";

const tgConfigPage = {
    pluginUniqueId: "9e1d84f2-901d-44a6-ba92-7fcf1a5598ba",

    modifiedGroups: new Map(),
    currentGroup: null,

    loadConfiguration: (page) => {
        ApiClient.getPluginConfiguration(tgConfigPage.pluginUniqueId).then(
            (config) => {
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
        page.querySelector("#EnableBotService").checked = config.EnableBotService ?? true;
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

    deleteRequest: (page, imdbId) => {
        if (!confirm("Diese Medienanfrage wirklich löschen?")) return;

        window.ApiClient.ajax({
            url: window.ApiClient.getUrl(`/api/RiNnoFinConfig/RemoveRequest/${encodeURIComponent(imdbId)}`),
            type: "DELETE"
        }).then(() => {
            tgConfigPage.loadRequests(page);
            window.Dashboard.alert('Medienanfrage erfolgreich gelöscht.');
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
                config.EnableBotService = page.querySelector("#EnableBotService").checked;

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

        [userNamesList, enableAllFolders, delGroupBtn].forEach(element => {
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

        const linkedText = (page.querySelector("#LinkedTelegramGroupId")?.innerText || "").trim();
        const linkedId = (linkedText && linkedText !== "Keine" && linkedText !== "None") ? Number(linkedText) : 0;
        const hasLinkedChat = !!linkedId;

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

            page.querySelector("#LinkedTelegramGroupId").innerHTML = groupData.TelegramGroupChat?.TelegramChatId ?? "Keine";
            page.querySelector("#UserNames").value = groupData.UserNames.join("\r\n");
            page.querySelector("#SyncUserNames").checked = groupData.TelegramGroupChat?.SyncUserNames ?? true;
            page.querySelector("#NotifyNewContent").checked = groupData.TelegramGroupChat?.NotifyNewContent ?? true;
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

        [sync, notify, allowReq].forEach(el => {
            if (el) {
                el.disabled = !hasLinked;
                el.parentElement.title = hasLinked ? '' : 'Verknüpfe zuerst einen Telegram-Chat mit /link';
            }
        });

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
                    page.querySelector("#LinkedTelegramGroupId").innerHTML = "Keine";
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
    window.Dashboard.showLoadingMsg();

    tgConfigPage.addTextAreaStyle(view);
    tgConfigPage.loadConfiguration(view);
    tgConfigPage.loadRequests(view);

    tgConfigPage.populateFolders(view).then(() => {
        const inputs = [
            "#EnableAllFolders",
            "#UserNames",
            ".folder-checkbox",
            "#SyncUserNames",
            "#NotifyNewContent",
            "#AllowRequests"
        ];

        inputs.forEach(selector => {
            const elements = view.querySelectorAll(selector);
            elements.forEach(element => {
                element.addEventListener('change', () => tgConfigPage.updateGroupData(view));
            });
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

    view.querySelector("#RefreshRequests")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.loadRequests(view);
        window.Dashboard.alert('Wunschliste aktualisiert.');
    });

    view.querySelector("#AddManualRequest")?.addEventListener("click", (e) => {
        e.preventDefault();
        tgConfigPage.addRequest(view);
    });

    const inputElement = view.querySelector("#TgBotToken");
    
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
