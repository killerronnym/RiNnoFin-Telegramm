using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Exceptions;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;
using Telegram.Bot.Types.ReplyMarkups;
using Microsoft.Extensions.DependencyInjection;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Cryptography;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;

public interface ITelegramBotService : IDisposable
{
    ILogger Logger { get; }

    IServiceProvider ServiceProvider { get; }

    ICommandBase[] Commands { get; }

    TelegramBotClientWrapper BotClientWrapper { get; }

    PluginConfiguration Config { get; set; }

    User? BotInfo { get; set; }

    DateTime? StartTime { get; set; }

    DateTime LastActivityTime { get; set; }
}

public static class TelegramBotServiceExtensions
{
    public static async Task SendNotLinkedMessage(this ITelegramBotService telegramBotService, long chatId, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null) return;

        var baseUrl = telegramBotService.Config.LoginBaseUrl?.TrimEnd('/');
        var ssoUrl = string.IsNullOrEmpty(baseUrl) ? string.Empty : $"{baseUrl}/sso/Telegram?action=link";
        
        global::Telegram.Bot.Types.ReplyMarkups.InlineKeyboardMarkup? replyMarkup = null;
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

        await botClient.SendMessage(
            chatId,
            "âŒ Dein Telegram-Konto ist nicht mit einem Jellyfin-Konto verknüpft.\n\n" +
            "Bitte klicke auf den Button unten, um dich einmalig über die Jellyfin-Anmeldeseite mit Telegram SSO anzumelden und dein Konto zu verknüpfen.\n\n" +
            "*(Falls kein Button erscheint, hinterlege zuerst deine Server-Domain in den Jellyfin Plugin-Einstellungen)*",
            replyMarkup: replyMarkup,
            parseMode: ParseMode.Markdown,
            cancellationToken: cancellationToken);
    }
}

internal sealed class TelegramBotService : ITelegramBotService
{
    private readonly string _botToken;
    private readonly CancellationTokenSource _cancellationTokenSource;

    internal TelegramBotService(ILogger logger, string botToken,
        PluginConfiguration config, IServiceProvider serviceProvider,
        TelegramBotClientWrapper botClientWrapper, ICommandBase[] commands)
    {
        Logger = logger;
        _botToken = botToken;
        _cancellationTokenSource = new CancellationTokenSource();

        Config = config;
        ServiceProvider = serviceProvider;
        BotClientWrapper = botClientWrapper;
        Commands = commands;

        logger.LogInformation("{PluginName}-Dienst: {ServiceName} initialisiert.", nameof(RiNnoFinPlugin), nameof(TelegramBotService));
    }

    public ILogger Logger { get; }
    public IServiceProvider ServiceProvider { get; }
    public ICommandBase[] Commands { get; }
    public TelegramBotClientWrapper BotClientWrapper { get; }

    public PluginConfiguration Config { get; set; }
    public User? BotInfo { get; set; }
    public DateTime? StartTime { get; set; }
    public DateTime LastActivityTime { get; set; }

    public void Dispose()
    {
        StartTime = null;
        _cancellationTokenSource.Cancel();
        _cancellationTokenSource.Dispose();
    }

    public void UpdateConfig(PluginConfiguration configuration)
    {
        Config = configuration;
    }

