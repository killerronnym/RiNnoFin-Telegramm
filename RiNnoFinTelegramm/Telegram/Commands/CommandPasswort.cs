using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Cryptography;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandPasswort : ICommandBase
{
    public string Command => "passwort";

    public bool NeedsAdmin => false;

    public async Task Execute(ITelegramBotService telegramBotService,
        Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        // PasswortÃ¤nderung ist nur in einem privaten Chat zulÃ¤ssig
        if (message.Chat.Type != ChatType.Private)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "âŒ Aus SicherheitsgrÃ¼nden kann dieser Befehl nur in einem privaten Chat mit dem Bot verwendet werden.",
                cancellationToken: cancellationToken);
            return;
        }

        var senderId = message.From?.Id;
        if (senderId == null) return;

        // PrÃ¼fen, ob das Telegram-Konto verknÃ¼pft ist
        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null) return;
        
        var link = config.TelegramUserLinks?.FirstOrDefault(l => l.TelegramUserId == senderId.Value);
        if (link == null)
        {
            await telegramBotService.SendNotLinkedMessage(message.Chat.Id, cancellationToken);
            return;
        }

        var messageText = message.Text?.Trim() ?? string.Empty;
        var parts = messageText.Split(' ', 2, StringSplitOptions.RemoveEmptyEntries);

        if (parts.Length < 2)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "âš ï¸ Bitte gib das neue Passwort an. Format: `/passwort <NeuesPasswort>`",
                parseMode: ParseMode.Markdown,
                cancellationToken: cancellationToken);
            return;
        }

        var newPassword = parts[1];

        // Passwort validieren (Beispiel: MindestlÃ¤nge 6 Zeichen)
        if (newPassword.Length < 6)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "âš ï¸ Das neue Passwort muss mindestens 6 Zeichen lang sein.",
                cancellationToken: cancellationToken);
            return;
        }

        try
        {
            var userManager = telegramBotService.ServiceProvider.GetRequiredService<IUserManager>();
            var cryptoProvider = telegramBotService.ServiceProvider.GetRequiredService<ICryptoProvider>();

            var user = userManager.GetUserByName(link.JellyfinUsername);
            if (user == null)
            {
                await botClient.SendMessage(
                    message.Chat.Id,
                    $"âŒ Der verknÃ¼pfte Jellyfin-Benutzer '{link.JellyfinUsername}' wurde nicht gefunden.",
                    cancellationToken: cancellationToken);
                return;
            }

            // Neues Passwort hashen und speichern
            user.Password = cryptoProvider.CreatePasswordHash(newPassword).ToString();
            await userManager.UpdateUserAsync(user).ConfigureAwait(false);

            await botClient.SendMessage(
                message.Chat.Id,
                "âœ… Das Passwort wurde erfolgreich zurÃ¼ckgesetzt.",
                cancellationToken: cancellationToken);

            // Benachrichtigungs-E-Mail senden
            if (config.EnableEmail && !string.IsNullOrWhiteSpace(link.EmailAddress))
            {
                try
                {
                    var emailService = new EmailService(telegramBotService.Logger);
                    string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplatePasswordChanged)
                        ? config.EmailTemplatePasswordChanged.Replace("{username}", user.Username)
                        : $@"
                        <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                            <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                                <h2 style='color: #22c55e;'>Passwort geÃ¤ndert âœ…</h2>
                                <p>Hallo <strong>{user.Username}</strong>,</p>
                                <p>Wir haben registriert, dass dein Passwort Ã¼ber den Telegram-Bot geÃ¤ndert wurde.</p>
                                <p>Falls du dies nicht selbst getan hast, kontaktiere bitte umgehend deinen Administrator!</p>
                                <br/>
                                <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
                            </div>
                        </div>";
                    
                    await emailService.SendEmailAsync(config, link.EmailAddress, "Passwort-Ã„nderung (Telegram)", htmlBody);
                }
                catch (Exception ex)
                {
                    telegramBotService.Logger.LogWarning(ex, "Konnte keine BestÃ¤tigungs-E-Mail versenden.");
                }
            }
        }
        catch (Exception ex)
        {
            telegramBotService.Logger.LogError(ex, "Fehler beim Ã„ndern des Passworts fÃ¼r {Username}", link.JellyfinUsername);
            await botClient.SendMessage(
                message.Chat.Id,
                "âŒ Bei der PasswortÃ¤nderung ist ein interner Fehler aufgetreten.",
                cancellationToken: cancellationToken);
        }
    }
}
