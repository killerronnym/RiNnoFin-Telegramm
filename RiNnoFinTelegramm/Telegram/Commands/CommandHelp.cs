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
        sb.AppendLine("📖 *RiNnoFin Telegramm - Hilfe*");
        sb.AppendLine();
        sb.AppendLine("Hier ist eine Übersicht aller verfügbaren Befehle:");
        sb.AppendLine();
        sb.AppendLine("💬 *Allgemeine Befehle:*");
        sb.AppendLine("• `/start` - Startet den Bot und zeigt Begrüßungsnachricht");
        sb.AppendLine("• `/help` - Zeigt diese Hilfe an");
        sb.AppendLine("• `/ping` - Prüft, ob der Bot aktiv ist");
        sb.AppendLine("• `/newsletter` - Zeigt deine Newsletter-Einstellungen");
        sb.AppendLine("• `/abonnieren` - Abonniert neue Medien-Benachrichtigungen");
        sb.AppendLine("• `/deabonnieren` - Deaktiviert Benachrichtigungen");
        sb.AppendLine("• `/passwort <neues_passwort>` - Ändert dein Jellyfin-Passwort");
        sb.AppendLine("• `/status` - Zeigt Statistiken über deine Bibliotheken");
        sb.AppendLine();
        sb.AppendLine("👥 *Gruppen-Befehle (nur Admins):*");
        sb.AppendLine("• `/link <rinnofin_gruppe>` - Verknüpft die Gruppe");
        sb.AppendLine("• `/unlink` - Hebt Gruppenverbindung auf");
        sb.AppendLine("• `/userlist` - Listet verknüpfte Gruppen-Mitglieder auf");
        sb.AppendLine("• `/quiz` - Sendet ein Medien-Quiz in der Gruppe");
        sb.AppendLine("• `/NeuBenutzer` - Erstellt eine Einladung (benötigt JFA-Go)");

        await botClient.SendMessage(
            message.Chat.Id,
            sb.ToString(),
            parseMode: ParseMode.Markdown,
            cancellationToken: cancellationToken);
    }
}
