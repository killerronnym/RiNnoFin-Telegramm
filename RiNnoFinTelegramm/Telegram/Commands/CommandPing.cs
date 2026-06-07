using System.Threading;
using System.Threading.Tasks;
using Telegram.Bot;
using Telegram.Bot.Types;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandPing : ICommandBase
{
    public string Command => "ping";

    public bool NeedsAdmin => false;

    public async Task Execute(ITelegramBotService telegramBotService,
        Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var username = message.From?.Username ?? "Unbekannt";
        var status = isAdmin ? "Administrator" : "Benutzer";
        var reply = $"Pong! 🏓\nIch bin online und mit Jellyfin verbunden.\n\nDein Telegram-Benutzername: @{username}\nDein Status: {status}";

        await botClient.SendMessage(
            message.Chat.Id,
            reply,
            cancellationToken: cancellationToken);
    }
}
