using System.Threading;
using System.Threading.Tasks;
using Telegram.Bot.Types;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

public interface ICommandBase
{
    string Command { get; }

    bool NeedsAdmin { get; }

    Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken);
}
