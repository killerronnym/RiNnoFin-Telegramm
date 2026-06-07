using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Providers;
using MediaBrowser.Model.Entities;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Classes;

public static class MetadataResolver
{
    public static async Task<(string title, int? year, bool found)> FindRemoteMetadataAsync(IProviderManager providerManager,
        string imdbId, CancellationToken cancellationToken)
    {
        var movieInfo = new MovieInfo { Name = imdbId, ProviderIds = { { nameof(MetadataProvider.Imdb), imdbId } } };
        var movieQuery = new RemoteSearchQuery<MovieInfo> { SearchInfo = movieInfo, IncludeDisabledProviders = false };

        var seriesInfo = new SeriesInfo { Name = imdbId, ProviderIds = { { nameof(MetadataProvider.Imdb), imdbId } } };
        var seriesQuery = new RemoteSearchQuery<SeriesInfo> { SearchInfo = seriesInfo, IncludeDisabledProviders = false };

        try
        {
            var movieTask = providerManager.GetRemoteSearchResults<Movie, MovieInfo>(movieQuery, cancellationToken);
            var seriesTask = providerManager.GetRemoteSearchResults<Series, SeriesInfo>(seriesQuery, cancellationToken);

            await Task.WhenAll(movieTask, seriesTask).ConfigureAwait(false);

            var allResults = seriesTask.Result.Concat(movieTask.Result).ToArray();
            var firstOrDefault = allResults
                                     .Where(r => r.ProviderIds.Values.Any(id => string.Equals(id, imdbId, StringComparison.OrdinalIgnoreCase)))
                                     .OrderByDescending(r => r.ProductionYear.HasValue)
                                     .FirstOrDefault()
                                 ?? allResults.FirstOrDefault();

            if (firstOrDefault != null)
            {
                return (firstOrDefault.Name, firstOrDefault.ProductionYear, true);
            }
        }
        catch (Exception e)
        {
            Console.WriteLine("FindRemoteMetadataAsync Exception: {0}", e);
        }

        return (string.Empty, null, false);
    }
}
