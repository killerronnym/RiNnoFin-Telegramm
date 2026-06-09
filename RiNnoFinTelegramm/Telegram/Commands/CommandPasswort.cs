using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Cryptography;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandPasswort : ICommandBase
{
    public string Command => "passwort";

    public bool NeedsAdmin => false;

    public async Task Execute(ITelegramBotService telegramBotService,
        Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        // Passwortänderung ist nur in einem privaten Chat zulässig
        if (message.Chat.Type != ChatType.Private)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "❌ Aus Sicherheitsgründen kann dieser Befehl nur in einem privaten Chat mit dem Bot verwendet werden.",
                cancellationToken: cancellationToken);
            return;
        }

        var senderId = message.From?.Id;
        if (senderId == null) return;

        // Prüfen, ob das Telegram-Konto verknüpft ist
        var link = telegramBotService.Config.TelegramUserLinks.FirstOrDefault(l => l.TelegramUserId == senderId.Value);
        if (link == null)
        {
            await telegramBotService.SendNotLinkedMessage(message.Chat.Id, cancellationToken);
            return;
        }

        var config = RiNnoFinPlugin.Instance?.Configuration;
        string email = "Nicht in JFA-Go hinterlegt oder JFA-Go nicht konfiguriert";

        if (config != null && !string.IsNullOrWhiteSpace(config.JfaGoUrl) && !string.IsNullOrWhiteSpace(config.JfaGoUsername))
        {
            try
            {
                var jfaGoUrl = config.JfaGoUrl.TrimEnd('/');
                using var httpClient = new System.Net.Http.HttpClient();
                
                var loginRequest = new System.Net.Http.HttpRequestMessage(System.Net.Http.HttpMethod.Get, $"{jfaGoUrl}/token/login");
                var authBytes = System.Text.Encoding.UTF8.GetBytes($"{config.JfaGoUsername}:{config.JfaGoPassword ?? ""}");
                loginRequest.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(authBytes));
                
                var loginResponse = await httpClient.SendAsync(loginRequest, cancellationToken);
                if (loginResponse.IsSuccessStatusCode)
                {
                    var loginResponseContent = await loginResponse.Content.ReadAsStringAsync(cancellationToken);
                    string? token = null;
                    try
                    {
                        var doc = System.Text.Json.JsonDocument.Parse(loginResponseContent);
                        if (doc.RootElement.TryGetProperty("token", out var tokenProp))
                            token = tokenProp.GetString();
                    }
                    catch { }

                    if (!string.IsNullOrEmpty(token))
                    {
                        var usersReq = new System.Net.Http.HttpRequestMessage(System.Net.Http.HttpMethod.Get, $"{jfaGoUrl}/users");
                        usersReq.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", token);
                        var usersRes = await httpClient.SendAsync(usersReq, cancellationToken);
                        if (usersRes.IsSuccessStatusCode)
                        {
                            var usersJson = await usersRes.Content.ReadAsStringAsync(cancellationToken);
                            var usersDoc = System.Text.Json.JsonDocument.Parse(usersJson);
                            
                            foreach (var u in usersDoc.RootElement.EnumerateArray())
                            {
                                if (u.TryGetProperty("name", out var nameProp) && string.Equals(nameProp.GetString(), link.JellyfinUsername, StringComparison.OrdinalIgnoreCase))
                                {
                                    if (u.TryGetProperty("email", out var emailProp) && emailProp.ValueKind == System.Text.Json.JsonValueKind.String)
                                        email = emailProp.GetString() ?? email;
                                    else if (u.TryGetProperty("emailAddress", out var emailAddrProp) && emailAddrProp.ValueKind == System.Text.Json.JsonValueKind.String)
                                        email = emailAddrProp.GetString() ?? email;
                                    else if (u.TryGetProperty("email_address", out var emailAddrProp2) && emailAddrProp2.ValueKind == System.Text.Json.JsonValueKind.String)
                                        email = emailAddrProp2.GetString() ?? email;
                                        
                                    break;
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                telegramBotService.Logger.LogWarning(ex, "Konnte JFA-Go E-Mail für Benutzer {User} nicht abrufen.", link.JellyfinUsername);
            }
        }

        var inlineKeyboard = new global::Telegram.Bot.Types.ReplyMarkups.InlineKeyboardMarkup(new[]
        {
            new []
            {
                global::Telegram.Bot.Types.ReplyMarkups.InlineKeyboardButton.WithCallbackData("Ja", "passwort_confirm_yes"),
                global::Telegram.Bot.Types.ReplyMarkups.InlineKeyboardButton.WithCallbackData("Nein", "passwort_confirm_no"),
            }
        });

        await botClient.SendMessage(
            message.Chat.Id,
            $"Möchten Sie wirklich das Passwort zurücksetzen?\n\n*Jellyfin-Benutzername:* {link.JellyfinUsername}\n*JFA-Go E-Mail:* {email}",
            parseMode: ParseMode.Markdown,
            replyMarkup: inlineKeyboard,
            cancellationToken: cancellationToken);
    }
}

internal class CommandPasswortStep2 : ICommandBase
{
    public string Command => "passwort_step2";
    public bool NeedsAdmin => false;

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var senderId = message.From?.Id;
        if (senderId == null) return;

        var link = telegramBotService.Config.TelegramUserLinks.FirstOrDefault(l => l.TelegramUserId == senderId.Value);
        if (link == null) return;

        var newPassword = message.Text?.Trim();
        if (string.IsNullOrEmpty(newPassword) || newPassword.Length < 4)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "❌ Das Passwort ist zu kurz. Es muss aus Sicherheitsgründen mindestens 4 Zeichen lang sein. Bitte rufe /passwort erneut auf.",
                cancellationToken: cancellationToken);
            return;
        }

        try
        {
            var userManager = telegramBotService.ServiceProvider.GetRequiredService<IUserManager>();
            var cryptoProvider = telegramBotService.ServiceProvider.GetRequiredService<ICryptoProvider>();

            var user = userManager.GetUserByName(link.JellyfinUsername);
            if (user == null)
            {
                await botClient.SendMessage(
                    message.Chat.Id,
                    $"❌ Der verknüpfte Jellyfin-Benutzer '{link.JellyfinUsername}' wurde nicht gefunden.",
                    cancellationToken: cancellationToken);
                return;
            }

            // Neues Passwort hashen und speichern
            user.Password = cryptoProvider.CreatePasswordHash(newPassword).ToString();
            await userManager.UpdateUserAsync(user).ConfigureAwait(false);

            await botClient.SendMessage(
                message.Chat.Id,
                "✅ Das Passwort wurde erfolgreich zurückgesetzt.",
                cancellationToken: cancellationToken);
        }
        catch (Exception ex)
        {
            telegramBotService.Logger.LogError(ex, "Fehler beim Ändern des Passworts für {Username}", link.JellyfinUsername);
            await botClient.SendMessage(
                message.Chat.Id,
                "❌ Bei der Passwortänderung ist ein interner Fehler aufgetreten.",
                cancellationToken: cancellationToken);
        }
    }
}
