using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;
using Telegram.Bot.Types.ReplyMarkups;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandVerbinden : ICommandBase
{
    public string Command => "verbinden";

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
                "❌ Die Account-Verknüpfung kann aus Sicherheitsgründen nur im privaten Chat mit dem Bot durchgeführt werden.",
                cancellationToken: cancellationToken);
            return;
        }

        var senderId = message.From?.Id;
        if (senderId == null) return;

        var config = telegramBotService.Config;
        var existingLink = config.TelegramUserLinks?.FirstOrDefault(l => l.TelegramUserId == senderId.Value);

        if (existingLink != null)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                $"✅ Dein Telegram-Konto ist bereits mit dem Jellyfin-Account *{existingLink.JellyfinUsername}* verknüpft.",
                parseMode: ParseMode.Markdown,
                cancellationToken: cancellationToken);
            return;
        }

        await botClient.SendMessage(
            message.Chat.Id,
            "🔑 *Account-Verknüpfung starten*\n\nBitte gib deine registrierte E-Mail-Adresse ein (antworte direkt auf diese Nachricht):",
            parseMode: ParseMode.Markdown,
            replyMarkup: new ForceReplyMarkup { Selective = true },
            cancellationToken: cancellationToken);
    }
}
