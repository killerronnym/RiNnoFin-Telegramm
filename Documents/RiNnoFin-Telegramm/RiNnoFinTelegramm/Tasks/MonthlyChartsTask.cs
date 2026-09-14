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
    public class MonthlyChartsTask : IScheduledTask
    {
        private readonly ILogger<MonthlyChartsTask> _logger;
        private readonly ILibraryManager _libraryManager;
        private readonly TelegramBotClientWrapper _botWrapper;

        public MonthlyChartsTask(ILogger<MonthlyChartsTask> logger, ILibraryManager libraryManager, TelegramBotClientWrapper botWrapper)
        {
            _logger = logger;
            _libraryManager = libraryManager;
            _botWrapper = botWrapper;
        }

        public string Name => "RiNnoFin Monatliche Server-Charts";

        public string Key => "RiNnoFinMonthlyCharts";

        public string Description => "Sendet am Ende des Monats die bestbewerteten Neuerscheinungen des Monats in die Telegram-Gruppe.";

        public string Category => "RiNnoFin";

        public IEnumerable<TaskTriggerInfo> GetDefaultTriggers()
        {
            return Array.Empty<TaskTriggerInfo>();
        }

        public async Task ExecuteAsync(IProgress<double> progress, CancellationToken cancellationToken)
        {
            // Führe dies nur aus, wenn wir uns in den letzten 7 Tagen des Monats befinden
            var today = DateTime.UtcNow.Date;
            var daysInMonth = DateTime.DaysInMonth(today.Year, today.Month);
            if (today.Day < daysInMonth - 7)
            {
                _logger.LogInformation("Noch nicht Ende des Monats, überspringe Monats-Charts.");
                return;
            }

            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config == null || _botWrapper.Client == null) return;

            var notifyGroups = config.TelegramGroups?
                .Where(g => g.TelegramGroupChat is { NotifyNewContent: true })
                .ToArray() ?? Array.Empty<Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramGroup>();

            if (notifyGroups.Length == 0)
            {
                _logger.LogInformation("Keine Telegram-Gruppen für die Monats-Charts konfiguriert.");
                return;
            }

            var minDate = new DateTime(today.Year, today.Month, 1, 0, 0, 0, DateTimeKind.Utc);
            
            var query = new InternalItemsQuery
            {
                IncludeItemTypes = new[] { BaseItemKind.Movie, BaseItemKind.Series },
                MinDateCreated = minDate,
                IsFolder = false,
                IsVirtualItem = false
            };

            var newItems = _libraryManager.GetItemList(query);

            var topMovies = newItems.Where(i => i.GetType().Name == "Movie")
                                    .OrderByDescending(i => i.CommunityRating ?? 0)
                                    .Take(3)
                                    .ToList();

            var topSeries = newItems.Where(i => i.GetType().Name == "Series")
                                    .OrderByDescending(i => i.CommunityRating ?? 0)
                                    .Take(3)
                                    .ToList();

            if (topMovies.Count == 0 && topSeries.Count == 0)
            {
                _logger.LogInformation("Keine neuen Inhalte diesen Monat für die Charts.");
                return;
            }

            progress.Report(20);

            var sb = new StringBuilder();
            sb.AppendLine("🏆 *RiNnoFin Monats-Charts* 🏆");
            sb.AppendLine();
            sb.AppendLine("Die bestbewerteten Neuerscheinungen diesen Monat:");
            sb.AppendLine();

            if (topMovies.Count > 0)
            {
                sb.AppendLine("🎬 *Top Filme:*");
                for (int i = 0; i < topMovies.Count; i++)
                {
                    var m = topMovies[i];
                    var rating = m.CommunityRating.HasValue ? $" ⭐️ {m.CommunityRating.Value:0.0}" : "";
                    sb.AppendLine($"{i+1}. {Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramMarkdown.Escape(m.Name)}{Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramMarkdown.Escape(rating)}");
                }
                sb.AppendLine();
            }

            if (topSeries.Count > 0)
            {
                sb.AppendLine("📺 *Top Serien:*");
                for (int i = 0; i < topSeries.Count; i++)
                {
                    var s = topSeries[i];
                    var rating = s.CommunityRating.HasValue ? $" ⭐️ {s.CommunityRating.Value:0.0}" : "";
                    sb.AppendLine($"{i+1}. {Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramMarkdown.Escape(s.Name)}{Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramMarkdown.Escape(rating)}");
                }
                sb.AppendLine();
            }

            sb.AppendLine("_Sichere dir schon mal Popcorn für den nächsten Monat!_ 🍿");

            var messageText = sb.ToString();

            int total = notifyGroups.Length;
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
                    _logger.LogError(ex, "Fehler beim Senden der Monats-Charts an Gruppe {Group}", group.GroupName);
                }
                processed++;
                progress.Report(20 + (processed / (double)total * 80));
            }

            progress.Report(100);
            _logger.LogInformation("Monats-Charts erfolgreich gesendet.");
        }
    }
}
