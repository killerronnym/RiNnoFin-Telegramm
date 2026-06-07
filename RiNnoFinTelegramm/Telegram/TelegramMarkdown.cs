using System.Linq;
using System.Text;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;

internal static class TelegramMarkdown
{
    private static readonly char[] MarkdownV2SpecialChars =
    [
        '_', '*', '[', ']', '(', ')', '~', '`', '>', '#',
        '+', '-', '=', '|', '{', '}', '.', '!'
    ];

    public static string Escape(string? text)
    {
        if (string.IsNullOrEmpty(text))
        {
            return text ?? string.Empty;
        }

        var sb = new StringBuilder(text.Length * 2);

        foreach (var ch in text)
        {
            if (MarkdownV2SpecialChars.Contains(ch))
            {
                sb.Append('\\');
            }

            sb.Append(ch);
        }

        return sb.ToString();
    }
}
