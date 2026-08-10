[CmdletBinding()]
param(
    [ValidateSet("x64")]
    [string]$Architecture = "x64",
    [switch]$SkipToolDownload
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$project = Join-Path $repoRoot "native\SandSound\SandSound.csproj"
$output = Join-Path $repoRoot "artifacts\SandSound-win-$Architecture"
$cache = Join-Path $repoRoot "artifacts\.cache"
$dotnet = Join-Path $repoRoot ".tools\dotnet\dotnet.exe"

if (-not (Test-Path $dotnet)) {
    $dotnet = (Get-Command dotnet -ErrorAction Stop).Source
}

$resolvedRoot = [IO.Path]::GetFullPath($repoRoot)
$resolvedOutput = [IO.Path]::GetFullPath($output)
if (-not $resolvedOutput.StartsWith((Join-Path $resolvedRoot "artifacts"), [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to replace an output directory outside this repository."
}

if (Test-Path $resolvedOutput) {
    Remove-Item -LiteralPath $resolvedOutput -Recurse -Force
}
New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null
New-Item -ItemType Directory -Path $cache -Force | Out-Null

& $dotnet publish $project `
    --configuration Release `
    --runtime "win-$Architecture" `
    --self-contained true `
    --output $resolvedOutput `
    -p:PublishSingleFile=true `
    -p:IncludeAllContentForSelfExtract=true
if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed with exit code $LASTEXITCODE." }

$tools = Join-Path $resolvedOutput "Tools"
New-Item -ItemType Directory -Path $tools -Force | Out-Null

if (-not $SkipToolDownload) {
    $ytDlp = Join-Path $cache "yt-dlp.exe"
    if (-not (Test-Path $ytDlp)) {
        Invoke-WebRequest -UseBasicParsing `
            "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" `
            -OutFile $ytDlp
    }
    Copy-Item -LiteralPath $ytDlp -Destination (Join-Path $tools "yt-dlp.exe") -Force

    $ffmpegArchive = Join-Path $cache "ffmpeg-release-essentials.zip"
    if (-not (Test-Path $ffmpegArchive)) {
        Invoke-WebRequest -UseBasicParsing `
            "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" `
            -OutFile $ffmpegArchive
    }
    $ffmpegExtract = Join-Path $cache "ffmpeg-release-essentials"
    if (-not (Test-Path $ffmpegExtract)) {
        Expand-Archive -LiteralPath $ffmpegArchive -DestinationPath $ffmpegExtract
    }
    $ffmpeg = Get-ChildItem -Path $ffmpegExtract -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
    $ffprobe = Get-ChildItem -Path $ffmpegExtract -Filter "ffprobe.exe" -Recurse | Select-Object -First 1
    if (-not $ffmpeg -or -not $ffprobe) { throw "FFmpeg archive did not contain the expected tools." }
    Copy-Item -LiteralPath $ffmpeg.FullName -Destination (Join-Path $tools "ffmpeg.exe") -Force
    Copy-Item -LiteralPath $ffprobe.FullName -Destination (Join-Path $tools "ffprobe.exe") -Force
}

New-Item -ItemType Directory -Path (Join-Path $resolvedOutput "Data") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $resolvedOutput "Downloads") -Force | Out-Null

$size = [math]::Round(((Get-ChildItem $resolvedOutput -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host "Portable SandSound created at: $resolvedOutput"
Write-Host "Total size: $size MB"
Write-Host "Copy this entire folder to a USB drive and launch SandSound.exe."
