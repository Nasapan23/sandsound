# SandSound 2.0

SandSound is a native Windows downloader for YouTube audio, video, and playlists. Version 2.0 is a complete C# and WinUI 3 rewrite designed to run directly from a USB drive without an installer, Python, .NET, FFmpeg, or yt-dlp already installed on the destination computer.

For an overview of the 2.0 architecture, portability model, and release pipeline, see [SandSound 2.0 implementation notes](docs/sandsound-2.0.md).

## Why native WinUI instead of Chromium

WinUI 3 gives SandSound the Windows 11 control set, Mica backdrop, native accessibility, DPI handling, keyboard behavior, and substantially less application overhead than shipping a browser engine. The published app is unpackaged and self-contained: the .NET and Windows App SDK runtimes travel with the executable, while yt-dlp and FFmpeg live in the adjacent `Tools` folder.

## Features

- URL inspection for individual videos and playlists
- YouTube search with direct queueing
- MP3, M4A, OPUS, FLAC, WAV, MP4, WebM, and MKV output
- Multi-select playlist downloads and per-playlist folders
- Concurrent download queue with per-item progress and cancellation
- Cookie-file authentication for restricted content
- Portable settings, logs, history, and default download directory
- System, light, and dark themes
- No installer and no writes to the Windows registry or user profile

## Run a portable release

Copy the complete `SandSound-win-x64` folder to a USB drive or any Windows folder, then launch `SandSound.exe`. Keep the `Tools` folder beside the executable. SandSound creates these portable folders beside itself:

```text
SandSound-win-x64/
├── SandSound.exe
├── Tools/
│   ├── yt-dlp.exe
│   ├── ffmpeg.exe
│   └── ffprobe.exe
├── Data/          settings, history, and logs
└── Downloads/     default media destination
```

The destination computer must run a supported 64-bit edition of Windows 10 (1809 or later) or Windows 11. Writing downloads back to the USB drive can be slower than using a local download folder, which can be changed in Settings.

## Build from source

Requirements:

- Windows 10/11 x64
- .NET 10 SDK or Visual Studio with .NET desktop tooling
- Internet access the first time packages and portable tools are restored

Create the complete release folder:

```powershell
.\scripts\publish-portable.ps1
```

The output is written to `artifacts\SandSound-win-x64`. The script restores/publishes the native app and downloads the official yt-dlp Windows executable plus an FFmpeg essentials build. Cached downloads are reused on later runs.

For a quick development build when yt-dlp is already on `PATH`:

```powershell
dotnet build .\native\SandSound\SandSound.csproj -c Debug -r win-x64
```

## Project layout

```text
native/SandSound/
├── Models/        app data and queue state
├── Services/      yt-dlp process host, persistence, and scheduling
├── App.xaml       global WinUI resources
└── MainWindow.*   native application shell
scripts/
└── publish-portable.ps1
```

The previous Python/CustomTkinter implementation remains available in the repository's `main` branch and earlier releases. This branch contains only the native application and its portable build pipeline.

## Portable-data note

Settings and history are intentionally stored next to the executable. This makes the app truly movable, but it also means anyone with access to the USB drive can read the selected cookie-file path and download history. Cookie contents are never copied into SandSound's data folder.

SandSound is a GUI wrapper around [yt-dlp](https://github.com/yt-dlp/yt-dlp). Only download content you are authorized to save and follow the rules applicable to the service and your location.

## License

MIT — see [LICENSE](LICENSE).
