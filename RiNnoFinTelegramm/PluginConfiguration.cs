using System;
using System.Collections.Generic;
using System.Xml.Serialization;
using Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;
using MediaBrowser.Model.Plugins;

namespace Jellyfin.Plugin.RiNnoFinTelegramm;

public class PluginConfiguration : BasePluginConfiguration
{
    public string PredefinedDeactivateReasons { get; set; } = "Verstoß gegen die Nutzungsbedingungen\nAccount längere Zeit inaktiv\nAuf eigenen Wunsch deaktiviert\nZahlung ausstehend";
    public string PredefinedDeleteReasons { get; set; } = "Verstoß gegen die Nutzungsbedingungen\nAccount längere Zeit inaktiv\nAuf eigenen Wunsch gelöscht\nSicherheitsbedenken";

    public string? LoginBaseUrl { get; set; }

    public string BotToken { get; set; } = Constants.DefaultBotToken;

    public string BotUsername { get; set; } = "INVALID_BOT_TOKEN";

    public bool EnableBotService { get; set; } = true;

    public List<string> AdminUserNames { get; set; } = [];

    public int MaxSessionCount { get; set; } = -1;

    public string ForcedUrlScheme { get; set; } = "none";

    public string? DefaultProfileUserId { get; set; }

    public string RegistrationTheme { get; set; } = "jellyfin";
    public DateTime LastEmailNewsletterSent { get; set; } = DateTime.UtcNow;

    public string TmdbApiKey { get; set; } = string.Empty;



    // Neue SMTP & E-Mail Einstellungen
    public bool EnableEmail { get; set; } = false;
    public string SmtpServer { get; set; } = "smtp.strato.de";
    public int SmtpPort { get; set; } = 587;
    public string SmtpUsername { get; set; } = "RinnoFin@brainless-rp.de";
    public string SmtpPassword { get; set; } = string.Empty;
    public string EmailSenderAddress { get; set; } = "RinnoFin@brainless-rp.de";
    public string EmailSenderName { get; set; } = "Rinno Einladungssystem";
    public bool SmtpUseSsl { get; set; } = true;

    // E-Mail Vorlagen (Betreff)
    public string EmailSubjectInvite { get; set; } = "Du wurdest zu RiNnoFin Media eingeladen! 🍿";
    public string EmailSubjectWelcome { get; set; } = "Willkommen bei RiNnoFin Media! 🐧🎬";
    public string EmailSubjectPasswordReset { get; set; } = "Passwort zurücksetzen - RiNnoFin Media 🔑";
    public string EmailSubjectPasswordChanged { get; set; } = "Passwort erfolgreich geändert ✅";
    public string EmailSubjectAccountEnabled { get; set; } = "Dein RiNnoFin Account wurde wieder aktiviert! 🎉";
    public string EmailSubjectAccountDisabled { get; set; } = "Dein RiNnoFin Account wurde deaktiviert ⚠️";
    public string EmailSubjectAccountDeleted { get; set; } = "Dein RiNnoFin Account wurde gelöscht 🗑️";
    public string EmailSubjectExpirationWarning { get; set; } = "Dein Account läuft bald ab ⏳";
    public string EmailSubjectAccountExpired { get; set; } = "Account abgelaufen ⚠️";
    public string EmailSubjectNewsletterMovies { get; set; } = "Neue Filme auf RiNnoFin! 🍿";
    public string EmailSubjectNewsletterSeries { get; set; } = "Neue Serien & Episoden! 📺";
    public string EmailSubjectRueckblick { get; set; } = "Dein wöchentlicher RiNnoFin Rückblick 📺";
    public string EmailSubjectAnnounce { get; set; } = "Wichtige Ankündigung! 📢";

    // E-Mail Vorlagen (HTML-Inhalt)
    public string EmailTemplateInvite { get; set; } = @"
<div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
        <h2 style='color: #2563eb;'>Du wurdest eingeladen! 🍿</h2>
        <p>Hallo <strong>{username}</strong>,</p>
        <p>Du wurdest eingeladen, Teil unserer <strong>RiNnoFin Media</strong> Community zu werden.</p>
        <p>Klicke auf den untenstehenden Button, um deinen Benutzernamen und dein Passwort festzulegen:</p>
        <div style='text-align: center; margin: 30px 0;'>
            <a href='{inviteLink}' style='background-color: #2563eb; color: #fff; padding: 14px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;'>Account erstellen</a>
        </div>
        <p style='color: #6b7280; font-size: 13px;'>Dieser Link ist einmalig gültig.</p>
        <hr style='border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;' />
        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
    </div>
</div>";

