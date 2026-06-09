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
            var link = senderId.HasValue ? telegramBotService.Config.TelegramUserLinks?.FirstOrDefault(l => l.TelegramUserId == senderId.Value) : null;

            var welcomeText = isAdmin 
                ? Constants.PrivateAdminWelcomeMessage 
                : Constants.PrivateUserWelcomeMessage;

            var userUsername = message.From?.Username;
            if (!isAdmin)
            {
                if (string.IsNullOrEmpty(userUsername))
                {
                    welcomeText = "âš ï¸ *Achtung:* Du hast keinen Telegram-Benutzernamen gesetzt!\nBitte lege in den Telegram-Einstellungen einen Benutzernamen fest, damit du dich mit Jellyfin verknÃ¼pfen kannst.\n\n" + welcomeText;
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
                welcomeText = "âŒ Dein Telegram-Konto ist noch *nicht* mit einem Jellyfin-Konto verknÃ¼pft!\nUm alle Befehle nutzen zu kÃ¶nnen, verknÃ¼pfe bitte zuerst dein Konto:\n\n" + welcomeText;
                
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
                        global::Telegram.Bot.Types.ReplyMarkups.InlineKeyboardButton.WithLoginUrl("ðŸ”— Mit Jellyfin verknÃ¼pfen", loginUrl)
                    );
                }
            }
            else
            {
                welcomeText = "âœ… Dein Konto ist erfolgreich mit Jellyfin verknÃ¼pft!\n\n" + welcomeText;
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
