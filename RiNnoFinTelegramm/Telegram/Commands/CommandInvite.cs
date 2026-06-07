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

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandInvite : ICommandBase
{
    public string Command => "invite";

    public bool NeedsAdmin => true;

    private static readonly HttpClient HttpClient = new();

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

        var text = message.Text?.Trim();
        var parts = text?.Split(' ', StringSplitOptions.RemoveEmptyEntries);

        if (parts == null || parts.Length < 3)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "⚠️ Falsche Verwendung. Bitte nutze das Format:\n`/invite <Benutzername> <E-Mail>`\n\nBeispiel: `/invite Max max@example.com`",
                cancellationToken: cancellationToken);
            return;
        }

        var username = parts[1];
        var email = parts[2];

        try
        {
            var jfaGoUrl = config.JfaGoUrl.TrimEnd('/');
            
            // Generate the payload for jfa-go
            // Typically, JFA-Go creates invites via POST /invites. 
            // We'll pass the email and an optional label (username).
            var payload = new
            {
                email = email,
                label = username,
                send_to = email // Instruct jfa-go to send the email directly
            };

            var json = JsonSerializer.Serialize(payload);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            var request = new HttpRequestMessage(HttpMethod.Post, $"{jfaGoUrl}/invites");
            // Standard JFA-Go authentication often uses basic auth or custom headers, but standard OpenAPI key auth is often via Authorization or x-api-token.
            // We will provide a Bearer token or Authorization header. If the user uses username:password in the API Key field, we handle that.
            if (config.JfaGoApiKey.Contains(':'))
            {
                var authBytes = Encoding.UTF8.GetBytes(config.JfaGoApiKey);
                request.Headers.Authorization = new AuthenticationHeaderValue("Basic", Convert.ToBase64String(authBytes));
            }
            else
            {
                request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", config.JfaGoApiKey);
                // Also add it as a custom header just in case JFA-Go expects it differently
                request.Headers.Add("Authorization", config.JfaGoApiKey);
            }

            request.Content = content;

            var response = await HttpClient.SendAsync(request, cancellationToken);
            var responseContent = await response.Content.ReadAsStringAsync(cancellationToken);

            if (response.IsSuccessStatusCode)
            {
                await botClient.SendMessage(
                    message.Chat.Id,
                    $"✅ Einladung für *{username}* erfolgreich erstellt und an *{email}* gesendet!",
                    parseMode: global::Telegram.Bot.Types.Enums.ParseMode.Markdown,
                    cancellationToken: cancellationToken);
            }
            else
            {
                // Versuche einen Fallback auf den /users Endpunkt falls /invites nicht der richtige war.
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
