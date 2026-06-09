using System;
using System.Collections.Generic;
using System.Net.Mime;
using System.Threading;
using System.Threading.Tasks;
using System.Linq;
using System.IO;
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
            if (config != null && config.AdminUserNames != null && config.AdminUserNames.Count > 0 && config.TelegramUserLinks != null && config.TelegramUserLinks.Count > 0)
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
                            "âœ… *Test erfolgreich!*\nDein Jellyfin-Server hat den Bot-Token erfolgreich Ã¼berprÃ¼ft und sich mit Telegram verbunden.",
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
            return StatusCode(500, new ValidateBotTokenResponse { ErrorMessage = "UngÃ¼ltiger Token oder Verbindungsfehler" });
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
            return BadRequest("Gruppe ist nicht mit Telegram verknÃ¼pft.");
        }

        var botClient = _botClientWrapper.Client;
        if (botClient == null)
        {
            return BadRequest("Telegram Bot ist nicht aktiv.");
        }

        // Topic ID ist optional â€“ 0 oder null bedeutet: kein Topic (Hauptchat)
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
            
            // Erstelle eine temporÃ¤re Konfiguration fÃ¼r den Test
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
                        <h2 style='color: #2c3e50;'>âœ… Erfolgreiche Test-Verbindung</h2>
                        <p>Hallo Admin,</p>
                        <p>Dein E-Mail Server (<strong>{request.SmtpServer}</strong>) funktioniert einwandfrei!</p>
                        <p>Das RiNnoFin Telegramm-Plugin kann nun automatisch Einladungen und Passwort-Reset-Links an deine Benutzer verschicken.</p>
                        <br/>
                        <p style='color: #7f8c8d; font-size: 12px;'>Diese E-Mail wurde automatisch generiert.</p>
                    </div>
                </div>";

            var targetEmail = !string.IsNullOrWhiteSpace(request.TestEmailAddress) ? request.TestEmailAddress : request.SmtpUsername;

            // Sende Test-E-Mail an die angegebene Test-Adresse
            await emailService.SendEmailAsync(tempConfig, targetEmail, "RiNnoFin Media - E-Mail Test erfolgreich! ðŸŽ‰", htmlBody);

            return Ok(new { message = $"E-Mail erfolgreich an {targetEmail} versendet!" });
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
            return BadRequest(new { message = "Alle Felder mÃ¼ssen ausgefÃ¼llt sein." });
        }

        if (!Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands.InviteTokenManager.ActiveInvites.TryRemove(request.Token, out var email))
        {
            return BadRequest(new { message = "UngÃ¼ltiger oder abgelaufener Einladungslink." });
        }

        try
        {
            var existingUser = userManager.GetUserByName(request.Username);
            if (existingUser != null)
            {
                return BadRequest(new { message = "Dieser Benutzername ist bereits vergeben." });
            }

            // Create user
            var user = await userManager.CreateUserAsync(request.Username).ConfigureAwait(false);
            
            // Set password
            user.Password = cryptoProvider.CreatePasswordHash(request.Password).ToString();
            await userManager.UpdateUserAsync(user).ConfigureAwait(false);

            // Clone Policy if provided
            if (Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands.InviteTokenManager.InviteProfiles.TryRemove(request.Token, out var profileUserId) && profileUserId.HasValue)
            {
                var profileUser = userManager.GetUserById(profileUserId.Value);
                if (profileUser != null)
                {
                    var profileDto = userManager.GetUserDto(profileUser, string.Empty);
                    await userManager.UpdatePolicyAsync(user.Id, profileDto.Policy).ConfigureAwait(false);
                }
            }

            // Speichern der E-Mail im Plugin-Config (damit wir wissen, wem dieser Account gehÃ¶rt)
            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config != null)
            {
                if (config.TelegramUserLinks == null) config.TelegramUserLinks = new List<TelegramUserLink>();
                var existingLink = config.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == user.Id);
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
                string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplateWelcome)
                    ? config.EmailTemplateWelcome.Replace("{username}", user.Username)
                    : $@"
                    <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                        <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                            <h2 style='color: #2563eb;'>Willkommen an Bord! ðŸ§ðŸŽ¬</h2>
                            <p>Hallo <strong>{user.Username}</strong>,</p>
                            <p>Dein Account bei <strong>RiNnoFin Media</strong> wurde erfolgreich erstellt.</p>
                            <p>Du kannst dich ab sofort mit deinem gewÃ¤hlten Passwort auf all deinen GerÃ¤ten einloggen.</p>
                            <br/>
                            <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Viel SpaÃŸ beim Streamen! ðŸ¿ Dein RiNnoFin-Team</p>
                        </div>
                    </div>";

                try { await emailService.SendEmailAsync(config, email, "Willkommen bei RiNnoFin Media! ðŸ¿", htmlBody); } catch (Exception emailEx) { _logger.LogError(emailEx, "Konnte Willkommens-E-Mail nicht senden."); }
            }

            return Ok(new { message = "Account erfolgreich erstellt!" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Erstellen des Accounts für Einladung.");
            return BadRequest(new { message = "Fehler beim Erstellen des Accounts: " + ex.Message });
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
        var userLink = config.TelegramUserLinks?.FirstOrDefault(l => string.Equals(l.EmailAddress, request.Email, StringComparison.OrdinalIgnoreCase));
        
        // Aus SicherheitsgrÃ¼nden immer OK zurÃ¼ckgeben, auch wenn E-Mail nicht existiert
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

            string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplatePasswordReset)
                ? config.EmailTemplatePasswordReset.Replace("{resetLink}", resetLink).Replace("{username}", userLink.JellyfinUsername ?? "")
                : $@"
                <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                        <h2 style='color: #2563eb;'>Passwort zurÃ¼cksetzen ðŸ”‘</h2>
                        <p>Hallo <strong>{userLink.JellyfinUsername}</strong>,</p>
                        <p>Jemand (vermutlich du) hat das ZurÃ¼cksetzen des Passworts fÃ¼r deinen RiNnoFin-Account angefordert.</p>
                        <p>Klicke auf den untenstehenden Button, um ein neues Passwort festzulegen:</p>
                        <div style='text-align: center; margin: 30px 0;'>
                            <a href='{resetLink}' style='background-color: #2563eb; color: #fff; padding: 14px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;'>Passwort zurÃ¼cksetzen</a>
                        </div>
                        <p style='color: #6b7280; font-size: 13px;'>Wenn du das nicht warst, kannst du diese E-Mail einfach ignorieren.</p>
                        <hr style='border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;' />
                        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
                    </div>
                </div>";

            await emailService.SendEmailAsync(config, userLink.EmailAddress, "Passwort zurÃ¼cksetzen - RiNnoFin Media", htmlBody);
            
            return Ok();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Senden der Reset-E-Mail.");
            return BadRequest(new { message = "Fehler beim Senden der E-Mail." });
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
            return BadRequest(new { message = "Alle Felder mÃ¼ssen ausgefÃ¼llt sein." });
        }

        if (!ResetTokenManager.ActiveResetTokens.TryRemove(request.Token, out var userId))
        {
            return BadRequest(new { message = "UngÃ¼ltiger oder abgelaufener Reset-Link." });
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

            // Optional: BestÃ¤tigungsmail
            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config != null)
            {
                var userLink = config.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == userId);
                if (userLink != null && !string.IsNullOrEmpty(userLink.EmailAddress))
                {
                    string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplatePasswordChanged)
                        ? config.EmailTemplatePasswordChanged.Replace("{username}", user.Username)
                        : $@"
                        <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                            <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                                <h2 style='color: #22c55e;'>Passwort geÃ¤ndert âœ…</h2>
                                <p>Hallo <strong>{user.Username}</strong>,</p>
                                <p>Dein Passwort wurde erfolgreich geÃ¤ndert.</p>
                                <p>Falls du dies nicht selbst getan hast, kontaktiere bitte umgehend deinen Administrator!</p>
                            </div>
                        </div>";
                    await emailService.SendEmailAsync(config, userLink.EmailAddress, "Passwort erfolgreich geÃ¤ndert", htmlBody);
                }
            }

            return Ok(new { message = "Passwort erfolgreich geÃ¤ndert!" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Zurücksetzen des Passworts.");
            return BadRequest(new { message = "Interner Fehler beim Zurücksetzen." });
        }
    }
        [HttpGet("GetUsers")]
        [ProducesResponseType(StatusCodes.Status200OK)]
        public ActionResult<IEnumerable<UserDto>> GetUsers([FromServices] MediaBrowser.Controller.Library.IUserManager userManager)
        {
            var config = RiNnoFinPlugin.Instance?.Configuration;
            var users = userManager.Users.ToList();
            var dtos = new List<UserDto>();

            foreach (var u in users)
            {
                var link = config?.TelegramUserLinks != null ? config.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == u.Id) : null;
                var uDto = userManager.GetUserDto(u, null);
                dtos.Add(new UserDto
                {
                    Id = u.Id,
                    Username = u.Username,
                    Email = link?.EmailAddress ?? "",
                    HasTelegram = link?.TelegramUserId > 0,
                    IsDisabled = uDto.Policy.IsDisabled,
                    IsAdmin = uDto.Policy.IsAdministrator,
                    LastActivityDate = u.LastActivityDate
                });
            }

            return Ok(dtos.OrderBy(d => d.Username));
        }

        [HttpPost("AdminCreateInvite")]
        [ProducesResponseType(StatusCodes.Status200OK)]
        public async Task<ActionResult> AdminCreateInvite([FromBody] AdminCreateInviteRequest request)
        {
            if (string.IsNullOrWhiteSpace(request.Email))
                return BadRequest(new { message = "E-Mail darf nicht leer sein." });

            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config == null || !config.EnableEmail)
                return BadRequest(new { message = "E-Mail-Versand ist in der Konfiguration nicht aktiviert." });

            string token = Guid.NewGuid().ToString("N");
            Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands.InviteTokenManager.ActiveInvites[token] = request.Email;
            
            if (Guid.TryParse(request.ProfileUserId, out var profileId))
            {
                Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands.InviteTokenManager.InviteProfiles[token] = profileId;
            }

            string inviteUrl = $"{config.LoginBaseUrl?.TrimEnd('/')}/sso/Telegram/invite?token={token}";
            string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplateInvite)
                ? config.EmailTemplateInvite.Replace("{inviteLink}", inviteUrl)
                : $@"
                <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                        <h2 style='color: #3b82f6;'>Du wurdest eingeladen! ðŸŽ‰</h2>
                        <p>Hallo,</p>
                        <p>Du wurdest eingeladen, einen Account auf unserem Media-Server zu erstellen.</p>
                        <p>Klicke auf den Button unten, um deinen Account einzurichten:</p>
                        <a href='{inviteUrl}' style='display: inline-block; padding: 10px 20px; margin-top: 20px; background-color: #3b82f6; color: #fff; text-decoration: none; border-radius: 4px; font-weight: bold;'>Account erstellen</a>
                    </div>
                </div>";

            var emailService = new Jellyfin.Plugin.RiNnoFinTelegramm.Services.EmailService(_logger);
            await emailService.SendEmailAsync(config, request.Email, "Einladung zum Media-Server", htmlBody);

            return Ok(new { message = "Einladung erfolgreich versendet." });
        }

        [HttpPost("AdminEnableUser")]
        public async Task<ActionResult> AdminEnableUser([FromServices] MediaBrowser.Controller.Library.IUserManager userManager, [FromBody] List<Guid> userIds)
        {
            foreach (var id in userIds)
            {
                var user = userManager.GetUserById(id);
                if (user != null)
                {
                    var dto = userManager.GetUserDto(user, string.Empty);
                    dto.Policy.IsDisabled = false;
                    await userManager.UpdatePolicyAsync(id, dto.Policy).ConfigureAwait(false);
                }
            }
            return Ok(new { message = "Benutzer erfolgreich aktiviert." });
        }

        [HttpPost("AdminDisableUser")]
        public async Task<ActionResult> AdminDisableUser([FromServices] MediaBrowser.Controller.Library.IUserManager userManager, [FromBody] List<Guid> userIds)
        {
            foreach (var id in userIds)
            {
                var user = userManager.GetUserById(id);
                if (user != null)
                {
                    var dto = userManager.GetUserDto(user, string.Empty);
                    dto.Policy.IsDisabled = true;
                    await userManager.UpdatePolicyAsync(id, dto.Policy).ConfigureAwait(false);
                }
            }
            return Ok(new { message = "Benutzer erfolgreich deaktiviert." });
        }

        [HttpPost("AdminDeleteUser")]
        public async Task<ActionResult> AdminDeleteUser([FromServices] MediaBrowser.Controller.Library.IUserManager userManager, [FromBody] List<Guid> userIds)
        {
            foreach (var id in userIds)
            {
                var user = userManager.GetUserById(id);
                if (user != null)
                {
                    await userManager.DeleteUserAsync(id).ConfigureAwait(false);
                }
            }
            return Ok(new { message = "Benutzer erfolgreich gelÃ¶scht." });
        }

        [HttpPost("AdminSendPasswordReset")]
        public async Task<ActionResult> AdminSendPasswordReset([FromServices] MediaBrowser.Controller.Library.IUserManager userManager, [FromBody] List<Guid> userIds)
        {
            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config == null || !config.EnableEmail)
                return BadRequest(new { message = "E-Mail-Versand ist nicht aktiviert." });

            var emailService = new Jellyfin.Plugin.RiNnoFinTelegramm.Services.EmailService(_logger);
            int sentCount = 0;

            foreach (var id in userIds)
            {
                var user = userManager.GetUserById(id);
                if (user == null) continue;

                var userLink = config.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == id);
                if (userLink == null || string.IsNullOrWhiteSpace(userLink.EmailAddress)) continue;

                string token = Guid.NewGuid().ToString("N");
                ResetTokenManager.ActiveResetTokens[token] = id;
                string resetUrl = $"{config.LoginBaseUrl?.TrimEnd('/')}/sso/Telegram/ResetPassword?token={token}";

                string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplatePasswordReset)
                    ? config.EmailTemplatePasswordReset.Replace("{resetLink}", resetUrl).Replace("{username}", user.Username)
                    : $@"
                    <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                        <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                            <h2 style='color: #ef4444;'>Passwort zurÃ¼cksetzen ðŸ”‘</h2>
                            <p>Hallo <strong>{user.Username}</strong>,</p>
                            <p>Du hast das ZurÃ¼cksetzen deines Passworts angefordert.</p>
                            <a href='{resetUrl}' style='display: inline-block; padding: 10px 20px; margin-top: 20px; background-color: #ef4444; color: #fff; text-decoration: none; border-radius: 4px; font-weight: bold;'>Passwort jetzt zurÃ¼cksetzen</a>
                        </div>
                    </div>";

                await emailService.SendEmailAsync(config, userLink.EmailAddress, "Passwort zurÃ¼cksetzen", htmlBody);
                sentCount++;
            }

            return Ok(new { message = $"{sentCount} Reset-E-Mails erfolgreich versendet." });
        }
    [HttpPost("UploadLogo")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<IActionResult> UploadLogo([FromForm] IFormFile file)
    {
        if (file == null || file.Length == 0)
        {
            return BadRequest("Keine Datei hochgeladen.");
        }

        var plugin = RiNnoFinPlugin.Instance;
        if (plugin == null) return StatusCode(500, "Plugin Instanz ist null.");

        var customLogoPath = Path.Combine(plugin.ApplicationPaths.PluginsPath, Constants.PluginName, Constants.PluginDataFolder, "CustomLogo.png");
        var dir = Path.GetDirectoryName(customLogoPath);
        if (dir != null && !Directory.Exists(dir))
        {
            Directory.CreateDirectory(dir);
        }

        await using var stream = new FileStream(customLogoPath, FileMode.Create);
        await file.CopyToAsync(stream);

        return Ok(new { message = "Logo erfolgreich hochgeladen." });
    }

    [HttpPost("ResetLogo")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    public IActionResult ResetLogo()
    {
        var plugin = RiNnoFinPlugin.Instance;
        if (plugin == null) return StatusCode(500, "Plugin Instanz ist null.");

        var customLogoPath = Path.Combine(plugin.ApplicationPaths.PluginsPath, Constants.PluginName, Constants.PluginDataFolder, "CustomLogo.png");
        if (System.IO.File.Exists(customLogoPath))
        {
            System.IO.File.Delete(customLogoPath);
        }
        return Ok(new { message = "Logo erfolgreich zurückgesetzt." });
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
    public string TestEmailAddress { get; set; } = string.Empty;
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

public class AdminCreateInviteRequest
{
    public string Email { get; set; } = string.Empty;
    public string ProfileUserId { get; set; } = string.Empty;
}

public class UserDto
{
    public Guid Id { get; set; }
    public string Username { get; set; } = string.Empty;
    public string Email { get; set; } = string.Empty;
    public bool HasTelegram { get; set; }
    public bool IsDisabled { get; set; }
    public bool IsAdmin { get; set; }
    public DateTime? LastActivityDate { get; set; }
}

public static class ResetTokenManager
{
    // Key: Token, Value: Jellyfin UserId
    public static readonly System.Collections.Concurrent.ConcurrentDictionary<string, Guid> ActiveResetTokens = new();
}
