using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace SandSound.Models;

public enum DownloadState
{
    Queued,
    Downloading,
    Processing,
    Completed,
    Failed,
    Cancelled
}

public sealed class DownloadItem : INotifyPropertyChanged
{
    private DownloadState _state = DownloadState.Queued;
    private double _progress;
    private string _detail = "Waiting";

    public required string Id { get; init; }
    public required string Url { get; init; }
    public required string Title { get; init; }
    public required string Format { get; init; }
    public string PlaylistTitle { get; init; } = string.Empty;
    public CancellationTokenSource Cancellation { get; } = new();

    public DownloadState State
    {
        get => _state;
        set { if (_state != value) { _state = value; OnPropertyChanged(); OnPropertyChanged(nameof(StateText)); OnPropertyChanged(nameof(CanCancel)); } }
    }

    public double Progress
    {
        get => _progress;
        set { if (Math.Abs(_progress - value) > 0.01) { _progress = value; OnPropertyChanged(); } }
    }

    public string Detail
    {
        get => _detail;
        set { if (_detail != value) { _detail = value; OnPropertyChanged(); } }
    }

    public string StateText => State.ToString();
    public bool CanCancel => State is DownloadState.Queued or DownloadState.Downloading or DownloadState.Processing;

    public event PropertyChangedEventHandler? PropertyChanged;
    private void OnPropertyChanged([CallerMemberName] string? name = null) => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}
