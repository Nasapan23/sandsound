# SandSound 2.0 implementation

SandSound 2.0 is a full replacement for the original Python and CustomTkinter application. The product is now a native Windows desktop application written in C# on .NET 10 with WinUI 3.

## Why it was rebuilt

The rewrite removes several moving parts from the installed application: Python, a browser-style UI runtime, PyInstaller packaging, and a separate installer. A single native codebase makes the application easier to maintain, gives it Windows-native accessibility and DPI behavior, and reduces the number of runtime dependencies that can fail on another computer.

The media engines remain purpose-built tools: yt-dlp handles media discovery and downloads, while FFmpeg handles conversion. SandSound coordinates those tools through C# services and presents their progress in the native interface.

## Architecture

The implementation is deliberately small and organized around the responsibilities below.

| Area | Responsibility |
| --- | --- |
| `MainWindow` | WinUI 3 application shell, navigation, user input, and view state. |
| `Models` | Download, history, media-preview, and settings data. |
| `Services/YtDlpService` | URL inspection, YouTube search, and yt-dlp command construction. |
| `Services/DownloadQueueService` | Concurrent queue execution, progress, cancellation, and completed-download handling. |
| `Services/SettingsService` and `HistoryService` | Portable JSON-backed settings and download history. |
| `Services/AppPaths` and `AppLog` | Paths relative to the executable and portable diagnostic logging. |
| `scripts/publish-portable.ps1` | Self-contained .NET publish plus yt-dlp and FFmpeg packaging. |

There is no server component and no profile or registry storage requirement. User-facing data stays beside the executable.

## Fully portable release

The release is an unpackaged, self-contained Windows x64 folder. It can be copied to a USB drive or another Windows folder and run by launching `SandSound.exe`.

```text
SandSound-win-x64/
├── SandSound.exe
├── Tools/
│   ├── yt-dlp.exe
│   ├── ffmpeg.exe
│   └── ffprobe.exe
├── Data/
└── Downloads/
```

`Data` contains settings, download history, and logs. `Downloads` is the default media destination. Both folders are created next to the executable, so moving the full release folder moves the application and its local data together.

## Build and release

The project pins the .NET SDK in `global.json`. A local portable release is built with:

```powershell
.\scripts\publish-portable.ps1
```

GitHub Actions uses the same publishing script on Windows. Each pull request and branch build produces a downloadable portable ZIP artifact. Pushing a version tag such as `v2.0.1` also creates a GitHub Release containing that ZIP.

## Migration from 1.x

The legacy Python code, PyInstaller configuration, installer, screenshots, and Python test suite were removed from the 2.0 rewrite branch. They remain available in the repository history and the `main` branch until the rewrite is merged. The 2.0 branch is the authoritative source for the native application and portable release pipeline.
