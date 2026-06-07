using System;
using System.Collections.Generic;
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

    // Episode batching: group episodes per series, flush after 30s of inactivity
    private readonly ConcurrentDictionary<string, List<Episode>> _pendingEpisodeBatches = new();
    private readonly ConcurrentDictionary<string, Timer> _episodeFlushTimers = new();
    private readonly ConcurrentDictionary<string, DateTime> _recentlyAddedSeries = new();
    private readonly object _batchLock = new();
    private static readonly TimeSpan EpisodeBatchWindow = TimeSpan.FromSeconds(30);

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
        foreach (var t in _episodeFlushTimers.Values)
            t.Dispose();
        GC.SuppressFinalize(this);
    }

    public void OnItemUpdated(object? sender, ItemChangeEventArgs e)
    {
        // Seasons are suppressed — episodes handle grouping
        if (e.Item is Season or Series) return;

        if (e.Item is Episode episode)
        {
            if (IsMetadataComplete(episode) && _pendingNotifications.TryRemove(episode.Id, out _))
            {
                QueueEpisodeForBatch(episode);
                RemoveRequestIfNeeded(episode);
            }
            return;
        }

        if (e.Item is not (Movie or JellyfinAudio or MusicAlbum)) return;

        _logger.LogInformation("Element aktualisiert: {ItemType} - {ItemName}", e.Item.GetType().Name, e.Item.Name);

        if (IsMetadataComplete(e.Item) && _pendingNotifications.TryRemove(e.Item.Id, out _))
        {
            SendRichNotificationAsync(e.Item);
            RemoveRequestIfNeeded(e.Item);
        }
    }

    public void OnItemAdded(object? sender, ItemChangeEventArgs e)
    {
        // Seasons suppressed
        if (e.Item is Season) return;

        // Series: just mark as recently added so episode flush knows it's a new series
        if (e.Item is Series)
        {
            _recentlyAddedSeries[e.Item.Name] = DateTime.UtcNow;
            _logger.LogInformation("Neue Serie erkannt (wird über Episoden gemeldet): {Name}", e.Item.Name);
            return;
        }

        // Episodes: batch
        if (e.Item is Episode episode)
        {
            _logger.LogInformation("Episode hinzugefügt (batching): {Series} - {Name}", episode.SeriesName, episode.Name);
            if (IsMetadataComplete(episode))
            {
                QueueEpisodeForBatch(episode);
                RemoveRequestIfNeeded(episode);
            }
            else
            {
                _pendingNotifications.TryAdd(episode.Id, DateTime.UtcNow);
            }
            return;
        }

        if (e.Item is not (Movie or JellyfinAudio or MusicAlbum)) return;

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

    // ── Episode Batching ──────────────────────────────────────────────────────

    private void QueueEpisodeForBatch(Episode episode)
    {
        var key = episode.SeriesName ?? episode.Id.ToString();

        lock (_batchLock)
        {
            var batch = _pendingEpisodeBatches.GetOrAdd(key, _ => new List<Episode>());
            if (!batch.Any(ep => ep.Id == episode.Id))
                batch.Add(episode);
        }

        // Debounce: reset timer so we wait another 30s after the last episode arrives
        if (_episodeFlushTimers.TryGetValue(key, out var existing))
        {
            existing.Change(EpisodeBatchWindow, Timeout.InfiniteTimeSpan);
        }
        else
        {
            var t = new Timer(_ => FlushEpisodeBatch(key), null, EpisodeBatchWindow, Timeout.InfiniteTimeSpan);
            if (!_episodeFlushTimers.TryAdd(key, t))
                t.Dispose();
        }
    }

    private void FlushEpisodeBatch(string seriesKey)
    {
        if (_episodeFlushTimers.TryRemove(seriesKey, out var t))
            t.Dispose();

        List<Episode> episodes;
        lock (_batchLock)
        {
            if (!_pendingEpisodeBatches.TryRemove(seriesKey, out var batch) || batch.Count == 0)
                return;
            episodes = batch
                .OrderBy(ep => ep.ParentIndexNumber ?? 0)
                .ThenBy(ep => ep.IndexNumber ?? 0)
                .ToList();
        }

        // Is this part of a freshly imported series (added within last 10 min)?
        bool isNewSeries = _recentlyAddedSeries.TryGetValue(seriesKey, out var addedAt)
                           && DateTime.UtcNow - addedAt < TimeSpan.FromMinutes(10);

        _logger.LogInformation("Flushing episode batch '{Series}': {Count} episodes, isNewSeries={New}",
            seriesKey, episodes.Count, isNewSeries);

        SendEpisodeBatchNotification(episodes, isNewSeries);
    }

    private void SendEpisodeBatchNotification(List<Episode> episodes, bool isNewSeries)
    {
        if (_botClientWrapper.Client == null || episodes.Count == 0) return;

        var config = RiNnoFinPlugin.Instance?.Configuration
                     ?? throw new Exception("RiNnoFinPlugin Instanz/Konfiguration ist null.");

        var notifyGroups = config.TelegramGroups
            .Where(g => g.TelegramGroupChat is { NotifyNewContent: true })
            .ToArray();

        var notifyUsers = config.TelegramUserLinks
            .Where(u => u.SubscribedToNewsletter)
            .ToArray();

        if (notifyGroups.Length == 0 && notifyUsers.Length == 0) return;

        var firstEp = episodes[0];
        var seriesName = firstEp.SeriesName ?? firstEp.Name;

        // Try to find the Series item for image + overview
        BaseItem? seriesItem = _libraryManager.GetItemList(new MediaBrowser.Controller.Entities.InternalItemsQuery
        {
            Name = seriesName,
            IncludeItemTypes = new[] { Jellyfin.Data.Enums.BaseItemKind.Series }
        }).FirstOrDefault();

        string? imagePath = null;
        if (seriesItem?.HasImage(ImageType.Primary) == true)
            imagePath = seriesItem.GetImagePath(ImageType.Primary);
        else if (firstEp.HasImage(ImageType.Primary))
            imagePath = firstEp.GetImagePath(ImageType.Primary);

        var baseUrl = config.LoginBaseUrl?.TrimEnd('/');
        string seriesUrl = seriesItem != null && !string.IsNullOrWhiteSpace(baseUrl)
            ? $"{baseUrl}/web/index.html#!/details?id={seriesItem.Id:N}"
            : string.Empty;

        string seriesTitleLink = !string.IsNullOrEmpty(seriesUrl)
            ? $"[{TelegramMarkdown.Escape(seriesName)}]({TelegramMarkdown.Escape(seriesUrl)})"
            : TelegramMarkdown.Escape(seriesName);

        var yearStr = firstEp.ProductionYear.HasValue ? $" ({firstEp.ProductionYear.Value})" : string.Empty;
        var message = new StringBuilder();

        if (episodes.Count == 1 && !isNewSeries)
        {
            // ── Single new episode ──────────────────────────────────────────
            var ep = episodes[0];
            var code = $"S{ep.ParentIndexNumber ?? 0:00}E{ep.IndexNumber ?? 0:00}";
            message.AppendLine($"📺 *Neue Episode:* {seriesTitleLink} \\- {TelegramMarkdown.Escape(code)} \\- {TelegramMarkdown.Escape(ep.Name)}");

            if (!string.IsNullOrEmpty(ep.Overview))
            {
                message.AppendLine();
                var ov = ep.Overview.Length > 300 ? ep.Overview[..300] + "..." : ep.Overview;
                message.AppendLine(TelegramMarkdown.Escape(ov));
            }
        }
        else
        {
            // ── Grouped: new series or multiple episodes ────────────────────
            string header = isNewSeries ? "Neue Serie" : "Neue Episoden";
            message.AppendLine($"📺 *{header}:* {seriesTitleLink}{TelegramMarkdown.Escape(yearStr)}");

            var bySeason = episodes
                .GroupBy(ep => ep.ParentIndexNumber ?? 0)
                .OrderBy(g => g.Key);

            foreach (var season in bySeason)
            {
                var eps = season.OrderBy(ep => ep.IndexNumber ?? 0).ToList();
                var firstNum = eps.First().IndexNumber ?? 1;
                var lastNum  = eps.Last().IndexNumber  ?? firstNum;
                string line = firstNum == lastNum
                    ? $"Staffel {season.Key} · Episode {firstNum}"
                    : $"Staffel {season.Key} · Episode {firstNum} bis {lastNum} \\({eps.Count} Episoden\\)";
                message.AppendLine(TelegramMarkdown.Escape(line));
            }

            // Series overview
            if (seriesItem != null && !string.IsNullOrEmpty(seriesItem.Overview))
            {
                message.AppendLine();
                var ov = seriesItem.Overview.Length > 400
                    ? seriesItem.Overview[..400] + "..."
                    : seriesItem.Overview;
                message.AppendLine(TelegramMarkdown.Escape(ov));
            }
        }

        message.AppendLine();

        // Links
        var links = new List<string>();
        if (!string.IsNullOrEmpty(seriesUrl))
            links.Add($"[🔗 In Jellyfin öffnen]({TelegramMarkdown.Escape(seriesUrl)})");

        var imdbId = (seriesItem ?? (BaseItem)firstEp).GetProviderId(MetadataProvider.Imdb);
        if (!string.IsNullOrEmpty(imdbId))
            links.Add($"[ℹ️ IMDb]({TelegramMarkdown.Escape($"https://www.imdb.com/title/{imdbId}")})");

        if (links.Any())
            message.AppendLine(string.Join(" \\| ", links));

        var text = message.ToString();

        foreach (var group in notifyGroups)
            SendToChat(group.TelegramGroupChat!.TelegramChatId, text, imagePath, group.TelegramGroupChat.ContentTopicId);

        foreach (var user in notifyUsers)
            SendToChat(user.TelegramUserId, text, imagePath, null);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private void CheckForTimeouts(object? state)
    {
        _logger.LogInformation("Prüfe auf abgelaufene Benachrichtigungen...");

        foreach (var item in _pendingNotifications)
        {
            if (DateTime.UtcNow - item.Value <= TimeSpan.FromHours(24)) continue;

            if (!_pendingNotifications.TryRemove(item.Key, out _)) continue;

            var baseItem = _libraryManager.GetItemById(item.Key);
            if (baseItem != null)
            {
                if (baseItem is Episode ep)
                    QueueEpisodeForBatch(ep);
                else
                    SendRichNotificationAsync(baseItem, true);
                RemoveRequestIfNeeded(baseItem);
            }
        }
    }

    private void RemoveRequestIfNeeded(BaseItem item)
    {
        if (!IsMetadataComplete(item)) return;

        var imdbId = item.GetProviderId(MetadataProvider.Imdb);
        if (string.IsNullOrEmpty(imdbId)) return;

        try
        {
            _requestService.RemoveRequestAsync(imdbId, CancellationToken.None).Wait();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Entfernen der Anfrage für '{ItemName}'", item.Name);
        }
    }

    private bool IsMetadataComplete(BaseItem item)
    {
        if (item is JellyfinAudio or MusicAlbum) return true;
        return !string.IsNullOrEmpty(item.GetProviderId(MetadataProvider.Imdb))
               && item.HasImage(ImageType.Primary);
    }

    private void SendRichNotificationAsync(BaseItem item, bool isTimeout = false)
    {
        if (_botClientWrapper.Client == null) return;

        var config = RiNnoFinPlugin.Instance?.Configuration
                     ?? throw new Exception("RiNnoFinPlugin Instanz/Konfiguration ist null.");

        var notifyGroups = config.TelegramGroups
            .Where(g => g.TelegramGroupChat is { NotifyNewContent: true })
            .ToArray();

        var notifyUsers = config.TelegramUserLinks
            .Where(u => u.SubscribedToNewsletter)
            .ToArray();

        if (notifyGroups.Length == 0 && notifyUsers.Length == 0) return;

        _logger.LogInformation("Sende Benachrichtigung für '{ItemName}'.", item.Name);

        string? imagePath = null;
        if (item.HasImage(ImageType.Primary))
            imagePath = item.GetImagePath(ImageType.Primary);
        else if (item.HasImage(ImageType.Backdrop))
            imagePath = item.GetImagePath(ImageType.Backdrop);

        var message = new StringBuilder();
        var yearStr = item.ProductionYear.HasValue ? $" ({item.ProductionYear.Value})" : string.Empty;
        var baseUrl = config.LoginBaseUrl?.TrimEnd('/');
        string jellyfinUrl = !string.IsNullOrWhiteSpace(baseUrl)
            ? $"{baseUrl}/web/index.html#!/details?id={item.Id:N}"
            : string.Empty;

        string titleLink = !string.IsNullOrEmpty(jellyfinUrl)
            ? $"[{TelegramMarkdown.Escape(item.Name)}]({TelegramMarkdown.Escape(jellyfinUrl)})"
            : TelegramMarkdown.Escape(item.Name);

        if (item is Movie)
            message.AppendLine($"🎬 *Neuer Film:* {titleLink}{TelegramMarkdown.Escape(yearStr)}");
        else if (item is JellyfinAudio or MusicAlbum)
            message.AppendLine($"🎵 *Neue Musik:* {titleLink}");
        else
            message.AppendLine($"🎉 *Neues Element:* {titleLink}");

        if (isTimeout)
            message.AppendLine("_(Metadaten unvollständig)_");

        message.AppendLine();

        if (!string.IsNullOrEmpty(item.Overview))
        {
            var ov = item.Overview.Length > 400 ? item.Overview[..400] + "..." : item.Overview;
            message.AppendLine(TelegramMarkdown.Escape(ov));
            message.AppendLine();
        }

        var audioLangs = item.GetStreamLanguages(MediaStreamType.Audio);
        if (audioLangs.Length > 0)
            message.AppendLine(TelegramMarkdown.Escape("🔊 Audio: " + string.Join(", ", audioLangs)));

        var subLangs = item.GetStreamLanguages(MediaStreamType.Subtitle);
        if (subLangs.Length > 0)
            message.AppendLine(TelegramMarkdown.Escape("📝 Untertitel: " + string.Join(", ", subLangs)));

        if (audioLangs.Length > 0 || subLangs.Length > 0)
            message.AppendLine();

        var links = new List<string>();
        if (!string.IsNullOrEmpty(jellyfinUrl))
            links.Add($"[🔗 In Jellyfin öffnen]({TelegramMarkdown.Escape(jellyfinUrl)})");

        var imdbId = item.GetProviderId(MetadataProvider.Imdb);
        if (!string.IsNullOrEmpty(imdbId))
            links.Add($"[ℹ️ IMDb]({TelegramMarkdown.Escape($"https://www.imdb.com/title/{imdbId}")})");
        else
        {
            var tmdbId = item.GetProviderId(MetadataProvider.Tmdb);
            if (!string.IsNullOrEmpty(tmdbId))
            {
                var tmdbUrl = item is Movie
                    ? $"https://www.themoviedb.org/movie/{tmdbId}"
                    : $"https://www.themoviedb.org/tv/{tmdbId}";
                links.Add($"[ℹ️ TMDb]({TelegramMarkdown.Escape(tmdbUrl)})");
            }
        }

        if (links.Any())
            message.AppendLine(string.Join(" \\| ", links));

        var text = message.ToString();

        foreach (var group in notifyGroups)
            SendToChat(group.TelegramGroupChat!.TelegramChatId, text, imagePath, group.TelegramGroupChat.ContentTopicId);

        foreach (var user in notifyUsers)
            SendToChat(user.TelegramUserId, text, imagePath, null);
    }

    private void SendToChat(long chatId, string messageText, string? imagePath, int? messageThreadId)
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
                    parseMode: ParseMode.MarkdownV2,
                    messageThreadId: messageThreadId
                ).Wait(TimeSpan.FromSeconds(30));
            }
            else
            {
                _ = _botClientWrapper.Client.SendMessage(
                    chatId,
                    text: messageText,
                    parseMode: ParseMode.MarkdownV2,
                    messageThreadId: messageThreadId
                ).Wait(TimeSpan.FromSeconds(30));
            }
        }
        catch (Exception e)
        {
            _logger.LogError("Fehler beim Senden der Benachrichtigung an Chat '{ChatId}': {Msg}", chatId, e.Message);
        }
    }
}
