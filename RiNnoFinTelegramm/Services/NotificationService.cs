using System;
using System.Collections.Concurrent;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using Jellyfin.Plugin.RiNnoFinTelegramm.Classes;
using Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Entities.Audio;
using JellyfinAudio = MediaBrowser.Controller.Entities.Audio.Audio;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Entities;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Services;

public class NotificationService : IDisposable
{
    private readonly TelegramBotClientWrapper _botClientWrapper;
    private readonly ILibraryManager _libraryManager;
    private readonly ILogger<NotificationService> _logger;
    private readonly ConcurrentDictionary<Guid, DateTime> _pendingNotifications = new();
    private readonly RequestService _requestService;
    private readonly Timer _timer;

    public NotificationService(
        ILogger<NotificationService> logger,
        ILibraryManager libraryManager,
        TelegramBotClientWrapper botClientWrapper,
        RequestService requestService)
    {
        _logger = logger;
        _botClientWrapper = botClientWrapper;
        _libraryManager = libraryManager;
        _requestService = requestService;
        _timer = new Timer(CheckForTimeouts, null, TimeSpan.Zero, TimeSpan.FromHours(1));
    }

    public void Dispose()
    {
        _timer.Dispose();
        GC.SuppressFinalize(this);
    }

    public void OnItemUpdated(object? sender, ItemChangeEventArgs e)
    {
        if (e.Item is not (Movie or Series or Season or Episode or JellyfinAudio or MusicAlbum))
        {
            return;
        }

        _logger.LogInformation("Element aktualisiert: {ItemType} - {ItemName}", e.Item.GetType().Name, e.Item.Name);

        if (IsMetadataComplete(e.Item) && _pendingNotifications.TryRemove(e.Item.Id, out _))
        {
            SendRichNotificationAsync(e.Item);
            RemoveRequestIfNeeded(e.Item);
        }
    }

    public void OnItemAdded(object? sender, ItemChangeEventArgs e)
    {
        if (e.Item is not (Movie or Series or Season or Episode or JellyfinAudio or MusicAlbum))
        {
            return;
        }

        _logger.LogInformation("Element hinzugefügt: {ItemType} - {ItemName}", e.Item.GetType().Name, e.Item.Name);

        if (IsMetadataComplete(e.Item))
        {
            SendRichNotificationAsync(e.Item);
            RemoveRequestIfNeeded(e.Item);
        }
        else
        {
            _pendingNotifications.TryAdd(e.Item.Id, DateTime.UtcNow);
        }
    }

    private void CheckForTimeouts(object? state)
    {
        _logger.LogInformation("Prüfe auf abgelaufene Benachrichtigungen...");

        foreach (var item in _pendingNotifications)
        {
            if (DateTime.UtcNow - item.Value <= TimeSpan.FromHours(24))
            {
                continue;
            }

            if (!_pendingNotifications.TryRemove(item.Key, out _))
            {
                continue;
            }

            var baseItem = _libraryManager.GetItemById(item.Key);
            if (baseItem != null)
            {
                SendRichNotificationAsync(baseItem, true);
                RemoveRequestIfNeeded(baseItem);
            }
        }
    }

    private void RemoveRequestIfNeeded(BaseItem item)
    {
        if (!IsMetadataComplete(item))
        {
            return;
        }

        var imdbId = item.GetProviderId(MetadataProvider.Imdb);
        if (string.IsNullOrEmpty(imdbId))
        {
            return;
        }

        try
        {
            _requestService.RemoveRequestAsync(imdbId, CancellationToken.None).Wait();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Entfernen der Anfrage für Element: {ItemType} - '{ItemName}'", item.GetType().Name, item.Name);
        }
    }

    private bool IsMetadataComplete(BaseItem item)
    {
        if (item is JellyfinAudio or MusicAlbum)
        {
            // Musik hat keine IMDb-ID; sofortige Freigabe
            return true;
        }

        return !string.IsNullOrEmpty(item.GetProviderId(MetadataProvider.Imdb)) &&
               item.HasImage(ImageType.Primary);
    }

