using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using MediaBrowser.Controller;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Telegram.Bot;
using Telegram.Bot.Types;
using Telegram.Bot.Types.Enums;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;

internal class CommandStats : ICommandBase
{
    public string Command => "status";

    public bool NeedsAdmin => true;

    public async Task Execute(ITelegramBotService telegramBotService, Message message, bool isAdmin, CancellationToken cancellationToken)
    {
        var botClient = telegramBotService.BotClientWrapper.Client;
        if (botClient == null)
        {
            telegramBotService.Logger.LogError("Telegram-Bot-Client-Wrapper ist in CommandStats null.");
            return;
        }

        var statsMessage = GetSystemStatsMessage(telegramBotService, isAdmin);

        await botClient.SendMessage(
            message.Chat.Id,
            statsMessage,
            parseMode: ParseMode.Markdown,
            cancellationToken: cancellationToken);
    }

    private string GetSystemStatsMessage(ITelegramBotService telegramBotService, bool isAdmin)
    {
        var serverApplicationHost = telegramBotService.ServiceProvider.GetRequiredService<IServerApplicationHost>();
        var process = Process.GetCurrentProcess();

        string botUptimeText = "Unbekannt";
        if (telegramBotService.StartTime.HasValue)
        {
            var botUptime = DateTime.UtcNow - telegramBotService.StartTime.Value;
            botUptimeText = FormatTimeSpan(botUptime);
        }

        var serverUptime = DateTime.UtcNow - process.StartTime.ToUniversalTime();

        var workingSet = process.WorkingSet64;
        var totalPhysicalMemory = GetTotalPhysicalMemory();
        var percentUsed = totalPhysicalMemory > 0
            ? (double)workingSet / totalPhysicalMemory
            : 0;

        var baseUrl = telegramBotService.Config.LoginBaseUrl;
        var serverUrl = baseUrl != null
            ? "Server-URL: " + baseUrl + "\n"
            : "";

        var sb = new StringBuilder();

        sb.AppendLine("📊 *RiNnoFin Server-Statistiken* 📊");
        sb.AppendLine();
        sb.AppendLine("🖥️ *Jellyfin Server*");
        sb.Append(serverUrl);
        sb.Append("Version: `").Append(serverApplicationHost.ApplicationVersion).Append("`\n");
        sb.Append("Laufzeit: `").Append(FormatTimeSpan(serverUptime)).Append("`\n");

        if (isAdmin)
        {
            sb.Append("Prozess-Speicher: `").Append(FormatBytes(workingSet)).Append("`\n");
            if (totalPhysicalMemory > 0)
            {
                sb.Append("Gesamtspeicher: `").Append(FormatBytes(totalPhysicalMemory)).Append("`\n");
                sb.Append("Speicherauslastung: `").Append(percentUsed.ToString("P1", CultureInfo.CurrentCulture)).Append("`\n\n");
            }
            else
            {
                sb.Append("Gesamtspeicher: `Unbekannt`\n\n");
            }
        }
        else
        {
            sb.AppendLine();
        }

        sb.AppendLine("🤖 *Telegram Bot*");
        sb.Append("Laufzeit: `").Append(botUptimeText).Append("`\n\n");

        if (isAdmin)
        {
            sb.AppendLine("💾 *Speicherplatz*");
            sb.Append(GetDiskInfo());
        }

        return sb.ToString();
    }

    private long GetTotalPhysicalMemory()
    {
        try
        {
            var gcInfo = GC.GetGCMemoryInfo();
            return gcInfo.TotalAvailableMemoryBytes;
        }
        catch
        {
            return 0;
        }
    }

    private string FormatTimeSpan(TimeSpan timeSpan)
    {
        return timeSpan.Days > 0
            ? $"{timeSpan.Days}d {timeSpan.Hours}h {timeSpan.Minutes}m {timeSpan.Seconds}s"
            : $"{timeSpan.Hours}h {timeSpan.Minutes}m {timeSpan.Seconds}s";
    }

    private string FormatBytes(long bytes)
    {
        string[] suffixes = ["B", "KB", "MB", "GB", "TB"];
        var counter = 0;
        double number = bytes;
        while (number >= 1024 && counter < suffixes.Length - 1)
        {
            number /= 1024;
            counter++;
        }

        return $"{number:F2} {suffixes[counter]}";
    }

    private string GetDiskInfo()
    {
        var result = new StringBuilder();

        var drives = DriveInfo.GetDrives()
            .Where(d => d is { IsReady: true, TotalSize: > 0, DriveType: DriveType.Removable or DriveType.Fixed or DriveType.Network })
            .ToList();

        foreach (var drive in drives)
        {
            var totalSize = drive.TotalSize;
            var freeSpace = drive.AvailableFreeSpace;
            var usedSpace = totalSize - freeSpace;
            var percentUsed = (double)usedSpace / totalSize;

            result.Append("`")
                .Append(drive.Name)
                .Append("` - `")
                .Append(FormatBytes(usedSpace))
                .Append("`/`")
                .Append(FormatBytes(totalSize))
                .Append("` (`")
                .Append(percentUsed.ToString("P1", CultureInfo.CurrentCulture))
                .Append("`)\n");
        }

        return result.ToString();
    }
}
