using System;
using System.Collections.Generic;
using System.Net.Mime;
using System.Threading;
using System.Threading.Tasks;
using System.Linq;
using Jellyfin.Plugin.RiNnoFinTelegramm.Classes;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;
using MediaBrowser.Controller.Providers;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using Telegram.Bot;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Controller;

[ApiController]
[Route("api/{Controller}")]
[Authorize(Policy = "RequiresElevation")]
public class RiNnoFinConfigController : ControllerBase
{
    private readonly IProviderManager _providerManager;
    private readonly RequestService _requestService;
    private readonly TelegramBotClientWrapper _botClientWrapper;
    private readonly ILogger<RiNnoFinConfigController> _logger;

    public RiNnoFinConfigController(
        RequestService requestService,
        IProviderManager providerManager,
        TelegramBotClientWrapper botClientWrapper,
        ILogger<RiNnoFinConfigController> _loggerVal)
    {
        _requestService = requestService ?? throw new ArgumentNullException(nameof(requestService));
        _providerManager = providerManager ?? throw new ArgumentNullException(nameof(providerManager));
        _botClientWrapper = botClientWrapper ?? throw new ArgumentNullException(nameof(botClientWrapper));
        _logger = _loggerVal ?? throw new ArgumentNullException(nameof(_loggerVal));
    }

