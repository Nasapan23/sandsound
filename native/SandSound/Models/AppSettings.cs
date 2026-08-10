namespace SandSound.Models;

public sealed class AppSettings
{
    public string DownloadDirectory { get; set; } = string.Empty;
    public string DefaultFormat { get; set; } = "mp3";
    public string DefaultQuality { get; set; } = "Best";
    public string Theme { get; set; } = "System";
    public string CookieFile { get; set; } = string.Empty;
    public int ConcurrentDownloads { get; set; } = 3;
    public bool CreatePlaylistFolders { get; set; } = true;
}
