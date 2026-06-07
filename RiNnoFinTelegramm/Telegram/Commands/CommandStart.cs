using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandStart : ICommandBase
{
    public string Command => "start";

    public bool NeedsAdmin => false;

    public async Task Execute(ITelegramBotService telegramBotService,
        Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        if (message.Chat.Type == ChatType.Private)
        {
            var senderId = message.From?.Id;
            var link = senderId.HasValue ? telegramBotService.Config.TelegramUserLinks.FirstOrDefault(l => l.TelegramUserId == senderId.Value) : null;

            var welcomeText = isAdmin 
                ? Constants.PrivateAdminWelcomeMessage 
                : Constants.PrivateUserWelcomeMessage;

            var userUsername = message.From?.Username;
            if (!isAdmin)
            {
                if (string.IsNullOrEmpty(userUsername))
                {
                    welcomeText = "⚠️ *Achtung:* Du hast keinen Telegram-Benutzernamen gesetzt!\nBitte lege in den Telegram-Einstellungen einen Benutzernamen fest, damit du dich mit Jellyfin verknüpfen kannst.\n\n" + welcomeText;
                }
                else
                {
                    welcomeText = $"Hallo @{userUsername}!\n(Status: Benutzer)\n\n" + welcomeText;
                }
            }
            else
            {
                welcomeText = $"Hallo Admin @{userUsername}!\n(Status: Administrator)\n\n" + welcomeText;
            }

            global::Telegram.Bot.Types.ReplyMarkups.InlineKeyboardMarkup? replyMarkup = null;

            if (link == null)
            {
                welcomeText = "❌ Dein Telegram-Konto ist noch *nicht* mit einem Jellyfin-Konto verknüpft!\nUm alle Befehle nutzen zu können, verknüpfe bitte zuerst dein Konto:\n\n" + welcomeText;
                
                var baseUrl = telegramBotService.Config.LoginBaseUrl?.TrimEnd('/');
                var ssoUrl = string.IsNullOrEmpty(baseUrl) ? string.Empty : $"{baseUrl}/sso/Telegram";
                if (!string.IsNullOrEmpty(ssoUrl))
                {
                    var loginUrl = new global::Telegram.Bot.Types.LoginUrl
                    {
                        Url = ssoUrl,
                        RequestWriteAccess = true
                    };
                    replyMarkup = new global::Telegram.Bot.Types.ReplyMarkups.InlineKeyboardMarkup(
                        global::Telegram.Bot.Types.ReplyMarkups.InlineKeyboardButton.WithLoginUrl("🔗 Mit Jellyfin verknüpfen", loginUrl)
                    );
                }
            }
            else
            {
                welcomeText = "✅ Dein Konto ist erfolgreich mit Jellyfin verknüpft!\n\n" + welcomeText;
            }

            await botClient.SendMessage(
                message.Chat.Id,
                welcomeText,
                replyMarkup: replyMarkup,
                parseMode: ParseMode.Markdown,
                cancellationToken: cancellationToken);
        }
        else
        {
            await botClient.SendMessage(
                message.Chat.Id,
                Constants.GroupWelcomeMessage,
                cancellationToken: cancellationToken);
        }
    }
}
