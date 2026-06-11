using System;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.ReplyMarkups;
using System.Collections.Concurrent;
using System.Linq;
using Jellyfin.Plugin.RiNnoFinTelegramm.Classes;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandNeuBenutzer : ICommandBase
{
    public string Command => "NeuerBenutzer";
    public bool NeedsAdmin => true;

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null || !config.EnableEmail)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "âš ï¸ Der E-Mail-Versand ist deaktiviert. Bitte richte zuerst den SMTP-Server in den Plugin-Einstellungen ein.",
                cancellationToken: cancellationToken);
            return;
        }

        var parts = message.Text?.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (parts != null && parts.Length > 2)
        {
            // If they type: /NeuerBenutzer UserName max@beispiel.de
            var username = parts[1];
            var email = parts[2];
            await CommandNeuBenutzerStep2.HandleEmailInput(telegramBotService, message, email, username, cancellationToken);
        }
        else
        {
            // Ask for username
            await botClient.SendMessage(
                message.Chat.Id,
                "Bitte gib den gewÃ¼nschten Benutzernamen fÃ¼r die neue Einladung ein:",
                replyMarkup: new ForceReplyMarkup { Selective = true },
                cancellationToken: cancellationToken);
        }
    }
}

internal class CommandNeuBenutzerAlias : ICommandBase
{
    public string Command => "NeuBenutzer";
    public bool NeedsAdmin => true;

    public Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var cmd = new CommandNeuBenutzer();
        return cmd.Execute(telegramBotService, message, isAdmin, cancellationToken);
    }
}


internal class CommandNeuBenutzerStep1 : ICommandBase
{
    public string Command => "neubenutzer_step1"; // internal state
    public bool NeedsAdmin => true;

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var username = message.Text?.Trim();
        if (string.IsNullOrWhiteSpace(username)) return;

        await botClient.SendMessage(
            message.Chat.Id,
            $"Bitte gib nun die E-Mail-Adresse für den Benutzer '{username}' ein:",
            replyMarkup: new ForceReplyMarkup { Selective = true },
            cancellationToken: cancellationToken);
    }
}

internal class CommandNeuBenutzerStep2 : ICommandBase
{
    public string Command => "neubenutzer_step2"; // internal state
    public bool NeedsAdmin => true;

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var email = message.Text?.Trim();
        if (string.IsNullOrWhiteSpace(email)) return;

        var replyText = message.ReplyToMessage?.Text ?? "";
        string username = "Neuer Benutzer";
        
        var match = Regex.Match(replyText, @"Benutzer '([^']+)' ein:");
        if (match.Success)
        {
            username = match.Groups[1].Value;
        }

        await HandleEmailInput(telegramBotService, message, email, username, cancellationToken);
    }

    public static async Task HandleEmailInput(ITelegramBotService telegramBotService, Message message, string email, string username, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        if (!Regex.IsMatch(email, @"^[^@\s]+@[^@\s]+\.[^@\s]+$"))
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "?? Die eingegebene E-Mail-Adresse scheint ungültig zu sein. Bitte versuche es erneut mit /NeuBenutzer.",
                cancellationToken: cancellationToken);
            return;
        }

        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null) return;

        try
        {
            var token = Guid.NewGuid().ToString("N");
            InviteTokenManager.AddInvite(token, email, username);

            var baseUrl = config.LoginBaseUrl?.TrimEnd('/') ?? "http://localhost:8096";
            var inviteLink = $"{baseUrl}/sso/Telegram/invite?token={token}&username={Uri.EscapeDataString(username)}";

            var emailService = new EmailService(telegramBotService.Logger);
            string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplateInvite) 
                ? config.EmailTemplateInvite.Replace("{inviteLink}", inviteLink).Replace("{username}", username)
                : $@"
                <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                        <h2 style='color: #2563eb;'>Du wurdest eingeladen! ??</h2>
                        <p>Hallo {username}!</p>
                        <p>Du wurdest eingeladen, Teil unserer <strong>RiNnoFin Media</strong> Community zu werden.</p>
                        <p>Klicke auf den untenstehenden Button, um dein Passwort festzulegen:</p>
                        <div style='text-align: center; margin: 30px 0;'>
                            <a href='{inviteLink}' style='background-color: #2563eb; color: #fff; padding: 14px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;'>Account erstellen</a>
                        </div>
                        <p style='color: #6b7280; font-size: 13px;'>Dieser Link ist einmalig gültig.</p>
                        <hr style='border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;' />
                        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
                    </div>
                </div>";

            var subject = !string.IsNullOrWhiteSpace(config.EmailSubjectInvite) ? config.EmailSubjectInvite.Replace("{username}", username) : $"Deine Einladung zu RiNnoFin Media ??";
            await emailService.SendEmailAsync(config, email, subject, htmlBody);

            await botClient.SendMessage(
                message.Chat.Id,
                $"?? Die Einladungs-E-Mail für den Benutzer *{username}* wurde erfolgreich an *{email}* gesendet!\nDer Nutzer kann nun über den Link seinen Account erstellen.",
                parseMode: global::Telegram.Bot.Types.Enums.ParseMode.Markdown,
                cancellationToken: cancellationToken);
        }
        catch (Exception ex)
        {
            telegramBotService.Logger.LogError(ex, "Fehler beim Senden der Einladung.");
            await botClient.SendMessage(
                message.Chat.Id,
                $"? Fehler beim Versenden der E-Mail:\n{ex.Message}",
                cancellationToken: cancellationToken);
        }
    }
}

public static class InviteTokenManager
{
    public static void AddInvite(string token, string email, string username = "", string? profileUserId = null, int? expirationDays = null)
    {
        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config != null)
        {
            if (config.PersistedInvites == null) config.PersistedInvites = new();
            config.PersistedInvites.Add(new PersistedInvite
            {
                Token = token,
                Email = email,
                Username = username,
                ProfileUserId = profileUserId,
                ExpirationDays = expirationDays
            });
            RiNnoFinPlugin.Instance?.SaveConfiguration(config);
            PluginLog.Info($"[InviteTokenManager] Einladung hinzugefügt und persistiert: {email} (Token: {token})");
        }
    }

    public static bool TryGetInvite(string token, out string email, out string username, out Guid? profileUserId, out int? expirationDays)
    {
        email = string.Empty;
        username = string.Empty;
        profileUserId = null;
        expirationDays = null;
        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null || config.PersistedInvites == null) return false;

        var invite = config.PersistedInvites.FirstOrDefault(i => i.Token == token);
        if (invite == null) return false;

        email = invite.Email;
        username = invite.Username ?? "";
        expirationDays = invite.ExpirationDays;
        if (Guid.TryParse(invite.ProfileUserId, out var parsedGuid))
        {
            profileUserId = parsedGuid;
        }
        return true;
    }

    public static void RemoveInvite(string token)
    {
        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null || config.PersistedInvites == null) return;
        var invite = config.PersistedInvites.FirstOrDefault(i => i.Token == token);
        if (invite != null)
        {
            config.PersistedInvites.Remove(invite);
            RiNnoFinPlugin.Instance?.SaveConfiguration(config);
            PluginLog.Info($"[InviteTokenManager] Einladung verbraucht und aus Persistenz entfernt: {invite.Email}");
        }
    }

    public static bool TryGetAndRemoveInvite(string token, out string email, out string username, out Guid? profileUserId, out int? expirationDays)
    {
        if (TryGetInvite(token, out email, out username, out profileUserId, out expirationDays))
        {
            RemoveInvite(token);
            return true;
        }
        return false;
    }
}
