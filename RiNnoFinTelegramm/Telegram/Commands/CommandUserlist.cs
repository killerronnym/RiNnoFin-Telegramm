using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandUserlist : ICommandBase
{
    public string Command => "userlist";

    public bool NeedsAdmin => false;

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null)
        {
            telegramBotService.Logger.LogError("Telegram-Bot-Client-Wrapper ist in CommandUserlist null.");
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
                Constants.GroupWelcomeMessage,
                cancellationToken: cancellationToken);
            return;
        }

        var userListText = linkedGroup.UserNames.Any()
            ? string.Join("\n", linkedGroup.UserNames.Select(u => $"- @{u}"))
            : "*(Keine Benutzer auf der Whitelist)*";

        var response = $"👥 *Mitglieder der RiNnoFin-Gruppe '{linkedGroup.GroupName}':*\n\n{userListText}";

        await botClient.SendMessage(
            message.Chat.Id,
            response,
            parseMode: ParseMode.Markdown,
            cancellationToken: cancellationToken);
    }
}
