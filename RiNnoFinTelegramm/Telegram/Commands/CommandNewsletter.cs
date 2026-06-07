using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;
using Telegram.Bot.Types.ReplyMarkups;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandNewsletter : ICommandBase
{
    // We handle /newsletter, /abonnieren, and /deabonnieren.
    // Since this class is registered in assembly scanning, we can create multiple small classes
    // or register one and direct in the service, but since we scan by type implementing ICommandBase,
    // let's make separate files for each command, or we can make one and handle matches in the service.
    // Wait, since assembly scanning instantiates each class, each class handles exactly one command.
    // Let's create CommandNewsletter for "/newsletter", and then we'll write CommandAbonnieren and CommandDeabonnieren!
    public string Command => "newsletter";

    public bool NeedsAdmin => false;

    public async Task Execute(ITelegramBotService telegramBotService,
        Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        if (message.Chat.Type != ChatType.Private)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "❌ Dieser Befehl ist nur in privaten Chats verfügbar.",
                cancellationToken: cancellationToken);
            return;
        }

        var senderId = message.From?.Id;
        if (senderId == null) return;

        var link = telegramBotService.Config.TelegramUserLinks.FirstOrDefault(l => l.TelegramUserId == senderId.Value);
        if (link == null)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "❌ Dein Telegram-Konto ist nicht mit einem Jellyfin-Konto verknüpft.\n\n" +
                "Bitte melde dich erst über Jellyfin mit Telegram SSO an.",
                cancellationToken: cancellationToken);
            return;
        }

        var status = link.SubscribedToNewsletter ? "Abonniert 🔔" : "Deaktiviert 🔕";
        var text = $"📰 *RiNnoFin Newsletter-Einstellungen*\n\n" +
                   $"Aktueller Status: *{status}*\n\n" +
                   $"Du kannst den Newsletter abonnieren, um Benachrichtigungen über neu hinzugefügte Filme, Serien und Musik zu erhalten.";

        var keyboard = new InlineKeyboardMarkup(new[]
        {
            new[]
            {
                InlineKeyboardButton.WithCallbackData("🔔 Abonnieren", "newsletter_subscribe"),
                InlineKeyboardButton.WithCallbackData("🔕 Deaktivieren", "newsletter_unsubscribe")
            }
        });

        await botClient.SendMessage(
            message.Chat.Id,
            text,
            parseMode: ParseMode.Markdown,
            replyMarkup: keyboard,
            cancellationToken: cancellationToken);
    }
}
