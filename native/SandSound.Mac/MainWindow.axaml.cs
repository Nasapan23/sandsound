using System.Diagnostics;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.Primitives;
using Avalonia.Input;
using Avalonia.Interactivity;
using Avalonia.Media;
using Avalonia.Platform.Storage;
using Avalonia.Styling;
using SandSound.Models;
using SandSound.Services;

namespace SandSound;

public sealed partial class MainWindow : Window
{
    private static readonly string[] Formats = ["mp3", "m4a", "opus", "flac", "wav", "mp4", "webm", "mkv"];
    private static readonly string[] Qualities = ["Best", "320 kbps", "256 kbps", "192 kbps", "1080p", "720p", "480p"];
    private static readonly string[] Themes = ["System", "Light", "Dark"];

    private readonly SettingsService _settings = new();
    private readonly HistoryService _history = new();
    private YtDlpService? _ytDlp;
    private DownloadQueueService? _queue;
    private MediaItem? _preview;
    private string _previewSourceUrl = string.Empty;
    private bool _searchMode;
    private bool _initialized;
    private bool _checkingForUpdates;
    private CancellationTokenSource? _discoveryCancellation;

    public MainWindow()
    {
        InitializeComponent();
        Opened += async (_, _) => await InitializeAsync();
        Closing += (_, _) =>
        {
            _discoveryCancellation?.Cancel();
            _queue?.CancelAll();
        };
    }

    private async Task InitializeAsync()
    {
        if (_initialized) return;
        _initialized = true;

        FormatBox.ItemsSource = Formats;
        QualityBox.ItemsSource = Qualities;
        ThemeBox.ItemsSource = Themes;

        await _settings.LoadAsync();
        ApplyTheme(_settings.Current.Theme);
        await _history.LoadAsync();
        _ytDlp = new YtDlpService(_settings);
        _queue = new DownloadQueueService(_ytDlp, _settings, _history);

        DownloadsList.ItemsSource = _queue.Items;
        HistoryList.ItemsSource = _history.Items;
        PlaylistHistoryList.ItemsSource = _history.Playlists;
        DownloadDirectoryBox.Text = _settings.Current.DownloadDirectory;
        CookieFileBox.Text = _settings.Current.CookieFile;
        PlaylistFoldersCheck.IsChecked = _settings.Current.CreatePlaylistFolders;
        ThemeBox.SelectedItem = _settings.Current.Theme;
        ConcurrencyBox.Value = _settings.Current.ConcurrentDownloads;
        FormatBox.SelectedItem = _settings.Current.DefaultFormat;
        QualityBox.SelectedItem = _settings.Current.DefaultQuality;
        PortablePathText.Text = AppPaths.ExecutableDirectory;
        RuntimeStatusText.Text = _ytDlp.HasPortableTool
            ? $"Ready — yt-dlp is bundled. FFmpeg is {(_ytDlp.HasPortableFfmpeg ? "bundled." : "missing.")}"
            : "Development mode — yt-dlp will be resolved from PATH. Run the macOS portable publish script before copying the app.";

        Navigation.SelectedIndex = 0;
        _ = CheckForUpdatesAsync(userInitiated: false);
    }

    private void UrlMode_Click(object? sender, RoutedEventArgs e)
    {
        _searchMode = false;
        UrlModeButton.IsChecked = true;
        SearchModeButton.IsChecked = false;
        SourceBox.Watermark = "Paste a YouTube video or playlist URL";
        InspectButton.Content = "Inspect";
        SearchResultsSection.IsVisible = false;
    }

    private void SearchMode_Click(object? sender, RoutedEventArgs e)
    {
        _searchMode = true;
        UrlModeButton.IsChecked = false;
        SearchModeButton.IsChecked = true;
        SourceBox.Watermark = "Artist, title, remix, label…";
        InspectButton.Content = "Search";
        PreviewCard.IsVisible = false;
    }

