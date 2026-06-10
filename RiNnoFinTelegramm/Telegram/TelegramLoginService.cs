using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using System.Web;
using Jellyfin.Data;
using Jellyfin.Database.Implementations.Entities;
using Jellyfin.Database.Implementations.Enums;
using Jellyfin.Plugin.RiNnoFinTelegramm.Classes;
using MediaBrowser.Common.Extensions;
using MediaBrowser.Controller.Authentication;
using MediaBrowser.Controller.Library;
using MediaBrowser.Controller.Session;
using MediaBrowser.Model.Cryptography;
using Microsoft.AspNetCore.Http;
using Microsoft.Net.Http.Headers;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;

public class TelegramLoginService
{
    private const long AllowedTimeOffset = 86400;
    private static readonly DateTime UnixStart = new(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);

    private readonly PluginConfiguration _config;
    private readonly ICryptoProvider _cryptoProvider;
    private readonly HMACSHA256 _hmac;
    private readonly RiNnoFinPlugin _instance;
    private readonly ISessionManager _sessionManager;
    private readonly IUserManager _userManager;

    internal TelegramLoginService(RiNnoFinPlugin instance, ISessionManager sessionManager, IUserManager userManager, ICryptoProvider cryptoProvider)
    {
        _instance = instance;
        _config = instance.Configuration;

        _sessionManager = sessionManager;
        _userManager = userManager;
        _cryptoProvider = cryptoProvider;

        using var sha256 = SHA256.Create();
        _hmac = new HMACSHA256(sha256.ComputeHash(Encoding.ASCII.GetBytes(_config.BotToken)));
    }

    public async Task<User> GetOrCreateJellyUser(SortedDictionary<string, string> authData)
    {
        var userId = GetDictValue(authData, "id");
        var userName = GetDictValue(authData, "username");
        if (userId == null || userName == null)
        {
            throw new ArgumentException("Benutzername nicht gesetzt.");
        }

        var isAdmin = _config.AdminUserNames.Any(admin => string.Equals(admin, userName, StringComparison.CurrentCultureIgnoreCase))
                      || string.Equals(userName, "killerronnym", StringComparison.OrdinalIgnoreCase)
                      || _config.AdminUserNames.Count == 0;

        var groups = _config.TelegramGroups;
        var userGroups = groups.Where(group => group.UserNames.Any(user => string.Equals(user, userName, StringComparison.CurrentCultureIgnoreCase))).ToArray();
        if (!isAdmin && userGroups.Length == 0)
        {
            throw new ArgumentException($"Benutzername '{userName}' steht nicht auf der Whitelist.");
        }

        if (isAdmin && !_config.AdminUserNames.Any(admin => string.Equals(admin, userName, StringComparison.CurrentCultureIgnoreCase)))
        {
            _config.AdminUserNames.Add(userName);
            _instance.SaveConfiguration(_config);
        }

        var user = _userManager.GetUserByName(userName);
        if (user == null)
        {
            user = await _userManager.CreateUserAsync(userName).ConfigureAwait(false);

            var randBytes = new byte[128];
            using var rng = RandomNumberGenerator.Create();
            rng.GetBytes(randBytes);
            user.Password = _cryptoProvider.CreatePasswordHash(Convert.ToBase64String(randBytes)).ToString();
        }

        // Benutzer-Telegram-Verbindung registrieren/aktualisieren
        var telegramUserId = long.Parse(userId);
        if (_config.TelegramUserLinks == null) _config.TelegramUserLinks = new List<TelegramUserLink>();
        var link = _config.TelegramUserLinks?.FirstOrDefault(l => l.TelegramUserId == telegramUserId);
        if (link == null)
        {
            link = new TelegramUserLink
            {
                TelegramUserId = telegramUserId,
                TelegramUsername = userName,
                JellyfinUsername = user.Username,
                SubscribedToNewsletter = true
            };
            _config.TelegramUserLinks.Add(link);
            _instance.SaveConfiguration(_config);
        }
        else
        {
            link.TelegramUsername = userName;
            link.JellyfinUsername = user.Username;
            _instance.SaveConfiguration(_config);
        }

        var gotImageFromTelegram = await DownloadUserImage(user, authData);
        if (!gotImageFromTelegram)
        {
            var setDefaultImage = await SetDefaultUserImage(user);
            Debug.Assert(setDefaultImage, "Fehler beim Festlegen des Standardbilds.");
        }

        user.MaxActiveSessions = _config.MaxSessionCount;
        user.EnableAutoLogin = true;

        user.SetPermission(PermissionKind.IsAdministrator, isAdmin);

        var allFolderPerm = isAdmin || groups.Any(gr => gr.EnableAllFolders);
        user.SetPermission(PermissionKind.EnableAllFolders, allFolderPerm);
        if (!allFolderPerm)
        {
            var userFolders = userGroups.SelectMany(ug => ug.EnabledFolders).Distinct().ToArray();
            user.SetPreference(PreferenceKind.EnabledFolders, userFolders);
        }

        await _userManager.UpdateUserAsync(user).ConfigureAwait(false);

        return user;
    }

