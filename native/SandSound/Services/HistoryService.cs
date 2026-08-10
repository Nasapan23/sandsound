using System.Collections.ObjectModel;
using System.Text.Json;
using SandSound.Models;

namespace SandSound.Services;

public sealed class HistoryService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };
    private readonly SemaphoreSlim _saveLock = new(1, 1);
    public ObservableCollection<HistoryEntry> Items { get; } = [];
    public ObservableCollection<PlaylistHistoryEntry> Playlists { get; } = [];

    public async Task LoadAsync()
    {
        try
        {
            if (!File.Exists(AppPaths.HistoryFile)) return;
            await using var stream = File.OpenRead(AppPaths.HistoryFile);
            var entries = await JsonSerializer.DeserializeAsync<List<HistoryEntry>>(stream) ?? [];
            foreach (var entry in entries.OrderByDescending(x => x.DownloadedAt)) Items.Add(entry);
            RefreshPlaylists();
        }
        catch (Exception ex)
        {
            AppLog.Write("Could not load download history", ex);
        }
    }

    public async Task AddAsync(HistoryEntry entry)
    {
        Items.Insert(0, entry);
        RefreshPlaylists();
        await SaveAsync();
    }

    public async Task ClearAsync()
    {
        Items.Clear();
        Playlists.Clear();
        await SaveAsync();
    }

    public bool ContainsMedia(string mediaId) => !string.IsNullOrWhiteSpace(mediaId) && Items.Any(x => x.MediaId == mediaId);

    private void RefreshPlaylists()
    {
        var playlists = Items
            .Where(x => !string.IsNullOrWhiteSpace(x.PlaylistId) && !string.IsNullOrWhiteSpace(x.PlaylistUrl))
            .GroupBy(x => x.PlaylistId, StringComparer.Ordinal)
            .Select(group => new PlaylistHistoryEntry
            {
                PlaylistId = group.Key,
                PlaylistUrl = group.OrderByDescending(x => x.DownloadedAt).First().PlaylistUrl,
                Title = group.OrderByDescending(x => x.DownloadedAt).First().PlaylistTitle,
                DownloadedCount = group.Select(x => x.MediaId).Where(x => !string.IsNullOrWhiteSpace(x)).Distinct(StringComparer.Ordinal).Count(),
                LastDownloadedAt = group.Max(x => x.DownloadedAt)
            })
            .OrderByDescending(x => x.LastDownloadedAt)
            .ToList();

        Playlists.Clear();
        foreach (var playlist in playlists) Playlists.Add(playlist);
    }

    private async Task SaveAsync()
    {
        await _saveLock.WaitAsync();
        try
        {
            await using var stream = File.Create(AppPaths.HistoryFile);
            await JsonSerializer.SerializeAsync(stream, Items.ToList(), JsonOptions);
        }
        finally
        {
            _saveLock.Release();
        }
    }
}
