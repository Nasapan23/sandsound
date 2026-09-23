# SandSound 2.0 implementation

SandSound 2.0 is a full replacement for the original Python and CustomTkinter application. The product is written in C# on .NET 10, with a WinUI 3 shell on Windows and a parallel Avalonia shell on macOS.

## Why it was rebuilt

The rewrite removes several moving parts from the installed application: Python, a browser-style UI runtime, PyInstaller packaging, and a separate installer. A single native codebase makes the application easier to maintain, gives it Windows-native accessibility and DPI behavior, and reduces the number of runtime dependencies that can fail on another computer.

The media engines remain purpose-built tools: yt-dlp handles media discovery and downloads, while FFmpeg handles conversion. SandSound coordinates those tools through C# services and presents their progress in the native interface.

## Architecture

The implementation is deliberately small and organized around the responsibilities below.

| Area | Responsibility |
| --- | --- |
| `native/SandSound/MainWindow` | WinUI 3 application shell, navigation, user input, and view state. |
| `native/SandSound.Mac/MainWindow` | Equivalent macOS application shell built with Avalonia. |
| `Models` | Download, history, media-preview, and settings data. |
| `Services/YtDlpService` | URL inspection, YouTube search, and yt-dlp command construction. |
| `Services/DownloadQueueService` | Concurrent queue execution, progress, cancellation, and completed-download handling. |
| `Services/SettingsService` and `HistoryService` | Portable JSON-backed settings and download history. |
| `Services/AppPaths` and `AppLog` | Paths relative to the portable release root and portable diagnostic logging. |
| `scripts/publish-portable.ps1` | Self-contained Windows publish plus yt-dlp and FFmpeg packaging. |
| `scripts/publish-portable-macos.sh` | Self-contained macOS app bundle plus architecture-specific tools. |

There is no server component and no profile or registry storage requirement. User-facing data stays beside the application in the portable release folder.

## Fully portable release

Releases are self-contained folders. They can be copied to a USB drive or another folder and launched without installing .NET, yt-dlp, or FFmpeg.

```text
SandSound-win-x64/
├── SandSound.exe
├── Tools/
│   ├── yt-dlp.exe
│   ├── ffmpeg.exe
│   └── ffprobe.exe
├── Data/
└── Downloads/

SandSound-macos-arm64/ (or macos-x64)
├── SandSound.app/
│   └── Contents/MacOS/Tools/
│       ├── yt-dlp
│       ├── ffmpeg
│       └── ffprobe
├── Data/
└── Downloads/
```

`Data` contains settings, download history, and logs. `Downloads` is the default media destination. Both folders are created in the release root, so moving the full release folder moves the application and its local data together.

## Build and release

The project pins the .NET SDK in `global.json`. A local portable release is built with:

```powershell
.\scripts\publish-portable.ps1
```

GitHub Actions runs the Windows publisher and parallel Apple Silicon/Intel macOS publishers. Each pull request and branch build produces downloadable portable ZIP artifacts. Pushing a version tag such as `v2.0.3` creates a GitHub Release containing all three archives.

## Migration from 1.x

The legacy Python code, PyInstaller configuration, installer, screenshots, and Python test suite were removed from the 2.0 rewrite. They remain available in the repository history; the current branch is authoritative for the native applications and portable release pipelines.
