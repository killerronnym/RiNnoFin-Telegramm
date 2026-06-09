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

        var textStream = GetType().Assembly.GetManifestResourceStream(view.EmbeddedResourcePath);
        if (textStream == null)
        {
            return StatusCode(500, $"Ressource konnte nicht geladen werden: {view.EmbeddedResourcePath}");
        }

        using var reader = new StreamReader(textStream);
        var html = await reader.ReadToEndAsync();
        var replaced = html
            .Replace("{{SERVER_URL}}", serverUrl)
            .Replace("{{TELEGRAM_BOT_NAME}}", botUsername)
            .Replace("/*{{CUSTOM_CSS}}*/", _brandingOptions.CustomCss ?? string.Empty);

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
