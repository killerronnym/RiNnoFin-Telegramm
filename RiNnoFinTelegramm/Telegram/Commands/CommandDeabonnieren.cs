using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandDeabonnieren : ICommandBase
{
    public string Command => "deabonnieren";

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
                "âŒ Dieser Befehl ist nur in privaten Chats verfügbar.",
                cancellationToken: cancellationToken);
            return;
        }

        var senderId = message.From?.Id;
        if (senderId == null) return;

        var link = telegramBotService.Config.TelegramUserLinks?.FirstOrDefault(l => l.TelegramUserId == senderId.Value);
        if (link == null)
        {
            await telegramBotService.SendNotLinkedMessage(message.Chat.Id, cancellationToken);
            return;
        }

        link.SubscribedToNewsletter = false;
        RiNnoFinPlugin.Instance!.SaveConfiguration(telegramBotService.Config);

        await botClient.SendMessage(
            message.Chat.Id,
            "🔕 *Erfolgreich abgemeldet!*\n\nDu erhältst keine weiteren Medienbenachrichtigungen mehr auf diesem Server.",
            parseMode: ParseMode.Markdown,
            cancellationToken: cancellationToken);
    }
}
