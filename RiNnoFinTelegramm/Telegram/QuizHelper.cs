using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Data.Enums;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Library;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;

public static class QuizHelper
{
    private static readonly Random Rng = new();

    private static readonly string[] Genres =
    {
        "Action", "Komödie", "Drama", "Science Fiction", "Horror", "Thriller",
        "Dokumentarfilm", "Animation", "Abenteuer", "Fantasy", "Krimi", "Romantik"
    };

    public static async Task<bool> SendQuizQuestionAsync(ITelegramBotClient botClient, long chatId, int? messageThreadId, ILogger logger, CancellationToken cancellationToken)
    {
        try
        {
            var libraryManager = RiNnoFinPlugin.Instance?.LibraryManager;
            if (libraryManager == null)
            {
                logger.LogError("QuizHelper: LibraryManager ist null.");
                return false;
            }

            // Fetch movies and series
            var query = new InternalItemsQuery
            {
                IncludeItemTypes = new[] { BaseItemKind.Movie, BaseItemKind.Series },
                Recursive = true,
                IsVirtualItem = false
            };

            var items = libraryManager.GetItemList(query)
                .Where(i => !string.IsNullOrEmpty(i.Name))
                .ToList();

            if (items.Count == 0)
            {
                logger.LogWarning("QuizHelper: Keine Filme oder Serien in der Bibliothek gefunden.");
                await botClient.SendMessage(
                    chatId,
                    "⚠️ Es wurden keine Filme oder Serien in der Bibliothek gefunden, um ein Quiz zu erstellen.",
                    messageThreadId: messageThreadId,
                    cancellationToken: cancellationToken
                );
                return false;
            }

            // Choose a random question type:
            // 0: Year of Production
            // 1: Genre
            // 2: Episode association
            int questionType = Rng.Next(0, 3);
            
            // If we have very few series, type 2 might fail, so let's check and fallback if needed
            var seriesItems = items.Where(i => i is Series).ToList();
            if (questionType == 2 && seriesItems.Count == 0)
            {
                questionType = Rng.Next(0, 2);
            }

            string questionText = string.Empty;
            List<string> options = new();
            int correctOptionIndex = 0;

            if (questionType == 0) // Year
            {
                // Find an item with a production year
                var itemsWithYear = items.Where(i => i.ProductionYear.HasValue).ToList();
                if (itemsWithYear.Count == 0) itemsWithYear = items; // Fallback

                var selectedItem = itemsWithYear[Rng.Next(itemsWithYear.Count)];
                int correctYear = selectedItem.ProductionYear ?? Rng.Next(1990, 2026);

                var isMovie = selectedItem is Movie;
                var mediaTypeWord = isMovie ? "Film" : "Serie";
                questionText = $"Aus welchem Jahr stammt der {mediaTypeWord} '{selectedItem.Name}'?";

                // Generate 3 unique wrong years close to correct
                var wrongYears = new HashSet<int>();
                while (wrongYears.Count < 3)
                {
                    int offset = Rng.Next(-10, 10);
                    if (offset != 0)
                    {
                        int wrongYear = correctYear + offset;
                        if (wrongYear > 1900 && wrongYear <= DateTime.UtcNow.Year)
                        {
                            wrongYears.Add(wrongYear);
                        }
                    }
                }

                var allOptions = wrongYears.Select(y => y.ToString()).ToList();
                correctOptionIndex = Rng.Next(0, 4);
                allOptions.Insert(correctOptionIndex, correctYear.ToString());
                options = allOptions;
            }
            else if (questionType == 1) // Genre
            {
                var itemsWithGenres = items.Where(i => i.Genres != null && i.Genres.Length > 0).ToList();
                if (itemsWithGenres.Count == 0)
                {
                    // Fallback to year type
                    return await SendQuizQuestionAsync(botClient, chatId, messageThreadId, logger, cancellationToken);
                }

                var selectedItem = itemsWithGenres[Rng.Next(itemsWithGenres.Count)];
                string correctGenre = selectedItem.Genres[0];

                var isMovie = selectedItem is Movie;
                var mediaTypeWord = isMovie ? "Film" : "Serie";
                questionText = $"Welchem Genre ist der {mediaTypeWord} '{selectedItem.Name}' zugeordnet?";

                // Generate 3 wrong genres
                var wrongGenres = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                var otherGenresInLibrary = itemsWithGenres
                    .SelectMany(i => i.Genres)
                    .Where(g => !string.Equals(g, correctGenre, StringComparison.OrdinalIgnoreCase))
                    .Distinct()
                    .ToList();

                var pool = otherGenresInLibrary.Count >= 3 ? otherGenresInLibrary : Genres.ToList();
                while (wrongGenres.Count < 3)
                {
                    string randomGenre = pool[Rng.Next(pool.Count)];
                    if (!string.Equals(randomGenre, correctGenre, StringComparison.OrdinalIgnoreCase))
                    {
                        wrongGenres.Add(randomGenre);
                    }
                }

                var allOptions = wrongGenres.ToList();
                correctOptionIndex = Rng.Next(0, 4);
                allOptions.Insert(correctOptionIndex, correctGenre);
                options = allOptions;
            }
            else // Episode association
            {
                // Fetch all episodes
                var epQuery = new InternalItemsQuery
                {
                    IncludeItemTypes = new[] { BaseItemKind.Episode },
                    Recursive = true,
                    IsVirtualItem = false
                };
                var episodes = libraryManager.GetItemList(epQuery)
                    .Where(e => e is Episode && !string.IsNullOrEmpty(e.Name) && !string.IsNullOrEmpty(((Episode)e).SeriesName))
                    .Cast<Episode>()
                    .ToList();

                if (episodes.Count == 0)
                {
                    // Fallback to year type
                    return await SendQuizQuestionAsync(botClient, chatId, messageThreadId, logger, cancellationToken);
                }

                var selectedEpisode = episodes[Rng.Next(episodes.Count)];
                string correctSeries = selectedEpisode.SeriesName!;
                questionText = $"Zu welcher Serie gehört die Episode '{selectedEpisode.Name}'?";

                // Generate 3 wrong series names
                var wrongSeries = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                var allSeriesNames = seriesItems.Select(s => s.Name).Where(n => !string.Equals(n, correctSeries, StringComparison.OrdinalIgnoreCase)).Distinct().ToList();

                if (allSeriesNames.Count >= 3)
                {
                    while (wrongSeries.Count < 3)
                    {
                        string randomSeries = allSeriesNames[Rng.Next(allSeriesNames.Count)];
                        wrongSeries.Add(randomSeries);
                    }
                }
                else
                {
                    // Fallback to another question type if not enough series
                    return await SendQuizQuestionAsync(botClient, chatId, messageThreadId, logger, cancellationToken);
                }

                var allOptions = wrongSeries.ToList();
                correctOptionIndex = Rng.Next(0, 4);
                allOptions.Insert(correctOptionIndex, correctSeries);
                options = allOptions;
            }

            // Ensure option text length does not exceed 100 characters (Telegram limit)
            options = options.Select(o => o.Length > 100 ? o.Substring(0, 97) + "..." : o).ToList();
            if (questionText.Length > 300)
            {
                questionText = questionText.Substring(0, 297) + "...";
            }

            var pollOptions = options.Select(o => new InputPollOption(o)).ToArray();

            await botClient.SendPoll(
                chatId: chatId,
                question: questionText,
                options: pollOptions,
                type: PollType.Quiz,
                correctOptionId: correctOptionIndex,
                isAnonymous: false,
                messageThreadId: messageThreadId,
                cancellationToken: cancellationToken
            );

            return true;
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Fehler beim Erstellen/Senden der Quizfrage.");
            return false;
        }
    }
}
