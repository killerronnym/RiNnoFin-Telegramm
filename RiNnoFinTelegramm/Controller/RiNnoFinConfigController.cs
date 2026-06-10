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
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using MediaBrowser.Controller.Net;
using Telegram.Bot;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Controller;

[ApiController]
[Route("api/[controller]")]
[AllowAnonymous]
public class RiNnoFinConfigController : ControllerBase
{
    private readonly ILogger<RiNnoFinConfigController> _logger;

    public RiNnoFinConfigController(ILogger<RiNnoFinConfigController> _loggerVal)
    {
        _logger = _loggerVal ?? throw new ArgumentNullException(nameof(_loggerVal));
        PluginLog.Info("RiNnoFinConfigController constructor called.");
    }

    private async Task<bool> IsUserAdmin()
    {
        try
        {
            // 1. Versuche über die ClaimsPrincipal-Identität des Requests zu gehen
            var userIdStr = User.FindFirst("Jellyfin-UserId")?.Value
                         ?? User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value 
                         ?? User.FindFirst("id")?.Value
                         ?? User.FindFirst("UserId")?.Value;

            if (!string.IsNullOrEmpty(userIdStr) && Guid.TryParse(userIdStr, out var userId))
            {
                var userManager = RiNnoFinPlugin.UserManager;
                if (userManager != null)
                {
                    var user = userManager.GetUserById(userId);
                    if (user != null)
                    {
                        var dto = userManager.GetUserDto(user, string.Empty);
                        if (dto?.Policy != null && dto.Policy.IsAdministrator)
                        {
                            return true;
                        }
                    }
                }
            }

            // 2. Fallback: Manuelle Authentifizierung über Jellyfins IAuthService
            var authService = HttpContext.RequestServices.GetService(typeof(IAuthService)) as IAuthService;
            if (authService != null)
            {
                var authInfo = await authService.Authenticate(Request).ConfigureAwait(false);
                if (authInfo != null && authInfo.UserId != Guid.Empty)
                {
                    var userManager = RiNnoFinPlugin.UserManager;
                    if (userManager != null)
                    {
                        var user = userManager.GetUserById(authInfo.UserId);
                        if (user != null)
                        {
                            var dto = userManager.GetUserDto(user, string.Empty);
                            if (dto?.Policy != null && dto.Policy.IsAdministrator)
                            {
                                return true;
                            }
                        }
                    }
                }
            }

            PluginLog.Warn("[ConfigAPI] Admin-Check fehlgeschlagen: Kein Administrator authentifiziert.");
            return false;
        }
        catch (Exception ex)
        {
            PluginLog.Error(ex, "[ConfigAPI] Fehler im IsUserAdmin check");
            return false;
        }
    }

