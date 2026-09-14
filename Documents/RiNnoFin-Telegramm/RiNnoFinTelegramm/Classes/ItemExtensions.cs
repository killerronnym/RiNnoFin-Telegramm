using System;
using System.Linq;
using Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Entities.Audio;
using MediaBrowser.Model.Entities;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Classes;

internal static class ItemExtensions
{
    internal static string GetDisplayText(this BaseItem item)
    {
        var displayText = item.Name;
        if (item.ProductionYear.HasValue)
        {
            displayText += $" ({item.ProductionYear.Value})";
        }

        if (item is Movie movie)
        {
            displayText += " [Film";
            var minuteDuration = movie.RunTimeTicks.HasValue ? (int)(movie.RunTimeTicks.Value / TimeSpan.TicksPerMinute) : 0;
            if (minuteDuration > 0)
            {
                displayText += $", {minuteDuration} Min\\.";
            }
            displayText += "]";
        }
        else if (item is Series series)
        {
            var episodeCount = series.GetRecursiveChildren().OfType<Episode>().Count();
            var seasonCount = series.GetRecursiveChildren().OfType<Season>().Count();
            displayText += $" [Serie, {seasonCount} Staffeln, {episodeCount} Episoden]";
        }
        else if (item is Season season)
        {
            var episodeCount = season.GetRecursiveChildren().OfType<Episode>().Count();
            if (!string.IsNullOrEmpty(season.SeriesName))
            {
                displayText = $"{season.SeriesName} - {displayText}";
            }
            displayText += $" [Staffel {season.IndexNumber ?? 0}, {episodeCount} Episoden]";
        }
        else if (item is Episode episode)
        {
            if (!string.IsNullOrEmpty(episode.SeriesName))
            {
                displayText = $"{episode.SeriesName} - {displayText}";
            }
            displayText += $" [Staffel {episode.ParentIndexNumber ?? 0}, Episode {episode.IndexNumber ?? 0}]";
        }
        else if (item is Audio audio)
        {
            var artist = audio.Artists.FirstOrDefault();
            if (!string.IsNullOrEmpty(artist))
            {
                displayText = $"{artist} - {displayText}";
            }
            if (!string.IsNullOrEmpty(audio.Album))
            {
                displayText += $" (Album: {audio.Album})";
            }
            displayText += " [Musik]";
        }
        else if (item is MusicAlbum album)
        {
            var artist = album.Artists.FirstOrDefault();
            if (!string.IsNullOrEmpty(artist))
            {
                displayText = $"{artist} - {displayText}";
            }
            displayText += " [Musikalbum]";
        }

        return displayText;
    }

    internal static string GetTelegramHyperlink(this BaseItem item, string? baseUrl)
    {
        var displayText = item.GetDisplayText();
        var safeDisplayText = TelegramMarkdown.Escape(displayText);

        if (string.IsNullOrWhiteSpace(baseUrl))
        {
            return safeDisplayText;
        }

        var itemUrl = $"{baseUrl.TrimEnd('/')}/web/index.html#!/details?id={item.Id:N}";
        var safeItemUrl = TelegramMarkdown.Escape(itemUrl);

        return $"[{safeDisplayText}]({safeItemUrl})";
    }

    internal static string[] GetStreamLanguages(this BaseItem item, MediaStreamType type)
    {
        return item.GetMediaStreams()
            .Where(m => m.Type == type && !string.IsNullOrEmpty(m.Language))
            .Select(m => m.Language!)
            .Distinct()
            .ToArray();
    }

    internal static string? GetExtraLink(this BaseItem item)
    {
        var imdbId = item.GetProviderId(MetadataProvider.Imdb);
        if (!string.IsNullOrEmpty(imdbId))
        {
            return $" \\- [IMDb]({TelegramMarkdown.Escape($"https://www.imdb.com/title/{imdbId}")})";
        }

        var tmdbId = item.GetProviderId(MetadataProvider.Tmdb);
        if (!string.IsNullOrEmpty(tmdbId))
        {
            var tmdbUrl = item is Movie
                ? $"https://www.themoviedb.org/movie/{tmdbId}"
                : $"https://www.themoviedb.org/tv/{tmdbId}";

            return $" \\- [TMDb]({TelegramMarkdown.Escape(tmdbUrl)})";
        }

        var tvdbId = item.GetProviderId(MetadataProvider.Tvdb);
        if (!string.IsNullOrEmpty(tvdbId))
        {
            return $" \\- [TVDb]({TelegramMarkdown.Escape($"https://www.thetvdb.com/?tab=series&id={tvdbId}")})";
        }

        var malId = item.GetProviderId("MyAnimeList");
        if (!string.IsNullOrEmpty(malId))
        {
            return $" \\- [MyAnimeList]({TelegramMarkdown.Escape($"https://myanimelist.net/anime/{malId}")})";
        }

        var aniDbId = item.GetProviderId("AniDB");
        if (!string.IsNullOrEmpty(aniDbId))
        {
            return $" \\- [AniDB]({TelegramMarkdown.Escape($"https://anidb.net/anime/{aniDbId}")})";
        }

        var aniListId = item.GetProviderId("AniList");
        if (!string.IsNullOrEmpty(aniListId))
        {
            return $" \\- [AniList]({TelegramMarkdown.Escape($"https://anilist.co/anime/{aniListId}")})";
        }

        return null;
    }
}
