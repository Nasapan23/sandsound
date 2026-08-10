using System.Diagnostics;
using System.Net.Http.Headers;
using System.Text.Json;

namespace SandSound.Services;

public sealed record UpdateInfo(
    Version Version,
    string Tag,
    string PageUrl,
    string Notes,
    string? DownloadUrl,
    string? AssetName);

public sealed class UpdateService
{
    public static readonly Version CurrentVersion = new(2, 0, 2);
    private const string LatestReleaseApi = "https://api.github.com/repos/Nasapan23/sandsound/releases/latest";
    private const string PortableAssetName = "SandSound-win-x64.zip";

    public async Task<UpdateInfo?> CheckAsync(CancellationToken cancellationToken = default)
    {
        using var client = CreateClient();
        await using var stream = await client.GetStreamAsync(LatestReleaseApi, cancellationToken);
        using var payload = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
        var root = payload.RootElement;
        var tag = root.GetProperty("tag_name").GetString() ?? string.Empty;
        if (!Version.TryParse(tag.TrimStart('v', 'V').Split('-', 2)[0], out var version) || version <= CurrentVersion)
            return null;

        var asset = root.TryGetProperty("assets", out var assets)
            ? assets.EnumerateArray().FirstOrDefault(item => string.Equals(
                item.TryGetProperty("name", out var name) ? name.GetString() : null,
                PortableAssetName,
                StringComparison.OrdinalIgnoreCase))
            : default;
        var hasAsset = asset.ValueKind == JsonValueKind.Object;
        return new UpdateInfo(
            version,
            tag,
            root.GetProperty("html_url").GetString() ?? "https://github.com/Nasapan23/sandsound/releases/latest",
            root.TryGetProperty("body", out var body) ? body.GetString() ?? string.Empty : string.Empty,
            hasAsset && asset.TryGetProperty("browser_download_url", out var downloadUrl) ? downloadUrl.GetString() : null,
            hasAsset && asset.TryGetProperty("name", out var assetName) ? assetName.GetString() : null);
    }

    public bool CanApplyUpdate() =>
        OperatingSystem.IsWindows() &&
        Environment.ProcessPath is { } processPath &&
        processPath.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) &&
        File.Exists(processPath) &&
        Directory.Exists(AppPaths.ExecutableDirectory);

    public async Task DownloadAndApplyAsync(UpdateInfo update, CancellationToken cancellationToken = default)
    {
        if (!CanApplyUpdate())
            throw new InvalidOperationException("Automatic updates are available only from the portable SandSound app.");
        if (string.IsNullOrWhiteSpace(update.DownloadUrl) || string.IsNullOrWhiteSpace(update.AssetName))
            throw new InvalidOperationException("This release does not include a portable update package.");

        var updateDirectory = Path.Combine(Path.GetTempPath(), "SandSound-Update-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(updateDirectory);
        var archivePath = Path.Combine(updateDirectory, update.AssetName);

        try
        {
            using var client = CreateClient();
            using var response = await client.GetAsync(update.DownloadUrl, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
            response.EnsureSuccessStatusCode();
            await using var source = await response.Content.ReadAsStreamAsync(cancellationToken);
            await using var destination = File.Create(archivePath);
            await source.CopyToAsync(destination, cancellationToken);
            await destination.FlushAsync(cancellationToken);
            if (new FileInfo(archivePath).Length == 0) throw new InvalidOperationException("The update download was empty.");

            StartReplacementHelper(archivePath, updateDirectory);
        }
        catch
        {
            TryDelete(updateDirectory);
            throw;
        }
    }

    private static HttpClient CreateClient()
    {
        var client = new HttpClient { Timeout = TimeSpan.FromSeconds(30) };
        client.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("SandSound", CurrentVersion.ToString()));
        client.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        return client;
    }

    private static void StartReplacementHelper(string archivePath, string updateDirectory)
    {
        var processPath = Environment.ProcessPath ?? throw new InvalidOperationException("Could not locate SandSound.");
        var scriptPath = Path.Combine(updateDirectory, "apply-update.ps1");
        File.WriteAllText(scriptPath, ReplacementScript);
        var powershell = Path.Combine(Environment.SystemDirectory, "WindowsPowerShell", "v1.0", "powershell.exe");
        if (!File.Exists(powershell)) powershell = "powershell.exe";

        var startInfo = new ProcessStartInfo(powershell)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            WorkingDirectory = updateDirectory
        };
        startInfo.ArgumentList.Add("-NoProfile");
        startInfo.ArgumentList.Add("-ExecutionPolicy");
        startInfo.ArgumentList.Add("Bypass");
        startInfo.ArgumentList.Add("-File");
        startInfo.ArgumentList.Add(scriptPath);
        startInfo.ArgumentList.Add("-TargetDirectory");
        startInfo.ArgumentList.Add(AppPaths.ExecutableDirectory);
        startInfo.ArgumentList.Add("-TargetExe");
        startInfo.ArgumentList.Add(processPath);
        startInfo.ArgumentList.Add("-ArchivePath");
        startInfo.ArgumentList.Add(archivePath);
        startInfo.ArgumentList.Add("-ParentPid");
        startInfo.ArgumentList.Add(Environment.ProcessId.ToString());
        if (Process.Start(startInfo) is null) throw new InvalidOperationException("Could not start the update installer.");
    }

    private static void TryDelete(string path)
    {
        try { if (Directory.Exists(path)) Directory.Delete(path, true); }
        catch { /* The helper or antivirus may still hold the temporary files. */ }
    }

    private const string ReplacementScript = """
param(
    [Parameter(Mandatory = $true)][string]$TargetDirectory,
    [Parameter(Mandatory = $true)][string]$TargetExe,
    [Parameter(Mandatory = $true)][string]$ArchivePath,
    [Parameter(Mandatory = $true)][int]$ParentPid
)

$ErrorActionPreference = 'Stop'
$updateRoot = Join-Path (Split-Path -Parent $ArchivePath) 'unpacked'
$backupRoot = Join-Path (Split-Path -Parent $TargetDirectory) ('.sandsound-backup-' + [guid]::NewGuid().ToString('N'))

try {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if (-not (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 500
    }

    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $updateRoot -Force
    $sourceRoot = $updateRoot
    if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot 'SandSound.exe'))) {
        $candidate = Get-ChildItem -LiteralPath $updateRoot -Directory | Select-Object -First 1
        if ($candidate) { $sourceRoot = $candidate.FullName }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot 'SandSound.exe'))) {
        throw 'The update archive does not contain SandSound.exe.'
    }

    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    Get-ChildItem -LiteralPath $TargetDirectory -Force |
        Where-Object { $_.Name -notin @('Data', 'Downloads') } |
        Move-Item -Destination $backupRoot -Force

    try {
        Get-ChildItem -LiteralPath $sourceRoot -Force |
            Where-Object { $_.Name -notin @('Data', 'Downloads') } |
            Copy-Item -Destination $TargetDirectory -Recurse -Force
    }
    catch {
        Get-ChildItem -LiteralPath $TargetDirectory -Force |
            Where-Object { $_.Name -notin @('Data', 'Downloads') } |
            Remove-Item -Recurse -Force
        Get-ChildItem -LiteralPath $backupRoot -Force |
            Copy-Item -Destination $TargetDirectory -Recurse -Force
        throw
    }

    Start-Process -FilePath $TargetExe -WorkingDirectory $TargetDirectory
}
finally {
    Start-Sleep -Milliseconds 500
    Remove-Item -LiteralPath $backupRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Split-Path -Parent $ArchivePath) -Recurse -Force -ErrorAction SilentlyContinue
}
""";
}