    private void SendRichNotificationAsync(BaseItem item, bool isTimeout = false)
    {
        if (_botClientWrapper.Client == null)
        {
            _logger.LogInformation("Kann Benachrichtigung für '{ItemName}' nicht senden: Bot-Client ist null.", item.Name);
            return;
        }

        var config = RiNnoFinPlugin.Instance?.Configuration
                     ?? throw new Exception("RiNnoFinPlugin Instanz/Konfiguration ist null.");

        var notifyGroups = config.TelegramGroups
            .Where(g => g.TelegramGroupChat is { NotifyNewContent: true })
            .ToArray();

        var notifyUsers = config.TelegramUserLinks
            .Where(u => u.SubscribedToNewsletter)
            .ToArray();

        if (notifyGroups.Length == 0 && notifyUsers.Length == 0)
        {
            _logger.LogInformation("Keine Benachrichtigung gesendet für '{ItemName}': Keine Abonnenten oder aktiven Gruppen.", item.Name);
            return;
        }

        _logger.LogInformation("Sende Benachrichtigung für '{ItemName}' an {GroupCount} Gruppen und {UserCount} Benutzer.", item.Name, notifyGroups.Length, notifyUsers.Length);

        string? imagePath = null;
        if (item.HasImage(ImageType.Primary))
        {
            imagePath = item.GetImagePath(ImageType.Primary);
        }
        else if (item.HasImage(ImageType.Backdrop))
        {
            imagePath = item.GetImagePath(ImageType.Backdrop);
        }

        var message = new StringBuilder();

        if (item is Movie)
        {
            message.AppendLine("🎬 *Neuer Film hinzugefügt\\!*");
        }
        else if (item is Series or Season or Episode)
        {
            message.AppendLine("📺 *Neue Episode/Serie hinzugefügt\\!*");
        }
        else if (item is JellyfinAudio or MusicAlbum)
        {
            message.AppendLine("🎵 *Neue Musik hinzugefügt\\!*");
        }
        else
        {
            message.AppendLine("🎉 *Neues Element hinzugefügt\\!*");
        }

        if (isTimeout)
        {
            message.AppendLine("_(Metadaten unvollständig)_");
        }

        message.AppendLine();
        message.Append(item.GetTelegramHyperlink(config.LoginBaseUrl));

        var extraLink = item.GetExtraLink();
        if (extraLink != null)
        {
            message.Append(extraLink);
        }

        message.AppendLine();

        var audioLanguages = item.GetStreamLanguages(MediaStreamType.Audio);
        if (audioLanguages.Length > 0)
        {
            var audioLine = "Audio: " + string.Join(", ", audioLanguages);
            message.AppendLine(TelegramMarkdown.Escape(audioLine));
        }

        var subtitleLanguages = item.GetStreamLanguages(MediaStreamType.Subtitle);
        if (subtitleLanguages.Length > 0)
        {
            var subsLine = "Untertitel: " + string.Join(", ", subtitleLanguages);
            message.AppendLine(TelegramMarkdown.Escape(subsLine));
        }

        var messageText = message.ToString();

        // 1. Senden an Gruppen
        foreach (var notifyGroup in notifyGroups)
        {
            SendToChat(notifyGroup.TelegramGroupChat!.TelegramChatId, messageText, imagePath);
        }

        // 2. Senden an Abonnenten (Newsletter)
        foreach (var notifyUser in notifyUsers)
        {
            SendToChat(notifyUser.TelegramUserId, messageText, imagePath);
        }
    }

    private void SendToChat(long chatId, string messageText, string? imagePath)
    {
        try
        {
            if (_botClientWrapper.Client == null) return;

            if (!string.IsNullOrEmpty(imagePath) && File.Exists(imagePath))
            {
                using var fromFile = new FileStream(imagePath, FileMode.Open, FileAccess.Read);
                _ = _botClientWrapper.Client.SendPhoto(
                    chatId,
                    showCaptionAboveMedia: true,
                    caption: messageText,
                    photo: InputFile.FromStream(fromFile),
                    parseMode: ParseMode.MarkdownV2
                ).Wait(TimeSpan.FromSeconds(30));
            }
            else
            {
                _ = _botClientWrapper.Client.SendMessage(
                    chatId,
                    text: messageText,
                    parseMode: ParseMode.MarkdownV2
                ).Wait(TimeSpan.FromSeconds(30));
            }
        }
        catch (Exception e)
        {
            _logger.LogError("Fehler beim Senden der Benachrichtigung an Chat '{ChatId}': {Msg}", chatId, e.Message);
        }
    }
}
