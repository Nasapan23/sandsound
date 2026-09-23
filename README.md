# SandSound 2.0

SandSound is a portable desktop downloader for YouTube audio, video, and playlists. Version 2.0 ships parallel native desktop shells: WinUI 3 on Windows and Avalonia on macOS, backed by the same C# models and download services. Both releases run from a movable folder without an installer, Python, .NET, FFmpeg, or yt-dlp already installed on the destination computer.

For an overview of the 2.0 architecture, portability model, and release pipeline, see [SandSound 2.0 implementation notes](docs/sandsound-2.0.md).

## Native desktop shells instead of Chromium

WinUI 3 gives the Windows build the Windows control set and native window behavior. The macOS build uses Avalonia's native desktop backend while sharing SandSound's models, portable storage, yt-dlp integration, queue, and history behavior. The published apps are self-contained; the .NET runtime, yt-dlp, and FFmpeg all travel with the application.

## Features

- URL inspection for individual videos and playlists
- YouTube search with direct queueing
- MP3, M4A, OPUS, FLAC, WAV, MP4, WebM, and MKV output
- Multi-select playlist downloads and per-playlist folders
- Concurrent download queue with per-item progress and cancellation
- Cookie-file authentication for restricted content
- Portable settings, logs, history, and default download directory
- System, light, and dark themes
- Separate Intel and Apple Silicon macOS builds
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

### macOS

Download the archive matching the Mac processor, extract the complete folder, and open `SandSound.app`:

```text
SandSound-macos-arm64/       Apple Silicon
├── SandSound.app/
│   └── Contents/MacOS/Tools/   bundled yt-dlp, FFmpeg, and FFprobe
├── Data/
└── Downloads/

SandSound-macos-x64/         Intel
└── ...same layout...
```

The app supports macOS 13 and later, including macOS 27. Keep the `.app`, `Data`, and `Downloads` entries together when moving it. Public CI artifacts are ad-hoc signed; until release builds are Developer ID signed and notarized, the first launch may require Control-clicking `SandSound.app`, choosing **Open**, and confirming the prompt.

## Build from source

Windows requirements:

- Windows 10/11 x64
- .NET 10 SDK or Visual Studio with .NET desktop tooling
- Internet access the first time packages and portable tools are restored

Create the complete release folder:

```powershell
.\scripts\publish-portable.ps1
```

The output is written to `artifacts\SandSound-win-x64`. The script restores/publishes the native app and downloads the official yt-dlp Windows executable plus an FFmpeg essentials build. Cached downloads are reused on later runs.

macOS requirements:

- macOS 13 or later
- .NET 10 SDK
- Internet access the first time packages and portable tools are restored

Create an Apple Silicon release (use `x64` for an Intel release):

```bash
bash ./scripts/publish-portable-macos.sh --architecture arm64
```

The output is written to `artifacts/SandSound-macos-arm64`. The script creates a standard `.app` bundle, downloads the macOS yt-dlp binary plus architecture-matched static FFmpeg tools, creates the portable data folders, and ad-hoc signs the app bundle.

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
native/SandSound.Mac/
├── Services/      Avalonia UI-thread queue adapter
├── App.axaml      macOS application resources
└── MainWindow.*   parallel macOS application shell
scripts/
├── publish-portable.ps1
└── publish-portable-macos.sh
```

The previous Python/CustomTkinter implementation remains available in the repository history and earlier releases. The current source contains the Windows and macOS C# applications and their portable build pipelines.

## Portable-data note

Settings and history are intentionally stored in the release folder beside the application. This makes the app truly movable, but it also means anyone with access to the USB drive can read the selected cookie-file path and download history. Cookie contents are never copied into SandSound's data folder.

SandSound is a GUI wrapper around [yt-dlp](https://github.com/yt-dlp/yt-dlp). Only download content you are authorized to save and follow the rules applicable to the service and your location.

## License

MIT — see [LICENSE](LICENSE).
