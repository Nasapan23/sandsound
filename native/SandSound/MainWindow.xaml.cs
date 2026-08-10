using System.Diagnostics;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using SandSound.Models;
using SandSound.Services;
using Windows.Graphics;
using Windows.Storage.Pickers;
using WinRT.Interop;

namespace SandSound;

public sealed partial class MainWindow : Window
{
    private readonly SettingsService _settings = new();
    private readonly HistoryService _history = new();
    private YtDlpService? _ytDlp;
    private DownloadQueueService? _queue;
    private MediaItem? _preview;
    private string _previewSourceUrl = string.Empty;
    private bool _searchMode;
    private bool _checkingForUpdates;
    private bool _installingUpdate;
    private CancellationTokenSource? _discoveryCancellation;

    public MainWindow()
    {
        InitializeComponent();
        Title = "SandSound";
        ExtendsContentIntoTitleBar = true;
        SetTitleBar(AppTitleBar);
        ConfigureWindow();
        Closed += (_, _) =>
        {
            _discoveryCancellation?.Cancel();
            _queue?.CancelAll();
        };
        _ = InitializeAsync();
    }

    private async Task InitializeAsync()
    {
        await _settings.LoadAsync();
        ApplyTheme(_settings.Current.Theme);
        await _history.LoadAsync();
        _ytDlp = new YtDlpService(_settings);
        _queue = new DownloadQueueService(_ytDlp, _settings, _history, DispatcherQueue);

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
            ? "Ready — yt-dlp is bundled. FFmpeg is " + (File.Exists(Path.Combine(AppPaths.ToolsDirectory, "ffmpeg.exe")) ? "bundled." : "missing.")
            : "Development mode — yt-dlp will be resolved from PATH. Run the portable publish script before copying to USB.";

        Navigation.SelectedItem = Navigation.MenuItems[0];
        _ = CheckForUpdatesAsync(userInitiated: false);
    }

    private void ConfigureWindow()
    {
        var windowHandle = WindowNative.GetWindowHandle(this);
        var windowId = Microsoft.UI.Win32Interop.GetWindowIdFromWindow(windowHandle);
        var appWindow = AppWindow.GetFromWindowId(windowId);
        appWindow.Resize(new SizeInt32(1100, 780));
        if (appWindow.Presenter is OverlappedPresenter presenter)
        {
            presenter.PreferredMinimumWidth = 760;
            presenter.PreferredMinimumHeight = 620;
        }
        appWindow.TitleBar.PreferredHeightOption = TitleBarHeightOption.Standard;
    }

