using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandQuiz : ICommandBase
{
    public string Command => "quiz";

    public bool NeedsAdmin => true;

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        // Try to delete the slash command message immediately (so it disappears)
        try
        {
            await botClient.DeleteMessage(message.Chat.Id, message.MessageId, cancellationToken);
        }
        catch (Exception ex)
        {
            telegramBotService.Logger.LogWarning(ex, "Fehler beim Löschen des /quiz-Befehls in Chat '{ChatId}'. Der Bot benötigt eventuell Administrationsrechte zum Löschen von Nachrichten.", message.Chat.Id);
        }

        // Get the matching Telegram group config to check if there is a specific QuizTopicId
        int? messageThreadId = null;
        var group = telegramBotService.Config.TelegramGroups.FirstOrDefault(g => g.TelegramGroupChat?.TelegramChatId == message.Chat.Id);
        if (group?.TelegramGroupChat != null)
        {
            if (group.TelegramGroupChat.EnableQuiz == false)
            {
                // Quiz is disabled for this group
                return;
            }
            messageThreadId = group.TelegramGroupChat.QuizTopicId;
        }

        // Generate and send the quiz question
        await QuizHelper.SendQuizQuestionAsync(botClient, message.Chat.Id, messageThreadId, telegramBotService.Logger, cancellationToken);
    }
}
