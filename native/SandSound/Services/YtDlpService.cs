using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using SandSound.Models;

namespace SandSound.Services;

public sealed record DownloadProgress(double Percent, string Detail, bool Processing = false);

public sealed class YtDlpService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true };
    private static readonly Regex ProgressPattern = new(
        @"SANDSOUND:\s*(?<percent>[\d.]+)%?\|(?<speed>[^|]*)\|(?<eta>.*)$",
        RegexOptions.Compiled | RegexOptions.CultureInvariant);

    private readonly SettingsService _settings;
    private string Executable => AppPaths.FindTool("yt-dlp.exe", "yt-dlp");

    public YtDlpService(SettingsService settings) => _settings = settings;

    public bool HasPortableTool => File.Exists(Path.Combine(AppPaths.ToolsDirectory, "yt-dlp.exe"));

    public async Task<MediaItem> InspectAsync(string url, bool forceRefresh = false, CancellationToken cancellationToken = default)
    {
        var args = CommonArguments();
        if (forceRefresh) args.Add("--no-cache-dir");
        args.AddRange(["--dump-single-json", "--flat-playlist", url]);
        var result = await ProcessRunner.RunAsync(Executable, args, cancellationToken: cancellationToken);
        EnsureSuccess(result);
        return JsonSerializer.Deserialize<MediaItem>(result.StandardOutput, JsonOptions)
               ?? throw new InvalidOperationException("yt-dlp returned no media information.");
    }

    public async Task<IReadOnlyList<MediaItem>> SearchAsync(string query, int count = 6, CancellationToken cancellationToken = default)
    {
        var args = CommonArguments();
        args.AddRange(["--dump-single-json", "--flat-playlist", $"ytsearch{Math.Clamp(count, 1, 12)}:{query}"]);
        var result = await ProcessRunner.RunAsync(Executable, args, cancellationToken: cancellationToken);
        EnsureSuccess(result);
        var root = JsonSerializer.Deserialize<MediaItem>(result.StandardOutput, JsonOptions);
        return root?.Entries?.Where(x => !string.IsNullOrWhiteSpace(x.Id)).ToList() ?? [];
    }

    public async Task DownloadAsync(
        DownloadItem item,
        IProgress<DownloadProgress> progress,
        CancellationToken cancellationToken)
    {
        var settings = _settings.Current;
        var outputDirectory = settings.DownloadDirectory;
        if (settings.CreatePlaylistFolders && !string.IsNullOrWhiteSpace(item.PlaylistTitle))
            outputDirectory = Path.Combine(outputDirectory, SanitizeFileName(item.PlaylistTitle));
        Directory.CreateDirectory(outputDirectory);

        var args = CommonArguments();
        args.AddRange([
            "--newline",
            "--no-color",
            "--windows-filenames",
            "--no-playlist",
            "--progress-template", "download:SANDSOUND:%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s",
            "--output", Path.Combine(outputDirectory, "%(title)s [%(id)s].%(ext)s"),
            "--add-metadata"
        ]);

        var format = item.Format.ToLowerInvariant();
        if (format is "mp3" or "m4a" or "opus" or "flac" or "wav")
        {
            args.AddRange(["--extract-audio", "--audio-format", format]);
            if (settings.DefaultQuality != "Best" && format == "mp3")
            {
                var quality = settings.DefaultQuality.Replace(" kbps", string.Empty, StringComparison.OrdinalIgnoreCase);
                args.AddRange(["--audio-quality", quality + "K"]);
            }
        }
        else
        {
            var selector = settings.DefaultQuality switch
            {
                "1080p" => "bv*[height<=1080]+ba/b[height<=1080]",
                "720p" => "bv*[height<=720]+ba/b[height<=720]",
                "480p" => "bv*[height<=480]+ba/b[height<=480]",
                _ => "bv*+ba/b"
            };
            args.AddRange(["--format", selector, "--merge-output-format", format]);
        }
        args.Add(item.Url);

        var result = await ProcessRunner.RunAsync(Executable, args, line =>
        {
            var match = ProgressPattern.Match(line.Trim());
            if (match.Success)
            {
                var raw = match.Groups["percent"].Value.Trim();
                _ = double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var percent);
                var speed = match.Groups["speed"].Value.Trim();
                var eta = match.Groups["eta"].Value.Trim();
                var detail = string.Join("  •  ", new[] { speed, string.IsNullOrWhiteSpace(eta) ? string.Empty : $"ETA {eta}" }.Where(x => !string.IsNullOrWhiteSpace(x)));
                progress.Report(new DownloadProgress(percent, detail));
            }
            else if (line.Contains("[Merger]", StringComparison.OrdinalIgnoreCase) ||
                     line.Contains("[ExtractAudio]", StringComparison.OrdinalIgnoreCase) ||
                     line.Contains("[VideoConvertor]", StringComparison.OrdinalIgnoreCase))
            {
                progress.Report(new DownloadProgress(100, "Finishing media…", true));
            }
        }, cancellationToken);

        EnsureSuccess(result);
    }

    private List<string> CommonArguments()
    {
        var args = new List<string> { "--no-warnings", "--ignore-config" };
        var cookieFile = _settings.Current.CookieFile;
        if (!string.IsNullOrWhiteSpace(cookieFile) && File.Exists(cookieFile))
            args.AddRange(["--cookies", cookieFile]);

        var ffmpeg = Path.Combine(AppPaths.ToolsDirectory, "ffmpeg.exe");
        if (File.Exists(ffmpeg)) args.AddRange(["--ffmpeg-location", AppPaths.ToolsDirectory]);
        return args;
    }

    private static void EnsureSuccess(ProcessResult result)
    {
        if (result.ExitCode == 0) return;
        var message = result.StandardError.Split(Environment.NewLine, StringSplitOptions.RemoveEmptyEntries).LastOrDefault()
                      ?? "yt-dlp could not complete the request.";
        throw new InvalidOperationException(message.Replace("ERROR: ", string.Empty, StringComparison.OrdinalIgnoreCase));
    }

    private static string SanitizeFileName(string value)
    {
        foreach (var character in Path.GetInvalidFileNameChars()) value = value.Replace(character, '_');
        return value.Trim().TrimEnd('.');
    }
}
