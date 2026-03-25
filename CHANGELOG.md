# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project uses semantic versioning.

## [Unreleased]

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
