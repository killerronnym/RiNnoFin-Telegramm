using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using MediaBrowser.Controller.Session;
using MediaBrowser.Model.Tasks;
using Microsoft.Extensions.Logging;
using Telegram.Bot;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Tasks
{
    public class ServerMonitoringTask : IScheduledTask
    {
        private readonly ILogger<ServerMonitoringTask> _logger;
        private readonly TelegramBotClientWrapper _botWrapper;
        private readonly ISessionManager _sessionManager;

        public ServerMonitoringTask(ILogger<ServerMonitoringTask> logger, TelegramBotClientWrapper botWrapper, ISessionManager sessionManager)
        {
            _logger = logger;
            _botWrapper = botWrapper;
            _sessionManager = sessionManager;
        }

        public string Name => "RiNnoFin Server-Überwachung";

        public string Key => "RiNnoFinServerMonitoring";

        public string Description => "Überwacht Festplattenplatz und aktive Transcodierungen und warnt Administratoren bei Problemen.";

        public string Category => "RiNnoFin";

        public IEnumerable<TaskTriggerInfo> GetDefaultTriggers()
        {
            return Array.Empty<TaskTriggerInfo>();
        }

        public async Task ExecuteAsync(IProgress<double> progress, CancellationToken cancellationToken)
        {
            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config == null || _botWrapper.Client == null) return;

            var adminUsernames = config.AdminUserNames ?? new List<string>();
            var adminTelegramIds = new List<long>();

            if (config.TelegramUserLinks != null)
            {
                foreach (var link in config.TelegramUserLinks)
                {
                    if (adminUsernames.Contains(link.JellyfinUsername, StringComparer.OrdinalIgnoreCase) && link.TelegramUserId != 0)
                    {
                        adminTelegramIds.Add(link.TelegramUserId);
                    }
                }
            }

            if (adminTelegramIds.Count == 0)
            {
                _logger.LogInformation("Server-Überwachung: Keine konfigurierten Administratoren mit verknüpftem Telegram-Konto gefunden.");
                return;
            }

            var warnings = new List<string>();

            // 1. Festplatten-Alarm (mehr als 95% voll)
            foreach (var drive in DriveInfo.GetDrives())
            {
                if (drive.IsReady)
                {
                    try
                    {
                        double usedPercent = 100.0 * (drive.TotalSize - drive.TotalFreeSpace) / drive.TotalSize;
                        if (usedPercent >= 95.0)
                        {
                            warnings.Add($"💾 *Festplatten-Warnung:*\nLaufwerk `{drive.Name}` ist zu *{usedPercent:F1}%* voll!\nNur noch {FormatBytes(drive.TotalFreeSpace)} frei.");
                        }
                    }
                    catch { /* Ignore unreadable drives */ }
                }
            }

            progress.Report(50);

            // 2. Transcoding-Warnung
            try
            {
                int transcodingCount = 0;
                foreach (var session in _sessionManager.Sessions)
                {
                    if (session.PlayState?.PlayMethod == MediaBrowser.Model.Session.PlayMethod.Transcode)
                    {
                        transcodingCount++;
                    }
                }

                if (transcodingCount >= 3)
                {
                    warnings.Add($"🔥 *Transcoding-Warnung:*\nAktuell laufen *{transcodingCount} Transcoding-Streams* gleichzeitig!\nDies kann zu hoher CPU-Auslastung führen.");
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Fehler beim Überprüfen der Sessions für die Transcoding-Warnung.");
            }

            progress.Report(80);

            if (warnings.Count > 0)
            {
                string message = "🚨 *RiNnoFin Server-Alarm* 🚨\n\n" + string.Join("\n\n", warnings);

                foreach (var adminId in adminTelegramIds.Distinct())
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    try
                    {
                        await _botWrapper.Client.SendMessage(
                            chatId: adminId,
                            text: message,
                            parseMode: global::Telegram.Bot.Types.Enums.ParseMode.Markdown,
                            cancellationToken: cancellationToken);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Fehler beim Senden der Alarm-Nachricht an Admin {AdminId}", adminId);
                    }
                }
            }

            progress.Report(100);
        }

        private static string FormatBytes(long bytes)
        {
            string[] sizes = { "B", "KB", "MB", "GB", "TB" };
            double len = bytes;
            int order = 0;
            while (len >= 1024 && order < sizes.Length - 1)
            {
                order++;
                len = len / 1024;
            }
            return $"{len:0.##} {sizes[order]}";
        }
    }
}
