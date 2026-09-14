using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Data.Enums;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Entities;
using MediaBrowser.Model.Tasks;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Tasks
{
    public class EmailNewsletterTask : IScheduledTask
    {
        private readonly ILogger<EmailNewsletterTask> _logger;
        private readonly ILibraryManager? _libraryManager;

        public EmailNewsletterTask(ILogger<EmailNewsletterTask> logger, ILibraryManager? libraryManager = null)
        {
            _logger = logger;
            _libraryManager = libraryManager;
        }

        private ILibraryManager? LibraryManager => _libraryManager ?? RiNnoFinPlugin.LibraryManager;

        public string Name => "RiNnoFin E-Mail Newsletter (Live-Batch)";

        public string Key => "RiNnoFinEmailNewsletter";

        public string Description => "Sammelt neu hinzugefügte Filme und Serien seit dem letzten Lauf und versendet sie als gebündelte E-Mail (z.B. alle 2 Stunden).";

        public string Category => "RiNnoFin";

        public IEnumerable<TaskTriggerInfo> GetDefaultTriggers()
        {
            return Array.Empty<TaskTriggerInfo>();
        }

        public async Task ExecuteAsync(IProgress<double> progress, CancellationToken cancellationToken)
        {
            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config == null || !config.EnableEmail) return;

            var libManager = LibraryManager;
            if (libManager == null)
            {
                _logger.LogWarning("LibraryManager ist nicht verfügbar.");
                return;
            }

            var emailUsers = config.TelegramUserLinks?
                .Where(u => u.SubscribeEmailNewsletter && !string.IsNullOrWhiteSpace(u.EmailAddress))
                .ToArray() ?? Array.Empty<Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramUserLink>();

            if (emailUsers.Length == 0)
            {
                _logger.LogInformation("Keine E-Mail-Abonnenten für den Newsletter gefunden.");
                return;
            }

            var minDate = config.LastEmailNewsletterSent;
            
            // Check interval
            var interval = config.NewsletterInterval?.ToLower() ?? "wöchentlich";
            var timePassed = DateTime.UtcNow - minDate;
            bool shouldRun = false;
            if (interval.Contains("täglich") && timePassed.TotalHours >= 23) shouldRun = true;
            else if (interval.Contains("wöchentlich") && timePassed.TotalDays >= 6.5) shouldRun = true;
            else if (interval.Contains("zweimal") && timePassed.TotalDays >= 3) shouldRun = true;
            else if (interval.Contains("monatlich") && timePassed.TotalDays >= 28) shouldRun = true;
            else if (timePassed.TotalDays >= 7) shouldRun = true; // Fallback

            if (!shouldRun)
            {
                _logger.LogInformation($"Newsletter-Intervall ({config.NewsletterInterval}) noch nicht erreicht.");
                return;
            }

            var query = new InternalItemsQuery
            {
                IncludeItemTypes = new[] { BaseItemKind.Movie, BaseItemKind.Episode, BaseItemKind.Series },
                MinDateCreated = minDate,
                IsVirtualItem = false
            };

            var newItems = libManager.GetItemList(query);

            var movies = newItems.Where(i => i.GetType().Name == "Movie").OrderByDescending(i => i.DateCreated).ToList();
            var episodes = newItems.Where(i => i.GetType().Name == "Episode").Cast<Episode>().ToList();
            var newSeries = newItems.Where(i => i.GetType().Name == "Series").OrderByDescending(i => i.DateCreated).ToList();

            if (movies.Count == 0 && episodes.Count == 0 && newSeries.Count == 0)
            {
                _logger.LogInformation("Keine neuen Inhalte seit dem letzten Lauf gefunden.");
                config.LastEmailNewsletterSent = DateTime.UtcNow;
                RiNnoFinPlugin.Instance!.UpdateConfiguration(config);
                return;
            }

            progress.Report(20);

            var emailService = new EmailService(_logger);
            var baseUrl = config.LoginBaseUrl?.TrimEnd('/') ?? "";
            var contentBuilder = new StringBuilder();

            // --- Process Movies ---
            if (movies.Count > 0)
            {
                contentBuilder.AppendLine("<h2 style='color:#f8fafc; font-size:22px; border-bottom:2px solid #38bdf8; padding-bottom:8px; margin-bottom:24px; margin-top:0;'>🎬 Neue Filme</h2>");
                foreach (var movie in movies)
                {
                    var yearText = movie.ProductionYear.HasValue ? $" ({movie.ProductionYear.Value})" : string.Empty;
                    var coverUrl = movie.HasImage(ImageType.Primary) && !string.IsNullOrWhiteSpace(baseUrl)
                        ? $"{baseUrl}/Items/{movie.Id}/Images/Primary"
                        : "";
                    var libraryName = movie.GetParents().FirstOrDefault(p => p.GetType().Name == "CollectionFolder")?.Name
                        ?? movie.GetParents().LastOrDefault(p => p.Name != "root" && p.Name != "Server")?.Name ?? "Filme";
                    var playUrl = string.IsNullOrWhiteSpace(baseUrl) ? "#" : $"{baseUrl}/web/index.html#!/details?id={movie.Id}";

                    contentBuilder.AppendLine("<table width='100%' cellpadding='0' cellspacing='0' style='margin-bottom: 24px; background: #152238; border-radius: 12px; overflow: hidden; border: 1px solid #1e3a5f;'><tr>");
                    if (!string.IsNullOrEmpty(coverUrl))
                        contentBuilder.AppendLine($"<td width='140' style='padding: 0;'><img src='{coverUrl}' style='width: 140px; height: 210px; object-fit: cover; display: block;' alt='Cover' /></td>");
                    contentBuilder.AppendLine("<td style='padding: 20px; vertical-align: top;'>");
                    contentBuilder.AppendLine($"<h3 style='margin: 0 0 8px 0; color: #f8fafc; font-size: 18px;'>{movie.Name}<span style='color: #94a3b8; font-weight: 400;'>{yearText}</span></h3>");
                    contentBuilder.AppendLine($"<p style='margin: 0 0 12px 0; font-size: 12px; color: #38bdf8; text-transform: uppercase; letter-spacing: 1px;'>{libraryName}</p>");
                    if (!string.IsNullOrEmpty(movie.Overview))
                    {
                        var overview = movie.Overview.Length > 180 ? movie.Overview.Substring(0, 177) + "..." : movie.Overview;
                        contentBuilder.AppendLine($"<p style='margin: 0 0 16px 0; font-size: 14px; color: #cbd5e1; line-height: 1.5;'>{overview}</p>");
                    }
                    contentBuilder.AppendLine($"<a href='{playUrl}' style='display: inline-block; background: #0ea5e9; color: #fff; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600;'>▶️ Ansehen</a>");
                    contentBuilder.AppendLine("</td></tr></table>");
                }
            }

            // --- Process Series & Episodes ---
            var seriesGroups = episodes.GroupBy(e => e.SeriesId).ToList();
            var allSeriesToDisplay = new Dictionary<Guid, (Series series, int episodeCount)>();

            foreach (var s in newSeries)
            {
                allSeriesToDisplay[s.Id] = ((Series)s, 0); // New series
            }

            foreach (var group in seriesGroups)
            {
                var seriesId = group.Key;
                if (!seriesId.Equals(Guid.Empty))
                {
                    var series = _libraryManager.GetItemById(seriesId) as Series;
                    if (series != null)
                    {
                        if (allSeriesToDisplay.ContainsKey(series.Id))
                        {
                            var existing = allSeriesToDisplay[series.Id];
                            allSeriesToDisplay[series.Id] = (existing.series, existing.episodeCount + group.Count());
                        }
                        else
                        {
                            allSeriesToDisplay[series.Id] = (series, group.Count());
                        }
                    }
                }
            }

            if (allSeriesToDisplay.Count > 0)
            {
                contentBuilder.AppendLine("<h2 style='color:#f8fafc; font-size:22px; border-bottom:2px solid #38bdf8; padding-bottom:8px; margin-bottom:24px; margin-top:32px;'>📺 Neue Serien & Episoden</h2>");
                foreach (var kvp in allSeriesToDisplay.Values)
                {
                    var s = kvp.series;
                    var epCount = kvp.episodeCount;
                    
                    var yearText = s.ProductionYear.HasValue ? $" ({s.ProductionYear.Value})" : string.Empty;
                    var coverUrl = s.HasImage(ImageType.Primary) && !string.IsNullOrWhiteSpace(baseUrl)
                        ? $"{baseUrl}/Items/{s.Id}/Images/Primary"
                        : "";
                    var libraryName = s.GetParents().FirstOrDefault(p => p.GetType().Name == "CollectionFolder")?.Name
                        ?? s.GetParents().LastOrDefault(p => p.Name != "root" && p.Name != "Server")?.Name ?? "Serien";
                    var playUrl = string.IsNullOrWhiteSpace(baseUrl) ? "#" : $"{baseUrl}/web/index.html#!/details?id={s.Id}";

                    string statusText = epCount > 0 ? $"<span style='color: #34d399; font-weight: bold;'>+{epCount} EP</span>" : "<span style='color: #a78bfa; font-weight: bold;'>NEU</span>";

                    contentBuilder.AppendLine("<table width='100%' cellpadding='0' cellspacing='0' style='margin-bottom: 24px; background: #152238; border-radius: 12px; overflow: hidden; border: 1px solid #1e3a5f;'><tr>");
                    if (!string.IsNullOrEmpty(coverUrl))
                        contentBuilder.AppendLine($"<td width='140' style='padding: 0;'><img src='{coverUrl}' style='width: 140px; height: 210px; object-fit: cover; display: block;' alt='Cover' /></td>");
                    contentBuilder.AppendLine("<td style='padding: 20px; vertical-align: top;'>");
                    contentBuilder.AppendLine($"<h3 style='margin: 0 0 8px 0; color: #f8fafc; font-size: 18px;'>{s.Name}<span style='color: #94a3b8; font-weight: 400;'>{yearText}</span></h3>");
                    contentBuilder.AppendLine($"<p style='margin: 0 0 12px 0; font-size: 12px; color: #38bdf8; text-transform: uppercase; letter-spacing: 1px;'>{libraryName} | {statusText}</p>");
                    if (!string.IsNullOrEmpty(s.Overview))
                    {
                        var overview = s.Overview.Length > 180 ? s.Overview.Substring(0, 177) + "..." : s.Overview;
                        contentBuilder.AppendLine($"<p style='margin: 0 0 16px 0; font-size: 14px; color: #cbd5e1; line-height: 1.5;'>{overview}</p>");
                    }
                    contentBuilder.AppendLine($"<a href='{playUrl}' style='display: inline-block; background: #0ea5e9; color: #fff; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600;'>▶️ Zur Serie</a>");
                    contentBuilder.AppendLine("</td></tr></table>");
                }
            }

            var emailTemplate = config.EmailTemplateNewsletterCombined ?? string.Empty;
            var subject = config.EmailSubjectNewsletterCombined ?? "Neue Filme & Serien auf RiNnoFin! 🍿📺";

            foreach (var user in emailUsers)
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    var body = emailTemplate
                        .Replace("{username}", user.JellyfinUsername ?? "Benutzer")
                        .Replace("{content}", contentBuilder.ToString())
                        .Replace("{serverUrl}", baseUrl);

                    await emailService.SendEmailAsync(config, user.EmailAddress!, subject, body);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Fehler beim Senden der kombinierten Newsletter-E-Mail an {Email}", user.EmailAddress);
                }
            }

            // Aktualisiere das Datum für den nächsten Lauf
            config.LastEmailNewsletterSent = DateTime.UtcNow;
            RiNnoFinPlugin.Instance!.UpdateConfiguration(config);

            progress.Report(100);
            _logger.LogInformation("Kombinierter E-Mail Newsletter Batch erfolgreich gesendet.");
        }
    }
}
