using System.Text.Json.Serialization;

namespace SandSound.Models;

public sealed class MediaItem
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("title")]
    public string Title { get; set; } = "Untitled";

    [JsonPropertyName("webpage_url")]
    public string? WebpageUrl { get; set; }

    [JsonPropertyName("url")]
    public string? RawUrl { get; set; }

    [JsonPropertyName("uploader")]
    public string? Creator { get; set; }

    [JsonPropertyName("channel")]
    public string? Channel { get; set; }

    [JsonPropertyName("duration")]
    public double? DurationSeconds { get; set; }

    [JsonPropertyName("thumbnail")]
    public string? Thumbnail { get; set; }

    [JsonPropertyName("entries")]
    public List<MediaItem>? Entries { get; set; }

    public string DisplayCreator => Creator ?? Channel ?? "YouTube";
    public string DurationText => DurationSeconds is > 0
        ? TimeSpan.FromSeconds(DurationSeconds.Value).ToString(DurationSeconds >= 3600 ? @"h\:mm\:ss" : @"m\:ss")
        : string.Empty;
    public string EffectiveUrl => WebpageUrl ?? (string.IsNullOrWhiteSpace(Id) ? RawUrl ?? string.Empty : $"https://www.youtube.com/watch?v={Id}");
    public string Subtitle => string.IsNullOrEmpty(DurationText) ? DisplayCreator : $"{DisplayCreator}  •  {DurationText}";
}
