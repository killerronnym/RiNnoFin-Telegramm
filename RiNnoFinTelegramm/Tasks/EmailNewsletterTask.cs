using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Data.Enums;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Entities;
using MediaBrowser.Model.Tasks;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Tasks
{
    public class EmailNewsletterTask : IScheduledTask
    {
        private readonly ILogger<EmailNewsletterTask> _logger;
        private readonly ILibraryManager _libraryManager;

        public EmailNewsletterTask(ILogger<EmailNewsletterTask> logger, ILibraryManager libraryManager)
        {
            _logger = logger;
            _libraryManager = libraryManager;
        }

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

            var emailUsers = config.TelegramUserLinks?
                .Where(u => u.SubscribeEmailNewsletter && !string.IsNullOrWhiteSpace(u.EmailAddress))
                .ToArray() ?? Array.Empty<Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramUserLink>();

            if (emailUsers.Length == 0)
            {
                _logger.LogInformation("Keine E-Mail-Abonnenten für den Newsletter gefunden.");
                return;
            }

            var minDate = config.LastEmailNewsletterSent;
            
            var query = new InternalItemsQuery
            {
                IncludeItemTypes = new[] { BaseItemKind.Movie, BaseItemKind.Series },
                MinDateCreated = minDate,
                IsFolder = false,
                IsVirtualItem = false
            };

            var newItems = _libraryManager.GetItemList(query);

            var movies = newItems.Where(i => i.GetType().Name == "Movie").OrderByDescending(i => i.DateCreated).ToList();
            var series = newItems.Where(i => i.GetType().Name == "Series").OrderByDescending(i => i.DateCreated).ToList();

            if (movies.Count == 0 && series.Count == 0)
            {
                _logger.LogInformation("Keine neuen Inhalte seit dem letzten Lauf gefunden.");
                config.LastEmailNewsletterSent = DateTime.UtcNow;
                RiNnoFinPlugin.Instance!.UpdateConfiguration(config);
                return;
            }

            progress.Report(20);

            var emailService = new EmailService(_logger);
            var baseUrl = config.LoginBaseUrl?.TrimEnd('/') ?? "";

            // --- Send Movies Batch ---
            if (movies.Count > 0)
            {
                var contentBuilder = new StringBuilder();
                foreach (var movie in movies)
                {
                    var yearText = movie.ProductionYear.HasValue ? $" ({movie.ProductionYear.Value})" : string.Empty;
                    var coverUrl = movie.HasImage(ImageType.Primary) && !string.IsNullOrWhiteSpace(baseUrl)
                        ? $"{baseUrl}/Items/{movie.Id}/Images/Primary"
                        : "";
                    var libraryName = movie.GetParents().FirstOrDefault(p => p.GetType().Name == "CollectionFolder")?.Name
                        ?? movie.GetParents().LastOrDefault(p => p.Name != "root" && p.Name != "Server")?.Name;

                    contentBuilder.AppendLine("<div style='display: flex; gap: 15px; margin-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 15px;'>");
                    if (!string.IsNullOrEmpty(coverUrl))
                        contentBuilder.AppendLine($"<img src='{coverUrl}' style='width: 120px; border-radius: 8px; object-fit: cover;' alt='Cover' />");
                    contentBuilder.AppendLine("<div>");
                    contentBuilder.AppendLine($"<p style='margin-top: 0; font-size: 16px;'><strong>{movie.Name}</strong>{yearText}</p>");
                    if (!string.IsNullOrEmpty(libraryName))
                        contentBuilder.AppendLine($"<p style='margin: 5px 0; font-size: 12px; color: #9ca3af;'>Ordner: <strong>{libraryName}</strong></p>");
                    if (!string.IsNullOrEmpty(movie.Overview))
                        contentBuilder.AppendLine($"<p style='font-size: 14px;'><em>{movie.Overview}</em></p>");
                    contentBuilder.AppendLine("</div></div>");
                }

                var emailTemplate = config.EmailTemplateNewsletterMovies ?? string.Empty;
                var subject = config.EmailSubjectNewsletterMovies ?? "Neue Filme! 🍿";

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
                        _logger.LogError(ex, "Fehler beim Senden der Filme-Newsletter-E-Mail an {Email}", user.EmailAddress);
                    }
                }
            }

            progress.Report(60);

            // --- Send Series Batch ---
            if (series.Count > 0)
            {
                var contentBuilder = new StringBuilder();
                foreach (var s in series)
                {
                    var yearText = s.ProductionYear.HasValue ? $" ({s.ProductionYear.Value})" : string.Empty;
                    var coverUrl = s.HasImage(ImageType.Primary) && !string.IsNullOrWhiteSpace(baseUrl)
                        ? $"{baseUrl}/Items/{s.Id}/Images/Primary"
                        : "";
                    var libraryName = s.GetParents().FirstOrDefault(p => p.GetType().Name == "CollectionFolder")?.Name
                        ?? s.GetParents().LastOrDefault(p => p.Name != "root" && p.Name != "Server")?.Name;

                    contentBuilder.AppendLine("<div style='display: flex; gap: 15px; margin-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 15px;'>");
                    if (!string.IsNullOrEmpty(coverUrl))
                        contentBuilder.AppendLine($"<img src='{coverUrl}' style='width: 120px; border-radius: 8px; object-fit: cover;' alt='Cover' />");
                    contentBuilder.AppendLine("<div>");
                    contentBuilder.AppendLine($"<p style='margin-top: 0; font-size: 16px;'><strong>{s.Name}</strong>{yearText}</p>");
                    if (!string.IsNullOrEmpty(libraryName))
                        contentBuilder.AppendLine($"<p style='margin: 5px 0; font-size: 12px; color: #9ca3af;'>Ordner: <strong>{libraryName}</strong></p>");
                    if (!string.IsNullOrEmpty(s.Overview))
                        contentBuilder.AppendLine($"<p style='font-size: 14px;'><em>{s.Overview}</em></p>");
                    contentBuilder.AppendLine("</div></div>");
                }

                var emailTemplate = config.EmailTemplateNewsletterSeries ?? string.Empty;
                var subject = config.EmailSubjectNewsletterSeries ?? "Neue Serien! 📺";

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
                        _logger.LogError(ex, "Fehler beim Senden der Serien-Newsletter-E-Mail an {Email}", user.EmailAddress);
                    }
                }
            }

            // Aktualisiere das Datum für den nächsten Lauf
            config.LastEmailNewsletterSent = DateTime.UtcNow;
            RiNnoFinPlugin.Instance!.UpdateConfiguration(config);

            progress.Report(100);
            _logger.LogInformation("E-Mail Newsletter Batch erfolgreich gesendet.");
        }
    }
}