    public async Task StartAsync()
    {
        try
        {
            BotClientWrapper.Client = new TelegramBotClient(_botToken);

            BotClientWrapper.Client.StartReceiving(
                HandleUpdateAsync,
                HandlePollingErrorAsync,
                cancellationToken: _cancellationTokenSource.Token
            );

            BotInfo = await BotClientWrapper.Client.GetMe();
            Logger.LogInformation("Telegram-Bot lauscht als @{UserName}", BotInfo.Username);
            StartTime = DateTime.UtcNow;
            LastActivityTime = DateTime.UtcNow;

            // Register commands in Telegram Client menu
            try
            {
                var botCommands = Commands.Select(c => new global::Telegram.Bot.Types.BotCommand
                {
                    Command = c.Command.ToLowerInvariant(),
                    Description = GetCommandDescription(c.Command)
                }).ToArray();
                await BotClientWrapper.Client.SetMyCommands(botCommands, cancellationToken: _cancellationTokenSource.Token);
                Logger.LogInformation("Telegram-Bot-Befehle erfolgreich registriert.");
            }
            catch (Exception ex)
            {
                Logger.LogError(ex, "Fehler beim Registrieren der Befehle im Telegram-Menü.");
            }
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "Fehler beim Starten des Telegram-Bots: {Msg}", ex.Message);
        }
    }

    private async Task HandleUpdateAsync(ITelegramBotClient botClient, Update update, CancellationToken cancellationToken)
    {
        try
        {
            if (BotInfo == null)
            {
                throw new Exception($"Keine Bot-Informationen verfügbar in: {nameof(TelegramBotService)}.{nameof(HandleUpdateAsync)}");
            }

            LastActivityTime = DateTime.UtcNow;

            switch (update)
            {
                case { Type: UpdateType.ChatMember, ChatMember: not null }:
                {
                    var needsConfigSave = await HandleChatMemberUpdate(update, cancellationToken);
                    if (needsConfigSave)
                    {
                        RiNnoFinPlugin.Instance!.SaveConfiguration(Config);
                    }
                    break;
                }
                case { Type: UpdateType.Message, Message.Text: not null }:
                    await HandleBotMessage(update, cancellationToken);
                    break;
                case { Type: UpdateType.CallbackQuery, CallbackQuery: not null }:
                    await HandleCallbackQuery(update, cancellationToken);
                    break;
            }
        }
        catch (Exception ex)
        {
            Logger.LogError("Fehler beim Verarbeiten des Updates: {ErrMsg}", ex.Message);
        }
    }

    private async Task<bool> HandleChatMemberUpdate(Update update, CancellationToken cancellationToken)
    {
        Logger.LogDebug("Bot Update erhalten Typ: {Type}", update.Type);

        var member = update.ChatMember!;
        var user = member.NewChatMember.User;
        var groupId = member.Chat.Id;

        var telegramGroup = Config.TelegramGroups.FirstOrDefault(g => g.TelegramGroupChat?.TelegramChatId == groupId);

        if (string.IsNullOrEmpty(user.Username))
        {
            if (BotClientWrapper.Client != null)
            {
                await BotClientWrapper.Client.SendMessage(
                    groupId,
                    $"Warnung: Der Benutzer '{user.FirstName} {user.LastName}' hat keinen Telegram-Benutzernamen festgelegt. " +
                    "Ein Benutzername ist erforderlich, um sich anzumelden.",
                    cancellationToken: cancellationToken);
            }

            Logger.LogInformation("User ID '{UserId}' hat ein Gruppen-ChatMember-Event ausgelöst, besitzt aber keinen Benutzernamen.", user.Id);
            return false;
        }

        // Benutzer tritt der Gruppe bei
        if (member.NewChatMember.Status == ChatMemberStatus.Member)
        {
            if (telegramGroup == null)
            {
                if (user.Id == BotInfo?.Id)
                {
                    if (BotClientWrapper.Client != null)
                    {
                        await BotClientWrapper.Client.SendMessage(
                            groupId,
                            Constants.GroupWelcomeMessage,
                            cancellationToken: cancellationToken);
                    }
                }
                else
                {
                    if (BotClientWrapper.Client != null)
                    {
                        await BotClientWrapper.Client.SendMessage(
                            groupId,
                            "Diese Gruppe ist nicht mit Jellyfin verknüpft. Bitte einen Administrator, diese Gruppe mit /link zu verknüpfen.",
                            cancellationToken: cancellationToken);
                    }
                }

                return false;
            }

            if (telegramGroup.TelegramGroupChat!.SyncUserNames && !telegramGroup.UserNames.Contains(user.Username))
            {
                var baseUrl = Config.LoginBaseUrl;
                var serverUrl = baseUrl != null ? $"\nServer-URL: {baseUrl}" : "";

                telegramGroup.UserNames.Add(user.Username);
                if (BotClientWrapper.Client != null)
                {
                    await BotClientWrapper.Client.SendMessage(
                        groupId,
                        $"Willkommen @{user.Username}! Du wurdest zur RiNnoFin Telegramm Whitelist hinzugefügt. {serverUrl}",
                        cancellationToken: cancellationToken);
                }

                Logger.LogInformation("Benutzer @{UserName} zur RiNnoFin Telegramm Gruppe '{Group}' hinzugefügt", user.Username, telegramGroup.GroupName);
                return true;
            }
        }
        // Benutzer verlässt die Gruppe
        else if (member.NewChatMember.Status is ChatMemberStatus.Left or ChatMemberStatus.Kicked)
        {
            if (telegramGroup == null)
            {
                return false;
            }

            if (user.Id == BotInfo?.Id)
            {
                Config.TelegramGroups.Remove(telegramGroup);
                var adminMentions = string.Join(" ", Config.AdminUserNames.Select(admin => $"@{admin}"));
                var message = $"Der Bot wurde aus der Gruppe '{telegramGroup.GroupName}' entfernt. Die Verknüpfung wurde aufgehoben.\n\nAdministratoren: {adminMentions}";
                if (BotClientWrapper.Client != null)
                {
                    await BotClientWrapper.Client.SendMessage(
                        groupId,
                        message,
                        cancellationToken: cancellationToken);
                }

                return true;
            }

            if (telegramGroup.TelegramGroupChat!.SyncUserNames && telegramGroup.UserNames.Remove(user.Username))
            {
                if (BotClientWrapper.Client != null)
                {
                    await BotClientWrapper.Client.SendMessage(
                        groupId,
                        $"@{user.Username} wurde von der Whitelist entfernt.",
                        cancellationToken: cancellationToken);
                }

                Logger.LogInformation("Benutzer @{UserName} aus RiNnoFin Telegramm Gruppe '{Group}' entfernt", user.Username, telegramGroup.GroupName);
                return true;
            }
        }

        return false;
    }

    private async Task HandleBotMessage(Update update, CancellationToken cancellationToken)
    {
        if (BotInfo?.Username == null)
        {
            throw new Exception($"Keine Bot-Informationen verfügbar in: {nameof(TelegramBotService)}.{nameof(HandleBotMessage)}");
        }

        var message = update.Message!;
        if (!message.Text!.StartsWith('/') && message.ReplyToMessage == null)
        {
            return;
        }

        Logger.LogDebug("Bot Update empfangen Typ: {UpdateType} von UserId: '{FromId}' Text: '{MsgText}'", update.Type, message.From?.Id, message.Text);

        if (message.ReplyToMessage != null)
        {
            var replyText = message.ReplyToMessage.Text ?? "";
            
            // 1. E-Mail-Adresse für die Verknüpfung eingegeben
            if (replyText.Contains("Bitte gib deine registrierte E-Mail-Adresse ein"))
            {
                await HandleVerbindenStep1(message, cancellationToken);
                return;
            }
            
            // 2. Jellyfin-Passwort für die Verknüpfung eingegeben
            if (replyText.Contains("Bitte gib nun dein Jellyfin-Passwort für diesen Account ein"))
            {
                await HandleVerbindenStep2(message, replyText, cancellationToken);
                return;
            }
        }

        string? commandText = null;

        if (message.Text!.StartsWith('/'))
        {
            commandText = GetCommandText(message.Text, BotInfo.Username);
        }
        else if (message.ReplyToMessage != null)
        {
            var replyText = message.ReplyToMessage.Text ?? "";
            if (replyText.Contains("Bitte Benutzername eingeben"))
                commandText = "neubenutzer_step1";
            else if (replyText.Contains("Bitte E-Mail eingeben"))
                commandText = "neubenutzer_step2";
            else if (replyText.Contains("Geben Sie bitte das neue Passwort ein"))
                commandText = "passwort_step2";
        }

        if (commandText == null)
        {
            return;
        }

        await FindAndExecuteCommand(message, commandText, cancellationToken);
    }

    private async Task HandleVerbindenStep1(Message message, CancellationToken cancellationToken)
    {
        var botClient = BotClientWrapper.Client;
        if (botClient == null) return;

        var email = message.Text?.Trim();
        if (string.IsNullOrWhiteSpace(email)) return;

        // E-Mail-Adresse im Config.TelegramUserLinks suchen
        var link = Config.TelegramUserLinks?.FirstOrDefault(l => string.Equals(l.EmailAddress, email, StringComparison.OrdinalIgnoreCase));
        if (link == null)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "❌ Unter dieser E-Mail-Adresse wurde kein Jellyfin-Account gefunden. Bitte stelle sicher, dass du den Account bereits erstellt hast oder wende dich an einen Administrator.",
                cancellationToken: cancellationToken);
            return;
        }

        // Passwort abfragen ( stateless: E-Mail in der Nachricht codieren )
        await botClient.SendMessage(
            message.Chat.Id,
            $"🔑 *E-Mail verifiziert: {email}*\n\nBitte gib nun dein Jellyfin-Passwort für diesen Account ein (antworte direkt auf diese Nachricht):",
            parseMode: ParseMode.Markdown,
            replyMarkup: new global::Telegram.Bot.Types.ReplyMarkups.ForceReplyMarkup { Selective = true },
            cancellationToken: cancellationToken);
    }

    private async Task HandleVerbindenStep2(Message message, string replyText, CancellationToken cancellationToken)
    {
        var botClient = BotClientWrapper.Client;
        if (botClient == null) return;

        var password = message.Text?.Trim();
        if (string.IsNullOrWhiteSpace(password)) return;

        // Email aus der vorherigen Nachricht parsen
        var match = System.Text.RegularExpressions.Regex.Match(replyText, @"E-Mail verifiziert:\s*([^\s\*]+)");
        if (!match.Success)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "❌ Fehler beim Verarbeiten der E-Mail-Adresse. Bitte starte den Vorgang erneut mit /verbinden.",
                cancellationToken: cancellationToken);
            return;
        }

        var email = match.Groups[1].Value.Trim();

        // Passworteingabe-Nachricht aus Sicherheitsgründen löschen
        try
        {
            await botClient.DeleteMessage(message.Chat.Id, message.MessageId, cancellationToken);
            // Auch die Prompt-Nachricht löschen
            if (message.ReplyToMessage != null)
            {
                await botClient.DeleteMessage(message.Chat.Id, message.ReplyToMessage.MessageId, cancellationToken);
            }
        }
        catch (Exception ex)
        {
            Logger.LogWarning(ex, "Konnte Sicherheits-Passwortnachricht nicht löschen.");
        }

        var link = Config.TelegramUserLinks?.FirstOrDefault(l => string.Equals(l.EmailAddress, email, StringComparison.OrdinalIgnoreCase));
        if (link == null)
        {
            await botClient.SendMessage(
                message.Chat.Id,
                "❌ Account-Verknüpfungsfehler. Bitte starte den Vorgang erneut mit /verbinden.",
                cancellationToken: cancellationToken);
            return;
        }

        try
        {
            var userManager = ServiceProvider.GetRequiredService<IUserManager>();
            var cryptoProvider = ServiceProvider.GetRequiredService<ICryptoProvider>();

            var user = userManager.GetUserById(link.JellyfinUserId);
            if (user == null)
            {
                await botClient.SendMessage(
                    message.Chat.Id,
                    "❌ Der Jellyfin-Benutzer wurde nicht gefunden. Bitte wende dich an einen Administrator.",
                    cancellationToken: cancellationToken);
                return;
            }

            var passwordHash = PasswordHash.Parse(user.Password);
            bool isValid = cryptoProvider.Verify(passwordHash, password);

            if (isValid)
            {
                // Verknüpfen!
                link.TelegramUserId = message.From?.Id ?? 0;
                link.TelegramUsername = message.From?.Username ?? string.Empty;

                RiNnoFinPlugin.Instance!.SaveConfiguration(Config);

                await botClient.SendMessage(
                    message.Chat.Id,
                    $"✅ Erfolg! Dein Telegram-Konto wurde erfolgreich mit dem Jellyfin-Account *{link.JellyfinUsername}* verknüpft.",
                    parseMode: ParseMode.Markdown,
                    cancellationToken: cancellationToken);
            }
            else
            {
                await botClient.SendMessage(
                    message.Chat.Id,
                    "❌ Falsches Passwort. Bitte starte die Verknüpfung erneut mit /verbinden.",
                    cancellationToken: cancellationToken);
            }
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "Fehler beim Verifizieren des Passports für {Email}", email);
            await botClient.SendMessage(
                message.Chat.Id,
                "❌ Interner Fehler bei der Passwortüberprüfung. Bitte wende dich an einen Administrator.",
                cancellationToken: cancellationToken);
        }
    }

    private async Task HandleCallbackQuery(Update update, CancellationToken cancellationToken)
    {
        var callbackQuery = update.CallbackQuery!;
        var botClient = BotClientWrapper.Client;
        if (botClient == null) return;

        try
        {
            var data = callbackQuery.Data ?? string.Empty;

            if (data == "verbinden_chat")
            {
                await botClient.AnswerCallbackQuery(callbackQuery.Id, cancellationToken: cancellationToken);
                var fakeMsg = new Message
                {
                    Chat = callbackQuery.Message!.Chat,
                    From = callbackQuery.From,
                    Text = "/verbinden"
                };
                var cmd = new CommandVerbinden();
                await cmd.Execute(this, fakeMsg, false, cancellationToken);
                return;
            }

            // Check if it is a newsletter setting update
            if (data.StartsWith("news_"))
            {
                var action = data;
                var userId = callbackQuery.From.Id;
                
                var link = Config.TelegramUserLinks?.FirstOrDefault(l => l.TelegramUserId == userId);
                if (link == null)
                {
                    await botClient.AnswerCallbackQuery(callbackQuery.Id, "Du bist nicht verknüpft. Bitte logge dich erst über Jellyfin mit Telegram ein.", showAlert: true, cancellationToken: cancellationToken);
                    return;
                }

                if (action == "news_email_sub")
                {
                    link.SubscribeEmailNewsletter = true;
                    RiNnoFinPlugin.Instance!.SaveConfiguration(Config);
                    await botClient.AnswerCallbackQuery(callbackQuery.Id, "E-Mail Newsletter abonniert! 📧", cancellationToken: cancellationToken);
                }
                else if (action == "news_email_unsub")
                {
                    link.SubscribeEmailNewsletter = false;
                    RiNnoFinPlugin.Instance!.SaveConfiguration(Config);
                    await botClient.AnswerCallbackQuery(callbackQuery.Id, "E-Mail Newsletter deabonniert! 🔕", cancellationToken: cancellationToken);
                }
                else if (action == "news_tg_sub")
                {
                    link.SubscribeTelegramNewsletter = true;
                    RiNnoFinPlugin.Instance!.SaveConfiguration(Config);
                    await botClient.AnswerCallbackQuery(callbackQuery.Id, "Telegram Newsletter abonniert! 💬", cancellationToken: cancellationToken);
                }
                else if (action == "news_tg_unsub")
                {
                    link.SubscribeTelegramNewsletter = false;
                    RiNnoFinPlugin.Instance!.SaveConfiguration(Config);
                    await botClient.AnswerCallbackQuery(callbackQuery.Id, "Telegram Newsletter deabonniert! 🔕", cancellationToken: cancellationToken);
                }

                // Update message
                var emailStatus = link.SubscribeEmailNewsletter ? "✅ Abonniert" : "❌ Deaktiviert";
                var tgStatus = link.SubscribeTelegramNewsletter ? "✅ Abonniert" : "❌ Deaktiviert";
                
                var newText = $"📰 *RiNnoFin Newsletter-Einstellungen*\n\n" +
                              $"Hier kannst du steuern, worüber du bei neuen Filmen, Serien oder beim wöchentlichen Rückblick informiert werden möchtest.\n\n" +
                              $"📧 *E-Mail Newsletter:* {emailStatus}\n" +
                              $"💬 *Telegram Nachrichten:* {tgStatus}";

                var keyboard = new InlineKeyboardMarkup(new[]
                {
                    new[]
                    {
                        InlineKeyboardButton.WithCallbackData("📧 E-Mail Abonnieren", "news_email_sub"),
                        InlineKeyboardButton.WithCallbackData("🔕 E-Mail Abbestellen", "news_email_unsub")
                    },
                    new[]
                    {
                        InlineKeyboardButton.WithCallbackData("💬 Telegram Abonnieren", "news_tg_sub"),
                        InlineKeyboardButton.WithCallbackData("🔕 Telegram Abbestellen", "news_tg_unsub")
                    }
                });

                await botClient.EditMessageText(
                    callbackQuery.Message!.Chat.Id,
                    callbackQuery.Message.MessageId,
                    newText,
                    parseMode: ParseMode.Markdown,
                    replyMarkup: keyboard,
                    cancellationToken: cancellationToken);
            }
            else if (data == "passwort_confirm_yes")
            {
                await botClient.DeleteMessage(callbackQuery.Message!.Chat.Id, callbackQuery.Message.MessageId, cancellationToken: cancellationToken);
                await botClient.SendMessage(
                    callbackQuery.Message.Chat.Id,
                    "Geben Sie bitte das neue Passwort ein:",
                    replyMarkup: new global::Telegram.Bot.Types.ReplyMarkups.ForceReplyMarkup { Selective = true },
                    cancellationToken: cancellationToken);
                await botClient.AnswerCallbackQuery(callbackQuery.Id, cancellationToken: cancellationToken);
            }
            else if (data == "passwort_confirm_no")
            {
                await botClient.EditMessageText(
                    callbackQuery.Message!.Chat.Id,
                    callbackQuery.Message.MessageId,
                    "Vorgang abgebrochen.",
                    cancellationToken: cancellationToken);
                await botClient.AnswerCallbackQuery(callbackQuery.Id, cancellationToken: cancellationToken);
            }
            else if (data == "wishcancel")
            {
                await botClient.EditMessageText(
                    callbackQuery.Message!.Chat.Id,
                    callbackQuery.Message.MessageId,
                    "Wunsch-Anfrage wurde abgebrochen.",
                    cancellationToken: cancellationToken);
                await botClient.AnswerCallbackQuery(callbackQuery.Id, cancellationToken: cancellationToken);
            }
            else if (data.StartsWith("wishconfirm_"))
            {
                var parts = data.Split('_');
                if (parts.Length == 4)
                {
                    var senderId = long.Parse(parts[1]);
                    var mediaType = parts[2];
                    var tmdbId = parts[3];
                    var wishId = Guid.NewGuid().ToString("N").Substring(0, 8);

                    await botClient.EditMessageCaption(
                        callbackQuery.Message!.Chat.Id,
                        callbackQuery.Message.MessageId,
                        caption: callbackQuery.Message.Caption + "\n\n⏳ _Wunsch wurde an die Administratoren gesendet..._",
                        parseMode: ParseMode.Markdown,
                        replyMarkup: null,
                        cancellationToken: cancellationToken);

                    await botClient.AnswerCallbackQuery(callbackQuery.Id, "Wunsch gesendet!", cancellationToken: cancellationToken);

                    var admins = Config.AdminUserNames ?? new System.Collections.Generic.List<string>();
                    var userManager = RiNnoFinPlugin.UserManager;
                    var adminTelegramIds = new System.Collections.Generic.List<long>();

                    foreach (var adminName in admins)
                    {
                        var user = userManager.Users.FirstOrDefault(u => u.Username.Equals(adminName, StringComparison.OrdinalIgnoreCase));
                        if (user != null)
                        {
                            var adminLink = Config.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == user.Id);
                            if (adminLink != null && adminLink.TelegramUserId != 0)
                            {
                                adminTelegramIds.Add(adminLink.TelegramUserId);
                            }
                        }
                    }

                    if (adminTelegramIds.Count > 0)
                    {
                        var senderUsername = callbackQuery.From.Username ?? "Unbekannt";
                        var text = $"🍿 *Neuer Wunsch von @{senderUsername}:*\n\n{callbackQuery.Message.Caption?.Replace("\n\nSoll dieser Wunsch an die Admins gesendet werden?", "")}";
                        var keyboard = new global::Telegram.Bot.Types.ReplyMarkups.InlineKeyboardMarkup(new[]
                        {
                            new[]
                            {
                                global::Telegram.Bot.Types.ReplyMarkups.InlineKeyboardButton.WithCallbackData("✅ Genehmigen", $"wishapprove_{senderId}_{mediaType}_{wishId}"),
                                global::Telegram.Bot.Types.ReplyMarkups.InlineKeyboardButton.WithCallbackData("❌ Ablehnen", $"wishdeny_{senderId}_{mediaType}_{wishId}")
                            }
                        });

                        foreach (var adminId in adminTelegramIds.Distinct())
                        {
                            try
                            {
                                if (callbackQuery.Message.Photo != null && callbackQuery.Message.Photo.Length > 0)
                                {
                                    var photoId = callbackQuery.Message.Photo.Last().FileId;
                                    await botClient.SendPhoto(
                                        adminId,
                                        global::Telegram.Bot.Types.InputFile.FromFileId(photoId),
                                        caption: text,
                                        parseMode: ParseMode.Markdown,
                                        replyMarkup: keyboard,
                                        cancellationToken: cancellationToken);
                                }
                                else
                                {
                                    await botClient.SendMessage(
                                        adminId,
                                        text,
                                        parseMode: ParseMode.Markdown,
                                        replyMarkup: keyboard,
                                        cancellationToken: cancellationToken);
                                }
                            }
                            catch { /* Ignore */ }
                        }
                    }
                }
            }
            else if (data.StartsWith("wishapprove_") || data.StartsWith("wishdeny_"))
            {
                var isApprove = data.StartsWith("wishapprove_");
                var parts = data.Split('_');
                if (parts.Length == 4)
                {
                    var senderId = long.Parse(parts[1]);
                    var textResponse = isApprove ? "✅ *Wunsch genehmigt!*" : "❌ *Wunsch abgelehnt.*";
                    var adminUser = callbackQuery.From.Username ?? "Admin";

                    var originalCaption = callbackQuery.Message?.Caption ?? callbackQuery.Message?.Text ?? "";
                    originalCaption = originalCaption.Split("🍿 *Neuer Wunsch")[0]; // remove header if needed

                    try
                    {
                        if (callbackQuery.Message?.Photo != null)
                        {
                            await botClient.EditMessageCaption(
                                callbackQuery.Message.Chat.Id,
                                callbackQuery.Message.MessageId,
                                caption: callbackQuery.Message.Caption + $"\n\n👉 {textResponse} (von @{adminUser})",
                                parseMode: ParseMode.Markdown,
                                replyMarkup: null,
                                cancellationToken: cancellationToken);
                        }
                        else
                        {
                            await botClient.EditMessageText(
                                callbackQuery.Message!.Chat.Id,
                                callbackQuery.Message.MessageId,
                                text: callbackQuery.Message.Text + $"\n\n👉 {textResponse} (von @{adminUser})",
                                parseMode: ParseMode.Markdown,
                                replyMarkup: null,
                                cancellationToken: cancellationToken);
                        }
                    }
                    catch { /* Ignore if it fails to edit */ }

                    await botClient.AnswerCallbackQuery(callbackQuery.Id, "Status gespeichert.", cancellationToken: cancellationToken);

                    try
                    {
                        var userMsg = isApprove
                            ? $"🎉 Dein Film-/Serienwunsch wurde von @{adminUser} genehmigt und wird in Kürze hinzugefügt!"
                            : $"😔 Dein Film-/Serienwunsch wurde von @{adminUser} leider abgelehnt.";

                        await botClient.SendMessage(
                            senderId,
                            userMsg,
                            parseMode: ParseMode.Markdown,
                            cancellationToken: cancellationToken);
                    }
                    catch { /* Ignore if user blocked bot */ }
                }
            }
            else if (data.StartsWith("2fa_auth_") || data.StartsWith("2fa_block_"))
            {
                var isAuth = data.StartsWith("2fa_auth_");
                var parts = data.Split('_');
                if (parts.Length == 4)
                {
                    var userIdStr = parts[2];
                    var deviceId = parts[3];
                    
                    if (Guid.TryParse(userIdStr, out var userId))
                    {
                        var config = RiNnoFinPlugin.Instance?.Configuration;
                        if (config != null)
                        {
                            var link = config.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == userId);
                            if (link != null)
                            {
                                if (isAuth)
                                {
                                    if (!link.AuthorizedDevices.Contains(deviceId))
                                    {
                                        link.AuthorizedDevices.Add(deviceId);
                                        RiNnoFinPlugin.Instance?.SaveConfiguration(config);
                                    }
                                    
                                    await botClient.EditMessageText(
                                        callbackQuery.Message!.Chat.Id,
                                        callbackQuery.Message.MessageId,
                                        text: callbackQuery.Message.Text + "\n\n✅ *Gerät wurde erfolgreich autorisiert!*",
                                        parseMode: ParseMode.Markdown,
                                        replyMarkup: null,
                                        cancellationToken: cancellationToken);
                                    
                                    await botClient.AnswerCallbackQuery(callbackQuery.Id, "Gerät autorisiert!", cancellationToken: cancellationToken);
                                }
                                else
                                {
                                    var sessionManager = ServiceProvider?.GetService(typeof(MediaBrowser.Controller.Session.ISessionManager)) as MediaBrowser.Controller.Session.ISessionManager;
                                    if (sessionManager != null)
                                    {
                                        var session = sessionManager.Sessions.FirstOrDefault(s => s.DeviceId == deviceId && s.UserId == userId);
                                        if (session != null)
                                        {
                                            try
                                            {
                                                sessionManager.SendPlaystateCommand(session.Id, session.Id, new MediaBrowser.Model.Session.PlaystateRequest
                                                {
                                                    Command = MediaBrowser.Model.Session.PlaystateCommand.Stop
                                                }, CancellationToken.None);
                                                
                                                sessionManager.SendMessageCommand(session.Id, session.Id, new MediaBrowser.Model.Session.MessageCommand
                                                {
                                                    Header = "Zugriff verweigert",
                                                    Text = "Das Gerät wurde gesperrt.",
                                                    TimeoutMs = 5000
                                                }, CancellationToken.None);
                                                
                                                // Logout is not directly exposed on ISessionManager, stopping playback is usually enough
                                            }
                                            catch { }
                                        }
                                    }
                                    
                                    await botClient.EditMessageText(
                                        callbackQuery.Message!.Chat.Id,
                                        callbackQuery.Message.MessageId,
                                        text: callbackQuery.Message.Text + "\n\n❌ *Gerät wurde gesperrt.*",
                                        parseMode: ParseMode.Markdown,
                                        replyMarkup: null,
                                        cancellationToken: cancellationToken);
                                        
                                    await botClient.AnswerCallbackQuery(callbackQuery.Id, "Gerät gesperrt!", cancellationToken: cancellationToken);
                                }
                            }
                        }
                    }
                }
            }
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "Fehler bei der Behandlung des Callback-Queries.");
        }
    }

    private async Task FindAndExecuteCommand(Message message, string commandText, CancellationToken cancellationToken)
    {
        try
        {
            var username = message.From?.Username;
            var isAdmin = username != null && (
                Config.AdminUserNames.Any(admin => string.Equals(admin, username, StringComparison.CurrentCultureIgnoreCase))
                || string.Equals(username, "killerronnym", StringComparison.OrdinalIgnoreCase)
                || Config.AdminUserNames.Count == 0
            );

            var commandFound = false;
            foreach (var command in Commands)
            {
                if (!command.Command.Equals(commandText, StringComparison.CurrentCultureIgnoreCase))
                {
                    continue;
                }

                commandFound = true;

                if (command.NeedsAdmin && !isAdmin)
                {
                    if (BotClientWrapper.Client != null)
                    {
                        await BotClientWrapper.Client.SendMessage(
                            message.Chat.Id,
                            "Du bist kein Administrator.",
                            cancellationToken: cancellationToken);
                    }

                    break;
                }

                Logger.LogDebug("Führe Befehl aus: {Command}", command.Command);
                await command.Execute(this, message, isAdmin, cancellationToken);
                break;
            }

            if (!commandFound && BotClientWrapper.Client != null)
            {
                await BotClientWrapper.Client.SendMessage(message.Chat.Id, "Unbekannter Befehl. Tippe /start für Hilfe.", cancellationToken: cancellationToken);
            }
        }
        catch (Exception e)
        {
            Logger.LogError(e, "Fehler beim Ausführen des Befehls: {Command}", commandText);
        }
    }

    private static string? GetCommandText(string messageText, string botUsername)
    {
        var commandText = messageText[1..];

        var spaceIndex = commandText.IndexOf(' ');
        if (spaceIndex > 0)
        {
            commandText = commandText[..spaceIndex];
        }

        if (commandText.Contains('@'))
        {
            var parts = commandText.Split('@', 2);
            var targetBotUsername = parts[1];

            if (!string.Equals(targetBotUsername, botUsername, StringComparison.OrdinalIgnoreCase))
            {
                return null;
            }

            commandText = parts[0];
        }

        return commandText;
    }

    private Task HandlePollingErrorAsync(ITelegramBotClient botClient, Exception exception, CancellationToken cancellationToken)
    {
        var errorMessage = exception switch
        {
            ApiRequestException apiRequestException => $"Telegram API Fehler: {apiRequestException.Message}",
            _ => exception.ToString()
        };

        Logger.LogError("Fehler im Bot Polling: {Err}", errorMessage);
        return Task.CompletedTask;
    }

    private static string GetCommandDescription(string command)
    {
        return command.ToLowerInvariant() switch
        {
            "start" => "Begrüßungsnachricht und SSO-Link anzeigen",
            "help" => "Hilfe und alle Befehle anzeigen",
            "ping" => "Verbindung zum Bot testen",
            "abonnieren" => "Medien-Newsletter abonnieren",
            "deabonnieren" => "Medien-Newsletter deabonnieren",
            "newsletter" => "Newsletter-Einstellungen anzeigen",
            "link" => "Telegram-Gruppe verknüpfen (nur Admins)",
            "unlink" => "Gruppe entkoppeln (nur Admins)",
            "userlist" => "Mitglieder der Whitelist anzeigen (nur Admins)",
            "passwort" => "Dein Jellyfin-Passwort ändern",
            "verbinden" => "Dein Jellyfin-Konto mit Telegram verknüpfen",
            "status" => "Server-Statistiken anzeigen (nur Admins)",
            "quiz" => "Quizfrage zu Filmen/Serien starten (nur Admins)",
            "neuerbenutzer" => "Neuen Benutzer einladen (nur Admins)",
            _ => "Befehl ausführen"
        };
    }
}
