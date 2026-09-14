using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Telegram.Bot;
using Jellyfin.Data.Enums;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Entities;
using MediaBrowser.Model.Tasks;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Tasks
{
    public class WeeklyDigestTask : IScheduledTask
    {
        private readonly ILogger<WeeklyDigestTask> _logger;
        private readonly ILibraryManager _libraryManager;
        private readonly TelegramBotClientWrapper _botWrapper;

        public WeeklyDigestTask(ILogger<WeeklyDigestTask> logger, ILibraryManager libraryManager, TelegramBotClientWrapper botWrapper)
        {
            _logger = logger;
            _libraryManager = libraryManager;
            _botWrapper = botWrapper;
        }

        public string Name => "RiNnoFin Wochenrückblick senden";

        public string Key => "RiNnoFinWeeklyDigest";

        public string Description => "Sendet jeden Freitag eine Zusammenfassung der neu hinzugefügten Filme und Serien an alle Abonnenten.";

        public string Category => "RiNnoFin";

        public IEnumerable<TaskTriggerInfo> GetDefaultTriggers()
        {
            return Array.Empty<TaskTriggerInfo>();
        }

        public async Task ExecuteAsync(IProgress<double> progress, CancellationToken cancellationToken)
        {
            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config == null || _botWrapper.Client == null) return;

            var notifyGroups = config.TelegramGroups?
                .Where(g => g.TelegramGroupChat is { NotifyNewContent: true })
                .ToArray() ?? Array.Empty<Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramGroup>();

            var notifyUsers = config.TelegramUserLinks?
                .Where(u => u.SubscribeTelegramNewsletter)
                .ToArray() ?? Array.Empty<Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramUserLink>();

            var emailUsers = config.TelegramUserLinks?
                .Where(u => u.SubscribeEmailNewsletter && !string.IsNullOrWhiteSpace(u.EmailAddress))
                .ToArray() ?? Array.Empty<Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramUserLink>();

            if (notifyGroups.Length == 0 && notifyUsers.Length == 0 && emailUsers.Length == 0)
            {
                _logger.LogInformation("Keine Abonnenten für den Wochenrückblick gefunden.");
                return;
            }

            var minDate = DateTime.UtcNow.AddDays(-7);
            
            var query = new InternalItemsQuery
            {
                IncludeItemTypes = new[] { BaseItemKind.Movie, BaseItemKind.Series },
                MinDateCreated = minDate,
                IsFolder = false,
                IsVirtualItem = false
            };

            var newItems = _libraryManager.GetItemList(query);

            var movies = newItems.Where(i => i.GetType().Name == "Movie").OrderByDescending(i => i.DateCreated).Take(10).ToList();
            var series = newItems.Where(i => i.GetType().Name == "Series").OrderByDescending(i => i.DateCreated).Take(10).ToList();

            if (movies.Count == 0 && series.Count == 0)
            {
                _logger.LogInformation("Keine neuen Inhalte in den letzten 7 Tagen. Kein Wochenrückblick gesendet.");
                return;
            }

            progress.Report(20);

            var sb = new StringBuilder();
            sb.AppendLine("📅 *Dein RiNnoFin Wochenrückblick* 📅");
            sb.AppendLine();
            sb.AppendLine("Das hast du diese Woche verpasst:");
            sb.AppendLine();

            if (movies.Count > 0)
            {
                sb.AppendLine("🎬 *Neue Filme:*");
                foreach (var movie in movies)
                {
                    var yearStr = movie.ProductionYear.HasValue ? $" ({movie.ProductionYear})" : "";
                    sb.AppendLine($"- {Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramMarkdown.Escape(movie.Name)}{Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramMarkdown.Escape(yearStr)}");
                }
                sb.AppendLine();
            }

            if (series.Count > 0)
            {
                sb.AppendLine("📺 *Neue Serien:*");
                foreach (var s in series)
                {
                    var yearStr = s.ProductionYear.HasValue ? $" ({s.ProductionYear})" : "";
                    sb.AppendLine($"- {Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramMarkdown.Escape(s.Name)}{Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramMarkdown.Escape(yearStr)}");
                }
                sb.AppendLine();
            }

            sb.AppendLine("_Viel Spaß beim Streamen am Wochenende!_ 🍿");

            var messageText = sb.ToString();

            int total = notifyGroups.Length + notifyUsers.Length;
            int processed = 0;

            foreach (var group in notifyGroups)
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    await _botWrapper.Client.SendMessage(
                        chatId: group.TelegramGroupChat!.TelegramChatId,
                        text: messageText,
                        parseMode: global::Telegram.Bot.Types.Enums.ParseMode.Markdown,
                        messageThreadId: group.TelegramGroupChat.ContentTopicId,
                        cancellationToken: cancellationToken);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Fehler beim Senden des Wochenrückblicks an Gruppe {Group}", group.GroupName);
                }
                processed++;
                progress.Report(20 + (processed / (double)total * 80));
            }

            foreach (var user in notifyUsers)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (user.TelegramUserId != 0)
                {
                    try
                    {
                        await _botWrapper.Client.SendMessage(
                            chatId: user.TelegramUserId,
                            text: messageText,
                            parseMode: global::Telegram.Bot.Types.Enums.ParseMode.Markdown,
                            cancellationToken: cancellationToken);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Fehler beim Senden des Wochenrückblicks an User {UserId}", user.TelegramUserId);
                    }
                }
                processed++;
                progress.Report(20 + (processed / (double)total * 80));
            }

            // --- SEND EMAILS ---
            if (config.EnableEmail && emailUsers.Length > 0)
            {
                var emailService = new EmailService(_logger);
                var htmlContentBuilder = new StringBuilder();
                if (movies.Count > 0)
                {
                    htmlContentBuilder.AppendLine("<h3>🎬 Neue Filme</h3><ul>");
                    foreach (var movie in movies)
                    {
                        var yearStr = movie.ProductionYear.HasValue ? $" ({movie.ProductionYear})" : "";
                        htmlContentBuilder.AppendLine($"<li><strong>{movie.Name}</strong>{yearStr}</li>");
                    }
                    htmlContentBuilder.AppendLine("</ul>");
                }
                if (series.Count > 0)
                {
                    htmlContentBuilder.AppendLine("<h3>📺 Neue Serien</h3><ul>");
                    foreach (var s in series)
                    {
                        var yearStr = s.ProductionYear.HasValue ? $" ({s.ProductionYear})" : "";
                        htmlContentBuilder.AppendLine($"<li><strong>{s.Name}</strong>{yearStr}</li>");
                    }
                    htmlContentBuilder.AppendLine("</ul>");
                }

                var htmlContent = htmlContentBuilder.ToString();
                var emailTemplate = config.EmailTemplateRueckblick ?? string.Empty;
                var serverUrl = config.LoginBaseUrl?.TrimEnd('/') + "/web/index.html" ?? "";

                foreach (var user in emailUsers)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    try
                    {
                        var body = emailTemplate
                            .Replace("{username}", user.JellyfinUsername ?? "Benutzer")
                            .Replace("{content}", htmlContent)
                            .Replace("{serverUrl}", serverUrl);

                        await emailService.SendEmailAsync(
                            config,
                            user.EmailAddress!,
                            config.EmailSubjectRueckblick,
                            body);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Fehler beim Senden der Rückblick-E-Mail an {Email}", user.EmailAddress);
                    }
                }
            }

            progress.Report(100);
            _logger.LogInformation("Wochenrückblick erfolgreich gesendet.");
        }
    }
}
