namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;

public class TelegramGroupChat
{
    public enum TelegramChatType
    {
        Group,
        Supergroup,
        Channel,
        Private
    }

    public long TelegramChatId { get; set; }

    public TelegramChatType ChatType { get; set; } = TelegramChatType.Group;

    public bool SyncUserNames { get; set; } = true;

    public bool NotifyNewContent { get; set; } = true;

    public bool AllowRequests { get; set; } = true;

    public int? ContentTopicId { get; set; }

    public int? QuizTopicId { get; set; }

    public bool EnableQuiz { get; set; } = true;
}
