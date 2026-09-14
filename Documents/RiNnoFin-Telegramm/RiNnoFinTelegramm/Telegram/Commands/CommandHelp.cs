using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandHelp : ICommandBase
{
    public string Command => "help";

    public bool NeedsAdmin => false;

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var sb = new StringBuilder();
        sb.AppendLine("📖 *RiNnoFin Media - Hilfe-Zentrum*");
        sb.AppendLine();
        sb.AppendLine("Hier ist eine Übersicht deiner Möglichkeiten:");
        sb.AppendLine();
        sb.AppendLine("📱 *Dein Account:*");
        sb.AppendLine("🔹 `/start` - Startet den Bot und zeigt das Hauptmenü");
        sb.AppendLine("🔹 `/ping` - Verbindungstest und Account-Status");
        sb.AppendLine("🔹 `/passwort <neu>` - Ändert dein persönliches Passwort");
        sb.AppendLine("🔹 `/wunsch <Titel>` - Sende einen Film-/Serienwunsch an die Admins");
        sb.AppendLine("🔹 `/newsletter` - Übersicht deiner Benachrichtigungen");
        sb.AppendLine("🔹 `/abonnieren` - Newsletter für neue Inhalte aktivieren");
        sb.AppendLine("🔹 `/deabonnieren` - Newsletter deaktivieren");
        sb.AppendLine("🔹 `/quiz` - Ein kleines Film- & Serien-Trivia spielen");
        sb.AppendLine();
        
        if (isAdmin)
        {
            sb.AppendLine("🛠️ *Admin-Funktionen:*");
            sb.AppendLine("🔸 `/status` - Server-Auslastung & Statistik anzeigen");
            sb.AppendLine("🔸 `/userlist` - Mitgliederliste dieser Gruppe anzeigen");
            sb.AppendLine("🔸 `/link <gruppe>` - Diesen Chat mit Jellyfin verknüpfen");
            sb.AppendLine("🔸 `/unlink` - Verknüpfung der Gruppe aufheben");
            sb.AppendLine("🔸 `/NeuerBenutzer` - Eine neue E-Mail-Einladung erstellen");
            sb.AppendLine();
        }
        
        sb.AppendLine("💡 _Tipp: Bei Problemen wende dich an einen Administrator._");

        await botClient.SendMessage(
            message.Chat.Id,
            sb.ToString(),
            parseMode: ParseMode.Markdown,
            cancellationToken: cancellationToken);
    }
}
