using System;
using System.Linq;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;
using Telegram.Bot.Types.ReplyMarkups;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandWunsch : ICommandBase
{
    public string Command => "wunsch";

    public bool NeedsAdmin => false;

    private static readonly HttpClient _httpClient = new HttpClient();

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        if (message.Chat.Type != ChatType.Private)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "⚠️ *Fehler:* Dieser Befehl ist nur in privaten Chats verfügbar.",
                parseMode: ParseMode.Markdown,
                cancellationToken: cancellationToken);
            return;
        }

        var senderId = message.From?.Id;
        var username = message.From?.Username ?? "Unbekannt";
        
        var link = senderId.HasValue ? telegramBotService.Config.TelegramUserLinks?.FirstOrDefault(l => l.TelegramUserId == senderId.Value) : null;
        if (link == null)
        {
            await telegramBotService.SendNotLinkedMessage(message.Chat.Id, cancellationToken);
            return;
        }

        var parts = message.Text?.Split(new[] { ' ' }, 2);
        if (parts == null || parts.Length < 2 || string.IsNullOrWhiteSpace(parts[1]))
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "⚠️ *Verwendung:* `/wunsch <Film oder Serie>`\nBeispiel: `/wunsch Inception`",
                parseMode: ParseMode.Markdown,
                cancellationToken: cancellationToken);
            return;
        }

        var query = parts[1].Trim();
        var apiKey = telegramBotService.Config.TmdbApiKey;

        if (string.IsNullOrWhiteSpace(apiKey))
        {
            // Fallback: Kein TMDB API Key konfiguriert
            await SendDirectWishToAdmins(telegramBotService, query, username, senderId.Value, cancellationToken);
            await botClient.SendMessage(
                message.Chat.Id,
                "✅ Dein Wunsch wurde direkt an die Administratoren weitergeleitet!",
                cancellationToken: cancellationToken);
            return;
        }

        try
        {
            var url = $"https://api.themoviedb.org/3/search/multi?api_key={apiKey}&query={Uri.EscapeDataString(query)}&language=de-DE&page=1";
            var response = await _httpClient.GetAsync(url, cancellationToken);
            response.EnsureSuccessStatusCode();

            var jsonString = await response.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(jsonString);
            var results = doc.RootElement.GetProperty("results");

            if (results.GetArrayLength() == 0)
            {
                await botClient.SendMessage(
                    message.Chat.Id,
                    "❌ Leider konnte ich unter diesem Namen nichts in der TMDB-Datenbank finden. Bitte überprüfe die Schreibweise.",
                    cancellationToken: cancellationToken);
                return;
            }

            var firstHit = results[0];
            var mediaType = firstHit.GetProperty("media_type").GetString();
            if (mediaType != "movie" && mediaType != "tv")
            {
                // Skip person or other types
                await SendDirectWishToAdmins(telegramBotService, query, username, senderId.Value, cancellationToken);
                await botClient.SendMessage(
                    message.Chat.Id,
                    "✅ Dein Wunsch wurde manuell an die Administratoren weitergeleitet!",
                    cancellationToken: cancellationToken);
                return;
            }

            var title = mediaType == "movie" ? firstHit.GetProperty("title").GetString() : firstHit.GetProperty("name").GetString();
            var releaseDateStr = "";
            
            if (mediaType == "movie" && firstHit.TryGetProperty("release_date", out var rd) && !string.IsNullOrEmpty(rd.GetString()))
                releaseDateStr = rd.GetString()!.Substring(0, 4);
            else if (mediaType == "tv" && firstHit.TryGetProperty("first_air_date", out var fad) && !string.IsNullOrEmpty(fad.GetString()))
                releaseDateStr = fad.GetString()!.Substring(0, 4);

            var posterPath = firstHit.TryGetProperty("poster_path", out var pp) ? pp.GetString() : null;
            var overview = firstHit.TryGetProperty("overview", out var ov) ? ov.GetString() : "";
            
            var displayTitle = $"{title} ({releaseDateStr})";
            var typeStr = mediaType == "movie" ? "Film" : "Serie";

            var msgText = $"🎬 *Dein Wunsch:*\n\n*{TelegramMarkdown.Escape(displayTitle)}*\nTyp: {typeStr}\n\n{TelegramMarkdown.Escape(overview?.Length > 200 ? overview.Substring(0, 197) + "..." : overview)}\n\nSoll dieser Wunsch an die Admins gesendet werden?";

            var keyboard = new InlineKeyboardMarkup(new[]
            {
                new[]
                {
                    InlineKeyboardButton.WithCallbackData("✅ Ja, bitte anfragen", $"wishconfirm_{senderId}_{mediaType}_{firstHit.GetProperty("id").GetInt32()}"),
                    InlineKeyboardButton.WithCallbackData("❌ Nein, abbrechen", "wishcancel")
                }
            });

            if (!string.IsNullOrEmpty(posterPath))
            {
                var imageUrl = $"https://image.tmdb.org/t/p/w500{posterPath}";
                await botClient.SendPhoto(
                    message.Chat.Id,
                    global::Telegram.Bot.Types.InputFile.FromUri(imageUrl),
                    caption: msgText,
                    parseMode: ParseMode.Markdown,
                    replyMarkup: keyboard,
                    cancellationToken: cancellationToken);
            }
            else
            {
                await botClient.SendMessage(
                    message.Chat.Id,
                    msgText,
                    parseMode: ParseMode.Markdown,
                    replyMarkup: keyboard,
                    cancellationToken: cancellationToken);
            }
        }
        catch (Exception ex)
        {
            telegramBotService.Logger.LogError(ex, "Fehler bei der TMDB Abfrage für Wunsch: {Query}", query);
            await SendDirectWishToAdmins(telegramBotService, query, username, senderId.Value, cancellationToken);
            await botClient.SendMessage(
                message.Chat.Id,
                "✅ (TMDB nicht erreichbar) Dein Wunsch wurde direkt an die Administratoren weitergeleitet!",
                cancellationToken: cancellationToken);
        }
    }

    private async Task SendDirectWishToAdmins(ITelegramBotService telegramBotService, string query, string username, long senderId, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var admins = telegramBotService.Config.AdminUserNames ?? new System.Collections.Generic.List<string>();
        var userManager = RiNnoFinPlugin.UserManager;
        var adminTelegramIds = new System.Collections.Generic.List<long>();

        foreach (var adminName in admins)
        {
            var user = userManager.Users.FirstOrDefault(u => u.Username.Equals(adminName, StringComparison.OrdinalIgnoreCase));
            if (user != null)
            {
                var adminLink = telegramBotService.Config.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == user.Id);
                if (adminLink != null && adminLink.TelegramUserId != 0)
                {
                    adminTelegramIds.Add(adminLink.TelegramUserId);
                }
            }
        }

        if (adminTelegramIds.Count == 0) return;

        var text = $"🍿 *Neuer Wunsch von @{username}:*\n\n{TelegramMarkdown.Escape(query)}";

        // Generate a random ID for this direct wish
        var wishId = Guid.NewGuid().ToString("N").Substring(0, 8);

        var keyboard = new InlineKeyboardMarkup(new[]
        {
            new[]
            {
                InlineKeyboardButton.WithCallbackData("✅ Genehmigen", $"wishapprove_{senderId}_text_{wishId}"),
                InlineKeyboardButton.WithCallbackData("❌ Ablehnen", $"wishdeny_{senderId}_text_{wishId}")
            }
        });

        foreach (var adminId in adminTelegramIds.Distinct())
        {
            try
            {
                await botClient.SendMessage(
                    chatId: adminId,
                    text: text,
                    parseMode: ParseMode.Markdown,
                    replyMarkup: keyboard,
                    cancellationToken: cancellationToken);
            }
            catch { /* Ignore */ }
        }
    }
}
