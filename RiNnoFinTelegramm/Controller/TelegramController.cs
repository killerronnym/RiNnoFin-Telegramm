using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Mime;
using System.Threading.Tasks;
using Jellyfin.Plugin.RiNnoFinTelegramm.Classes;
using Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;
using MediaBrowser.Common.Configuration;
using MediaBrowser.Controller.Library;
using MediaBrowser.Controller.Session;
using MediaBrowser.Model.Branding;
using MediaBrowser.Model.Cryptography;
using MediaBrowser.Model.Net;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;

using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using Telegram.Bot;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Controller;

[ApiController]
[Route("sso/{Controller}")]
public class TelegramController : ControllerBase
{
    private static readonly string[] EntryPoints = ["index.html", "login", "login.html"];

    private readonly BrandingOptions _brandingOptions;
    private readonly RiNnoFinPlugin _instance;
    private readonly TelegramLoginService _telegramLoginService;
    private readonly TelegramBotClientWrapper _botClientWrapper;

    public TelegramController(
        ISessionManager sessionManager,
        IUserManager userManager,
        ICryptoProvider cryptoProvider,
        IConfigurationManager configurationManager,
        TelegramBotClientWrapper botClientWrapper)
    {
        _instance = RiNnoFinPlugin.Instance ?? throw new ArgumentException("RiNnoFinPlugin Instanz ist null.");
        _telegramLoginService = new TelegramLoginService(_instance, sessionManager, userManager, cryptoProvider);
        _brandingOptions = configurationManager.GetConfiguration<BrandingOptions>("branding");
        _botClientWrapper = botClientWrapper;
    }