    [HttpPost(nameof(TestBotToken))]
    [Produces(MediaTypeNames.Application.Json)]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<ActionResult<ValidateBotTokenResponse>> TestBotToken([FromBody] ValidateBotTokenRequest request)
    {
        try
        {
            var botClient = new TelegramBotClient(request.Token);
            using var ct = new CancellationTokenSource(TimeSpan.FromMilliseconds(10000));
            var botInfo = await botClient.GetMe(ct.Token);

            bool messageSent = false;
            
            // Versuche an Administratoren zu senden, die bereits mit dem Bot interagiert haben
            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config != null && config.AdminUserNames.Count > 0 && config.TelegramUserLinks.Count > 0)
            {
                var adminUsernamesLower = config.AdminUserNames.Select(u => u.ToLowerInvariant()).ToList();
                var adminLinks = config.TelegramUserLinks
                    .Where(l => adminUsernamesLower.Contains(l.TelegramUsername.ToLowerInvariant()))
                    .ToList();

                foreach (var link in adminLinks)
                {
                    try
                    {
                        await botClient.SendMessage(
                            link.TelegramUserId,
                            "✅ *Test erfolgreich!*\nDein Jellyfin-Server hat den Bot-Token erfolgreich überprüft und sich mit Telegram verbunden.",
                            global::Telegram.Bot.Types.Enums.ParseMode.Markdown,
                            cancellationToken: ct.Token
                        );
                        messageSent = true;
                    }
                    catch
                    {
                        // Ignore send errors for individuals
                    }
                }
            }

            return Ok(new ValidateBotTokenResponse { Ok = true, BotUsername = botInfo.Username!, AdminMessageSent = messageSent });
        }
        catch (Exception)
        {
            return StatusCode(500, new ValidateBotTokenResponse { ErrorMessage = "Ungültiger Token oder Verbindungsfehler" });
        }
    }

    [HttpGet(nameof(GetRequests))]
    [Produces(MediaTypeNames.Application.Json)]
    [ProducesResponseType(StatusCodes.Status200OK)]
    public async Task<ActionResult<List<MediaRequest>>> GetRequests(CancellationToken cancellationToken)
    {
        var requests = await _requestService.GetRequestsAsync(cancellationToken).ConfigureAwait(false);
        return Ok(requests);
    }

    [HttpPost(nameof(SetRequests))]
    [Produces(MediaTypeNames.Application.Json)]
    [ProducesResponseType(StatusCodes.Status200OK)]
    public async Task<IActionResult> SetRequests([FromBody] List<MediaRequest> requests, CancellationToken cancellationToken)
    {
        await _requestService.SetRequestsAsync(requests, cancellationToken).ConfigureAwait(false);
        return Ok();
    }

    [HttpPost(nameof(AddRequest))]
    [Produces(MediaTypeNames.Application.Json)]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<ActionResult<MediaRequest>> AddRequest([FromBody] AddRequestRequest? request, CancellationToken cancellationToken)
    {
        if (request == null || string.IsNullOrWhiteSpace(request.ImdbId))
        {
            return BadRequest();
        }

        var imdbId = request.ImdbId.Trim();

        var (title, year, found) = await MetadataResolver
            .FindRemoteMetadataAsync(_providerManager, imdbId, cancellationToken)
            .ConfigureAwait(false);

        if (!found)
        {
            return NotFound();
        }

        var mediaRequest = new MediaRequest
        {
            ItemId = Guid.Empty,
            ImdbId = imdbId,
            Title = title,
            Year = year,
            UserId = "Manual",
            UserDisplayName = "Admin",
            RequestedAtUtc = DateTime.UtcNow
        };

        var result = await _requestService
            .TryAddRequestAsync(mediaRequest, 0, cancellationToken)
            .ConfigureAwait(false);

        return result switch
        {
            RequestAddResult.Duplicate => Conflict(),
            RequestAddResult.Added => Ok(mediaRequest),
            RequestAddResult.Removed => Ok(mediaRequest),
            _ => StatusCode(StatusCodes.Status500InternalServerError)
        };
    }

    [HttpDelete(nameof(RemoveRequest) + "/{imdbId}")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    public async Task<IActionResult> RemoveRequest(string imdbId, CancellationToken cancellationToken)
    {
        await _requestService.RemoveRequestAsync(imdbId, cancellationToken).ConfigureAwait(false);
        return Ok();
    }

    [HttpPost("TriggerQuiz/{groupName}")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> TriggerQuiz(string groupName, CancellationToken cancellationToken)
    {
        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null)
        {
            return BadRequest("Configuration not found.");
        }

        var group = config.TelegramGroups.FirstOrDefault(g => string.Equals(g.GroupName, groupName, StringComparison.OrdinalIgnoreCase));
        if (group == null)
        {
            return BadRequest("Group not found.");
        }

        if (group.TelegramGroupChat == null || group.TelegramGroupChat.TelegramChatId == 0)
        {
            return BadRequest("Gruppe ist nicht mit Telegram verknüpft.");
        }

        var botClient = _botClientWrapper.Client;
        if (botClient == null)
        {
            return BadRequest("Telegram Bot ist nicht aktiv.");
        }

        // Topic ID ist optional – 0 oder null bedeutet: kein Topic (Hauptchat)
        int? quizThreadId = (group.TelegramGroupChat.QuizTopicId ?? 0) > 0
            ? group.TelegramGroupChat.QuizTopicId
            : null;

        try
        {
            var success = await QuizHelper.SendQuizQuestionAsync(
                botClient,
                group.TelegramGroupChat.TelegramChatId,
                quizThreadId,
                _logger,
                cancellationToken
            );

            if (success)
                return Ok(new { message = "Quizfrage erfolgreich gesendet!" });
            else
                return StatusCode(StatusCodes.Status500InternalServerError, new { message = "Keine Medien in der Bibliothek gefunden." });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Senden der Quizfrage.");
            return StatusCode(StatusCodes.Status500InternalServerError, new { message = ex.Message });
        }
    }

    [HttpPost("TestSmtp")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> TestSmtp(
        [FromBody] TestSmtpRequest request,
        CancellationToken cancellationToken)
    {
        try
        {
            var emailService = new EmailService(_logger);
            
            // Erstelle eine temporäre Konfiguration für den Test
            var tempConfig = new PluginConfiguration
            {
                EnableEmail = true,
                SmtpServer = request.SmtpServer,
                SmtpPort = request.SmtpPort,
                SmtpUsername = request.SmtpUsername,
                SmtpPassword = request.SmtpPassword,
                EmailSenderAddress = request.EmailSenderAddress,
                EmailSenderName = request.EmailSenderName,
                SmtpUseSsl = request.SmtpUseSsl
            };

            string htmlBody = $@"
                <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
                        <h2 style='color: #2c3e50;'>✅ Erfolgreiche Test-Verbindung</h2>
                        <p>Hallo Admin,</p>
                        <p>Dein E-Mail Server (<strong>{request.SmtpServer}</strong>) funktioniert einwandfrei!</p>
                        <p>Das RiNnoFin Telegramm-Plugin kann nun automatisch Einladungen und Passwort-Reset-Links an deine Benutzer verschicken.</p>
                        <br/>
                        <p style='color: #7f8c8d; font-size: 12px;'>Diese E-Mail wurde automatisch generiert.</p>
                    </div>
                </div>";

            // Sende Test-E-Mail an die Absender-Adresse selbst
            await emailService.SendEmailAsync(tempConfig, request.SmtpUsername, "RiNnoFin Media - E-Mail Test erfolgreich! 🎉", htmlBody);

            return Ok(new { message = "E-Mail erfolgreich versendet!" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Senden der Test-E-Mail.");
            return StatusCode(StatusCodes.Status500InternalServerError, new { message = ex.Message });
        }
    }

    [AllowAnonymous]
    [HttpPost("AcceptInvite")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> AcceptInvite(
        [FromServices] MediaBrowser.Controller.Library.IUserManager userManager,
        [FromServices] MediaBrowser.Model.Cryptography.ICryptoProvider cryptoProvider,
        [FromServices] EmailService emailService,
        [FromBody] AcceptInviteRequest request,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(request.Token) || string.IsNullOrWhiteSpace(request.Username) || string.IsNullOrWhiteSpace(request.Password))
        {
            return BadRequest(new { message = "Alle Felder müssen ausgefüllt sein." });
        }

        if (!Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands.InviteTokenManager.ActiveInvites.TryRemove(request.Token, out var email))
        {
            return BadRequest(new { message = "Ungültiger oder abgelaufener Einladungslink." });
        }

        try
        {
            // Create user
            var user = await userManager.CreateUserAsync(request.Username).ConfigureAwait(false);
            
            // Set password
            user.Password = cryptoProvider.CreatePasswordHash(request.Password).ToString();
            await userManager.UpdateUserAsync(user).ConfigureAwait(false);

            // Speichern der E-Mail im Plugin-Config (damit wir wissen, wem dieser Account gehört)
            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config != null)
            {
                var existingLink = config.TelegramUserLinks.FirstOrDefault(l => l.JellyfinUserId == user.Id);
                if (existingLink != null)
                {
                    existingLink.EmailAddress = email;
                }
                else
                {
                    config.TelegramUserLinks.Add(new TelegramUserLink
                    {
                        JellyfinUserId = user.Id,
                        JellyfinUsername = user.Username,
                        EmailAddress = email
                    });
                }
                RiNnoFinPlugin.Instance?.UpdateConfiguration(config);

                // Send Welcome Email
                string htmlBody = $@"
                    <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                        <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                            <h2 style='color: #2563eb;'>Willkommen an Bord! 🐧🎬</h2>
                            <p>Hallo <strong>{user.Username}</strong>,</p>
                            <p>Dein Account bei <strong>RiNnoFin Media</strong> wurde erfolgreich erstellt.</p>
                            <p>Du kannst dich ab sofort mit deinem gewählten Passwort auf all deinen Geräten einloggen.</p>
                            <br/>
                            <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Viel Spaß beim Streamen! 🍿 Dein RiNnoFin-Team</p>
                        </div>
                    </div>";

                await emailService.SendEmailAsync(config, email, "Willkommen bei RiNnoFin Media! 🍿", htmlBody);
            }

            return Ok(new { message = "Account erfolgreich erstellt!" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Erstellen des Accounts für Einladung.");
            return StatusCode(StatusCodes.Status500InternalServerError, new { message = "Fehler beim Erstellen des Accounts: " + ex.Message });
        }
    }
    [AllowAnonymous]
    [HttpPost("RequestPasswordReset")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> RequestPasswordReset(
        [FromServices] EmailService emailService,
        [FromBody] RequestPasswordResetRequest request,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(request.Email))
        {
            return BadRequest(new { message = "E-Mail darf nicht leer sein." });
        }

        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null || !config.EnableEmail)
        {
            return StatusCode(StatusCodes.Status500InternalServerError, new { message = "E-Mail System ist deaktiviert." });
        }

        // Suche den User anhand der E-Mail
        var userLink = config.TelegramUserLinks.FirstOrDefault(l => string.Equals(l.EmailAddress, request.Email, StringComparison.OrdinalIgnoreCase));
        
        // Aus Sicherheitsgründen immer OK zurückgeben, auch wenn E-Mail nicht existiert
        if (userLink == null || userLink.JellyfinUserId == Guid.Empty)
        {
            return Ok();
        }

        try
        {
            var token = Guid.NewGuid().ToString("N");
            ResetTokenManager.ActiveResetTokens[token] = userLink.JellyfinUserId;

            var baseUrl = config.LoginBaseUrl?.TrimEnd('/') ?? "http://localhost:8096";
            var resetLink = $"{baseUrl}/sso/Telegram/reset?token={token}";

            string htmlBody = $@"
                <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                        <h2 style='color: #2563eb;'>Passwort zurücksetzen 🔑</h2>
                        <p>Hallo <strong>{userLink.JellyfinUsername}</strong>,</p>
                        <p>Jemand (vermutlich du) hat das Zurücksetzen des Passworts für deinen RiNnoFin-Account angefordert.</p>
                        <p>Klicke auf den untenstehenden Button, um ein neues Passwort festzulegen:</p>
                        <div style='text-align: center; margin: 30px 0;'>
                            <a href='{resetLink}' style='background-color: #2563eb; color: #fff; padding: 14px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;'>Passwort zurücksetzen</a>
                        </div>
                        <p style='color: #6b7280; font-size: 13px;'>Wenn du das nicht warst, kannst du diese E-Mail einfach ignorieren.</p>
                        <hr style='border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;' />
                        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
                    </div>
                </div>";

            await emailService.SendEmailAsync(config, userLink.EmailAddress, "Passwort zurücksetzen - RiNnoFin Media", htmlBody);
            
            return Ok();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Senden der Reset-E-Mail.");
            return StatusCode(StatusCodes.Status500InternalServerError, new { message = "Fehler beim Senden der E-Mail." });
        }
    }

    [AllowAnonymous]
    [HttpPost("ResetPassword")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> ResetPassword(
        [FromServices] MediaBrowser.Controller.Library.IUserManager userManager,
        [FromServices] MediaBrowser.Model.Cryptography.ICryptoProvider cryptoProvider,
        [FromServices] EmailService emailService,
        [FromBody] ResetPasswordRequest request,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(request.Token) || string.IsNullOrWhiteSpace(request.NewPassword))
        {
            return BadRequest(new { message = "Alle Felder müssen ausgefüllt sein." });
        }

        if (!ResetTokenManager.ActiveResetTokens.TryRemove(request.Token, out var userId))
        {
            return BadRequest(new { message = "Ungültiger oder abgelaufener Reset-Link." });
        }

        try
        {
            var user = userManager.GetUserById(userId);
            if (user == null)
            {
                return BadRequest(new { message = "Benutzer nicht gefunden." });
            }

            user.Password = cryptoProvider.CreatePasswordHash(request.NewPassword).ToString();
            await userManager.UpdateUserAsync(user).ConfigureAwait(false);

            // Optional: Bestätigungsmail
            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config != null)
            {
                var userLink = config.TelegramUserLinks.FirstOrDefault(l => l.JellyfinUserId == userId);
                if (userLink != null && !string.IsNullOrEmpty(userLink.EmailAddress))
                {
                    string htmlBody = $@"
                        <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                            <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                                <h2 style='color: #22c55e;'>Passwort geändert ✅</h2>
                                <p>Hallo <strong>{user.Username}</strong>,</p>
                                <p>Dein Passwort wurde erfolgreich geändert.</p>
                                <p>Falls du dies nicht selbst getan hast, kontaktiere bitte umgehend deinen Administrator!</p>
                            </div>
                        </div>";
                    await emailService.SendEmailAsync(config, userLink.EmailAddress, "Passwort erfolgreich geändert", htmlBody);
                }
            }

            return Ok(new { message = "Passwort erfolgreich geändert!" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Zurücksetzen des Passworts.");
            return StatusCode(StatusCodes.Status500InternalServerError, new { message = "Interner Fehler beim Zurücksetzen." });
        }
    }
}

public class AddRequestRequest
{
    public string ImdbId { get; set; } = string.Empty;
}

public class TestSmtpRequest
{
    public string SmtpServer { get; set; } = string.Empty;
    public int SmtpPort { get; set; }
    public string SmtpUsername { get; set; } = string.Empty;
    public string SmtpPassword { get; set; } = string.Empty;
    public string EmailSenderAddress { get; set; } = string.Empty;
    public string EmailSenderName { get; set; } = string.Empty;
    public bool SmtpUseSsl { get; set; }
}

public class AcceptInviteRequest
{
    public string Token { get; set; } = string.Empty;
    public string Username { get; set; } = string.Empty;
    public string Password { get; set; } = string.Empty;
}

public class RequestPasswordResetRequest
{
    public string Email { get; set; } = string.Empty;
}

public class ResetPasswordRequest
{
    public string Token { get; set; } = string.Empty;
    public string NewPassword { get; set; } = string.Empty;
}

public static class ResetTokenManager
{
    // Key: Token, Value: Jellyfin UserId
    public static readonly System.Collections.Concurrent.ConcurrentDictionary<string, Guid> ActiveResetTokens = new();
}
