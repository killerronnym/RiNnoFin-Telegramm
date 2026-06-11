const loadingSpinner = {
    loader: undefined,

    show: () => {
        if (!loadingSpinner.loader) {
            loadingSpinner.loader = document.getElementById("ssoSyncIcon");
        }
        if (loadingSpinner.loader) {
            loadingSpinner.loader.classList.add('animate-continuous');
        }
    },

    hide: () => {
        if (loadingSpinner.loader) {
            loadingSpinner.loader.classList.remove('animate-continuous');
        }
    }
};

window.onload = function () {
    const params = new URLSearchParams(window.location.search);
    if (params.has('id') && params.has('hash')) {
        const user = {
            id: params.get('id'),
            first_name: params.get('first_name'),
            last_name: params.get('last_name'),
            username: params.get('username'),
            photo_url: params.get('photo_url'),
            auth_date: params.get('auth_date'),
            hash: params.get('hash')
        };
        
        window.history.replaceState({}, document.title, window.location.pathname);
        setTimeout(() => onTelegramAuth(user), 100);
        return;
    }

    // Redirect only if not explicitly trying to link
    if (params.get('action') !== 'link') {
        const creds = localStorage.getItem("jellyfin_credentials");
        if (creds) {
            const parsedCreds = JSON.parse(creds);
            if (parsedCreds && parsedCreds.Servers && parsedCreds.Servers.length > 0) {
                const server = parsedCreds.Servers[0];
                if (server.Connect && server.Connect.Expires && new Date(server.Connect.Expires) > new Date()) {
                    const serverUrl = window.location.href.replace(/\/sso\/Telegram(\/login)?(\?.*)?/i, "");
                    window.location.replace(serverUrl);
                }
            }
        }
    }
};

let deviceId;
let deviceName;

function onTelegramAuth(user) {
    loadingSpinner.show();

    if (!deviceName) {
        deviceName = getDeviceName();
    }
    if (!deviceId) {
        deviceId = localStorage.getItem("_deviceId2");
        if (!deviceId) {
            deviceId = generateDeviceId2();
            localStorage.setItem("_deviceId2", deviceId);
        }
    }

    const creds = JSON.parse(localStorage.getItem("jellyfin_credentials") || "{}");
    const server = creds.Servers ? creds.Servers[0] : null;
    if (server && server.UserId) {
        user.jellyfinuserid = server.UserId;
    }

    fetch("{{SERVER_URL}}/sso/Telegram/Authenticate", {
        method: "POST",
        body: JSON.stringify(user),
        headers: {
            "Content-type": "application/json; charset=UTF-8",
            "X-DeviceName": deviceName,
            "X-DeviceId": deviceId
        }
    })
    .then((response) => {
        if (!response.ok) {
            return response.json().then(err => { throw err; });
        }
        return response.json();
    })
    .then((data) => {
        if (data.Ok) {
            setCredentialsAndRedirect(data.AuthenticatedUser);
        } else {
            showError(data.ErrorMessage ?? "Unbekannter Authentifizierungsfehler.");
            loadingSpinner.hide();
        }
    })
    .catch((error) => {
        showError(error.ErrorMessage ?? "Der Telegram-Account ist nicht auf der Whitelist oder der Server ist nicht erreichbar.");
        loadingSpinner.hide();
    });
}

function showError(message) {
    const elem = document.getElementById("errorMessage");
    elem.textContent = message;
    elem.style.display = "block";
}

function setCredentialsAndRedirect(resultData) {
    if (!resultData) {
        console.warn("Fehler beim Verarbeiten der Anmeldedaten:", resultData);
        return;
    }

    resultData.User.Id = resultData.User.Id.replaceAll("-", "");

    const userKeys = Object.keys(resultData.User);
    userKeys.forEach((element) => {
        if (resultData.User[element] === null || resultData.User[element] === undefined) {
            delete resultData.User[element];
        }
    });

    const userId = `user-${resultData.User.Id}-${resultData.User.ServerId}`;
    localStorage.setItem(userId, JSON.stringify(resultData.User));

    const storedCreds = JSON.parse(localStorage.getItem("jellyfin_credentials") || "{}");
    storedCreds.Servers = storedCreds.Servers || [];
    const currentServer = storedCreds.Servers[0] || {};
    currentServer.UserId = resultData.User.Id;
    currentServer.Id = resultData.User.ServerId;
    currentServer.AccessToken = resultData.AccessToken;
    currentServer.ManualAddress = "{{SERVER_URL}}";
    currentServer.manualAddressOnly = true;
    storedCreds.Servers[0] = currentServer;

    localStorage.setItem("jellyfin_credentials", JSON.stringify(storedCreds));
    localStorage.setItem("enableAutoLogin", "true");

    setTimeout(() => {
        window.location.replace("{{SERVER_URL}}");
    }, 200);
}

function generateDeviceId2() {
    return btoa([navigator.userAgent, new Date().toISOString()].join("|")).replace(/=/g, "1");
}

function getDeviceName() {
    function detectBrowser() {
        const userAgent = navigator.userAgent.toLowerCase();
        const browser = {};

        browser.ipad = /ipad/.test(userAgent);
        browser.iphone = /iphone/.test(userAgent);
        browser.android = /android/.test(userAgent);

        browser.tizen = userAgent.includes('tizen') || window.tizen != null;
        browser.web0s = userAgent.includes('netcast') || userAgent.includes('web0s');
        browser.operaTv = userAgent.includes('tv') && userAgent.includes('opr/');
        browser.xboxOne = userAgent.includes('xbox');
        browser.ps4 = userAgent.includes('playstation 4');

        const edgeRegex = /(edg|edge|edga|edgios)[ /]([\w.]+)/.test(userAgent);
        browser.edgeChromium = /(edg|edga|edgios)[ /]([\w.]+)/.test(userAgent);
        browser.edge = edgeRegex && !browser.edgeChromium;
        browser.chrome = /chrome/.test(userAgent) && !edgeRegex;
        browser.firefox = /firefox/.test(userAgent);
        browser.opera = /opera/.test(userAgent) || /opr/.test(userAgent);
        browser.safari = !browser.chrome && !browser.edgeChromium &&
            !browser.edge && !browser.opera &&
            userAgent.includes('webkit');

        if (!browser.ipad && navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1) {
            browser.ipad = true;
        }

        return browser;
    }

    const browserName = {
        tizen: 'Samsung Smart TV',
        web0s: 'LG Smart TV',
        operaTv: 'Opera TV',
        xboxOne: 'Xbox One',
        ps4: 'Sony PS4',
        chrome: 'Chrome',
        edgeChromium: 'Edge',
        edge: 'Legacy Edge',
        firefox: 'Firefox',
        opera: 'Opera',
        safari: 'Safari'
    };

    const browser = detectBrowser();
    let name = 'Web Browser - Telegram SSO';

    for (const key in browserName) {
        if (browser[key]) {
            name = browserName[key];
            break;
        }
    }

    if (browser.ipad) {
        name += ' iPad';
    } else if (browser.iphone) {
        name += ' iPhone';
    } else if (browser.android) {
        name += ' Android';
    }

    return name;
}
