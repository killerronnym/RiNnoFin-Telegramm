using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;
using MediaBrowser.Controller.Library;
using MediaBrowser.Controller.Session;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types.ReplyMarkups;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Services
{
    public class TwoFactorAuthService : IHostedService
    {
        private readonly ISessionManager _sessionManager;
        private readonly ILogger<TwoFactorAuthService> _logger;
        private readonly TelegramBotClientWrapper _botWrapper;

        public TwoFactorAuthService(ISessionManager sessionManager, ILogger<TwoFactorAuthService> logger, TelegramBotClientWrapper botWrapper)
        {
            _sessionManager = sessionManager;
            _logger = logger;
            _botWrapper = botWrapper;
        }

        public Task StartAsync(CancellationToken cancellationToken)
        {
            _sessionManager.SessionStarted += OnSessionStarted;
            return Task.CompletedTask;
        }

        public Task StopAsync(CancellationToken cancellationToken)
        {
            _sessionManager.SessionStarted -= OnSessionStarted;
            return Task.CompletedTask;
        }

        private async void OnSessionStarted(object? sender, SessionEventArgs e)
        {
            try
            {
                var session = e.SessionInfo;
                if (session == null || session.UserId == Guid.Empty || string.IsNullOrEmpty(session.DeviceId))
                    return;

                var config = RiNnoFinPlugin.Instance?.Configuration;
                if (config == null) return;

                var link = config.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == session.UserId);
                if (link == null || link.TelegramUserId == 0)
                    return; // No Telegram linked, can't do 2FA

                if (link.AuthorizedDevices.Contains(session.DeviceId))
                {
                    // Device is known
                    return;
                }

                // Device is unknown!
                _logger.LogInformation("Unbekanntes Gerät {DeviceId} von IP {IP} für User {User} erkannt. Sende Telegram 2FA...", session.DeviceId, session.RemoteEndPoint, session.UserName);

                var botClient = _botWrapper.Client;
                if (botClient == null) return;

                var text = $"🚨 *Neuer Login erkannt!*\n\n" +
                           $"👤 *Benutzer:* {session.UserName}\n" +
                           $"📱 *Gerät:* {session.DeviceName} ({session.Client})\n" +
                           $"🌐 *IP-Adresse:* {session.RemoteEndPoint}\n\n" +
                           $"Bist du das? Solange das Gerät nicht autorisiert ist, wird jede Videowiedergabe blockiert.";

                var keyboard = new InlineKeyboardMarkup(new[]
                {
                    new[]
                    {
                        InlineKeyboardButton.WithCallbackData("✅ Autorisieren", $"2fa_auth_{session.UserId}_{session.DeviceId}"),
                        InlineKeyboardButton.WithCallbackData("❌ Sperren & Rauswerfen", $"2fa_block_{session.UserId}_{session.DeviceId}")
                    }
                });

                await botClient.SendMessage(
                    link.TelegramUserId,
                    text,
                    parseMode: global::Telegram.Bot.Types.Enums.ParseMode.Markdown,
                    replyMarkup: keyboard
                );

                // Now hook PlaybackStart to block playback if still not authorized
                _sessionManager.PlaybackStart -= OnPlaybackStart;
                _sessionManager.PlaybackStart += OnPlaybackStart;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Fehler in OnSessionStarted (2FA)");
            }
        }

        private void OnPlaybackStart(object? sender, PlaybackProgressEventArgs e)
        {
            var session = e.Session;
            if (session == null || session.UserId == Guid.Empty || string.IsNullOrEmpty(session.DeviceId))
                return;

            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config == null) return;

            var link = config.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == session.UserId);
            if (link == null || link.TelegramUserId == 0) return;

            if (!link.AuthorizedDevices.Contains(session.DeviceId))
            {
                _logger.LogWarning("Playback auf nicht autorisiertem Gerät {DeviceId} (User {User}) blockiert!", session.DeviceId, session.UserName);

                // Sende Stop-Kommando
                try
                {
                    _sessionManager.SendPlaystateCommand(session.Id, session.Id, new MediaBrowser.Model.Session.PlaystateRequest
                    {
                        Command = MediaBrowser.Model.Session.PlaystateCommand.Stop
                    }, CancellationToken.None);

                    _sessionManager.SendMessageCommand(session.Id, session.Id, new MediaBrowser.Model.Session.MessageCommand
                    {
                        Header = "Sicherheitswarnung",
                        Text = "Bitte autorisiere dieses Gerät erst in deinem Telegram-Bot!",
                        TimeoutMs = 5000
                    }, CancellationToken.None);
                }
                catch { }
            }
        }
    }
}
