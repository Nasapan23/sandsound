namespace SandSound.Models;

/// <summary>
/// A persisted playlist that can be reopened to check for additions.
/// </summary>
public sealed class PlaylistHistoryEntry
{
    public required string PlaylistId { get; init; }
    public required string PlaylistUrl { get; init; }
    public required string Title { get; init; }
    public int DownloadedCount { get; init; }
    public DateTimeOffset LastDownloadedAt { get; init; }

    public string Subtitle => $"{DownloadedCount} downloaded  •  Last synced {LastDownloadedAt.LocalDateTime:g}";
}