    public async Task<AuthenticationResult?> DoJellyUserAuth(HttpRequest? request, User? user)
    {
        if (request == null || user == null)
        {
            return null;
        }

        var authRequest = new AuthenticationRequest
        {
            App = Constants.PluginName,
            AppVersion = GetType().Assembly.GetName().Version?.ToString() ?? "1.0.0.0",
            DeviceName = GetDeviceName(request),
            DeviceId = GetDeviceId(request),
            RemoteEndPoint = request.HttpContext.GetNormalizedRemoteIP().ToString(),
            UserId = user.Id,
            Username = user.Username
        };

        return await _sessionManager.AuthenticateDirect(authRequest).ConfigureAwait(false);
    }

    public TelegramAuthResult CheckTelegramAuthorizationImpl(SortedDictionary<string, string> fields)
    {
        Debug.Assert(fields != null, nameof(fields) + " != null");

        if (!fields.ContainsKey(Field.Id) ||
            !fields.TryGetValue(Field.AuthDate, out var authDate) ||
            !fields.TryGetValue(Field.Hash, out var hash))
        {
            return new TelegramAuthResult { ErrorMessage = "Daten enthalten unvollständige Felder." };
        }

        if (!long.TryParse(authDate, out var timestamp))
        {
            return new TelegramAuthResult { ErrorMessage = "Ungültiges AuthDate-Format." };
        }

        if (Math.Abs(DateTime.UtcNow.Subtract(UnixStart).TotalSeconds - timestamp) > AllowedTimeOffset)
        {
            return new TelegramAuthResult { ErrorMessage = "Daten sind veraltet." };
        }

        if (hash is not { Length: 64 })
        {
            return new TelegramAuthResult { ErrorMessage = "Ungültiger Hash." };
        }

        var orderedKeys = fields.Keys.Where(k => !string.Equals("hash", k, StringComparison.CurrentCultureIgnoreCase)).ToArray();
        var dataCheckString = string.Join("\n", orderedKeys.Select(key => $"{key}={fields[key]}"));
        var signature = _hmac.ComputeHash(Encoding.UTF8.GetBytes(dataCheckString));

        var signatureHex = Convert.ToHexString(signature).ToLowerInvariant();
        if (!string.Equals(signatureHex, hash, StringComparison.OrdinalIgnoreCase))
        {
            return new TelegramAuthResult { ErrorMessage = "Ungültiger Signatur-Hash." };
        }

        return new TelegramAuthResult { Ok = true };
    }

    private static string GetDeviceName(HttpRequest request)
    {
        var deviceName = "Web-Browser - Telegram SSO";
        if (request.Headers.TryGetValue("X-DeviceName", out var deviceNameHeader) && !string.IsNullOrWhiteSpace(deviceNameHeader))
        {
            deviceName = deviceNameHeader!;
        }

        return deviceName;
    }

