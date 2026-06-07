using System;
using System.Collections.Generic;
using System.Net.Mime;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.RiNnoFinTelegramm.Classes;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using MediaBrowser.Controller.Providers;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Telegram.Bot;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Controller;

[ApiController]
[Route("api/{Controller}")]
[Authorize(Policy = "RequiresElevation")]
public class RiNnoFinConfigController : ControllerBase
{
    private readonly IProviderManager _providerManager;
    private readonly RequestService _requestService;

    public RiNnoFinConfigController(RequestService requestService, IProviderManager providerManager)
    {
        _requestService = requestService ?? throw new ArgumentNullException(nameof(requestService));
        _providerManager = providerManager ?? throw new ArgumentNullException(nameof(providerManager));
    }

    [HttpPost(nameof(ValidateBotToken))]
    [Produces(MediaTypeNames.Application.Json)]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<ActionResult<ValidateBotTokenResponse>> ValidateBotToken([FromBody] ValidateBotTokenRequest request)
    {
        try
        {
            var botClient = new TelegramBotClient(request.Token);
            using var ct = new CancellationTokenSource(TimeSpan.FromMilliseconds(10000));
            var botInfo = await botClient.GetMe(ct.Token);

            return Ok(new ValidateBotTokenResponse { Ok = true, BotUsername = botInfo.Username! });
        }
        catch (Exception)
        {
            return StatusCode(500, new ValidateBotTokenResponse { ErrorMessage = "Ungültiger Token" });
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
}

public class AddRequestRequest
{
    public string ImdbId { get; set; } = string.Empty;
}
