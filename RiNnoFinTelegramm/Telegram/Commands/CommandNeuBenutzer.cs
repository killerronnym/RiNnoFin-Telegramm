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
    public string Command => "NeuBenutzer";
    public bool NeedsAdmin => true;

    private static readonly HttpClient HttpClient = new();
    
    // We store the username temporarily while waiting for the email
    private static readonly ConcurrentDictionary<long, string> PendingUsernames = new();

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null || string.IsNullOrWhiteSpace(config.JfaGoUrl) || string.IsNullOrWhiteSpace(config.JfaGoApiKey))
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "⚠️ JFA-Go ist noch nicht konfiguriert. Bitte trage die JFA-Go URL und den API Key in den Plugin-Einstellungen ein.",
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
        if (config == null || string.IsNullOrWhiteSpace(config.JfaGoUrl) || string.IsNullOrWhiteSpace(config.JfaGoApiKey))
        {
            return;
        }

        var email = message.Text?.Trim();
        if (string.IsNullOrWhiteSpace(email)) return;

        if (!CommandNeuBenutzerStep1.PendingUsernames.TryRemove(message.From!.Id, out var username))
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "⚠️ Entschuldigung, der Benutzername wurde nicht gefunden. Bitte starte mit /NeuBenutzer erneut.",
                cancellationToken: cancellationToken);
            return;
        }

        try
        {
            var jfaGoUrl = config.JfaGoUrl.TrimEnd('/');
            
            // JFA-Go Payload with profile "Standard User"
            var payload = new
            {
                email = email,
                label = username,
                profile = "Standard User",
                send_to = email
            };

            var json = JsonSerializer.Serialize(payload);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            var request = new HttpRequestMessage(HttpMethod.Post, $"{jfaGoUrl}/invites");
            
            if (config.JfaGoApiKey.Contains(':'))
            {
                var authBytes = Encoding.UTF8.GetBytes(config.JfaGoApiKey);
                request.Headers.Authorization = new AuthenticationHeaderValue("Basic", Convert.ToBase64String(authBytes));
            }
            else
            {
                request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", config.JfaGoApiKey);
                request.Headers.Add("Authorization", config.JfaGoApiKey);
            }

            request.Content = content;

            var response = await HttpClient.SendAsync(request, cancellationToken);
            var responseContent = await response.Content.ReadAsStringAsync(cancellationToken);

            if (response.IsSuccessStatusCode)
            {
                await botClient.SendMessage(
                    message.Chat.Id,
                    $"✅ Einladung für *{username}* (Profil: Standard User) wurde erfolgreich erstellt und an *{email}* gesendet!",
                    parseMode: global::Telegram.Bot.Types.Enums.ParseMode.Markdown,
                    cancellationToken: cancellationToken);
            }
            else
            {
                telegramBotService.Logger.LogWarning("JFA-Go Invite fehlgeschlagen: {Status} - {Response}", response.StatusCode, responseContent);
                
                await botClient.SendMessage(
                    message.Chat.Id,
                    $"❌ Fehler beim Erstellen der Einladung in JFA-Go.\nStatus: {response.StatusCode}\nNachricht: {responseContent}",
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
