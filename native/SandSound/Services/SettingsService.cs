using System.Text.Json;
using SandSound.Models;

namespace SandSound.Services;

public sealed class SettingsService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public AppSettings Current { get; private set; } = new();

    public async Task LoadAsync()
    {
        try
        {
            if (File.Exists(AppPaths.SettingsFile))
            {
                await using var stream = File.OpenRead(AppPaths.SettingsFile);
                Current = await JsonSerializer.DeserializeAsync<AppSettings>(stream, JsonOptions) ?? new AppSettings();
                Current.DownloadDirectory = AppPaths.FromStoredPath(Current.DownloadDirectory);
                Current.CookieFile = AppPaths.FromStoredPath(Current.CookieFile);
            }
        }
        catch (Exception ex)
        {
            AppLog.Write("Could not load settings", ex);
            Current = new AppSettings();
        }

        if (string.IsNullOrWhiteSpace(Current.DownloadDirectory))
            Current.DownloadDirectory = AppPaths.DefaultDownloadDirectory;
        Current.ConcurrentDownloads = Math.Clamp(Current.ConcurrentDownloads, 1, 8);
        Directory.CreateDirectory(Current.DownloadDirectory);
    }

    public async Task SaveAsync()
    {
        Directory.CreateDirectory(AppPaths.DataDirectory);
        await using var stream = File.Create(AppPaths.SettingsFile);
        var portableSettings = new AppSettings
        {
            DownloadDirectory = AppPaths.ToStoredPath(Current.DownloadDirectory),
            CookieFile = AppPaths.ToStoredPath(Current.CookieFile),
            DefaultFormat = Current.DefaultFormat,
            DefaultQuality = Current.DefaultQuality,
            Theme = Current.Theme,
            ConcurrentDownloads = Current.ConcurrentDownloads,
            CreatePlaylistFolders = Current.CreatePlaylistFolders
        };
        await JsonSerializer.SerializeAsync(stream, portableSettings, JsonOptions);
    }
}
