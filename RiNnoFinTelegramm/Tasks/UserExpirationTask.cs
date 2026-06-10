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
                            _logger.LogInformation($"Account {user.Username} abgelaufen. Wird deaktiviert.");
                            
                            dto.Policy.IsDisabled = true;
                            await userManager.UpdatePolicyAsync(user.Id, dto.Policy).ConfigureAwait(false);

                            if (!string.IsNullOrEmpty(link.EmailAddress))
                            {
                                string htmlBody = $@"
                                <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                                    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                                        <h2 style='color: #ef4444;'>Account abgelaufen ⚠️</h2>
                                        <p>Hallo <strong>{user.Username}</strong>,</p>
                                        <p>Dein Zugang zu RiNnoFin Media ist am {link.ExpirationDate.Value:dd.MM.yyyy} abgelaufen und der Account wurde deaktiviert.</p>
                                        <p>Bitte kontaktiere einen Administrator, um deinen Zugang zu verlängern.</p>
                                    </div>
                                </div>";
                                
                                try {
                                    await emailService.SendEmailAsync(config, link.EmailAddress, "Account abgelaufen - RiNnoFin Media", htmlBody);
                                } catch { /* Ignore */ }
                            }
                        }
                        // Warnung X Tage vorher (z.B. 3 Tage)
                        else if (!link.ExpirationNotified && (link.ExpirationDate.Value - DateTime.UtcNow).TotalDays <= 3)
                        {
                            _logger.LogInformation($"Sende Ablaufwarnung an {user.Username}.");
                            if (!string.IsNullOrEmpty(link.EmailAddress))
                            {
                                int daysLeft = (int)Math.Ceiling((link.ExpirationDate.Value - DateTime.UtcNow).TotalDays);
                                string htmlBody = $@"
                                <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                                    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                                        <h2 style='color: #eab308;'>Dein Account läuft bald ab ⏳</h2>
                                        <p>Hallo <strong>{user.Username}</strong>,</p>
                                        <p>Dein Zugang zu RiNnoFin Media läuft in {daysLeft} Tag(en) (am {link.ExpirationDate.Value:dd.MM.yyyy}) ab.</p>
                                        <p>Bitte wende dich an einen Administrator, falls du weiterhin Zugriff benötigst.</p>
                                    </div>
                                </div>";
                                
                                try {
                                    await emailService.SendEmailAsync(config, link.EmailAddress, "Account läuft bald ab - RiNnoFin Media", htmlBody);
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
