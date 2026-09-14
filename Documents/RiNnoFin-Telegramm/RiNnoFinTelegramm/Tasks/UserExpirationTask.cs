using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using MediaBrowser.Model.Tasks;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Tasks
{
    public class UserExpirationTask : IScheduledTask
    {
        private readonly ILogger<UserExpirationTask> _logger;

        public UserExpirationTask(ILogger<UserExpirationTask> logger)
        {
            _logger = logger;
        }

        public string Name => "RiNnoFin Accounts überprüfen";

        public string Key => "RiNnoFinUserExpiration";

        public string Description => "Überprüft Ablaufdaten von Benutzern, deaktiviert abgelaufene Accounts und sendet Warnungen für bald ablaufende Accounts.";

        public string Category => "RiNnoFin";

        public IEnumerable<TaskTriggerInfo> GetDefaultTriggers()
        {
            return Array.Empty<TaskTriggerInfo>();
        }

        public async Task ExecuteAsync(IProgress<double> progress, CancellationToken cancellationToken)
        {
            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config == null || config.TelegramUserLinks == null) return;

            var userManager = RiNnoFinPlugin.UserManager;
            if (userManager == null) return;

            var emailService = new EmailService(_logger);
            
            int totalLinks = config.TelegramUserLinks.Count;
            int processed = 0;

            foreach (var link in config.TelegramUserLinks)
            {
                cancellationToken.ThrowIfCancellationRequested();
                
                if (link.ExpirationDate.HasValue)
                {
                    var user = userManager.GetUserById(link.JellyfinUserId);
                    if (user != null)
                    {
                        var dto = userManager.GetUserDto(user, string.Empty);
                        if (dto.Policy.IsDisabled)
                        {
                            processed++;
                            continue; // Bereits deaktiviert
                        }

                        // Ist das Ablaufdatum erreicht?
                        if (DateTime.UtcNow >= link.ExpirationDate.Value)
                        {
                            _logger.LogInformation($"Account {user.Username} abgelaufen. Aktion: {config.ExpirationAction}");
                            
                            if (config.ExpirationAction == "Delete")
                            {
                                await userManager.DeleteUserAsync(user.Id).ConfigureAwait(false);
                            }
                            else
                            {
                                dto.Policy.IsDisabled = true;
                                await userManager.UpdatePolicyAsync(user.Id, dto.Policy).ConfigureAwait(false);
                            }

                            if (!string.IsNullOrEmpty(link.EmailAddress))
                            {
                                string htmlBody = config.EmailTemplateAccountExpired
                                    .Replace("{username}", user.Username)
                                    .Replace("{expirationDate}", link.ExpirationDate.Value.ToString("dd.MM.yyyy"));
                                
                                try {
                                    await emailService.SendEmailAsync(config, link.EmailAddress, config.EmailSubjectAccountExpired, htmlBody);
                                } catch { /* Ignore */ }
                            }
                        }
                        // Warnung X Tage vorher (z.B. 7 Tage)
                        else if (!link.ExpirationNotified && (link.ExpirationDate.Value - DateTime.UtcNow).TotalDays <= 7)
                        {
                            _logger.LogInformation($"Sende Ablaufwarnung an {user.Username}.");
                            if (!string.IsNullOrEmpty(link.EmailAddress))
                            {
                                int daysLeft = (int)Math.Ceiling((link.ExpirationDate.Value - DateTime.UtcNow).TotalDays);
                                string htmlBody = config.EmailTemplateExpirationWarning
                                    .Replace("{username}", user.Username)
                                    .Replace("{daysLeft}", daysLeft.ToString())
                                    .Replace("{expirationDate}", link.ExpirationDate.Value.ToString("dd.MM.yyyy"));
                                
                                try {
                                    await emailService.SendEmailAsync(config, link.EmailAddress, config.EmailSubjectExpirationWarning, htmlBody);
                                    link.ExpirationNotified = true;
                                    RiNnoFinPlugin.Instance.UpdateConfiguration(config);
                                } catch { /* Ignore */ }
                            }
                        }
                    }
                }
                
                processed++;
                progress.Report((double)processed / totalLinks * 100);
            }
        }
    }
}
