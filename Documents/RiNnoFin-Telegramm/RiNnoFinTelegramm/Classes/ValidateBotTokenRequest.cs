using System.ComponentModel.DataAnnotations;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Classes;

public class ValidateBotTokenRequest
{
    [Required]
    [StringLength(256)]
    public string Token { get; set; } = default!;
}