    [AllowAnonymous]
    [HttpGet("{fileName=Login}")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> Files([FromRoute] string fileName)
    {
        var lowerFilename = fileName.ToLower();
        if (EntryPoints.Contains(lowerFilename))
        {
            lowerFilename = "index";
        }
        else if (lowerFilename == "resetpassword")
        {
            lowerFilename = "reset";
        }

        var view = Constants.LoginFiles.FirstOrDefault(extra => extra.Name == lowerFilename);
        if (view == null)
        {
            return NotFound($"Ressource nicht gefunden: '{lowerFilename}'");
        }

        var mimeType = MimeTypes.GetMimeType(view.EmbeddedResourcePath);
        if (!view.NeedsReplacement)
        {
            if (view.Name == Constants.DefaultUserImageExtraFile)
            {
                var customLogoPath = Path.Combine(_instance.ApplicationPaths.PluginsPath, Constants.PluginName, Constants.PluginDataFolder, "CustomLogo.png");
                if (System.IO.File.Exists(customLogoPath))
                {
                    return PhysicalFile(customLogoPath, mimeType);
                }
            }

            var binaryStream = GetType().Assembly.GetManifestResourceStream(view.EmbeddedResourcePath);
            if (binaryStream == null)
            {
                return StatusCode(500, $"Ressource konnte nicht geladen werden: {view.EmbeddedResourcePath}");
            }

            return File(binaryStream, mimeType);
        }

        var botUsername = _instance.Configuration.BotUsername;
        var serverUrl = Request.GetRequestBase(_instance.Configuration);

        var config = _instance.Configuration;
        string html = string.Empty;
        bool loadedFromConfig = false;

        if (lowerFilename == "index" && !string.IsNullOrWhiteSpace(config.HtmlTemplateLogin))
        {
            html = config.HtmlTemplateLogin;
            loadedFromConfig = true;
        }
        else if (lowerFilename == "invite" && !string.IsNullOrWhiteSpace(config.HtmlTemplateInvite))
        {
            html = config.HtmlTemplateInvite;
            loadedFromConfig = true;
        }
        else if (lowerFilename == "forgot" && !string.IsNullOrWhiteSpace(config.HtmlTemplateForgot))
        {
            html = config.HtmlTemplateForgot;
            loadedFromConfig = true;
        }
        else if (lowerFilename == "reset" && !string.IsNullOrWhiteSpace(config.HtmlTemplateReset))
        {
            html = config.HtmlTemplateReset;
            loadedFromConfig = true;
        }
        else if (lowerFilename == "login.css" && !string.IsNullOrWhiteSpace(config.HtmlTemplateLoginCss))
        {
            html = config.HtmlTemplateLoginCss;
            loadedFromConfig = true;
        }
        else if (lowerFilename == "login.js" && !string.IsNullOrWhiteSpace(config.HtmlTemplateLoginJs))
        {
            html = config.HtmlTemplateLoginJs;
            loadedFromConfig = true;
        }

        if (!loadedFromConfig)
        {
            var textStream = GetType().Assembly.GetManifestResourceStream(view.EmbeddedResourcePath);
            if (textStream == null)
            {
                return StatusCode(500, $"Ressource konnte nicht geladen werden: {view.EmbeddedResourcePath}");
            }
            using var reader = new StreamReader(textStream);
            html = await reader.ReadToEndAsync();
        }
        var theme = _instance.Configuration.RegistrationTheme ?? "jellyfin";
        var themeCss = string.Empty;
        if (theme == "dark")
        {
            themeCss = @"
:root {
    --primary-gradient: linear-gradient(135deg, #4b5563 0%, #111827 100%);
    --bg-dark: #030712;
    --card-bg: rgba(17, 24, 39, 0.8);
    --border-color: rgba(255, 255, 255, 0.05);
}";
        }
        else if (theme == "light")
        {
            themeCss = @"
:root {
    --primary-gradient: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
    --bg-dark: #f3f4f6;
    --card-bg: rgba(255, 255, 255, 0.95);
    --border-color: rgba(0, 0, 0, 0.08);
    --text-primary: #1f2937;
    --text-secondary: #4b5563;
}
body::before, body::after { display: none; }
.loginCard { box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.8); }
.emby-input { background: rgba(0, 0, 0, 0.03) !important; border-color: rgba(0, 0, 0, 0.1) !important; color: #1f2937 !important; }
.emby-input:focus { border-color: #3b82f6 !important; }
.inputLabel { color: rgba(0, 0, 0, 0.6) !important; }
.emby-button.block { background: rgba(0, 0, 0, 0.03) !important; border-color: rgba(0, 0, 0, 0.08) !important; color: #1f2937 !important; }
.emby-button.block:hover { background: rgba(0, 0, 0, 0.06) !important; }";
        }
        else if (theme == "blue")
        {
            themeCss = @"
:root {
    --primary-gradient: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
    --bg-dark: #083344;
    --card-bg: rgba(15, 23, 42, 0.7);
    --border-color: rgba(6, 182, 212, 0.15);
}";
        }
        else if (theme == "green")
        {
            themeCss = @"
:root {
    --primary-gradient: linear-gradient(135deg, #10b981 0%, #059669 100%);
    --bg-dark: #064e3b;
    --card-bg: rgba(2, 48, 32, 0.7);
    --border-color: rgba(16, 185, 129, 0.15);
}";
        }
        else if (theme == "red")
        {
            themeCss = @"
:root {
    --primary-gradient: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%);
    --bg-dark: #450a0a;
    --card-bg: rgba(24, 9, 9, 0.75);
    --border-color: rgba(239, 68, 68, 0.15);
}";
        }

        var replaced = html
            .Replace("{{SERVER_URL}}", serverUrl)
            .Replace("{{TELEGRAM_BOT_NAME}}", botUsername)
            .Replace("/*{{CUSTOM_CSS}}*/", themeCss + "\n" + (_brandingOptions.CustomCss ?? string.Empty));

        return Content(replaced, mimeType);
    }

    [AllowAnonymous]
    [HttpPost(nameof(Authenticate))]
    [Produces(MediaTypeNames.Application.Json)]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<ActionResult<SsoAuthenticationResult>> Authenticate([FromBody] SortedDictionary<string, string> authData)
    {
        var requestBase = Request.GetRequestBase(_instance.Configuration);

        try
        {
            var telegramAuth = _telegramLoginService.CheckTelegramAuthorizationImpl(authData);
            if (!telegramAuth.Ok)
            {
                return Unauthorized(new SsoAuthenticationResult { ServerAddress = requestBase, ErrorMessage = telegramAuth.ErrorMessage });
            }

            var user = await _telegramLoginService.GetOrCreateJellyUser(authData);
            var authResult = await _telegramLoginService.DoJellyUserAuth(Request, user);

            // Send confirmation message to Telegram
            if (authData.TryGetValue("id", out var idStr) && long.TryParse(idStr, out var telegramChatId))
            {
                var client = _botClientWrapper.Client;
                if (client != null)
                {
                    try
                    {
                        var userName = authData.TryGetValue("username", out var name) ? name : user.Username;
                        var messageText = $"✅ *Verknüpfung erfolgreich!*\n\nDein Telegram-Konto @{userName} wurde erfolgreich mit dem Jellyfin-Konto *{user.Username}* verknüpft.\n\nDu kannst jetzt alle Bot-Befehle nutzen!";
                        await client.SendMessage(
                            telegramChatId,
                            messageText,
                            parseMode: global::Telegram.Bot.Types.Enums.ParseMode.Markdown);
                    }
                    catch
                    {
                        // Ignore message sending failures to avoid blocking login itself
                    }
                }
            }

            return Ok(new SsoAuthenticationResult { ServerAddress = requestBase, Ok = true, AuthenticatedUser = authResult });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new SsoAuthenticationResult { ServerAddress = requestBase, ErrorMessage = ex.Message });
        }
    }
}
