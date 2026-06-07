using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandAbonnieren : ICommandBase
{
    public string Command => "abonnieren";

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

        link.SubscribedToNewsletter = true;
        RiNnoFinPlugin.Instance!.SaveConfiguration(telegramBotService.Config);

        await botClient.SendMessage(
            message.Chat.Id,
            "🔔 *Erfolgreich abonniert!*\n\nDu erhältst nun Benachrichtigungen über neue Filme, Serien und Musik auf diesem Server.",
            parseMode: ParseMode.Markdown,
            cancellationToken: cancellationToken);
    }
}
