using System.Collections.ObjectModel;
using System.Text.Json;
using SandSound.Models;

namespace SandSound.Services;

public sealed class HistoryService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };
    private readonly SemaphoreSlim _saveLock = new(1, 1);
    public ObservableCollection<HistoryEntry> Items { get; } = [];

    public async Task LoadAsync()
    {
        try
        {
            if (!File.Exists(AppPaths.HistoryFile)) return;
            await using var stream = File.OpenRead(AppPaths.HistoryFile);
            var entries = await JsonSerializer.DeserializeAsync<List<HistoryEntry>>(stream) ?? [];
            foreach (var entry in entries.OrderByDescending(x => x.DownloadedAt)) Items.Add(entry);
        }
        catch (Exception ex)
        {
            AppLog.Write("Could not load download history", ex);
        }
    }

    public async Task AddAsync(HistoryEntry entry)
    {
        Items.Insert(0, entry);
        await SaveAsync();
    }

    public async Task ClearAsync()
    {
        Items.Clear();
        await SaveAsync();
    }

    public bool ContainsMedia(string mediaId) => !string.IsNullOrWhiteSpace(mediaId) && Items.Any(x => x.MediaId == mediaId);

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
