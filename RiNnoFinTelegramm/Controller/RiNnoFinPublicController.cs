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
        [FromServices] MediaBrowser.Controller.Library.IUserManager userManager,
        [FromServices] MediaBrowser.Model.Cryptography.ICryptoProvider cryptoProvider,
        [FromServices] EmailService emailService,
        [FromBody] AcceptInviteRequest request,
        CancellationToken cancellationToken)
    {
        PluginLog.Info($"[PublicAPI] AcceptInvite aufgerufen für Username: '{request.Username}' mit Token: '{request.Token}'");

        if (string.IsNullOrWhiteSpace(request.Token) || string.IsNullOrWhiteSpace(request.Username) || string.IsNullOrWhiteSpace(request.Password))
        {
            PluginLog.Warn("[PublicAPI] AcceptInvite abgelehnt: Eines der Pflichtfelder (Token, Username, Password) ist leer.");
            return BadRequest(new { message = "Alle Felder müssen ausgefüllt sein." });
        }

        if (!Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands.InviteTokenManager.TryGetAndRemoveInvite(request.Token, out var email, out var profileUserId))
        {
            PluginLog.Warn($"[PublicAPI] AcceptInvite abgelehnt: Token '{request.Token}' ist ungültig oder abgelaufen.");
            return BadRequest(new { message = "Ungültiger oder abgelaufener Einladungslink." });
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
                PluginLog.Info("[PublicAPI] E-Mail-Adresse erfolgreich verknüpft.");

                // Send Welcome Email
                string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplateWelcome)
                    ? config.EmailTemplateWelcome.Replace("{username}", user.Username)
                    : $@"
                    <div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
                        <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
                            <h2 style='color: #2563eb;'>Willkommen an Bord! 🍿</h2>
                            <p>Hallo <strong>{user.Username}</strong>,</p>
                            <p>Dein Account bei <strong>RiNnoFin Media</strong> wurde erfolgreich erstellt.</p>
                            <p>Du kannst dich ab sofort mit deinem gewählten Passwort auf all deinen Geräten einloggen.</p>
                            <br/>
                            <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Viel Spaß beim Streamen! 🍿 Dein RiNnoFin-Team</p>
                        </div>
                    </div>";

                try 
                {
                    PluginLog.Info($"[PublicAPI] Sende Willkommens-E-Mail an '{email}'...");
                    await emailService.SendEmailAsync(config, email, "Willkommen bei RiNnoFin Media! 🍿", htmlBody);
                    PluginLog.Info("[PublicAPI] Willkommens-E-Mail erfolgreich versendet.");
                } 
                catch (Exception emailEx) 
                {
                    PluginLog.Error(emailEx, "[PublicAPI] Konnte Willkommens-E-Mail nicht senden.");
                    _logger.LogError(emailEx, "[PublicAPI] Konnte Willkommens-E-Mail nicht senden."); 
                }
            }

            PluginLog.Info($"[PublicAPI] Registrierung für Benutzer '{request.Username}' erfolgreich abgeschlossen.");
            return Ok(new { message = "Account erfolgreich erstellt!" });
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

        var userLink = config.TelegramUserLinks?.FirstOrDefault(l => string.Equals(l.EmailAddress, request.Email, StringComparison.OrdinalIgnoreCase));
        if (userLink == null || userLink.JellyfinUserId == Guid.Empty)
        {
            return Ok(); // Aus Sicherheitsgründen immer OK
        }

        try
        {
            var token = Guid.NewGuid().ToString("N");
            ResetTokenManager.AddResetToken(token, userLink.JellyfinUserId);

            var baseUrl = config.LoginBaseUrl?.TrimEnd('/') ?? "http://localhost:8096";
            var resetLink = $"{baseUrl}/sso/Telegram/reset?token={token}";

            string htmlBody = !string.IsNullOrWhiteSpace(config.EmailTemplatePasswordReset)
                ? config.EmailTemplatePasswordReset.Replace("{resetLink}", resetLink).Replace("{username}", userLink.JellyfinUsername ?? "")
                : $@"
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
            return BadRequest(new { message = "Fehler beim Senden der E-Mail." });
        }
    }

    [HttpPost("ResetPassword")]
    [HttpPost("AcceptPasswordReset")] // Support both endpoints to be robust
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

        if (!ResetTokenManager.TryGetAndRemoveResetToken(request.Token, out var userId))
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
            return BadRequest(new { message = "Interner Fehler beim Zurücksetzen." });
        }
    }
}
