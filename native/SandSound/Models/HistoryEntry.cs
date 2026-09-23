namespace SandSound.Models;

public sealed class HistoryEntry
{
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string MediaId { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Url { get; set; } = string.Empty;
    public string Format { get; set; } = string.Empty;
    public string OutputDirectory { get; set; } = string.Empty;
    public string PlaylistId { get; set; } = string.Empty;
    public string PlaylistUrl { get; set; } = string.Empty;
    public string PlaylistTitle { get; set; } = string.Empty;
    public DateTimeOffset DownloadedAt { get; set; } = DateTimeOffset.Now;
    public string DateText => DownloadedAt.LocalDateTime.ToString("g");
    public string Subtitle => string.IsNullOrWhiteSpace(PlaylistTitle)
        ? $"{Format.ToUpperInvariant()}  •  {DateText}"
        : $"{PlaylistTitle}  •  {Format.ToUpperInvariant()}  •  {DateText}";
}