    private async void SourceBox_KeyDown(object? sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter) await DiscoverAsync();
    }

    private async void InspectButton_Click(object? sender, RoutedEventArgs e) => await DiscoverAsync();

    private async Task DiscoverAsync()
    {
        if (_ytDlp is null) return;
        var input = SourceBox.Text?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(input))
        {
            ShowMessage("Enter a URL or a search phrase.", MessageKind.Warning);
            return;
        }

        _discoveryCancellation?.Cancel();
        _discoveryCancellation = new CancellationTokenSource();
        SetDiscoveryBusy(true);
        try
        {
            if (_searchMode)
            {
                var results = await _ytDlp.SearchAsync(input, 6, _discoveryCancellation.Token);
                SearchResultsList.ItemsSource = results;
                SearchResultsSection.IsVisible = true;
                PreviewCard.IsVisible = false;
                if (results.Count == 0) ShowMessage("No results found.", MessageKind.Information);
            }
            else
            {
                if (!Uri.TryCreate(input, UriKind.Absolute, out _))
                    throw new InvalidOperationException("Enter a complete YouTube URL, including https://.");
                _preview = await _ytDlp.InspectAsync(input, cancellationToken: _discoveryCancellation.Token);
                _previewSourceUrl = input;
                ShowPreview(_preview);
            }
        }
        catch (OperationCanceledException) { }
        catch (Exception ex)
        {
            AppLog.Write("Media discovery failed", ex);
            ShowMessage(ex.Message, MessageKind.Error);
        }
        finally
        {
            SetDiscoveryBusy(false);
        }
    }

    private void ShowPreview(MediaItem media)
    {
        PreviewTitle.Text = media.Title;
        var isPlaylist = media.Entries is { Count: > 0 };
        PreviewSubtitle.Text = isPlaylist
            ? $"{media.Entries!.Count} videos  •  choose the items to queue"
            : media.Subtitle;
        PlaylistList.IsVisible = isPlaylist;
        PlaylistList.ItemsSource = isPlaylist ? media.Entries : null;
        ResyncPlaylistButton.IsVisible = isPlaylist && !string.IsNullOrWhiteSpace(_previewSourceUrl);
        PreviewCard.IsVisible = true;
        SearchResultsSection.IsVisible = false;

        if (isPlaylist && PlaylistList.SelectedItems is { } selectedItems)
        {
            selectedItems.Clear();
            foreach (var entry in media.Entries!) selectedItems.Add(entry);
        }
    }

    private void SearchDownload_Click(object? sender, RoutedEventArgs e)
    {
        if (sender is Button { DataContext: MediaItem media }) Enqueue([media]);
    }

    private void QueueButton_Click(object? sender, RoutedEventArgs e)
    {
        if (_preview is null) return;
        if (_preview.Entries is { Count: > 0 })
        {
            var selected = PlaylistList.SelectedItems?.OfType<MediaItem>().ToList() ?? [];
            if (selected.Count == 0)
            {
                ShowMessage("Select at least one playlist item.", MessageKind.Warning);
                return;
            }

            Enqueue(
                selected,
                playlistId: GetPlaylistId(_preview, _previewSourceUrl),
                playlistUrl: _previewSourceUrl,
                playlistTitle: _preview.Title,
                skipDownloaded: true);
        }
        else
        {
            Enqueue([_preview]);
        }
    }

    private void Enqueue(
        IReadOnlyList<MediaItem> media,
        string playlistId = "",
        string playlistUrl = "",
        string playlistTitle = "",
        bool skipDownloaded = false)
    {
        if (_queue is null || media.Count == 0) return;
        var queuedMedia = skipDownloaded
            ? media.Where(item => !_history.ContainsMedia(item.Id)).ToList()
            : media.ToList();
        var skipped = media.Count - queuedMedia.Count;
        if (queuedMedia.Count == 0)
        {
            ShowMessage("Every selected playlist item is already in your library.", MessageKind.Information);
            return;
        }

        var format = FormatBox.SelectedItem?.ToString() ?? "mp3";
        _settings.Current.DefaultFormat = format;
        _settings.Current.DefaultQuality = QualityBox.SelectedItem?.ToString() ?? "Best";
        _queue.Enqueue(queuedMedia, format, playlistId, playlistUrl, playlistTitle);
        var message = queuedMedia.Count == 1 ? "Added to the download queue." : $"Added {queuedMedia.Count} items to the queue.";
        if (skipped > 0) message += $" Skipped {skipped} already downloaded.";
        ShowMessage(message, MessageKind.Success);
        Navigation.SelectedIndex = 1;
    }

    private void CancelItem_Click(object? sender, RoutedEventArgs e)
    {
        if (sender is Button { DataContext: DownloadItem item }) item.Cancellation.Cancel();
    }

    private void CancelAll_Click(object? sender, RoutedEventArgs e) => _queue?.CancelAll();

    private void OpenDownloads_Click(object? sender, RoutedEventArgs e) => OpenPath(_settings.Current.DownloadDirectory);

    private async void ResyncPlaylist_Click(object? sender, RoutedEventArgs e)
    {
        if (_preview is not null && !string.IsNullOrWhiteSpace(_previewSourceUrl))
            await InspectPlaylistAsync(_previewSourceUrl, forceRefresh: true);
    }

    private async void OpenPlaylistHistory_Click(object? sender, RoutedEventArgs e)
    {
        if (sender is Button { DataContext: PlaylistHistoryEntry playlist })
            await InspectPlaylistAsync(playlist.PlaylistUrl, forceRefresh: false);
    }

    private async void ResyncPlaylistHistory_Click(object? sender, RoutedEventArgs e)
    {
        if (sender is Button { DataContext: PlaylistHistoryEntry playlist })
            await InspectPlaylistAsync(playlist.PlaylistUrl, forceRefresh: true);
    }

    private async Task InspectPlaylistAsync(string playlistUrl, bool forceRefresh)
    {
        if (_ytDlp is null || string.IsNullOrWhiteSpace(playlistUrl)) return;

        _discoveryCancellation?.Cancel();
        _discoveryCancellation = new CancellationTokenSource();
        SetDiscoveryBusy(true);
        try
        {
            _searchMode = false;
            UrlModeButton.IsChecked = true;
            SearchModeButton.IsChecked = false;
            SourceBox.Text = playlistUrl;
            SourceBox.Watermark = "Paste a YouTube video or playlist URL";
            InspectButton.Content = "Inspect";
            _preview = await _ytDlp.InspectAsync(playlistUrl, forceRefresh, _discoveryCancellation.Token);
            _previewSourceUrl = playlistUrl;
            ShowPreview(_preview);
            Navigation.SelectedIndex = 0;

            var currentCount = _preview.Entries?.Count ?? 0;
            var newCount = _preview.Entries?.Count(item => !_history.ContainsMedia(item.Id)) ?? 0;
            ShowMessage(
                forceRefresh
                    ? $"Playlist resynced: {currentCount} current tracks, {newCount} not yet downloaded."
                    : $"Playlist opened: {currentCount} current tracks, {newCount} not yet downloaded.",
                MessageKind.Success);
        }
        catch (OperationCanceledException) { }
        catch (Exception ex)
        {
            AppLog.Write("Playlist sync failed", ex);
            ShowMessage($"Could not resync playlist: {ex.Message}", MessageKind.Error);
        }
        finally
        {
            SetDiscoveryBusy(false);
        }
    }

    private async void ClearHistory_Click(object? sender, RoutedEventArgs e)
    {
        if (await ConfirmAsync("Clear download history?", "Downloaded files will not be deleted.", "Clear"))
        {
            await _history.ClearAsync();
            ShowMessage("Download history cleared.", MessageKind.Success);
        }
    }

    private async void ChooseDownloadFolder_Click(object? sender, RoutedEventArgs e)
    {
        var folders = await StorageProvider.OpenFolderPickerAsync(new FolderPickerOpenOptions
        {
            Title = "Choose a download folder",
            AllowMultiple = false
        });
        var path = folders.FirstOrDefault()?.TryGetLocalPath();
        if (!string.IsNullOrWhiteSpace(path)) DownloadDirectoryBox.Text = path;
    }

    private async void ChooseCookieFile_Click(object? sender, RoutedEventArgs e)
    {
        var files = await StorageProvider.OpenFilePickerAsync(new FilePickerOpenOptions
        {
            Title = "Choose a cookies file",
            AllowMultiple = false,
            FileTypeFilter =
            [
                new FilePickerFileType("Netscape cookie files") { Patterns = ["*.txt", "*.cookies"] },
                FilePickerFileTypes.All
            ]
        });
        var path = files.FirstOrDefault()?.TryGetLocalPath();
        if (!string.IsNullOrWhiteSpace(path)) CookieFileBox.Text = path;
    }

    private async void SaveSettings_Click(object? sender, RoutedEventArgs e)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(DownloadDirectoryBox.Text))
                throw new InvalidOperationException("Choose a download directory.");
            Directory.CreateDirectory(DownloadDirectoryBox.Text);
            _settings.Current.DownloadDirectory = DownloadDirectoryBox.Text;
            _settings.Current.CookieFile = CookieFileBox.Text ?? string.Empty;
            _settings.Current.CreatePlaylistFolders = PlaylistFoldersCheck.IsChecked == true;
            _settings.Current.Theme = ThemeBox.SelectedItem?.ToString() ?? "System";
            _settings.Current.ConcurrentDownloads = Math.Clamp((int)(ConcurrencyBox.Value ?? 3), 1, 8);
            await _settings.SaveAsync();
            _queue?.Reconfigure();
            ApplyTheme(_settings.Current.Theme);
            ShowMessage("Settings saved.", MessageKind.Success);
        }
        catch (Exception ex)
        {
            ShowMessage(ex.Message, MessageKind.Error);
        }
    }

    private async void CheckUpdates_Click(object? sender, RoutedEventArgs e) => await CheckForUpdatesAsync(userInitiated: true);

    private async Task CheckForUpdatesAsync(bool userInitiated)
    {
        if (_checkingForUpdates) return;
        _checkingForUpdates = true;
        try
        {
            if (userInitiated) ShowMessage("Checking GitHub for updates…", MessageKind.Information);
            var update = await new UpdateService().CheckAsync();
            if (update is null)
            {
                if (userInitiated) ShowMessage("SandSound is up to date.", MessageKind.Success);
                return;
            }

            var openRelease = await ConfirmAsync(
                $"SandSound {update.Tag} is available",
                "Download the matching macOS portable archive? Your Data and Downloads folders remain beside the app.",
                "Open release");
            if (openRelease) OpenPath(update.PageUrl);
        }
        catch (Exception ex)
        {
            AppLog.Write("Update check failed", ex);
            if (userInitiated) ShowMessage($"Update check failed: {ex.Message}", MessageKind.Error);
        }
        finally
        {
            _checkingForUpdates = false;
        }
    }

    private void ApplyTheme(string theme)
    {
        if (Application.Current is null) return;
        Application.Current.RequestedThemeVariant = theme switch
        {
            "Light" => ThemeVariant.Light,
            "Dark" => ThemeVariant.Dark,
            _ => ThemeVariant.Default
        };
    }

    private void SetDiscoveryBusy(bool busy)
    {
        InspectButton.IsEnabled = !busy;
        SourceBox.IsEnabled = !busy;
        ResyncPlaylistButton.IsEnabled = !busy;
        DiscoveryProgress.IsVisible = busy;
    }

    private void ShowMessage(string message, MessageKind kind)
    {
        MessageText.Text = message;
        MessageBanner.Background = new SolidColorBrush(kind switch
        {
            MessageKind.Success => Color.Parse("#183F2B"),
            MessageKind.Warning => Color.Parse("#4A391C"),
            MessageKind.Error => Color.Parse("#4A2024"),
            _ => Color.Parse("#20354A")
        });
        MessageBanner.IsVisible = true;
    }

    private async Task<bool> ConfirmAsync(string title, string message, string primaryText)
    {
        var accepted = false;
        var primary = new Button { Content = primaryText, Classes = { "accent" } };
        var cancel = new Button { Content = "Cancel" };
        var dialog = new Window
        {
            Title = title,
            Width = 460,
            SizeToContent = SizeToContent.Height,
            CanResize = false,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Content = new StackPanel
            {
                Margin = new Thickness(24),
                Spacing = 18,
                Children =
                {
                    new TextBlock { Text = title, FontSize = 20, FontWeight = FontWeight.SemiBold },
                    new TextBlock { Text = message, TextWrapping = TextWrapping.Wrap },
                    new StackPanel
                    {
                        Orientation = Avalonia.Layout.Orientation.Horizontal,
                        Spacing = 9,
                        HorizontalAlignment = Avalonia.Layout.HorizontalAlignment.Right,
                        Children = { cancel, primary }
                    }
                }
            }
        };
        primary.Click += (_, _) => { accepted = true; dialog.Close(); };
        cancel.Click += (_, _) => dialog.Close();
        await dialog.ShowDialog(this);
        return accepted;
    }

    private static string GetPlaylistId(MediaItem playlist, string playlistUrl)
    {
        if (Uri.TryCreate(playlistUrl, UriKind.Absolute, out var uri))
        {
            var listId = uri.Query.TrimStart('?')
                .Split('&', StringSplitOptions.RemoveEmptyEntries)
                .Select(part => part.Split('=', 2))
                .FirstOrDefault(pair => pair.Length == 2 && string.Equals(pair[0], "list", StringComparison.OrdinalIgnoreCase));
            if (listId is { Length: 2 } && !string.IsNullOrWhiteSpace(listId[1]))
                return Uri.UnescapeDataString(listId[1]);
        }

        return playlist.Id;
    }

    private static void OpenPath(string pathOrUrl)
    {
        var isWebUrl = Uri.TryCreate(pathOrUrl, UriKind.Absolute, out var uri) &&
                       uri.Scheme is "http" or "https";
        if (!isWebUrl && !Directory.Exists(pathOrUrl)) Directory.CreateDirectory(pathOrUrl);
        if (OperatingSystem.IsMacOS())
        {
            Process.Start(new ProcessStartInfo("open") { ArgumentList = { pathOrUrl }, UseShellExecute = false });
            return;
        }

        Process.Start(new ProcessStartInfo(pathOrUrl) { UseShellExecute = true });
    }

    private enum MessageKind
    {
        Information,
        Success,
        Warning,
        Error
    }
}