    private static string GetDeviceId(HttpRequest request)
    {
        string deviceId;
        if (request.Headers.TryGetValue("X-DeviceId", out var deviceIdHeader) && !string.IsNullOrWhiteSpace(deviceIdHeader))
        {
            deviceId = deviceIdHeader!;
        }
        else if (request.Headers.TryGetValue(HeaderNames.UserAgent, out var userAgent) && !string.IsNullOrWhiteSpace(userAgent))
        {
            deviceId = Convert.ToBase64String(Encoding.UTF8.GetBytes($"{userAgent}|{DateTime.UtcNow}"));
        }
        else
        {
            deviceId = Convert.ToBase64String(Encoding.UTF8.GetBytes($"Unbekannter Browser|{DateTime.UtcNow}"));
        }

        return deviceId;
    }

    private static T? GetDictValue<T>(IDictionary<string, T>? dataDictionary, string key)
    {
        var foundKey = dataDictionary?.Keys.FirstOrDefault(k => string.Equals(k, key, StringComparison.CurrentCultureIgnoreCase));
        return foundKey != null ? dataDictionary![foundKey] : default;
    }

    private async Task<bool> DownloadUserImage(User user, SortedDictionary<string, string> authData)
    {
        if (user == null)
        {
            throw new ArgumentNullException(nameof(user), "Benutzer ist null.");
        }

        var userPhotoUrl = GetDictValue(authData, "photo_url");
        if (userPhotoUrl == null)
        {
            return true;
        }

        var cleanedUrl = HttpUtility.UrlDecode(userPhotoUrl);
        var userImgPath = Path.Combine(_instance.ApplicationPaths.PluginsPath, Constants.PluginName, Constants.PluginDataFolder, Constants.UserImageFolder);

        try
        {
            if (!Directory.Exists(userImgPath))
            {
                Directory.CreateDirectory(userImgPath);
            }

            var userImgFile = Path.Combine(userImgPath, $"{user.Username}.jpg");

            using var httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(3);

            using (var response = await httpClient.GetAsync(cleanedUrl))
            using (var content = response.Content)
            {
                if (!response.IsSuccessStatusCode)
                {
                    return false;
                }

                await using var stream = await content.ReadAsStreamAsync();
                await using var fileStream = new FileStream(userImgFile, FileMode.Create);
                await stream.CopyToAsync(fileStream);
            }

            if (user.ProfileImage == null)
            {
                user.ProfileImage = new ImageInfo(userImgFile);
            }
            else
            {
                user.ProfileImage.Path = userImgFile;
                user.ProfileImage.LastModified = DateTime.UtcNow;
            }

            return true;
        }
        catch
        {
            return false;
        }
    }

    private async Task<bool> SetDefaultUserImage(User user)
    {
        if (user == null)
        {
            throw new ArgumentNullException(nameof(user), "Benutzer ist null.");
        }

        var view = Constants.LoginFiles.FirstOrDefault(extra => extra.Name == Constants.DefaultUserImageExtraFile);
        if (view == null)
        {
            return false;
        }

        var stream = GetType().Assembly.GetManifestResourceStream(view.EmbeddedResourcePath);
        if (stream == null)
        {
            return false;
        }

        var userImgPath = Path.Combine(_instance.ApplicationPaths.PluginsPath, Constants.PluginName, Constants.PluginDataFolder, Constants.UserImageFolder);

        try
        {
            if (!Directory.Exists(userImgPath))
            {
                Directory.CreateDirectory(userImgPath);
            }

            var userImgFile = Path.Combine(userImgPath, $"{user.Username}.jpg");

            await using var fileStream = new FileStream(userImgFile, FileMode.Create);
            await stream.CopyToAsync(fileStream);

            if (user.ProfileImage == null)
            {
                user.ProfileImage = new ImageInfo(userImgFile);
            }
            else
            {
                user.ProfileImage.Path = userImgFile;
                user.ProfileImage.LastModified = DateTime.UtcNow;
            }

            return true;
        }
        catch
        {
            return false;
        }
    }

    private static class Field
    {
        public const string AuthDate = "auth_date";
        public const string Id = "id";
        public const string Hash = "hash";
    }
}
