using System.Collections.ObjectModel;
using Avalonia.Threading;
using SandSound.Models;

namespace SandSound.Services;

public sealed class DownloadQueueService
{
    private readonly YtDlpService _ytDlp;
    private readonly SettingsService _settings;
    private readonly HistoryService _history;
    private SemaphoreSlim _slots;

    public ObservableCollection<DownloadItem> Items { get; } = [];

    public DownloadQueueService(YtDlpService ytDlp, SettingsService settings, HistoryService history)
    {
        _ytDlp = ytDlp;
        _settings = settings;
        _history = history;
        _slots = new SemaphoreSlim(settings.Current.ConcurrentDownloads);
    }

    public void Reconfigure() => _slots = new SemaphoreSlim(_settings.Current.ConcurrentDownloads);

    public void Enqueue(
        IEnumerable<MediaItem> media,
        string format,
        string playlistId = "",
        string playlistUrl = "",
        string playlistTitle = "")
    {
        foreach (var source in media)
        {
            var item = new DownloadItem
            {
                Id = Guid.NewGuid().ToString("N"),
                Url = source.EffectiveUrl,
                Title = source.Title,
                Format = format,
                PlaylistId = playlistId,
                PlaylistUrl = playlistUrl,
                PlaylistTitle = playlistTitle
            };
            Items.Insert(0, item);
            _ = RunAsync(item, source.Id);
        }
    }

    public void CancelAll()
    {
        foreach (var item in Items.Where(item => item.CanCancel)) item.Cancellation.Cancel();
    }

    private async Task RunAsync(DownloadItem item, string mediaId)
    {
        var slots = _slots;
        var acquiredSlot = false;
        try
        {
            await slots.WaitAsync(item.Cancellation.Token);
            acquiredSlot = true;
            Update(item, () => { item.State = DownloadState.Downloading; item.Detail = "Starting…"; });
            var progress = new Progress<DownloadProgress>(value => Update(item, () =>
            {
                item.Progress = value.Percent;
                item.Detail = string.IsNullOrWhiteSpace(value.Detail) ? "Downloading…" : value.Detail;
                item.State = value.Processing ? DownloadState.Processing : DownloadState.Downloading;
            }));
            await _ytDlp.DownloadAsync(item, progress, item.Cancellation.Token);
            Update(item, () => { item.Progress = 100; item.State = DownloadState.Completed; item.Detail = "Saved"; });
            await Dispatcher.UIThread.InvokeAsync(() => _history.AddAsync(new HistoryEntry
            {
                MediaId = mediaId,
                Title = item.Title,
                Url = item.Url,
                Format = item.Format,
                PlaylistId = item.PlaylistId,
                PlaylistUrl = item.PlaylistUrl,
                PlaylistTitle = item.PlaylistTitle,
                OutputDirectory = _settings.Current.DownloadDirectory
            }));
        }
        catch (OperationCanceledException)
        {
            Update(item, () => { item.State = DownloadState.Cancelled; item.Detail = "Cancelled"; });
        }
        catch (Exception ex)
        {
            AppLog.Write($"Download failed: {item.Url}", ex);
            Update(item, () => { item.State = DownloadState.Failed; item.Detail = ex.Message; });
        }
        finally
        {
            if (acquiredSlot) slots.Release();
        }
    }

    private static void Update(DownloadItem item, Action action)
    {
        if (Dispatcher.UIThread.CheckAccess()) action();
        else Dispatcher.UIThread.Post(action);
    }
}
