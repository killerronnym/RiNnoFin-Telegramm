using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;
using MediaBrowser.Controller.Library;
using MediaBrowser.Controller.Entities;
using Microsoft.Extensions.DependencyInjection;
using Jellyfin.Data.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandRueckblick : ICommandBase
{
    public string Command => "rueckblick";

    public bool NeedsAdmin => false;

    public async Task Execute(ITelegramBotService telegramBotService,
        Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var senderId = message.From?.Id;
        if (senderId == null) return;

        var link = telegramBotService.Config.TelegramUserLinks?.FirstOrDefault(l => l.TelegramUserId == senderId.Value);
        if (link == null)
        {
            await telegramBotService.SendNotLinkedMessage(message.Chat.Id, cancellationToken);
            return;
        }

        var libraryManager = telegramBotService.ServiceProvider.GetService<ILibraryManager>();
        
        string content = "Hier ist dein aktueller Rückblick der letzten 7 Tage:\n\n";
        bool hasItems = false;
        
        if (libraryManager != null)
        {
            // Get recently added items (e.g., movies and series)
            var query = new InternalItemsQuery
            {
                IncludeItemTypes = new[] { BaseItemKind.Movie, BaseItemKind.Series },
                MinDateCreated = DateTime.UtcNow.AddDays(-7),
                Limit = 5
            };
            
            var items = libraryManager.GetItemList(query);
            foreach (var item in items)
            {
                content += $"🎬 *{item.Name}* (Hinzugefügt am {item.DateCreated:dd.MM.yyyy})\n";
                if (!string.IsNullOrEmpty(item.Overview))
                {
                    var shortOverview = item.Overview.Length > 100 ? item.Overview.Substring(0, 100) + "..." : item.Overview;
                    content += $"_\"{shortOverview}\"_\n\n";
                }
                hasItems = true;
            }
        }

        if (!hasItems)
        {
            content += "In den letzten 7 Tagen gab es leider keine neuen Filme oder Serien auf dem Server.";
        }
        else
        {
            content += "\nViel Spaß beim Ansehen! 🍿";
        }

        await botClient.SendMessage(
            message.Chat.Id,
            content,
            parseMode: ParseMode.Markdown,
            cancellationToken: cancellationToken);
    }
}
