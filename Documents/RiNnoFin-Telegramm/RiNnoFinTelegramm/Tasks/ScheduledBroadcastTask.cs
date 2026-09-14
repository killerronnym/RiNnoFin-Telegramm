using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using MediaBrowser.Model.Tasks;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Tasks
{
    public class ScheduledBroadcastTask : IScheduledTask
    {
        private readonly ILogger<ScheduledBroadcastTask> _logger;

        public ScheduledBroadcastTask(ILogger<ScheduledBroadcastTask> logger)
        {
            _logger = logger;
        }

        public string Name => "RiNnoFin Geplante Nachrichten (Broadcast)";
        public string Key => "RiNnoFinScheduledBroadcast";
        public string Description => "Prueft alle 15 Minuten ob geplante Broadcast-Nachrichten versendet werden sollen.";
        public string Category => "RiNnoFin";

        public IEnumerable<TaskTriggerInfo> GetDefaultTriggers()
        {
            return Array.Empty<TaskTriggerInfo>();
        }

        public async Task ExecuteAsync(IProgress<double> progress, CancellationToken cancellationToken)
        {
            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config == null || config.ScheduledBroadcasts == null || config.ScheduledBroadcasts.Count == 0)
            {
                progress.Report(100); return;
            }

            var now = DateTime.UtcNow;
            var due = config.ScheduledBroadcasts.Where(b => !b.Sent && b.ScheduledAtUtc <= now).ToList();
            if (due.Count == 0) { progress.Report(100); return; }

            _logger.LogInformation("{Count} faellige Broadcast(s) gefunden.", due.Count);

            var botWrapper = RiNnoFinPlugin.Instance?.GetBotClientWrapper();
            var emailService = new EmailService(_logger as ILogger<EmailService> ?? Microsoft.Extensions.Logging.Abstractions.NullLogger<EmailService>.Instance);
            var recipients = config.TelegramUserLinks ?? new();
            int i = 0;

            foreach (var broadcast in due)
            {
                cancellationToken.ThrowIfCancellationRequested();
                int sent = 0;

                foreach (var user in recipients)
                {
                    if (broadcast.ViaTelegram && user.TelegramUserId != 0 && botWrapper?.Client != null)
                    {
                        try
                        {
                            await TelegramBotClientExtensions.SendMessage(
                                botWrapper.Client, user.TelegramUserId, broadcast.Message, parseMode: ParseMode.Markdown);
                            sent++;
                        }
                        catch (Exception ex) { _logger.LogError(ex, "Telegram-Fehler"); }
                    }

                    if (broadcast.ViaEmail && !string.IsNullOrWhiteSpace(user.EmailAddress) && config.EnableEmail)
                    {
                        try
                        {
                            var body = "<div style='font-family:Arial;padding:20px;background:#060b14;color:#f8fafc;'>" +
                                       "<div style='max-width:520px;margin:0 auto;background:#0d1623;border-radius:12px;padding:30px;border:1px solid #1e3a5f;'>" +
                                       "<p style='font-size:15px;line-height:1.6;white-space:pre-wrap;'>" +
                                       WebUtility.HtmlEncode(broadcast.Message) + "</p></div></div>";
                            await emailService.SendEmailAsync(config, user.EmailAddress, broadcast.Subject, body);
                            sent++;
                        }
                        catch (Exception ex) { _logger.LogError(ex, "Email-Fehler"); }
                    }
                }

                broadcast.Sent = true;
                _logger.LogInformation("Broadcast gesendet an {Count} Empfaenger.", sent);
                i++;
                progress.Report((double)i / due.Count * 100);
            }

            RiNnoFinPlugin.Instance!.UpdateConfiguration(config);
            progress.Report(100);
        }
    }
}
