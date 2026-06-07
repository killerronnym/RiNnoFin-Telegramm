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
        if (!message.Text!.StartsWith('/'))
        {
            return;
        }

        Logger.LogDebug("Bot Update empfangen Typ: {UpdateType} von UserId: '{FromId}' Text: '{MsgText}'", update.Type, message.From?.Id, message.Text);

        var commandText = GetCommandText(message.Text, BotInfo.Username);
        if (commandText == null)
        {
            return;
        }

        await FindAndExecuteCommand(message, commandText, cancellationToken);
    }

    private async Task HandleCallbackQuery(Update update, CancellationToken cancellationToken)
    {
        var callbackQuery = update.CallbackQuery!;
        var botClient = BotClientWrapper.Client;
        if (botClient == null) return;

        try
        {
            var data = callbackQuery.Data ?? string.Empty;
            
            // Check if it is a newsletter setting update
            if (data.StartsWith("newsletter_"))
            {
                var action = data.Replace("newsletter_", "");
                var userId = callbackQuery.From.Id;
                
                var link = Config.TelegramUserLinks.FirstOrDefault(l => l.TelegramUserId == userId);
                if (link == null)
                {
                    await botClient.AnswerCallbackQuery(callbackQuery.Id, "Du bist nicht verknüpft. Bitte logge dich erst über Jellyfin mit Telegram ein.", showAlert: true, cancellationToken: cancellationToken);
                    return;
                }

                if (action == "subscribe")
                {
                    link.SubscribedToNewsletter = true;
                    RiNnoFinPlugin.Instance!.SaveConfiguration(Config);
                    await botClient.AnswerCallbackQuery(callbackQuery.Id, "Newsletter abonniert! 🔔", cancellationToken: cancellationToken);
                    
                    var newText = "📰 *RiNnoFin Newsletter-Einstellungen*\n\nStatus: *Abonniert* 🔔\n\nDu erhältst Benachrichtigungen bei neuen Filmen, Serien und Musik.";
                    await botClient.EditMessageText(
                        callbackQuery.Message!.Chat.Id,
                        callbackQuery.Message.MessageId,
                        newText,
                        parseMode: ParseMode.Markdown,
                        cancellationToken: cancellationToken);
                }
                else if (action == "unsubscribe")
                {
                    link.SubscribedToNewsletter = false;
                    RiNnoFinPlugin.Instance!.SaveConfiguration(Config);
                    await botClient.AnswerCallbackQuery(callbackQuery.Id, "Newsletter deabonniert! 🔕", cancellationToken: cancellationToken);
                    
                    var newText = "📰 *RiNnoFin Newsletter-Einstellungen*\n\nStatus: *Deaktiviert* 🔕\n\nDu erhältst keine Medienbenachrichtigungen mehr.";
                    await botClient.EditMessageText(
                        callbackQuery.Message!.Chat.Id,
                        callbackQuery.Message.MessageId,
                        newText,
                        parseMode: ParseMode.Markdown,
                        cancellationToken: cancellationToken);
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
            var isAdmin = message.From?.Username != null && Config.AdminUserNames.Contains(message.From.Username);

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
}