    public string EmailTemplateWelcome { get; set; } = @"
<div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
        <h2 style='color: #2563eb;'>Willkommen an Bord! 🐧🎬</h2>
        <p>Hallo <strong>{username}</strong>,</p>
        <p>Dein Account bei <strong>RiNnoFin Media</strong> wurde erfolgreich erstellt.</p>
        <div style='background-color: #f8fafc; padding: 15px; border-radius: 6px; margin: 20px 0; border: 1px solid #e2e8f0;'>
            <h3 style='margin-top: 0; color: #334155; font-size: 16px;'>Deine Login-Daten:</h3>
            <p style='margin: 5px 0;'><strong>Benutzername:</strong> {username}</p>
            <p style='margin: 5px 0;'><strong>Passwort:</strong> Das von dir gewählte Passwort</p>
            <p style='margin: 5px 0;'><strong>Server-URL:</strong> <a href='{serverUrl}'>{serverUrl}</a></p>
        </div>
        <p>Du kannst dich ab sofort auf all deinen Geräten einloggen (z.B. im Browser, auf dem Smart-TV oder in der mobilen App).</p>
        <br/>
        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Viel Spaß beim Streamen! 🍿 Dein RiNnoFin-Team</p>
    </div>
</div>";

    public string EmailTemplatePasswordReset { get; set; } = @"
<div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
        <h2 style='color: #2563eb;'>Passwort zurücksetzen 🔑</h2>
        <p>Hallo <strong>{username}</strong>,</p>
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

    public string EmailTemplatePasswordChanged { get; set; } = @"
<div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
        <h2 style='color: #22c55e;'>Passwort geändert ✅</h2>
        <p>Hallo <strong>{username}</strong>,</p>
        <p>Dein Passwort wurde erfolgreich geändert.</p>
        <p>Falls du dies nicht selbst getan hast, kontaktiere bitte umgehend deinen Administrator!</p>
        <br/>
        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
    </div>
</div>";

    public string EmailTemplateAccountEnabled { get; set; } = @"
<div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
        <h2 style='color: #22c55e;'>🎉 Dein RinnoFin Account wurde wieder aktiviert!</h2>
        <p>Hallo <strong>{username}</strong>,</p>
        <p>Dein Account wurde soeben reaktiviert. Du kannst dich nun wieder einloggen.</p>
        <br/>
        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
    </div>
</div>";

    public string EmailTemplateAccountDisabled { get; set; } = @"
<div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
        <h2 style='color: #ef4444;'>⚠️ Dein RinnoFin Account wurde deaktiviert</h2>
        <p>Hallo <strong>{username}</strong>,</p>
        <p>Dein Account wurde deaktiviert. Bitte kontaktiere einen Administrator für weitere Informationen.</p>
        <br/>
        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
    </div>
</div>";

    public string EmailTemplateAccountDeleted { get; set; } = @"
<div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
        <h2 style='color: #ef4444;'>Account gelöscht 🗑️</h2>
        <p>Hallo <strong>{username}</strong>,</p>
        <p>Dein Account bei RiNnoFin Media wurde endgültig gelöscht. Alle deine persönlichen Daten wurden entfernt.</p>
        <br/>
        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
    </div>
</div>";