    [HttpPost(nameof(TestBotToken))]
    [Produces(MediaTypeNames.Application.Json)]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<ActionResult<ValidateBotTokenResponse>> TestBotToken([FromBody] ValidateBotTokenRequest request)
    {
        if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, new ValidateBotTokenResponse { ErrorMessage = "Admin-Rechte erforderlich." });

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
            return StatusCode(500, new ValidateBotTokenResponse { ErrorMessage = "Ungültiger Token oder Verbindungsfehler" });
        }
    }

    [HttpGet("GetRequests")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    public async Task<ActionResult<IReadOnlyList<MediaRequest>>> GetRequests(CancellationToken cancellationToken)
    {
        if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, null);

        var requestService = (RequestService)HttpContext.RequestServices.GetService(typeof(RequestService));
        var requests = await requestService.GetRequestsAsync(cancellationToken).ConfigureAwait(false);
        return Ok(requests);
    }

    [HttpPost("SetRequests")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    public async Task<ActionResult> SetRequests([FromBody] List<MediaRequest> requests, CancellationToken cancellationToken)
    {
        if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, null);
        var requestService = (RequestService)HttpContext.RequestServices.GetService(typeof(RequestService));
        await requestService.SetRequestsAsync(requests, cancellationToken).ConfigureAwait(false);
        return Ok();
    }

    [HttpPost("AddRequest")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<RequestAddResult>> AddRequest([FromBody] MediaRequest request, CancellationToken cancellationToken)
    {
        if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, null);
        var requestService = (RequestService)HttpContext.RequestServices.GetService(typeof(RequestService));
        var providerManager = (IProviderManager)HttpContext.RequestServices.GetService(typeof(IProviderManager));
        if (string.IsNullOrWhiteSpace(request.ImdbId))
        {
            return BadRequest("ImdbId is required.");
        }

        var config = RiNnoFinPlugin.Instance?.Configuration;
        var maxRequests = config?.MaxSessionCount ?? -1;

        var result = await requestService
            .TryAddRequestAsync(request, maxRequests, cancellationToken)
            .ConfigureAwait(false);

        return result switch
        {
            RequestAddResult.Duplicate => Conflict(),
            RequestAddResult.Added => Ok(result),
            RequestAddResult.Removed => Ok(result),
            _ => StatusCode(StatusCodes.Status500InternalServerError)
        };
    }

    [HttpPost("RemoveRequest")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult> RemoveRequest([FromQuery] string imdbId, CancellationToken cancellationToken)
    {
        if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, null);
        var requestService = (RequestService)HttpContext.RequestServices.GetService(typeof(RequestService));
        if (string.IsNullOrWhiteSpace(imdbId))
            return BadRequest("ImdbId is required.");

        await requestService.RemoveRequestAsync(imdbId, cancellationToken).ConfigureAwait(false);
        return Ok();
    }

    [HttpPost("TriggerQuiz/{groupName}")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> TriggerQuiz(string groupName, CancellationToken cancellationToken)
    {
        if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, null);
        var botClientWrapper = (TelegramBotClientWrapper)HttpContext.RequestServices.GetService(typeof(TelegramBotClientWrapper));
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

        var botClient = botClientWrapper.Client;
        if (botClient == null)
        {
            return BadRequest("Telegram Bot ist nicht aktiv.");
        }

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
        if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, new { message = "Admin-Rechte erforderlich." });
        try
        {
            var emailService = new EmailService(_logger);
            
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

            var targetEmail = !string.IsNullOrWhiteSpace(request.TestEmailAddress) ? request.TestEmailAddress : request.SmtpUsername;

            await emailService.SendEmailAsync(tempConfig, targetEmail, "RiNnoFin Media - E-Mail Test erfolgreich! 🎉", htmlBody);

            return Ok(new { message = $"E-Mail erfolgreich an {targetEmail} versendet!" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Senden der Test-E-Mail.");
            return StatusCode(StatusCodes.Status500InternalServerError, new { message = ex.Message });
        }
    }


        [HttpGet("GetUsers")]
        [ProducesResponseType(StatusCodes.Status200OK)]
        public async Task<IActionResult> GetUsers()
        {
            if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, new { message = "Admin-Rechte erforderlich." });
            PluginLog.Info($"GetUsers method entered. UserManager is null: {RiNnoFinPlugin.UserManager == null}");
            try
            {
                var userManager = RiNnoFinPlugin.UserManager;
                if (userManager == null)
                {
                    return StatusCode(StatusCodes.Status500InternalServerError, new { message = "UserManager instance is null." });
                }

                var config = RiNnoFinPlugin.Instance?.Configuration;
                
                System.Collections.IEnumerable usersList;
                var getUsersMethod = userManager.GetType().GetMethod("GetUsers", Type.EmptyTypes);
                if (getUsersMethod != null)
                {
                    usersList = (System.Collections.IEnumerable)getUsersMethod.Invoke(userManager, null);
                }
                else
                {
                    var usersProp = userManager.GetType().GetProperty("Users");
                    if (usersProp != null)
                    {
                        usersList = (System.Collections.IEnumerable)usersProp.GetValue(userManager, null);
                    }
                    else
                    {
                        throw new InvalidOperationException("Could not find GetUsers method or Users property on IUserManager.");
                    }
                }

                var dtos = new List<UserDto>();

                foreach (dynamic u in usersList)
                {
                    try
                    {
                        Guid uId = u.Id;
                        string uUsername = u.Username;
                        DateTime? uLastActivityDate = u.LastActivityDate;

                        var link = config?.TelegramUserLinks != null ? config.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == uId) : null;
                        var uDto = userManager.GetUserDto(u, string.Empty);
                        dtos.Add(new UserDto
                        {
                            Id = uId,
                            Username = uUsername,
                            Email = link?.EmailAddress ?? "",
                            HasTelegram = link?.TelegramUserId > 0,
                            IsDisabled = uDto?.Policy?.IsDisabled ?? false,
                            IsAdmin = uDto?.Policy?.IsAdministrator ?? false,
                            LastActivityDate = uLastActivityDate
                        });
                    }
                    catch (Exception innerEx)
                    {
                        PluginLog.Error(innerEx, $"Fehler beim Verarbeiten des Benutzers");
                        try
                        {
                            dtos.Add(new UserDto
                            {
                                Id = u.Id,
                                Username = u.Username ?? "Fehler",
                                Email = "Fehler beim Laden",
                                HasTelegram = false,
                                IsDisabled = false,
                                IsAdmin = false,
                                LastActivityDate = null
                            });
                        }
                        catch
                        {
                            // Ignore
                        }
                    }
                }

                return Ok(dtos.OrderBy(d => d.Username).ToList());
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Fehler in GetUsers");
                return StatusCode(StatusCodes.Status500InternalServerError, new { message = "GETUSERS_ERR: " + ex.ToString() });
            }
        }

        [HttpGet("GetLogs")]
        [ProducesResponseType(StatusCodes.Status200OK)]
        public async Task<ActionResult<IEnumerable<string>>> GetLogs()
        {
            if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, new { message = "Admin-Rechte erforderlich." });
            return Ok(PluginLog.GetLogs());
        }

        [HttpPost("AdminCreateInvite")]
        [ProducesResponseType(StatusCodes.Status200OK)]
        public async Task<ActionResult> AdminCreateInvite([FromBody] AdminCreateInviteRequest request)
        {
            if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, new { message = "Admin-Rechte erforderlich." });
            var userManager = RiNnoFinPlugin.UserManager;
            if (string.IsNullOrWhiteSpace(request.Email))
                return BadRequest(new { message = "E-Mail darf nicht leer sein." });

            var config = RiNnoFinPlugin.Instance?.Configuration;
            if (config == null || !config.EnableEmail)
                return BadRequest(new { message = "E-Mail-Versand ist in der Konfiguration nicht aktiviert." });

            if (!string.IsNullOrWhiteSpace(request.Username))
            {
                try
                {
                    PluginLog.Info($"[ConfigAPI] Erstelle sofortigen Account für Benutzer '{request.Username}'...");
                    var newUser = await userManager.CreateUserAsync(request.Username);

                    if (Guid.TryParse(request.ProfileUserId, out var profileId))
                    {
                        var profileUser = userManager.GetUserById(profileId);
                        if (profileUser != null)
                        {
                            var profileDto = userManager.GetUserDto(profileUser, string.Empty);
                            profileDto.Policy.IsDisabled = false;
                            await userManager.UpdatePolicyAsync(newUser.Id, profileDto.Policy).ConfigureAwait(false);

                            if (profileDto.Configuration != null)
                            {
                                var clonedConfigJson = System.Text.Json.JsonSerializer.Serialize(profileDto.Configuration);
                                var clonedConfig = System.Text.Json.JsonSerializer.Deserialize<MediaBrowser.Model.Configuration.UserConfiguration>(clonedConfigJson);
                                if (clonedConfig != null)
                                {
                                    await userManager.UpdateConfigurationAsync(newUser.Id, clonedConfig).ConfigureAwait(false);
                                }
                            }
                        }
                    }

                    if (config.TelegramUserLinks == null) config.TelegramUserLinks = new();
                    config.TelegramUserLinks.Add(new TelegramUserLink
                    {
                        JellyfinUserId = newUser.Id,
                        JellyfinUsername = newUser.Username,
                        EmailAddress = request.Email
                    });
                    RiNnoFinPlugin.Instance?.UpdateConfiguration(config);

                    string token = Guid.NewGuid().ToString("N");
                    ResetTokenManager.AddResetToken(token, newUser.Id);

                    string resetUrl = $"{config.LoginBaseUrl?.TrimEnd('/')}/sso/Telegram/reset?token={token}";
                    
                    string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplateInvite)
                        ? config.EmailTemplateInvite.Replace("{inviteLink}", resetUrl).Replace("Du wurdest eingeladen!", "Dein Account wurde erstellt!").Replace("Account erstellen", "Passwort festlegen")
                        : $@"
                        <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                            <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                                <h2 style='color: #3b82f6;'>Dein Account wurde erstellt! 🎉</h2>
                                <p>Hallo {request.Username},</p>
                                <p>Dein Account auf unserem Media-Server wurde eingerichtet.</p>
                                <p>Klicke auf den Button unten, um dein persönliches Passwort festzulegen:</p>
                                <a href='{resetUrl}' style='display: inline-block; padding: 10px 20px; margin-top: 20px; background-color: #3b82f6; color: #fff; text-decoration: none; border-radius: 4px; font-weight: bold;'>Passwort festlegen</a>
                            </div>
                        </div>";

                    var emailService = new Jellyfin.Plugin.RiNnoFinTelegramm.Services.EmailService(_logger);
                    await emailService.SendEmailAsync(config, request.Email, "Dein Account wurde erstellt", htmlBody);

                    return Ok(new { message = $"Benutzer '{request.Username}' wurde erstellt und eine E-Mail zur Passwortvergabe gesendet." });
                }
                catch (Exception ex)
                {
                    PluginLog.Error(ex, $"[ConfigAPI] Fehler beim sofortigen Anlegen des Benutzers '{request.Username}'.");
                    return StatusCode(500, new { message = "Fehler beim Anlegen des Benutzers: " + ex.Message });
                }
            }
            else
            {
                string token = Guid.NewGuid().ToString("N");
                Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands.InviteTokenManager.AddInvite(token, request.Email, request.ProfileUserId);

                string inviteUrl = $"{config.LoginBaseUrl?.TrimEnd('/')}/sso/Telegram/invite?token={token}";
                string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplateInvite)
                    ? config.EmailTemplateInvite.Replace("{inviteLink}", inviteUrl)
                    : $@"
                    <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                        <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                            <h2 style='color: #3b82f6;'>Du wurdest eingeladen! 🎉</h2>
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
        }

        [HttpPost("AdminEnableUser")]
        public async Task<ActionResult> AdminEnableUser([FromBody] List<Guid> userIds)
        {
            if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, new { message = "Admin-Rechte erforderlich." });
            var userManager = RiNnoFinPlugin.UserManager;
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
        public async Task<ActionResult> AdminDisableUser([FromBody] List<Guid> userIds)
        {
            if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, new { message = "Admin-Rechte erforderlich." });
            var userManager = RiNnoFinPlugin.UserManager;
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
        public async Task<ActionResult> AdminDeleteUser([FromBody] List<Guid> userIds)
        {
            if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, new { message = "Admin-Rechte erforderlich." });
            var userManager = RiNnoFinPlugin.UserManager;
            foreach (var id in userIds)
            {
                var user = userManager.GetUserById(id);
                if (user != null)
                {
                    await userManager.DeleteUserAsync(id).ConfigureAwait(false);
                }
            }
            return Ok(new { message = "Benutzer erfolgreich gelöscht." });
        }

        [HttpPost("AdminSendPasswordReset")]
        public async Task<ActionResult> AdminSendPasswordReset([FromBody] List<Guid> userIds)
        {
            if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, new { message = "Admin-Rechte erforderlich." });
            var userManager = RiNnoFinPlugin.UserManager;
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
                ResetTokenManager.AddResetToken(token, id);
                string resetUrl = $"{config.LoginBaseUrl?.TrimEnd('/')}/sso/Telegram/ResetPassword?token={token}";

                string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplatePasswordReset)
                    ? config.EmailTemplatePasswordReset.Replace("{resetLink}", resetUrl).Replace("{username}", user.Username)
                    : $@"
                    <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                        <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                            <h2 style='color: #ef4444;'>Passwort zurücksetzen 🔑</h2>
                            <p>Hallo <strong>{user.Username}</strong>,</p>
                            <p>Du hast das Zurücksetzen deines Passworts angefordert.</p>
                            <a href='{resetUrl}' style='display: inline-block; padding: 10px 20px; margin-top: 20px; background-color: #ef4444; color: #fff; text-decoration: none; border-radius: 4px; font-weight: bold;'>Passwort jetzt zurücksetzen</a>
                        </div>
                    </div>";

                await emailService.SendEmailAsync(config, userLink.EmailAddress, "Passwort zurücksetzen", htmlBody);
                sentCount++;
            }

            return Ok(new { message = $"{sentCount} Reset-E-Mails erfolgreich versendet." });
        }
    [HttpPost("UploadLogo")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<IActionResult> UploadLogo([FromForm] IFormFile file)
    {
        if (!await IsUserAdmin().ConfigureAwait(false)) return StatusCode(StatusCodes.Status403Forbidden, new { message = "Admin-Rechte erforderlich." });
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
    public string? Username { get; set; }
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
    public static void AddResetToken(string token, Guid jellyfinUserId)
    {
        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config != null)
        {
            if (config.PersistedResetTokens == null) config.PersistedResetTokens = new();
            config.PersistedResetTokens.Add(new PersistedResetToken
            {
                Token = token,
                JellyfinUserId = jellyfinUserId
            });
            RiNnoFinPlugin.Instance?.SaveConfiguration(config);
            PluginLog.Info($"[ResetTokenManager] Passwort-Reset-Token für User ID '{jellyfinUserId}' hinzugefügt und persistiert.");
        }
    }

    public static bool TryGetAndRemoveResetToken(string token, out Guid jellyfinUserId)
    {
        jellyfinUserId = Guid.Empty;
        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null || config.PersistedResetTokens == null) return false;

        var resetToken = config.PersistedResetTokens.FirstOrDefault(t => t.Token == token);
        if (resetToken == null) return false;

        jellyfinUserId = resetToken.JellyfinUserId;
        config.PersistedResetTokens.Remove(resetToken);
        RiNnoFinPlugin.Instance?.SaveConfiguration(config);
        PluginLog.Info($"[ResetTokenManager] Passwort-Reset-Token für User ID '{jellyfinUserId}' verbraucht und aus Persistenz entfernt.");
        return true;
    }
}


