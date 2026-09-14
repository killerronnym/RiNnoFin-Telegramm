using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandUnlink : ICommandBase
{
    public string Command => "unlink";

    public bool NeedsAdmin => true;

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null)
        {
            telegramBotService.Logger.LogError("Telegram-Bot-Client-Wrapper ist in CommandUnlink null.");
            return;
        }

        if (message.Chat.Type == ChatType.Private)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                isAdmin ? Constants.PrivateAdminWelcomeMessage : Constants.PrivateUserWelcomeMessage,
                cancellationToken: cancellationToken);
            return;
        }

        var linkedGroup = telegramBotService.Config.TelegramGroups.FirstOrDefault(g =>
            g.TelegramGroupChat != null && g.TelegramGroupChat.TelegramChatId == message.Chat.Id);

        if (linkedGroup == null)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "⚠️ *Fehler:* Diese Telegram-Gruppe ist mit keiner RiNnoFin-Gruppe verknüpft.",
                parseMode: ParseMode.Markdown,
                cancellationToken: cancellationToken);
            return;
        }

        var groupName = linkedGroup.GroupName;
        linkedGroup.TelegramGroupChat = null;

        RiNnoFinPlugin.Instance!.SaveConfiguration(telegramBotService.Config);

        await botClient.SendMessage(
            message.Chat.Id,
            $"✅ *Verknüpfung aufgehoben!*\n\nDiese Telegram-Gruppe wurde erfolgreich von der RiNnoFin-Gruppe `{groupName}` getrennt.",
            parseMode: ParseMode.Markdown,
            cancellationToken: cancellationToken);
    }
}
