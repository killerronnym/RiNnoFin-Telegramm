using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
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

        // Passwortänderung ist nur in einem privaten Chat zulässig
        if (message.Chat.Type != ChatType.Private)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "❌ Aus Sicherheitsgründen kann dieser Befehl nur in einem privaten Chat mit dem Bot verwendet werden.",
                cancellationToken: cancellationToken);
            return;
        }

        var senderId = message.From?.Id;
        if (senderId == null) return;

        // Prüfen, ob das Telegram-Konto verknüpft ist
        var link = telegramBotService.Config.TelegramUserLinks.FirstOrDefault(l => l.TelegramUserId == senderId.Value);
        if (link == null)
        {
            await telegramBotService.SendNotLinkedMessage(message.Chat.Id, cancellationToken);
            return;
        }

        var text = message.Text ?? string.Empty;
        var parts = text.Split(' ', 2, StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length < 2)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "🔑 *Passwort ändern*\n\n" +
                "Bitte gib dein neues Passwort wie folgt an:\n" +
                "`/passwort <DeinNeuesPasswort>`",
                parseMode: ParseMode.Markdown,
                cancellationToken: cancellationToken);
            return;
        }

        var newPassword = parts[1];
        if (newPassword.Length < 4)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "❌ Das Passwort ist zu kurz. Es muss aus Sicherheitsgründen mindestens 4 Zeichen lang sein.",
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
                    $"❌ Der verknüpfte Jellyfin-Benutzer '{link.JellyfinUsername}' wurde nicht gefunden.",
                    cancellationToken: cancellationToken);
                return;
            }

            // Neues Passwort hashen und speichern
            user.Password = cryptoProvider.CreatePasswordHash(newPassword).ToString();
            await userManager.UpdateUserAsync(user).ConfigureAwait(false);

            await botClient.SendMessage(
                message.Chat.Id,
                "✅ *Erfolgreich!* Dein Jellyfin-Passwort wurde geändert. Du kannst dich jetzt mit deinem neuen Passwort bei Jellyfin anmelden.",
                parseMode: ParseMode.Markdown,
                cancellationToken: cancellationToken);
        }
        catch (Exception ex)
        {
            telegramBotService.Logger.LogError(ex, "Fehler beim Ändern des Passworts für {Username}", link.JellyfinUsername);
            await botClient.SendMessage(
                message.Chat.Id,
                "❌ Bei der Passwortänderung ist ein interner Fehler aufgetreten.",
                cancellationToken: cancellationToken);
        }
    }
}
