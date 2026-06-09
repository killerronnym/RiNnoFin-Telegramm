using System.Collections.Generic;
using System.Xml.Serialization;
using Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;
using MediaBrowser.Model.Plugins;

namespace Jellyfin.Plugin.RiNnoFinTelegramm;

public class PluginConfiguration : BasePluginConfiguration
{
    public string? LoginBaseUrl { get; set; }

    public string BotToken { get; set; } = Constants.DefaultBotToken;

    public string BotUsername { get; set; } = "INVALID_BOT_TOKEN";

    public bool EnableBotService { get; set; } = true;

    public List<string> AdminUserNames { get; set; } = [];

    public int MaxSessionCount { get; set; } = -1;

    public string ForcedUrlScheme { get; set; } = "none";



    // Neue SMTP & E-Mail Einstellungen
    public bool EnableEmail { get; set; } = false;
    public string SmtpServer { get; set; } = "smtp.strato.de";
    public int SmtpPort { get; set; } = 587;
    public string SmtpUsername { get; set; } = "RinnoFin@brainless-rp.de";
    public string SmtpPassword { get; set; } = string.Empty;
    public string EmailSenderAddress { get; set; } = "RinnoFin@brainless-rp.de";
    public string EmailSenderName { get; set; } = "Rinno Einladungssystem";
    public bool SmtpUseSsl { get; set; } = true;

    // E-Mail Vorlagen
    public string EmailTemplateInvite { get; set; } = @"
<div style='font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;'>
    <div style='background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;'>
        <h2 style='color: #2563eb;'>Du wurdest eingeladen! 🍿</h2>
        <p>Hallo!</p>
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
        <p>Du kannst dich ab sofort mit deinem gewählten Passwort auf all deinen Geräten einloggen.</p>
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

    [XmlArray("TelegramGroups")]
    [XmlArrayItem(typeof(TelegramGroup), ElementName = "TelegramGroups")]
    public List<TelegramGroup> TelegramGroups { get; set; } = [];

    [XmlArray("TelegramUserLinks")]
    [XmlArrayItem(typeof(TelegramUserLink), ElementName = "TelegramUserLinks")]
    public List<TelegramUserLink> TelegramUserLinks { get; set; } = [];
}
