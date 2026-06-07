using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandLink : ICommandBase
{
    public string Command => "link";

    public bool NeedsAdmin => true;

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null)
        {
            telegramBotService.Logger.LogError("Telegram-Bot-Client-Wrapper ist in CommandLink null.");
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

        var parts = message.Text!.Split(' ');
        if (parts.Length != 2)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "Verwendung: `/link <rinnofin_gruppen_name>`",
                parseMode: ParseMode.Markdown,
                cancellationToken: cancellationToken);
            return;
        }

        var groupName = parts[1];
        var group = telegramBotService.Config.TelegramGroups.FirstOrDefault(g => g.GroupName == groupName);
        if (group == null)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                $"❌ RiNnoFin-Gruppe '{groupName}' wurde nicht gefunden.",
                cancellationToken: cancellationToken);
            return;
        }

        group.TelegramGroupChat = new TelegramGroupChat 
        { 
            TelegramChatId = message.Chat.Id, 
            SyncUserNames = true, 
            NotifyNewContent = true 
        };

        RiNnoFinPlugin.Instance!.SaveConfiguration(telegramBotService.Config);

        await botClient.SendMessage(
            message.Chat.Id,
            $"✅ Diese Telegram-Gruppe wurde erfolgreich mit der RiNnoFin-Gruppe '{groupName}' verknüpft.",
            cancellationToken: cancellationToken);
    }
}