    private void Navigation_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        if (args.SelectedItemContainer?.Tag is not string tag) return;
        HomePage.Visibility = tag == "home" ? Visibility.Visible : Visibility.Collapsed;
        QueuePage.Visibility = tag == "queue" ? Visibility.Visible : Visibility.Collapsed;
        LibraryPage.Visibility = tag == "library" ? Visibility.Visible : Visibility.Collapsed;
        SettingsPage.Visibility = tag == "settings" ? Visibility.Visible : Visibility.Collapsed;
    }

    private void UrlMode_Click(object sender, RoutedEventArgs e)
    {
        _searchMode = false;
        UrlModeButton.IsChecked = true;
        SearchModeButton.IsChecked = false;
        SourceBox.PlaceholderText = "Paste a YouTube video or playlist URL";
        InspectButton.Content = "Inspect";
        SearchResultsSection.Visibility = Visibility.Collapsed;
    }

    private void SearchMode_Click(object sender, RoutedEventArgs e)
    {
        _searchMode = true;
        UrlModeButton.IsChecked = false;
        SearchModeButton.IsChecked = true;
        SourceBox.PlaceholderText = "Artist, title, remix, label…";
        InspectButton.Content = "Search";
        PreviewCard.Visibility = Visibility.Collapsed;
    }

    private async void SourceBox_KeyDown(object sender, KeyRoutedEventArgs e)
    {
        if (e.Key == Windows.System.VirtualKey.Enter) await DiscoverAsync();
    }

    private async void InspectButton_Click(object sender, RoutedEventArgs e) => await DiscoverAsync();

    private async Task DiscoverAsync()
    {
        if (_ytDlp is null) return;
        var input = SourceBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(input))
        {
            ShowMessage("Enter a URL or a search phrase.", InfoBarSeverity.Warning);
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
                SearchResultsSection.Visibility = Visibility.Visible;
                PreviewCard.Visibility = Visibility.Collapsed;
                if (results.Count == 0) ShowMessage("No results found.", InfoBarSeverity.Informational);
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
            ShowMessage(ex.Message, InfoBarSeverity.Error);
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
        PlaylistList.Visibility = isPlaylist ? Visibility.Visible : Visibility.Collapsed;
        PlaylistList.ItemsSource = isPlaylist ? media.Entries : null;
        ResyncPlaylistButton.Visibility = isPlaylist && !string.IsNullOrWhiteSpace(_previewSourceUrl)
            ? Visibility.Visible
            : Visibility.Collapsed;
        PreviewCard.Visibility = Visibility.Visible;
        SearchResultsSection.Visibility = Visibility.Collapsed;
        if (isPlaylist) PlaylistList.SelectAll();
    }

    private void SearchDownload_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button { CommandParameter: MediaItem media }) Enqueue([media]);
    }

    private void QueueButton_Click(object sender, RoutedEventArgs e)
    {
        if (_preview is null) return;
        if (_preview.Entries is { Count: > 0 })
        {
            var selected = PlaylistList.SelectedItems.Cast<MediaItem>().ToList();
            if (selected.Count == 0)
            {
                ShowMessage("Select at least one playlist item.", InfoBarSeverity.Warning);
                return;
            }
            Enqueue(
                selected,
                playlistId: GetPlaylistId(_preview, _previewSourceUrl),
                playlistUrl: _previewSourceUrl,
                playlistTitle: _preview.Title,
                skipDownloaded: true);
        }
        else Enqueue([_preview]);
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
            ? media.Where(x => !_history.ContainsMedia(x.Id)).ToList()
            : media.ToList();
        var skipped = media.Count - queuedMedia.Count;
        if (queuedMedia.Count == 0)
        {
            ShowMessage("Every selected playlist item is already in your library.", InfoBarSeverity.Informational);
            return;
        }
        var format = FormatBox.SelectedItem?.ToString() ?? "mp3";
        _settings.Current.DefaultFormat = format;
        _settings.Current.DefaultQuality = QualityBox.SelectedItem?.ToString() ?? "Best";
        _queue.Enqueue(queuedMedia, format, playlistId, playlistUrl, playlistTitle);
        var message = queuedMedia.Count == 1 ? "Added to the download queue." : $"Added {queuedMedia.Count} items to the queue.";
        if (skipped > 0) message += $" Skipped {skipped} already downloaded.";
        ShowMessage(message, InfoBarSeverity.Success);
        Navigation.SelectedItem = Navigation.MenuItems[1];
    }

    private void CancelItem_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button { CommandParameter: DownloadItem item }) item.Cancellation.Cancel();
    }

    private void CancelAll_Click(object sender, RoutedEventArgs e) => _queue?.CancelAll();

    private void OpenDownloads_Click(object sender, RoutedEventArgs e) => OpenFolder(_settings.Current.DownloadDirectory);

    private async void ResyncPlaylist_Click(object sender, RoutedEventArgs e)
    {
        if (_preview is null || string.IsNullOrWhiteSpace(_previewSourceUrl)) return;
        await InspectPlaylistAsync(_previewSourceUrl, true);
    }

    private async void OpenPlaylistHistory_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button { CommandParameter: PlaylistHistoryEntry playlist })
            await InspectPlaylistAsync(playlist.PlaylistUrl, false);
    }

    private async void ResyncPlaylistHistory_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button { CommandParameter: PlaylistHistoryEntry playlist })
            await InspectPlaylistAsync(playlist.PlaylistUrl, true);
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
            SourceBox.PlaceholderText = "Paste a YouTube video or playlist URL";
            InspectButton.Content = "Inspect";
            _preview = await _ytDlp.InspectAsync(playlistUrl, forceRefresh, _discoveryCancellation.Token);
            _previewSourceUrl = playlistUrl;
            ShowPreview(_preview);
            Navigation.SelectedItem = Navigation.MenuItems[0];

            var currentCount = _preview.Entries?.Count ?? 0;
            var newCount = _preview.Entries?.Count(item => !_history.ContainsMedia(item.Id)) ?? 0;
            ShowMessage(forceRefresh
                ? $"Playlist resynced: {currentCount} current tracks, {newCount} not yet downloaded."
                : $"Playlist opened: {currentCount} current tracks, {newCount} not yet downloaded.",
                InfoBarSeverity.Success);
        }
        catch (OperationCanceledException) { }
        catch (Exception ex)
        {
            AppLog.Write("Playlist sync failed", ex);
            ShowMessage($"Could not resync playlist: {ex.Message}", InfoBarSeverity.Error);
        }
        finally
        {
            SetDiscoveryBusy(false);
        }
    }

    private async void ClearHistory_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new ContentDialog
        {
            XamlRoot = RootGrid.XamlRoot,
            Title = "Clear download history?",
            Content = "Downloaded files will not be deleted.",
            PrimaryButtonText = "Clear",
            CloseButtonText = "Cancel",
            DefaultButton = ContentDialogButton.Close
        };
        if (await dialog.ShowAsync() == ContentDialogResult.Primary) await _history.ClearAsync();
    }

    private async void ChooseDownloadFolder_Click(object sender, RoutedEventArgs e)
    {
        var picker = new FolderPicker { SuggestedStartLocation = PickerLocationId.Downloads };
        picker.FileTypeFilter.Add("*");
        InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
        var folder = await picker.PickSingleFolderAsync();
        if (folder is not null) DownloadDirectoryBox.Text = folder.Path;
    }

    private async void ChooseCookieFile_Click(object sender, RoutedEventArgs e)
    {
        var picker = new FileOpenPicker { SuggestedStartLocation = PickerLocationId.DocumentsLibrary };
        picker.FileTypeFilter.Add(".txt");
        picker.FileTypeFilter.Add(".cookies");
        InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
        var file = await picker.PickSingleFileAsync();
        if (file is not null) CookieFileBox.Text = file.Path;
    }

    private async void SaveSettings_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(DownloadDirectoryBox.Text))
                throw new InvalidOperationException("Choose a download directory.");
            Directory.CreateDirectory(DownloadDirectoryBox.Text);
            _settings.Current.DownloadDirectory = DownloadDirectoryBox.Text;
            _settings.Current.CookieFile = CookieFileBox.Text;
            _settings.Current.CreatePlaylistFolders = PlaylistFoldersCheck.IsChecked == true;
            _settings.Current.Theme = ThemeBox.SelectedItem?.ToString() ?? "System";
            _settings.Current.ConcurrentDownloads = Math.Clamp((int)ConcurrencyBox.Value, 1, 8);
            await _settings.SaveAsync();
            _queue?.Reconfigure();
            ApplyTheme(_settings.Current.Theme);
            ShowMessage("Settings saved.", InfoBarSeverity.Success);
        }
        catch (Exception ex)
        {
            ShowMessage(ex.Message, InfoBarSeverity.Error);
        }
    }

    private async void LegacyCheckUpdates_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            ShowMessage("Checking GitHub for updates…", InfoBarSeverity.Informational);
            var update = await new UpdateService().CheckAsync();
            if (update is null)
            {
                ShowMessage("SandSound is up to date.", InfoBarSeverity.Success);
                return;
            }

            var dialog = new ContentDialog
            {
                XamlRoot = RootGrid.XamlRoot,
                Title = $"SandSound {update.Tag} is available",
                Content = "Portable apps update by replacing the application folder. Your Data and Downloads folders can be copied into the new release.",
                PrimaryButtonText = "Open release",
                CloseButtonText = "Later",
                DefaultButton = ContentDialogButton.Primary
            };
            if (await dialog.ShowAsync() == ContentDialogResult.Primary)
                Process.Start(new ProcessStartInfo(update.PageUrl) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            ShowMessage($"Update check failed: {ex.Message}", InfoBarSeverity.Error);
        }
    }

    private async void CheckUpdates_Click(object sender, RoutedEventArgs e) => await CheckForUpdatesAsync(userInitiated: true);

    private async Task CheckForUpdatesAsync(bool userInitiated)
    {
        if (_checkingForUpdates || _installingUpdate) return;
        _checkingForUpdates = true;
        try
        {
            if (userInitiated) ShowMessage("Checking GitHub for updates...", InfoBarSeverity.Informational);
            var update = await new UpdateService().CheckAsync();
            if (update is null)
            {
                if (userInitiated) ShowMessage("SandSound is up to date.", InfoBarSeverity.Success);
                return;
            }

            await ShowUpdateDialogAsync(update);
        }
        catch (Exception ex)
        {
            AppLog.Write("Update check failed", ex);
            if (userInitiated) ShowMessage($"Update check failed: {ex.Message}", InfoBarSeverity.Error);
        }
        finally
        {
            _checkingForUpdates = false;
        }
    }

    private async Task ShowUpdateDialogAsync(UpdateInfo update)
    {
        var updater = new UpdateService();
        var canInstall = updater.CanApplyUpdate() && !string.IsNullOrWhiteSpace(update.DownloadUrl);
        var dialog = new ContentDialog
        {
            XamlRoot = RootGrid.XamlRoot,
            Title = $"SandSound {update.Tag} is available",
            Content = canInstall
                ? "Download and install it now? SandSound will restart automatically. Your Data and Downloads folders will be kept."
                : "This release is available, but this installation cannot be updated automatically.",
            PrimaryButtonText = canInstall ? "Update now" : "Open release",
            CloseButtonText = "Later",
            DefaultButton = ContentDialogButton.Primary
        };
        if (await dialog.ShowAsync() != ContentDialogResult.Primary) return;

        if (!canInstall)
        {
            Process.Start(new ProcessStartInfo(update.PageUrl) { UseShellExecute = true });
            return;
        }

        if (_queue?.Items.Any(item => item.CanCancel) == true)
        {
            ShowMessage("Finish or cancel active downloads before installing an update.", InfoBarSeverity.Warning);
            return;
        }

        _installingUpdate = true;
        try
        {
            ShowMessage("Downloading update...", InfoBarSeverity.Informational);
            await updater.DownloadAndApplyAsync(update);
            ShowMessage("Update downloaded. Restarting SandSound...", InfoBarSeverity.Success);
            Close();
        }
        catch (Exception ex)
        {
            AppLog.Write("Update installation failed", ex);
            ShowMessage($"Update installation failed: {ex.Message}", InfoBarSeverity.Error);
            _installingUpdate = false;
        }
    }

    private void ApplyTheme(string theme)
    {
        RootGrid.RequestedTheme = theme switch
        {
            "Light" => ElementTheme.Light,
            "Dark" => ElementTheme.Dark,
            _ => ElementTheme.Default
        };
    }

    private void SetDiscoveryBusy(bool busy)
    {
        InspectButton.IsEnabled = !busy;
        SourceBox.IsEnabled = !busy;
        ResyncPlaylistButton.IsEnabled = !busy;
        DiscoveryProgress.Visibility = busy ? Visibility.Visible : Visibility.Collapsed;
    }

    private void ShowMessage(string message, InfoBarSeverity severity)
    {
        MessageBar.Message = message;
        MessageBar.Severity = severity;
        MessageBar.IsOpen = true;
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

    private static void OpenFolder(string path)
    {
        Directory.CreateDirectory(path);
        Process.Start(new ProcessStartInfo("explorer.exe", path) { UseShellExecute = true });
    }
}
