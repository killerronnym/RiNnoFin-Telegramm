using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.RiNnoFinTelegramm.Classes;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Controller;

[ApiController]
[Route("api/[controller]")]
[AllowAnonymous]
public class RiNnoFinPublicController : ControllerBase
{
    private readonly ILogger<RiNnoFinPublicController> _logger;

    public RiNnoFinPublicController(ILogger<RiNnoFinPublicController> logger)
    {
        _logger = logger;
    }

    [HttpPost("AcceptInvite")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<IActionResult> AcceptInvite(
        [FromBody] AcceptInviteRequest request,
        CancellationToken cancellationToken)
    {
        var userManager = RiNnoFinPlugin.UserManager;
        var cryptoProvider = RiNnoFinPlugin.CryptoProvider;
        var emailService = new EmailService(_logger);

        PluginLog.Info($"[PublicAPI] AcceptInvite aufgerufen für Username: '{request.Username}' mit Token: '{request.Token}'");

        if (string.IsNullOrWhiteSpace(request.Token) || string.IsNullOrWhiteSpace(request.Username) || string.IsNullOrWhiteSpace(request.Password) || string.IsNullOrWhiteSpace(request.Email))
        {
            PluginLog.Warn("[PublicAPI] AcceptInvite abgelehnt: Eines der Pflichtfelder (Token, Username, Email, Password) ist leer.");
            return BadRequest(new { message = "Alle Felder müssen ausgefüllt sein." });
        }

        if (!Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands.InviteTokenManager.TryGetInvite(request.Token, out var email, out var inviteUsername, out var profileUserId, out var expirationDays))
        {
            PluginLog.Warn($"[PublicAPI] AcceptInvite abgelehnt: Token '{request.Token}' ist ungültig oder abgelaufen.");
            return BadRequest(new { message = "Ungültiger oder abgelaufener Einladungslink." });
        }

        if (!string.Equals(email, request.Email, StringComparison.OrdinalIgnoreCase))
        {
            PluginLog.Warn($"[PublicAPI] AcceptInvite abgelehnt: E-Mail stimmt nicht überein. Eingabe: {request.Email}, Erwartet: {email}");
            return BadRequest(new { message = "Die eingegebene E-Mail-Adresse stimmt nicht mit der Einladung überein." });
        }

        try
        {
            PluginLog.Info($"[PublicAPI] Prüfe ob Benutzer '{request.Username}' bereits existiert...");
            var existingUser = userManager.GetUserByName(request.Username);
            if (existingUser != null)
            {
                PluginLog.Warn($"[PublicAPI] Benutzername '{request.Username}' ist bereits vergeben.");
                return BadRequest(new { message = "Dieser Benutzername ist bereits vergeben." });
            }

            PluginLog.Info($"[PublicAPI] Erstelle neuen Jellyfin Benutzer '{request.Username}'...");
            var user = await userManager.CreateUserAsync(request.Username).ConfigureAwait(false);
            PluginLog.Info($"[PublicAPI] Jellyfin Benutzer '{request.Username}' erfolgreich angelegt (ID: {user.Id}). Setze Passwort...");
            
            // Set password
            user.Password = cryptoProvider.CreatePasswordHash(request.Password).ToString();
            await userManager.UpdateUserAsync(user).ConfigureAwait(false);
            PluginLog.Info("[PublicAPI] Passwort erfolgreich gesetzt und Benutzer aktualisiert.");

            // Clone Policy and Configuration if provided (or fallback to global default)
            var config = RiNnoFinPlugin.Instance?.Configuration;
            Guid? actualProfileUserId = profileUserId;
            if (!actualProfileUserId.HasValue && config != null && !string.IsNullOrEmpty(config.DefaultProfileUserId) && Guid.TryParse(config.DefaultProfileUserId, out var defaultId))
            {
                actualProfileUserId = defaultId;
                PluginLog.Info($"[PublicAPI] Kein spezifisches Profil übergeben. Verwende globales Standard-Profil mit ID '{defaultId}'.");
            }

            if (actualProfileUserId.HasValue)
            {
                PluginLog.Info($"[PublicAPI] Profil-Cloning angefordert. Kopiere Rechte von Profile-User ID: '{actualProfileUserId.Value}' auf neuen User '{user.Id}'...");
                var profileUser = userManager.GetUserById(actualProfileUserId.Value);
                if (profileUser != null)
                {
                    // 1. Copy policy and force the user to not be disabled
                    var profileDto = userManager.GetUserDto(profileUser, string.Empty);
                    profileDto.Policy.IsDisabled = false;
                    await userManager.UpdatePolicyAsync(user.Id, profileDto.Policy).ConfigureAwait(false);
                    PluginLog.Info("[PublicAPI] Policy-Rechte erfolgreich geklont und Status auf Aktiv gesetzt.");

                    // 2. Copy user configuration
                    try
                    {
                        if (profileDto.Configuration != null)
                        {
                            var clonedConfigJson = System.Text.Json.JsonSerializer.Serialize(profileDto.Configuration);
                            var clonedConfig = System.Text.Json.JsonSerializer.Deserialize<MediaBrowser.Model.Configuration.UserConfiguration>(clonedConfigJson);
                            if (clonedConfig != null)
                            {
                                await userManager.UpdateConfigurationAsync(user.Id, clonedConfig).ConfigureAwait(false);
                                PluginLog.Info("[PublicAPI] User-Konfiguration erfolgreich geklont.");
                            }
                        }
                    }
                    catch (Exception configEx)
                    {
                        PluginLog.Error(configEx, "[PublicAPI] Fehler beim Klonen der User-Konfiguration.");
                    }
                }
                else
                {
                    PluginLog.Warn($"[PublicAPI] Profil-User mit ID '{actualProfileUserId.Value}' wurde nicht gefunden. Rechte konnten nicht geklont werden.");
                }
            }
            else
            {
                PluginLog.Info("[PublicAPI] Kein Profil-Cloning für diesen Einladungslink konfiguriert.");
            }

            // Speichern der E-Mail im Plugin-Config (damit wir wissen, wem dieser Account gehört)
                if (config != null)
                {
                    PluginLog.Info("[PublicAPI] Verknüpfe E-Mail-Adresse in Plugin-Konfiguration...");
                    if (config.TelegramUserLinks == null) config.TelegramUserLinks = new List<TelegramUserLink>();
                    var existingLink = config.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == user.Id);
                    if (existingLink != null)
                    {
                        existingLink.EmailAddress = email;
                        existingLink.SubscribeTelegramNewsletter = request.SubscribeNewsletter;
                        existingLink.SubscribeEmailNewsletter = request.SubscribeNewsletter;
                        existingLink.ExpirationDate = expirationDays.HasValue ? DateTime.UtcNow.AddDays(expirationDays.Value) : null;
                    }
                    else
                    {
                        config.TelegramUserLinks.Add(new TelegramUserLink
                        {
                            JellyfinUserId = user.Id,
                            JellyfinUsername = user.Username,
                            EmailAddress = email,
                            SubscribeTelegramNewsletter = request.SubscribeNewsletter,
                            SubscribeEmailNewsletter = request.SubscribeNewsletter,
                            ExpirationDate = expirationDays.HasValue ? DateTime.UtcNow.AddDays(expirationDays.Value) : null
                        });
                    }
                    RiNnoFinPlugin.Instance?.UpdateConfiguration(config);
                    PluginLog.Info("[PublicAPI] E-Mail-Adresse erfolgreich verknüpft.");

                // Send Welcome Email
                var baseUrl = config.LoginBaseUrl?.TrimEnd('/') ?? "http://localhost:8096";
                string loginLink = $"{baseUrl}/web/index.html";
                string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplateWelcome)
                        ? config.EmailTemplateWelcome.Replace("{username}", user.Username).Replace("{loginLink}", loginLink)
                        : $@"
<div style='font-family: Arial, sans-serif; background-color: #060b14; padding: 40px 20px; color: #f8fafc;'>
    <div style='max-width: 520px; margin: 0 auto; background-color: #0d1623; border-radius: 16px; overflow: hidden; border: 1px solid #1e3a5f;'>
        <div style='background: #071020; padding: 36px 36px 32px; text-align: center; border-bottom: 1px solid #1e3a5f;'>
            <img src='https://i.imgur.com/ArlRygr.png' alt='RiNnoFin Media' style='height: 48px; width: auto; margin-bottom: 20px;' />
            <h1 style='font-size: 24px; font-weight: 800; color: #f8fafc; margin: 0;'>Willkommen bei <span style='color: #2563eb;'>RiNnoFin</span></h1>
        </div>
        <div style='padding: 32px 36px;'>
            <p style='font-size: 15px; color: #94a3b8; line-height: 1.6; margin-top: 0;'>Hallo <strong style='color: #e2e8f0;'>{user.Username}</strong>,</p>
            <p style='font-size: 15px; color: #94a3b8; line-height: 1.6;'>Dein Account wurde erfolgreich eingerichtet und ist ab sofort startklar. Wir freuen uns, dich an Bord zu haben!</p>
            
            <div style='text-align: center; margin: 35px 0;'>
                <a href='{loginLink}' style='display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; font-size: 16px;'>Jetzt Einloggen &rarr;</a>
            </div>
            
            <a href='https://t.me/+KZM7g40d8NkxNDIy' style='display: flex; align-items: center; background-color: rgba(0, 136, 204, 0.1); border: 1px solid rgba(0, 136, 204, 0.3); padding: 15px; border-radius: 8px; text-decoration: none; margin-bottom: 25px;'>
                <img src='https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/240px-Telegram_logo.svg.png' alt='Telegram' style='width: 40px; height: 40px; margin-right: 15px;' />
                <div>
                    <p style='margin: 0; color: #e2e8f0; font-weight: bold; font-size: 14px;'>Telegram Community beitreten</p>
                    <p style='margin: 5px 0 0; color: #94a3b8; font-size: 12px;'>News, Updates & Community</p>
                </div>
            </a>
            
            <hr style='border: none; border-top: 1px solid #1e293b; margin: 25px 0;' />
            <p style='font-size: 12px; color: #64748b; text-align: center; margin: 0;'>&copy; 2025 RiNnoFin Media. Alle Rechte vorbehalten.</p>
        </div>
    </div>
</div>";

                try 
                {
                    PluginLog.Info($"[PublicAPI] Sende Willkommens-E-Mail an '{email}'...");
                    var subject = !string.IsNullOrWhiteSpace(config.EmailSubjectWelcome) ? config.EmailSubjectWelcome : "Willkommen bei RiNnoFin Media! 🍿";
                    await emailService.SendEmailAsync(config, email, subject, htmlBody);
                    PluginLog.Info("[PublicAPI] Willkommens-E-Mail erfolgreich versendet.");
                } 
                catch (Exception emailEx) 
                {
                    PluginLog.Error(emailEx, "[PublicAPI] Konnte Willkommens-E-Mail nicht senden.");
                    _logger.LogError(emailEx, "[PublicAPI] Konnte Willkommens-E-Mail nicht senden."); 
                }
            }

            PluginLog.Info($"[PublicAPI] Registrierung für Benutzer '{request.Username}' erfolgreich abgeschlossen.");
            Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands.InviteTokenManager.RemoveInvite(request.Token);
            
            var botInfo = RiNnoFinPlugin.Instance?.Configuration;
            var botUsername = botInfo?.BotUsername;
            return Ok(new { message = "Account erfolgreich erstellt!", botUsername = botUsername });
        }
        catch (Exception ex)
        {
            PluginLog.Error(ex, $"[PublicAPI] Kritischer Fehler bei AcceptInvite für Username '{request.Username}'");
            _logger.LogError(ex, "[PublicAPI] Fehler beim Erstellen des Accounts für Einladung.");
            return BadRequest(new { message = "Fehler beim Erstellen des Accounts: " + ex.Message });
        }
    }

    [HttpPost("RequestPasswordReset")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> RequestPasswordReset(
        [FromBody] RequestPasswordResetRequest request,
        CancellationToken cancellationToken)
    {
        var emailService = new EmailService(_logger);

        PluginLog.Info($"[PublicAPI] RequestPasswordReset aufgerufen für Username: '{request.Username}', E-Mail: '{request.Email}'");
        if (string.IsNullOrWhiteSpace(request.Username) || string.IsNullOrWhiteSpace(request.Email))
        {
            return BadRequest(new { message = "Benutzername und E-Mail dürfen nicht leer sein." });
        }

        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null || !config.EnableEmail)
        {
            return StatusCode(StatusCodes.Status500InternalServerError, new { message = "E-Mail System ist deaktiviert." });
        }

        var userLink = config.TelegramUserLinks?.FirstOrDefault(l => 
            string.Equals(l.EmailAddress, request.Email, StringComparison.OrdinalIgnoreCase) && 
            string.Equals(l.JellyfinUsername, request.Username, StringComparison.OrdinalIgnoreCase));

        if (userLink == null || userLink.JellyfinUserId == Guid.Empty)
        {
            return BadRequest(new { message = "Die E-Mail-Adresse stimmt nicht mit dem Benutzernamen überein oder es ist keine E-Mail hinterlegt. Bitte wenden Sie sich an einen Administrator." });
        }

        try
        {
            var token = Guid.NewGuid().ToString("N");
            var activeUser = RiNnoFinPlugin.UserManager.GetUserByName(userLink.JellyfinUsername.Trim());
            PluginLog.Info($"[PublicAPI] RequestPasswordReset: GetUserByName('{userLink.JellyfinUsername.Trim()}') returned {(activeUser != null ? activeUser.Id.ToString() : "null")}");
            if (activeUser == null)
            {
                PluginLog.Warn($"[PublicAPI] RequestPasswordReset: Benutzer '{userLink.JellyfinUsername}' existiert in Jellyfin nicht mehr.");
                return BadRequest(new { message = "Benutzer existiert nicht mehr." });
            }
            ResetTokenManager.AddResetToken(token, activeUser.Id);

            var baseUrl = config.LoginBaseUrl?.TrimEnd('/') ?? "http://localhost:8096";
            var resetLink = $"{baseUrl}/sso/Telegram/reset?token={token}";

            string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplatePasswordReset)
                ? config.EmailTemplatePasswordReset.Replace("{resetLink}", resetLink).Replace("{username}", userLink.JellyfinUsername ?? "")
                : $@"
<div style='font-family: Arial, sans-serif; background-color: #060b14; padding: 40px 20px; color: #f8fafc;'>
    <div style='max-width: 520px; margin: 0 auto; background-color: #0d1623; border-radius: 16px; overflow: hidden; border: 1px solid #1e3a5f;'>
        <div style='background: #071020; padding: 36px 36px 32px; text-align: center; border-bottom: 1px solid #1e3a5f;'>
            <img src='https://i.imgur.com/ArlRygr.png' alt='RiNnoFin Media' style='height: 48px; width: auto; margin-bottom: 20px;' />
            <h1 style='font-size: 24px; font-weight: 800; color: #f8fafc; margin: 0;'>Passwort <span style='color: #f59e0b;'>zurücksetzen</span></h1>
        </div>
        <div style='padding: 32px 36px;'>
            <p style='font-size: 15px; color: #94a3b8; line-height: 1.6; margin-top: 0;'>Hallo <strong style='color: #e2e8f0;'>{userLink.JellyfinUsername}</strong>,</p>
            <p style='font-size: 15px; color: #94a3b8; line-height: 1.6;'>Jemand (vermutlich du) hat das Zurücksetzen des Passworts für deinen <strong>RiNnoFin Media</strong>-Account angefordert.</p>
            
            <div style='text-align: center; margin: 35px 0;'>
                <a href='{resetLink}' style='display: inline-block; background-color: #f59e0b; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; font-size: 16px;'>Neues Passwort festlegen &rarr;</a>
            </div>
            
            <div style='background-color: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 15px; border-radius: 8px; margin-bottom: 25px;'>
                <p style='margin: 0; color: #fca5a5; font-size: 13px; line-height: 1.5;'>Falls du diese Anfrage <strong>nicht</strong> gestellt hast, ignoriere diese E-Mail einfach. Dein Passwort bleibt sicher.</p>
            </div>
            
            <a href='https://t.me/+KZM7g40d8NkxNDIy' style='display: flex; align-items: center; background-color: rgba(0, 136, 204, 0.1); border: 1px solid rgba(0, 136, 204, 0.3); padding: 15px; border-radius: 8px; text-decoration: none; margin-bottom: 25px;'>
                <img src='https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/240px-Telegram_logo.svg.png' alt='Telegram' style='width: 40px; height: 40px; margin-right: 15px;' />
                <div>
                    <p style='margin: 0; color: #e2e8f0; font-weight: bold; font-size: 14px;'>Telegram Community beitreten</p>
                    <p style='margin: 5px 0 0; color: #94a3b8; font-size: 12px;'>News, Updates & Community</p>
                </div>
            </a>
            
            <hr style='border: none; border-top: 1px solid #1e293b; margin: 25px 0;' />
            <p style='font-size: 12px; color: #64748b; text-align: center; margin: 0;'>&copy; 2025 RiNnoFin Media. Alle Rechte vorbehalten.</p>
        </div>
    </div>
</div>";

            var subject = !string.IsNullOrWhiteSpace(config.EmailSubjectPasswordReset) ? config.EmailSubjectPasswordReset : "Passwort zurücksetzen - RiNnoFin Media";
            await emailService.SendEmailAsync(config, userLink.EmailAddress, subject, htmlBody);
            return Ok();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Senden der Reset-E-Mail.");
            return BadRequest(new { message = "Fehler beim Senden der E-Mail." });
        }
    }

    [HttpPost("ResetPassword")]
    [HttpPost("AcceptPasswordReset")] // Support both endpoints to be robust
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> ResetPassword(
        [FromBody] ResetPasswordRequest request,
        CancellationToken cancellationToken)
    {
        var userManager = RiNnoFinPlugin.UserManager;
        var cryptoProvider = RiNnoFinPlugin.CryptoProvider;
        var emailService = new EmailService(_logger);

        PluginLog.Info($"[PublicAPI] ResetPassword aufgerufen.");
        if (string.IsNullOrWhiteSpace(request.Token) || string.IsNullOrWhiteSpace(request.NewPassword) || string.IsNullOrWhiteSpace(request.Username) || string.IsNullOrWhiteSpace(request.Email))
        {
            return BadRequest(new { message = "Alle Felder müssen ausgefüllt sein (Token, Passwort, Benutzername, E-Mail)." });
        }

        if (!ResetTokenManager.TryGetResetToken(request.Token, out var userId))
        {
            PluginLog.Warn($"[PublicAPI] ResetPassword fehlgeschlagen: Ungültiger oder abgelaufener Reset-Link. Token: {request.Token}");
            return BadRequest(new { message = "Ungültiger oder abgelaufener Reset-Link." });
        }

        try
        {
            PluginLog.Info($"[PublicAPI] ResetPassword TryGetUserByName('{request.Username}')");
              var user = userManager.GetUserByName(request.Username);
              if (user != null) {
                  PluginLog.Info($"[PublicAPI] GetUserByName('{request.Username}') returned ID: {user.Id}");
              }
              if (user == null)
              {
                  PluginLog.Warn($"[PublicAPI] ResetPassword fehlgeschlagen: Benutzername '{request.Username}' nicht gefunden.");
                  return BadRequest(new { message = "Benutzer nicht gefunden." });
              }

              if (user.Id != userId)
              {
                  PluginLog.Warn($"[PublicAPI] ResetPassword fehlgeschlagen: Token gehört nicht zu diesem Benutzer. Token-ID: {userId}, User-ID: {user.Id}");
                  return BadRequest(new { message = "Dieser Reset-Link ist ungültig für den angegebenen Benutzernamen." });
              }

              var config = RiNnoFinPlugin.Instance?.Configuration;
            var userLink = config?.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == user.Id);
            if (userLink == null || !string.Equals(userLink.EmailAddress, request.Email, StringComparison.OrdinalIgnoreCase))
            {
                PluginLog.Warn($"[PublicAPI] ResetPassword fehlgeschlagen: E-Mail-Adresse stimmt nicht überein. Eingabe: '{request.Email}', Erwartet: '{userLink?.EmailAddress}'");
                return BadRequest(new { message = "Die eingegebene E-Mail-Adresse stimmt nicht mit dem Account überein." });
            }

            // All validations passed. Remove token now.
            ResetTokenManager.RemoveResetToken(request.Token);

            user.Password = cryptoProvider.CreatePasswordHash(request.NewPassword).ToString();
            await userManager.UpdateUserAsync(user).ConfigureAwait(false);

            if (config != null)
            {
                if (userLink != null && !string.IsNullOrEmpty(userLink.EmailAddress))
                {
                    string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplatePasswordChanged)
                        ? config.EmailTemplatePasswordChanged.Replace("{username}", user.Username)
                        : $@"
<div style='font-family: Arial, sans-serif; background-color: #060b14; padding: 40px 20px; color: #f8fafc;'>
    <div style='max-width: 520px; margin: 0 auto; background-color: #0d1623; border-radius: 16px; overflow: hidden; border: 1px solid #1e3a5f;'>
        <div style='background: #071020; padding: 36px 36px 32px; text-align: center; border-bottom: 1px solid #1e3a5f;'>
            <img src='https://i.imgur.com/ArlRygr.png' alt='RiNnoFin Media' style='height: 48px; width: auto; margin-bottom: 20px;' />
            <div style='margin-bottom: 15px;'><span style='font-size: 50px; color: #10b981;'>&#10003;</span></div>
            <h1 style='font-size: 24px; font-weight: 800; color: #f8fafc; margin: 0;'>Passwort <span style='color: #10b981;'>geändert</span></h1>
        </div>
        <div style='padding: 32px 36px;'>
            <p style='font-size: 15px; color: #94a3b8; line-height: 1.6; margin-top: 0;'>Hallo <strong style='color: #e2e8f0;'>{user.Username}</strong>,</p>
            <p style='font-size: 15px; color: #94a3b8; line-height: 1.6;'>Dein Passwort wurde erfolgreich geändert. Du kannst dich ab sofort mit deinen neuen Zugangsdaten anmelden.</p>
            
            <div style='background-color: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 15px; border-radius: 8px; margin: 30px 0;'>
                <p style='margin: 0; color: #fca5a5; font-size: 13px; line-height: 1.5;'>Falls du diese Änderung <strong>nicht</strong> selbst vorgenommen hast, kontaktiere bitte umgehend deinen Administrator!</p>
            </div>
            
            <a href='https://t.me/+KZM7g40d8NkxNDIy' style='display: flex; align-items: center; background-color: rgba(0, 136, 204, 0.1); border: 1px solid rgba(0, 136, 204, 0.3); padding: 15px; border-radius: 8px; text-decoration: none; margin-bottom: 25px;'>
                <img src='https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/240px-Telegram_logo.svg.png' alt='Telegram' style='width: 40px; height: 40px; margin-right: 15px;' />
                <div>
                    <p style='margin: 0; color: #e2e8f0; font-weight: bold; font-size: 14px;'>Telegram Community beitreten</p>
                    <p style='margin: 5px 0 0; color: #94a3b8; font-size: 12px;'>News, Updates & Community</p>
                </div>
            </a>
            
            <hr style='border: none; border-top: 1px solid #1e293b; margin: 25px 0;' />
            <p style='font-size: 12px; color: #64748b; text-align: center; margin: 0;'>&copy; 2025 RiNnoFin Media. Alle Rechte vorbehalten.</p>
        </div>
    </div>
</div>";
                    var subject = !string.IsNullOrWhiteSpace(config.EmailSubjectPasswordChanged) ? config.EmailSubjectPasswordChanged : "Passwort erfolgreich geändert";
                    await emailService.SendEmailAsync(config, userLink.EmailAddress, subject, htmlBody);
                }
            }

            return Ok(new { message = "Passwort erfolgreich geändert!" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Zurücksetzen des Passworts.");
            return BadRequest(new { message = "Interner Fehler beim Zurücksetzen." });
        }
    }

    [HttpGet("PortalConfig")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public async Task<IActionResult> GetPortalConfig()
    {
        var authService = HttpContext.RequestServices.GetService(typeof(MediaBrowser.Controller.Net.IAuthService)) as MediaBrowser.Controller.Net.IAuthService;
        if (authService == null) return StatusCode(500, "AuthService nicht verf�gbar");
        
        var authInfo = await authService.Authenticate(Request).ConfigureAwait(false);
        if (authInfo == null || authInfo.UserId == Guid.Empty) return Unauthorized(new { message = "Nicht autorisiert" });

        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null) return NotFound("Konfiguration nicht gefunden");

        var userManager = RiNnoFinPlugin.UserManager;
        var user = userManager?.GetUserById(authInfo.UserId);
        if (user == null) return Unauthorized(new { message = "Benutzer nicht gefunden" });

        var userLink = config.TelegramUserLinks?.FirstOrDefault(l => l.JellyfinUserId == authInfo.UserId);
        
        return Ok(new {
            EmailAddress = userLink?.EmailAddress ?? "",
            SubscribeEmailNewsletter = userLink?.SubscribeEmailNewsletter ?? true,
            SubscribeTelegramNewsletter = userLink?.SubscribeTelegramNewsletter ?? true,
            TelegramUsername = userLink?.TelegramUsername ?? ""
        });
    }

    public class PortalConfigUpdateRequest 
    {
        public string EmailAddress { get; set; } = string.Empty;
        public bool SubscribeEmailNewsletter { get; set; } = true;
        public bool SubscribeTelegramNewsletter { get; set; } = true;
    }

    [HttpPost("UpdatePortalConfig")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public async Task<IActionResult> UpdatePortalConfig([FromBody] PortalConfigUpdateRequest request)
    {
        var authService = HttpContext.RequestServices.GetService(typeof(MediaBrowser.Controller.Net.IAuthService)) as MediaBrowser.Controller.Net.IAuthService;
        if (authService == null) return StatusCode(500, "AuthService nicht verf�gbar");
        
        var authInfo = await authService.Authenticate(Request).ConfigureAwait(false);
        if (authInfo == null || authInfo.UserId == Guid.Empty) return Unauthorized(new { message = "Nicht autorisiert" });

        var config = RiNnoFinPlugin.Instance?.Configuration;
        if (config == null) return NotFound("Konfiguration nicht gefunden");

        var userManager = RiNnoFinPlugin.UserManager;
        var user = userManager?.GetUserById(authInfo.UserId);
        if (user == null) return Unauthorized(new { message = "Benutzer nicht gefunden" });

        if (config.TelegramUserLinks == null) config.TelegramUserLinks = new();

        var userLink = config.TelegramUserLinks.FirstOrDefault(l => l.JellyfinUserId == authInfo.UserId);
        if (userLink == null)
        {
            userLink = new Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.TelegramUserLink 
            {
                JellyfinUserId = authInfo.UserId,
                JellyfinUsername = user.Username ?? ""
            };
            config.TelegramUserLinks.Add(userLink);
        }

        userLink.EmailAddress = request.EmailAddress ?? "";
        userLink.SubscribeEmailNewsletter = request.SubscribeEmailNewsletter;
        userLink.SubscribeTelegramNewsletter = request.SubscribeTelegramNewsletter;
        
        RiNnoFinPlugin.Instance?.SaveConfiguration(config);
        
        return Ok(new { message = "Erfolgreich gespeichert" });
    }
}