    public string EmailTemplateExpirationWarning { get; set; } = @"
<!DOCTYPE html>
<html lang=""de"">
<head>
<meta charset=""UTF-8"">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
  body { font-family: 'Inter', Arial, sans-serif; background-color: #060b14; padding: 40px 20px; margin: 0; }
  .wrapper { max-width: 520px; margin: 0 auto; }
  .card { background: #0d1623; border-radius: 16px; overflow: hidden; border: 1px solid #1e3a5f; }
  .header { background: linear-gradient(180deg, #070d1a 0%, #0d1623 100%); padding: 36px 36px 32px; text-align: center; }
  .logo-wrap { margin-bottom: 28px; }
  .logo-wrap img { height: 48px; width: auto; }
  .icon-ring {
    width: 72px; height: 72px; margin: 0 auto 20px; border-radius: 50%;
    background: linear-gradient(135deg, rgba(234, 179, 8, 0.15), rgba(161, 98, 7, 0.1));
    border: 1px solid rgba(234, 179, 8, 0.4);
    display: flex; align-items: center; justify-content: center;
  }
  .headline { font-size: 27px; font-weight: 800; color: #f8fafc; line-height: 1.25; margin-bottom: 10px; }
  .headline span { color: #eab308; }
  .body { padding: 32px 36px; }
  .message-box { background: rgba(234, 179, 8, 0.05); border: 1px solid rgba(234, 179, 8, 0.2); border-radius: 12px; padding: 24px; margin-bottom: 32px; }
  .message-box p { font-size: 14px; color: #cbd5e1; line-height: 1.75; margin-bottom: 15px; }
  .message-box p:last-child { margin-bottom: 0; }
  .message-box strong { color: #f8fafc; }
  .footer-divider { height: 1px; background: #1e293b; margin-bottom: 20px; }
  .footer { display: flex; align-items: center; justify-content: space-between; }
  .footer img { height: 20px; width: auto; opacity: 0.4; }
  .footer-text { font-size: 11px; color: #1e3a5f; text-align: right; }
</style>
</head>
<body>
<div class=""wrapper"">
  <div class=""card"">
    <div class=""header"">
      <div class=""logo-wrap""><img src=""https://i.imgur.com/ArlRygr.png"" alt=""RiNnoFin Media"" /></div>
      <div class=""icon-ring"">
        <svg width=""36"" height=""36"" viewBox=""0 0 24 24"" fill=""none"" stroke=""#eab308"" stroke-width=""2"" stroke-linecap=""round"" stroke-linejoin=""round"">
          <circle cx=""12"" cy=""12"" r=""10""></circle>
          <polyline points=""12 6 12 12 16 14""></polyline>
        </svg>
      </div>
      <h1 class=""headline"">Account läuft <span>bald ab</span></h1>
    </div>
    <div class=""body"">
      <div class=""message-box"">
        <p>Hallo <strong>{username}</strong>,</p>
        <p>Dein Zugang zu RiNnoFin Media läuft in <strong>{daysLeft} Tag(en)</strong> ab (am {expirationDate}).</p>
        <p>Bitte wende dich an einen Administrator, falls du weiterhin Zugriff benötigst.</p>
      </div>
      <div class=""footer-divider""></div>
      <div class=""footer"">
        <img src=""https://i.imgur.com/ArlRygr.png"" alt=""RiNnoFin Media"" />
        <div class=""footer-text"">© 2026 RiNnoFin Media<br>Alle Rechte vorbehalten.</div>
      </div>
    </div>
  </div>
</div>
</body>
</html>";

    public string EmailTemplateAccountExpired { get; set; } = @"
<!DOCTYPE html>
<html lang=""de"">
<head>
<meta charset=""UTF-8"">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
  body { font-family: 'Inter', Arial, sans-serif; background-color: #060b14; padding: 40px 20px; margin: 0; }
  .wrapper { max-width: 520px; margin: 0 auto; }
  .card { background: #0d1623; border-radius: 16px; overflow: hidden; border: 1px solid #1e3a5f; }
  .header { background: linear-gradient(180deg, #070d1a 0%, #0d1623 100%); padding: 36px 36px 32px; text-align: center; }
  .logo-wrap { margin-bottom: 28px; }
  .logo-wrap img { height: 48px; width: auto; }
  .icon-ring {
    width: 72px; height: 72px; margin: 0 auto 20px; border-radius: 50%;
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(153, 27, 27, 0.1));
    border: 1px solid rgba(239, 68, 68, 0.4);
    display: flex; align-items: center; justify-content: center;
  }
  .headline { font-size: 27px; font-weight: 800; color: #f8fafc; line-height: 1.25; margin-bottom: 10px; }
  .headline span { color: #ef4444; }
  .body { padding: 32px 36px; }
  .message-box { background: rgba(239, 68, 68, 0.05); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 12px; padding: 24px; margin-bottom: 32px; }
  .message-box p { font-size: 14px; color: #cbd5e1; line-height: 1.75; margin-bottom: 15px; }
  .message-box p:last-child { margin-bottom: 0; }
  .message-box strong { color: #f8fafc; }
  .footer-divider { height: 1px; background: #1e293b; margin-bottom: 20px; }
  .footer { display: flex; align-items: center; justify-content: space-between; }
  .footer img { height: 20px; width: auto; opacity: 0.4; }
  .footer-text { font-size: 11px; color: #1e3a5f; text-align: right; }
</style>
</head>
<body>
<div class=""wrapper"">
  <div class=""card"">
    <div class=""header"">
      <div class=""logo-wrap""><img src=""https://i.imgur.com/ArlRygr.png"" alt=""RiNnoFin Media"" /></div>
      <div class=""icon-ring"">
        <svg width=""36"" height=""36"" viewBox=""0 0 24 24"" fill=""none"" stroke=""#ef4444"" stroke-width=""2"" stroke-linecap=""round"" stroke-linejoin=""round"">
          <circle cx=""12"" cy=""12"" r=""10""></circle>
          <line x1=""12"" y1=""8"" x2=""12"" y2=""12""></line>
          <line x1=""12"" y1=""16"" x2=""12.01"" y2=""16""></line>
        </svg>
      </div>
      <h1 class=""headline"">Account <span>abgelaufen</span></h1>
    </div>
    <div class=""body"">
      <div class=""message-box"">
        <p>Hallo <strong>{username}</strong>,</p>
        <p>Dein Zugang zu RiNnoFin Media ist am {expirationDate} abgelaufen und der Account wurde deaktiviert.</p>
        <p>Bitte kontaktiere einen Administrator, um deinen Zugang zu verlängern.</p>
      </div>
      <div class=""footer-divider""></div>
      <div class=""footer"">
        <img src=""https://i.imgur.com/ArlRygr.png"" alt=""RiNnoFin Media"" />
        <div class=""footer-text"">© 2026 RiNnoFin Media<br>Alle Rechte vorbehalten.</div>
      </div>
    </div>
  </div>
</div>
</body>
</html>";

    public string EmailTemplateNewsletterMovies { get; set; } = @"
<div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
        <h2 style='color: #8b5cf6;'>Neue Filme auf RiNnoFin! 🍿</h2>
        <p>Hallo <strong>{username}</strong>,</p>
        <p>Es gibt neue Filme auf dem Server:</p>
        <div style='background: #f9fafb; padding: 15px; border-radius: 8px; margin: 20px 0;'>
            {content}
        </div>
        <div style='text-align: center; margin: 30px 0;'>
            <a href='{serverUrl}' style='background-color: #8b5cf6; color: #fff; padding: 14px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;'>Jetzt ansehen</a>
        </div>
        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
    </div>
</div>";

    public string EmailTemplateNewsletterSeries { get; set; } = @"
<div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
        <h2 style='color: #10b981;'>Neue Serien & Episoden! 📺</h2>
        <p>Hallo <strong>{username}</strong>,</p>
        <p>Es gibt neue Serien auf dem Server:</p>
        <div style='background: #f9fafb; padding: 15px; border-radius: 8px; margin: 20px 0;'>
            {content}
        </div>
        <div style='text-align: center; margin: 30px 0;'>
            <a href='{serverUrl}' style='background-color: #10b981; color: #fff; padding: 14px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;'>Jetzt ansehen</a>
        </div>
        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
    </div>
</div>";

    public string EmailTemplateRueckblick { get; set; } = @"
<div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
        <h2 style='color: #0ea5e9;'>Dein Wochenrückblick 📺</h2>
        <p>Hallo <strong>{username}</strong>,</p>
        <p>Hier ist eine Zusammenfassung der Highlights, die du vielleicht verpasst hast:</p>
        <div style='background: #f9fafb; padding: 15px; border-radius: 8px; margin: 20px 0;'>
            {content}
        </div>
        <div style='text-align: center; margin: 30px 0;'>
            <a href='{serverUrl}' style='background-color: #0ea5e9; color: #fff; padding: 14px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;'>Jetzt stöbern</a>
        </div>
        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
    </div>
</div>";

    public string EmailTemplateAnnounce { get; set; } = @"
<div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
        <h2 style='color: #f59e0b;'>Wichtige Ankündigung 📢</h2>
        <p>Hallo <strong>{username}</strong>,</p>
        <div style='background: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0; color: #92400e; font-size: 15px; line-height: 1.5;'>
            {message}
        </div>
        <p style='color: #9ca3af; font-size: 12px; text-align: center;'>Dein RiNnoFin-Team</p>
    </div>
</div>";

    [XmlArray("TelegramGroups")]
    [XmlArrayItem(typeof(TelegramGroup), ElementName = "TelegramGroups")]
    public List<TelegramGroup> TelegramGroups { get; set; } = [];

    [XmlArray("TelegramUserLinks")]
    [XmlArrayItem(typeof(TelegramUserLink), ElementName = "TelegramUserLinks")]
    public List<TelegramUserLink> TelegramUserLinks { get; set; } = [];

    public List<PersistedInvite> PersistedInvites { get; set; } = [];
    public List<PersistedResetToken> PersistedResetTokens { get; set; } = [];

    // HTML-Vorlagen
    public string HtmlTemplateLogin { get; set; } = string.Empty;
    public string HtmlTemplateInvite { get; set; } = string.Empty;
    public string HtmlTemplateForgot { get; set; } = string.Empty;
    public string HtmlTemplateReset { get; set; } = string.Empty;
    public string HtmlTemplateLoginCss { get; set; } = string.Empty;
    public string HtmlTemplateLoginJs { get; set; } = string.Empty;

    public string ExpirationAction { get; set; } = "Disable"; // "Disable" or "Delete"
}

public class PersistedInvite
{
    public string Token { get; set; } = string.Empty;
    public string Email { get; set; } = string.Empty;
    public string? Username { get; set; }
    public string? ProfileUserId { get; set; }
    public int? ExpirationDays { get; set; }
}

public class PersistedResetToken
{
    public string Token { get; set; } = string.Empty;
    public Guid JellyfinUserId { get; set; }
}
