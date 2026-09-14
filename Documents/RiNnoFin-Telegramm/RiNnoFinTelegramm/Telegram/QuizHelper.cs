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

    /// <summary>
    /// Sends a random quiz question to the given chat.
    /// Throws on Telegram API errors so the caller can display the real message.
    /// Topic ID is optional – null or 0 means main chat.
    /// </summary>
    public static async Task<bool> SendQuizQuestionAsync(
        ITelegramBotClient botClient,
        long chatId,
        int? messageThreadId,
        ILogger logger,
        CancellationToken cancellationToken)
    {
        // Topic ID ist optional: 0 oder null → Hauptchat (kein Topic)
        int? threadId = (messageThreadId ?? 0) > 0 ? messageThreadId : null;

        logger.LogInformation("QuizHelper: Chat={ChatId} ThreadId={ThreadId}", chatId, threadId?.ToString() ?? "null");

        var libraryManager = RiNnoFinPlugin.Instance?.LibraryManager
            ?? throw new InvalidOperationException("LibraryManager ist nicht verfügbar.");

        var items = libraryManager.GetItemList(new InternalItemsQuery
        {
            IncludeItemTypes = new[] { BaseItemKind.Movie, BaseItemKind.Series },
            Recursive = true,
            IsVirtualItem = false
        }).Where(i => !string.IsNullOrEmpty(i.Name)).ToList();

        if (items.Count == 0)
        {
            await botClient.SendMessage(chatId,
                "⚠️ Keine Filme oder Serien in der Bibliothek gefunden.",
                messageThreadId: threadId,
                cancellationToken: cancellationToken);
            return false;
        }

        var seriesItems = items.Where(i => i is Series).ToList();
        int questionType = Rng.Next(0, 3);
        if (questionType == 2 && seriesItems.Count == 0)
            questionType = Rng.Next(0, 2);

        string questionText;
        List<string> options;
        int correctOptionIndex;

        if (questionType == 0) // Jahr
        {
            var withYear = items.Where(i => i.ProductionYear.HasValue).ToList();
            if (withYear.Count == 0) withYear = items;

            var item = withYear[Rng.Next(withYear.Count)];
            int correctYear = item.ProductionYear ?? Rng.Next(1990, 2026);
            questionText = $"Aus welchem Jahr stammt der {(item is Movie ? "Film" : "Serie")} '{item.Name}'?";

            var wrongYears = new HashSet<int>();
            while (wrongYears.Count < 3)
            {
                int offset = Rng.Next(-10, 10);
                if (offset == 0) continue;
                int wy = correctYear + offset;
                if (wy > 1900 && wy <= DateTime.UtcNow.Year) wrongYears.Add(wy);
            }
            options = wrongYears.Select(y => y.ToString()).ToList();
            correctOptionIndex = Rng.Next(0, 4);
            options.Insert(correctOptionIndex, correctYear.ToString());
        }
        else if (questionType == 1) // Genre
        {
            var withGenres = items.Where(i => i.Genres?.Length > 0).ToList();
            if (withGenres.Count == 0)
                return await SendQuizQuestionAsync(botClient, chatId, threadId, logger, cancellationToken);

            var item = withGenres[Rng.Next(withGenres.Count)];
            string correctGenre = item.Genres[0];
            questionText = $"Welchem Genre gehört der {(item is Movie ? "Film" : "Serie")} '{item.Name}' an?";

            var pool = withGenres.SelectMany(i => i.Genres)
                .Where(g => !string.Equals(g, correctGenre, StringComparison.OrdinalIgnoreCase))
                .Distinct().ToList();
            if (pool.Count < 3) pool = Genres.ToList();

            var wrongGenres = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            while (wrongGenres.Count < 3)
            {
                string g = pool[Rng.Next(pool.Count)];
                if (!string.Equals(g, correctGenre, StringComparison.OrdinalIgnoreCase))
                    wrongGenres.Add(g);
            }
            options = wrongGenres.ToList();
            correctOptionIndex = Rng.Next(0, 4);
            options.Insert(correctOptionIndex, correctGenre);
        }
        else // Episode-Zuordnung
        {
            var episodes = libraryManager.GetItemList(new InternalItemsQuery
            {
                IncludeItemTypes = new[] { BaseItemKind.Episode },
                Recursive = true,
                IsVirtualItem = false
            }).OfType<Episode>()
              .Where(ep => !string.IsNullOrEmpty(ep.Name) && !string.IsNullOrEmpty(ep.SeriesName))
              .ToList();

            if (episodes.Count == 0)
                return await SendQuizQuestionAsync(botClient, chatId, threadId, logger, cancellationToken);

            var ep = episodes[Rng.Next(episodes.Count)];
            string correctSeries = ep.SeriesName!;
            questionText = $"Zu welcher Serie gehört die Episode '{ep.Name}'?";

            var otherSeries = seriesItems.Select(s => s.Name)
                .Where(n => !string.Equals(n, correctSeries, StringComparison.OrdinalIgnoreCase))
                .Distinct().ToList();

            if (otherSeries.Count < 3)
                return await SendQuizQuestionAsync(botClient, chatId, threadId, logger, cancellationToken);

            var wrong = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            while (wrong.Count < 3)
                wrong.Add(otherSeries[Rng.Next(otherSeries.Count)]);

            options = wrong.ToList();
            correctOptionIndex = Rng.Next(0, 4);
            options.Insert(correctOptionIndex, correctSeries);
        }

        // Telegram-Längenbegrenzungen einhalten
        options = options.Select(o => o.Length > 100 ? o[..97] + "..." : o).ToList();
        if (questionText.Length > 300) questionText = questionText[..297] + "...";

        logger.LogInformation("QuizHelper: Sende Poll '{Q}' ({Count} Optionen)", questionText, options.Count);

        await botClient.SendPoll(
            chatId: chatId,
            question: questionText,
            options: options.Select(o => new InputPollOption(o)).ToArray(),
            type: PollType.Quiz,
            correctOptionId: correctOptionIndex,
            isAnonymous: false,
            messageThreadId: threadId,
            cancellationToken: cancellationToken
        );

        return true;
    }
}
