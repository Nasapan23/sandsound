# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project uses semantic versioning.

## [Unreleased]

## [2.0.1] - 2026-08-10

### Added
- Playlist history now keeps the playlist URL and downloaded track IDs so playlists can be reopened later.
- Playlist history and playlist previews now provide a resync action that fetches the current playlist contents.

### Fixed
- In-app notifications render above the active page instead of behind its controls.
- Resync bypasses yt-dlp's local cache and reports tracks not already in the library.

### Added
- Native Windows CI now restores the SDK pinned in `global.json`, publishes the complete portable folder, and verifies its executable and bundled media tools.
- GitHub Actions uploads a portable ZIP for every build and creates a GitHub Release ZIP automatically for version tags.

### Changed
- The download screen now has a more spacious, modern dashboard layout with clearer actions and improved visual hierarchy.

### Fixed
- Playlist detection now handles YouTube and Music YouTube `watch?...&list=...` URLs.

## [2.0.0] - 2026-08-08

### Added
- Complete native C# and WinUI 3 application with Mica, Windows 11 controls, and system theme support.
- Unpackaged, self-contained .NET 10 x64 publishing for copy-and-run USB deployment.
- Portable yt-dlp and FFmpeg toolchain bundled by `scripts/publish-portable.ps1`.
- Portable settings, download history, logs, and downloads stored beside the executable.
- Native URL inspection, YouTube search, playlist selection, concurrent queue, progress, and cancellation.
- MP3, M4A, OPUS, FLAC, WAV, MP4, WebM, and MKV output choices.
- Cookie-file authentication, playlist folders, smart re-download filtering, and GitHub update checks.

### Changed
- Replaced CustomTkinter, Python, PyInstaller, SQLite, and the Inno Setup installer with one native Windows codebase and a zipped portable release.
- Release artifacts no longer install files, create shortcuts, write registry values, or require administrator access.

### Removed
- Removed the legacy Python application, tests, screenshots, requirements, PyInstaller spec, and installer from the native rewrite branch. They remain recoverable from `main` and existing Git history.

## [1.0.6] - 2026-03-26

### Fixed
- Removed hidden placeholder frames that were reserving vertical space and pushing the whole UI downward.
- Update and playlist banners now only take space when visible, restoring the expected startup layout.

## [1.0.5] - 2026-03-26

### Added
- Background GitHub release checks with in-app update notifications for packaged Windows builds.
- Windows self-update flow that downloads the newest release, swaps the executable after exit, and restarts the app.
- Unit tests covering updater behavior and playlist bar text formatting.

### Fixed
- Playlist info bar now keeps the `View Playlist` button visible when playlist titles are very long.
- Playlist bar text is truncated cleanly instead of overrunning the action area.

## [1.0.4] - 2026-03-25

### Added
- SQLite persistence via `sandsound.db` for playlists, downloads, and metadata cache.
- Automatic one-time migration from legacy `download_history.json` with `.bak` backup.
- Async UI utilities (`DebouncedCallback`, `BackgroundTaskPool`) for smoother background work.
- Configurable concurrent download setting in the UI (bounded `1..8`).
- Download cancel support for single downloads and playlist batch downloads.
- Unit test suite covering config, database, download manager, downloader cache, and UI async helpers.

### Changed
- Playlist info loading now prefers cached data for responsiveness, then refreshes live data when needed.
- Requirements simplified to unpinned `yt-dlp`.
- README updated with runtime guidance for JavaScript runtime warnings.
- UI copy cleaned up to remove emoji-based status markers.

### Fixed
- Parallel download handling and task update buffering for improved stability.
- Playlist selection/open flow reliability in the app and playlist view.

### Build/CI
- GitHub Actions release workflow now caches pip dependencies and runs unit tests before packaging.
- PyInstaller spec updated with hook-based hidden import/data collection for `customtkinter` and `yt-dlp`.
- PyInstaller build command now uses warning-level logs for cleaner release output.

## [1.0.3] - 2026-03-25

### Changed
- Release packaging adjusted to reduce false-positive detections (UPX disabled).
