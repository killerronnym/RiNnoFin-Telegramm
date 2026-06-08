using System;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.ReplyMarkups;
using System.Collections.Concurrent;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandNeuBenutzer : ICommandBase
{
    // Akzeptiert sowohl NeuerBenutzer als auch NeuBenutzer falls der Nutzer sich vertippt
    public string Command => "NeuerBenutzer";
    public bool NeedsAdmin => true;

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null || string.IsNullOrWhiteSpace(config.JfaGoUrl) || string.IsNullOrWhiteSpace(config.JfaGoUsername))
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "⚠️ JFA-Go ist noch nicht konfiguriert. Bitte trage die JFA-Go URL, Benutzername und Passwort in den Plugin-Einstellungen ein.",
                cancellationToken: cancellationToken);
            return;
        }

        // Start step
        await botClient.SendMessage(
            message.Chat.Id,
            "Bitte Benutzername eingeben für den neuen Account:",
            replyMarkup: new ForceReplyMarkup { Selective = true },
            cancellationToken: cancellationToken);
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
    public string Command => "neubenutzer_step1";
    public bool NeedsAdmin => true;

    // We use a shared dictionary from a static class or just store it here
    public static readonly ConcurrentDictionary<long, string> PendingUsernames = new();

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var username = message.Text?.Trim();
        if (string.IsNullOrWhiteSpace(username)) return;

        PendingUsernames[message.From!.Id] = username;

        await botClient.SendMessage(
            message.Chat.Id,
            $"Benutzername '{username}' gespeichert.\nBitte E-Mail eingeben:",
            replyMarkup: new ForceReplyMarkup { Selective = true },
            cancellationToken: cancellationToken);
    }
}

internal class CommandNeuBenutzerStep2 : ICommandBase
{
    public string Command => "neubenutzer_step2";
    public bool NeedsAdmin => true;

    private static readonly HttpClient HttpClient = new();

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null || string.IsNullOrWhiteSpace(config.JfaGoUrl) || string.IsNullOrWhiteSpace(config.JfaGoUsername))
        {
            return;
        }

        var email = message.Text?.Trim();
        if (string.IsNullOrWhiteSpace(email)) return;

        // E-Mail Validierung
        if (!System.Text.RegularExpressions.Regex.IsMatch(email, @"^[^@\s]+@[^@\s]+\.[^@\s]+$"))
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "⚠️ Die eingegebene E-Mail-Adresse scheint ungültig zu sein. Bitte antworte erneut auf diese Nachricht mit einer korrekten E-Mail-Adresse.",
                replyMarkup: new ForceReplyMarkup { Selective = true },
                cancellationToken: cancellationToken);
            return;
        }

        if (!CommandNeuBenutzerStep1.PendingUsernames.TryRemove(message.From!.Id, out var username))
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "⚠️ Entschuldigung, der Benutzername wurde nicht gefunden. Bitte starte mit /NeuerBenutzer erneut.",
                cancellationToken: cancellationToken);
            return;
        }

        try
        {
            var jfaGoUrl = config.JfaGoUrl.TrimEnd('/');
            
            // 1. Authenticate with JFA-Go using username/password via GET /token/login
            var loginRequest = new HttpRequestMessage(HttpMethod.Get, $"{jfaGoUrl}/token/login");
            var authBytes = Encoding.UTF8.GetBytes($"{config.JfaGoUsername}:{config.JfaGoPassword ?? ""}");
            loginRequest.Headers.Authorization = new AuthenticationHeaderValue("Basic", Convert.ToBase64String(authBytes));

            var loginResponse = await HttpClient.SendAsync(loginRequest, cancellationToken);
            var loginResponseContent = await loginResponse.Content.ReadAsStringAsync(cancellationToken);

            if (!loginResponse.IsSuccessStatusCode)
            {
                telegramBotService.Logger.LogWarning("JFA-Go Login fehlgeschlagen: {Status} - {Response}", loginResponse.StatusCode, loginResponseContent);
                
                string errorMsg = loginResponse.StatusCode == System.Net.HttpStatusCode.Unauthorized
                    ? "❌ JFA-Go Login fehlgeschlagen (401 Unauthorized). Bitte überprüfe Benutzername und Passwort in den Plugin-Einstellungen."
                    : loginResponse.StatusCode == System.Net.HttpStatusCode.NotFound
                    ? "❌ JFA-Go Login-Endpunkt nicht gefunden (404 NotFound). Möglicherweise ist der API-Endpunkt 'GET /token/login' für deine JFA-Go Version nicht korrekt."
                    : $"❌ JFA-Go Login fehlgeschlagen (Status {loginResponse.StatusCode}).";

                await botClient.SendMessage(
                    message.Chat.Id,
                    errorMsg,
                    cancellationToken: cancellationToken);
                return;
            }

            // Extract token
            string? token = null;
            try
            {
                var doc = JsonDocument.Parse(loginResponseContent);
                if (doc.RootElement.TryGetProperty("token", out var tokenProp))
                {
                    token = tokenProp.GetString();
                }
            }
            catch { }

            if (string.IsNullOrWhiteSpace(token))
            {
                await botClient.SendMessage(
                    message.Chat.Id,
                    "❌ Konnte kein Token von JFA-Go erhalten.",
                    cancellationToken: cancellationToken);
                return;
            }

            // 2. Create Invite
            var invitePayload = new
            {
                email = email,
                label = username,
                profile = "Standard User",
                send_to = email,
                remaining_uses = 1,
                months = 0,
                days = 1, // Gültig für 1 Tag
                hours = 0,
                minutes = 0
            };

            var inviteJson = JsonSerializer.Serialize(invitePayload);
            var inviteContent = new StringContent(inviteJson, Encoding.UTF8, "application/json");

            var inviteRequest = new HttpRequestMessage(HttpMethod.Post, $"{jfaGoUrl}/invites");
            inviteRequest.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            inviteRequest.Content = inviteContent;

            var inviteResponse = await HttpClient.SendAsync(inviteRequest, cancellationToken);
            var inviteResponseContent = await inviteResponse.Content.ReadAsStringAsync(cancellationToken);

            if (inviteResponse.IsSuccessStatusCode)
            {
                await botClient.SendMessage(
                    message.Chat.Id,
                    $"✅ Einladung für *{username}* (Profil: Standard User) wurde erfolgreich erstellt und an *{email}* gesendet!",
                    parseMode: global::Telegram.Bot.Types.Enums.ParseMode.Markdown,
                    cancellationToken: cancellationToken);
            }
            else
            {
                telegramBotService.Logger.LogWarning("JFA-Go Invite fehlgeschlagen: {Status} - {Response}", inviteResponse.StatusCode, inviteResponseContent);
                
                await botClient.SendMessage(
                    message.Chat.Id,
                    $"❌ Fehler beim Erstellen der Einladung in JFA-Go.\nStatus: {inviteResponse.StatusCode}\nNachricht: {inviteResponseContent}",
                    cancellationToken: cancellationToken);
            }
        }
        catch (Exception ex)
        {
            telegramBotService.Logger.LogError(ex, "Fehler beim Aufruf der JFA-Go API.");
            await botClient.SendMessage(
                message.Chat.Id,
                $"❌ Verbindungsfehler zu JFA-Go:\n{ex.Message}",
                cancellationToken: cancellationToken);
        }
    }
}
