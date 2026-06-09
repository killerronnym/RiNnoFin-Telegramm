using System;
using System.Net;
using System.Net.Mail;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Services;

public class EmailService
{
    private readonly ILogger _logger;

    public EmailService(ILogger<EmailService> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public EmailService(ILogger logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public async Task SendEmailAsync(PluginConfiguration config, string toAddress, string subject, string htmlBody)
    {
        if (!config.EnableEmail)
        {
            _logger.LogWarning("E-Mail-Versand ist in der Konfiguration deaktiviert. Überspringe E-Mail an {0}", toAddress);
            return;
        }

        try
        {
            using var client = new SmtpClient(config.SmtpServer, config.SmtpPort)
            {
                Credentials = new NetworkCredential(config.SmtpUsername, config.SmtpPassword),
                EnableSsl = config.SmtpUseSsl
            };

            var fromAddress = new MailAddress(config.EmailSenderAddress, config.EmailSenderName);
            var toMailAddress = new MailAddress(toAddress);

            using var message = new MailMessage(fromAddress, toMailAddress)
            {
                Subject = subject,
                Body = htmlBody,
                IsBodyHtml = true
            };

            _logger.LogInformation("Sende E-Mail an {0} über {1}:{2}...", toAddress, config.SmtpServer, config.SmtpPort);
            await client.SendMailAsync(message).ConfigureAwait(false);
            _logger.LogInformation("E-Mail erfolgreich an {0} gesendet.", toAddress);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Senden der E-Mail an {0}", toAddress);
            throw;
        }
    }
}
