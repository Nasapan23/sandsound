"""
Main application window for SandSound.
"""

from concurrent.futures import Future
import threading
import time
import queue
import webbrowser
import customtkinter as ctk
from pathlib import Path
from typing import Optional, List

from .. import __version__
from ..config import Config
from ..database import SandSoundDatabase, extract_video_id
from ..downloader import Downloader, DownloadProgress, DownloadStatus, VideoInfo
from ..download_manager import DownloadManager, DownloadTask, AggregateProgress, TaskStatus
from ..history import DownloadHistory
from ..updater import AppUpdater, UpdateError, UpdateInfo
from .async_utils import BackgroundTaskPool
from .playlist_bar import build_playlist_bar_text
from .components import UrlInput, FormatSelector, ProgressCard, Colors
from .playlist_view import PlaylistViewDialog, PlaylistVideo, VideoStatus
from .playlist_history import PlaylistHistoryDialog
from .settings import SettingsDialog


class SandSoundApp(ctk.CTk):
    """Main application window."""

    URL_CACHE_MAX_AGE_SECONDS = 6 * 60 * 60
    PLAYLIST_DIALOG_CACHE_MAX_AGE_SECONDS = 15 * 60
    MAX_INFO_FETCH_WORKERS = 2

    def __init__(self, config: Config) -> None:
        super().__init__()

        self._config = config
        self._database = SandSoundDatabase()
        
        # Validate and clean cookie file if corrupted
        if config.cookie_file and Path(config.cookie_file).is_file():
            try:
                with open(config.cookie_file, "rb") as f:
                    content = f.read()
                    if b'\x00' in content:
                        # Cookie file is corrupted, clear it
                        print("[WARNING] Cookie file is corrupted (contains null bytes) - clearing it")
                        config.cookie_file = ""
            except Exception:
                pass
        
        self._downloader = Downloader(
            download_dir=config.download_dir,
            cookie_file=config.cookie_file if config.is_cookie_valid() else None,
            ffmpeg_location=config.get_ffmpeg_location(),
            database=self._database,
        )
        self._history = DownloadHistory(database=self._database)
        self._download_manager: Optional[DownloadManager] = None
        self._info_pool = BackgroundTaskPool(self.MAX_INFO_FETCH_WORKERS)
        self._download_pool = BackgroundTaskPool(1)
        self._update_pool = BackgroundTaskPool(1)
        self._download_future: Optional[Future] = None
        self._is_closing = False
        self._is_downloading = False
        self._cancel_event: Optional[threading.Event] = None
        self._current_video_info: Optional[VideoInfo] = None
        self._pending_playlist_url: Optional[str] = None
        self._playlist_fetch_in_progress = False
        self._playlist_dialog: Optional[PlaylistViewDialog] = None
        self._playlist_bar_visible = False
        self._info_request_token = 0
        self._entries_map: dict = {}  # For tracking entries during concurrent download
        self._updater = AppUpdater(current_version=__version__)
        self._available_update: Optional[UpdateInfo] = None
        self._update_banner_visible = False
        self._update_check_started = False
        self._update_action_in_progress = False
        
        # UI update throttling
        self._progress_queue = queue.Queue(maxsize=10)
        # Use per-task buffer to avoid dropping updates during bursts
        self._task_update_buffer: dict = {}
        self._task_buffer_lock = threading.Lock()
        self._aggregate_update_queue = queue.Queue(maxsize=5)
        self._last_progress_update = 0.0
        self._last_task_update = 0.0
        self._last_aggregate_update = 0.0
        self._progress_update_interval = 0.1  # Update UI max every 100ms
        self._task_update_interval = 0.15  # Update task UI max every 150ms
        self._aggregate_update_interval = 0.2  # Update aggregate UI max every 200ms
        self._pending_progress: Optional[DownloadProgress] = None
        self._pending_aggregate_update: Optional[AggregateProgress] = None

        self._setup_window()
        self._create_widgets()
        self._apply_theme()
        
        # Start progress update scheduler
        self.after(100, self._schedule_progress_updates)
        self.after(1200, self._check_for_updates_async)

    def _setup_window(self) -> None:
        """Configure main window."""
        self.title("SandSound - YouTube Downloader")
        self.geometry("700x600")
        self.minsize(600, 550)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # Center window on screen (use after to avoid blocking)
        def center_window():
            width = self.winfo_width()
            height = self.winfo_height()
            x = (self.winfo_screenwidth() // 2) - (width // 2)
            y = (self.winfo_screenheight() // 2) - (height // 2)
            self.geometry(f"+{x}+{y}")
        self.after(100, center_window)

    def _apply_theme(self) -> None:
        """Apply configured theme."""
        ctk.set_appearance_mode(self._config.theme)
        ctk.set_default_color_theme("blue")

    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        # Main container with padding
        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(fill="both", expand=True, padx=24, pady=24)

        # Header
        self._create_header()

        # Update banner (hidden by default)
        self._create_update_banner()

        # URL Input section
        self._create_url_section()

        # Playlist info bar (hidden by default)
        self._create_playlist_info_bar()

        # Format selection
        self._create_format_section()

        # Download button
        self._create_download_button()

        # Progress section
        self._create_progress_section()

        # Cookie warning if not configured
        self._create_cookie_warning()

    def _create_header(self) -> None:
        """Create header with title and settings button."""
        header = ctk.CTkFrame(self._container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 25))

        # Title
        title = ctk.CTkLabel(
            header,
            text="SandSound",
            font=("Segoe UI", 32, "bold"),
        )
        title.pack(side="left")

        # Subtitle
        subtitle = ctk.CTkLabel(
            header,
            text="YouTube Downloader",
            font=("Segoe UI", 14),
            text_color=("gray50", "gray60"),
        )
        subtitle.pack(side="left", padx=(10, 0), pady=(12, 0))

        # Right side buttons
        button_frame = ctk.CTkFrame(header, fg_color="transparent")
        button_frame.pack(side="right")
        
        # History button
        history_btn = ctk.CTkButton(
            button_frame,
            text="History",
            width=90,
            height=35,
            corner_radius=8,
            fg_color="transparent",
            border_width=2,
            command=self._open_history,
        )
        history_btn.pack(side="left", padx=(0, 8))
        
        # Settings button
        settings_btn = ctk.CTkButton(
            button_frame,
            text="Settings",
            width=100,
            height=35,
            corner_radius=8,
            fg_color="transparent",
            border_width=2,
            command=self._open_settings,
        )
        settings_btn.pack(side="left")

    def _create_update_banner(self) -> None:
        """Create the update notification banner."""
        self._update_banner = ctk.CTkFrame(
            self._container,
            corner_radius=12,
            fg_color=("#FFF3CD", "#5C4813"),
        )

        inner = ctk.CTkFrame(self._update_banner, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        self._update_label = ctk.CTkLabel(
            inner,
            text="",
            font=("Segoe UI Semibold", 12),
            text_color=("#856404", "#FFC107"),
            justify="left",
            wraplength=420,
        )
        self._update_label.pack(side="left", fill="x", expand=True, padx=(0, 12))

        button_frame = ctk.CTkFrame(inner, fg_color="transparent")
        button_frame.pack(side="right")

        self._update_details_btn = ctk.CTkButton(
            button_frame,
            text="Release Notes",
            width=110,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            text_color=Colors.TEXT_PRIMARY,
            command=self._open_update_release_notes,
        )
        self._update_details_btn.pack(side="left", padx=(0, 8))

        self._update_action_btn = ctk.CTkButton(
            button_frame,
            text="Update Now",
            width=110,
            height=34,
            corner_radius=8,
            fg_color=Colors.WARNING,
            hover_color="#D97706",
            text_color=Colors.TEXT_PRIMARY,
            command=self._start_update_install,
        )
        self._update_action_btn.pack(side="left", padx=(0, 8))

        self._update_later_btn = ctk.CTkButton(
            button_frame,
            text="Later",
            width=72,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            text_color=Colors.TEXT_PRIMARY,
            command=self._dismiss_update_banner,
        )
        self._update_later_btn.pack(side="left")

    def _create_url_section(self) -> None:
        """Create URL input section."""
        self._url_input = UrlInput(
            self._container,
            validate_callback=self._on_url_validate,
            on_submit=lambda url: self._start_download(),
        )
        self._url_input.pack(fill="x", pady=(0, 12))

    def _create_playlist_info_bar(self) -> None:
        """Create playlist info bar (shown when playlist detected)."""
        self._playlist_bar = ctk.CTkFrame(
            self._container,
            fg_color=Colors.BG_CARD,
            corner_radius=10,
            height=50
        )
        
        inner = ctk.CTkFrame(self._playlist_bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=15, pady=10)
        inner.grid_columnconfigure(1, weight=1)
        
        self._playlist_icon = ctk.CTkLabel(
            inner,
            text="Playlist",
            font=("Segoe UI", 16),
        )
        self._playlist_icon.grid(row=0, column=0, padx=(0, 10), sticky="w")
        
        self._playlist_info_label = ctk.CTkLabel(
            inner,
            text="Playlist detected",
            font=("Segoe UI", 13),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
            justify="left",
        )
        self._playlist_info_label.grid(row=0, column=1, sticky="ew")
        
        self._view_playlist_btn = ctk.CTkButton(
            inner,
            text="View Playlist",
            width=110,
            height=32,
            font=("Segoe UI Semibold", 12),
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_DARK,
            corner_radius=8,
            command=self._open_playlist_view
        )
        self._view_playlist_btn.grid(row=0, column=2, padx=(12, 0), sticky="e")

    def _create_format_section(self) -> None:
        """Create format/quality selection section."""
        format_label = ctk.CTkLabel(
            self._container,
            text="Output Format",
            font=("Segoe UI", 13, "bold"),
        )
        format_label.pack(anchor="w", pady=(0, 8))

        self._format_selector = FormatSelector(self._container)
        self._format_selector.pack(fill="x", pady=(0, 20))

    def _create_download_button(self) -> None:
        """Create download button."""
        self._download_btn = ctk.CTkButton(
            self._container,
            text="Download",
            height=50,
            font=("Segoe UI", 16, "bold"),
            corner_radius=10,
            command=self._start_download,
        )
        self._download_btn.pack(fill="x", pady=(0, 25))

    def _create_progress_section(self) -> None:
        """Create progress display section."""
        self._progress_card = ProgressCard(self._container)
        self._progress_card.pack(fill="x")

    def _create_cookie_warning(self) -> None:
        """Create cookie warning if not configured."""
        self._warning_frame = ctk.CTkFrame(
            self._container,
            corner_radius=10,
            fg_color=("#FFF3CD", "#5C4813"),
        )

        if not self._config.is_cookie_valid():
            self._warning_frame.pack(fill="x", pady=(20, 0))

            warning_text = ctk.CTkLabel(
                self._warning_frame,
                text="No cookie file configured. Some videos may not be accessible. Configure in Settings.",
                font=("Segoe UI", 12),
                text_color=("#856404", "#FFC107"),
                wraplength=600,
            )
            warning_text.pack(padx=15, pady=12)

    def _next_info_request_token(self) -> int:
        """Issue a token for the latest URL metadata request."""
        self._info_request_token += 1
        return self._info_request_token

    def _is_current_info_request(self, token: int, url: str) -> bool:
        """Check whether a metadata response still matches the active URL."""
        return (
            not self._is_closing
            and
            token == self._info_request_token
            and self.winfo_exists()
            and self._url_input.get_url() == url
        )

    def _schedule_on_ui(self, callback, delay_ms: int = 0) -> bool:
        """Schedule a callback on the Tk thread if the app is still alive."""
        if self._is_closing:
            return False
        try:
            if not self.winfo_exists():
                return False
            self.after(delay_ms, callback)
            return True
        except Exception:
            return False

    def _on_url_validate(self, url: str) -> bool:
        """Validate URL and fetch info if playlist."""
        is_valid = Downloader.is_valid_url(url)
        token = self._next_info_request_token()

        if not is_valid:
            self._current_video_info = None
            self._pending_playlist_url = None
            self._hide_playlist_bar()
            return False

        cached_info = self._downloader.get_cached_video_info(url)
        if cached_info:
            self._apply_video_info(cached_info, url=url, token=token)
        elif "playlist" in url.lower():
            self._pending_playlist_url = url
            self._show_playlist_bar(None)
        else:
            self._current_video_info = None
            self._pending_playlist_url = None
            self._hide_playlist_bar()

        needs_refresh = (
            cached_info is None
            or not self._downloader.is_cache_fresh(url, self.URL_CACHE_MAX_AGE_SECONDS)
        )
        if needs_refresh:
            self._info_pool.submit(self._fetch_video_info, url, token)

        return True

    def _apply_video_info(
        self,
        info: Optional[VideoInfo],
        *,
        url: str,
        token: Optional[int] = None,
    ) -> None:
        """Apply resolved metadata to the current UI state."""
        if token is not None and not self._is_current_info_request(token, url):
            return

        if info:
            self._current_video_info = info
        else:
            self._current_video_info = None

        if info and info.is_playlist:
            self._pending_playlist_url = info.url
            self._show_playlist_bar(info)
            return

        if "playlist" in url.lower():
            self._pending_playlist_url = url
            if info is None:
                self._show_playlist_bar(None)
            else:
                self._hide_playlist_bar()
            return

        self._pending_playlist_url = None
        self._hide_playlist_bar()

    def _fetch_video_info(self, url: str, token: int) -> None:
        """Fetch fresh video info in the background."""
        try:
            info = self._downloader.get_video_info(
                url,
                allow_cached=False,
                force_refresh=True,
            )
        except Exception as exc:
            print(f"Error fetching video info: {exc}")
            info = None

        self._schedule_on_ui(
            lambda: self._apply_video_info(info, url=url, token=token),
        )

    def _hide_playlist_bar(self) -> None:
        """Hide playlist info bar."""
        if self._playlist_bar_visible and self._playlist_bar.winfo_exists():
            self._playlist_bar.pack_forget()
            self._playlist_bar_visible = False
    
    def _show_playlist_bar(self, info: Optional[VideoInfo]) -> None:
        """Show playlist info bar."""
        try:
            if not hasattr(self, "_playlist_bar") or not self._playlist_bar.winfo_exists():
                return

            if info:
                if info.playlist_id and info.entries:
                    downloaded_ids = self._history.get_downloaded_video_ids(info.playlist_id)
                    new_count = sum(1 for e in info.entries if e.video_id not in downloaded_ids)
                    self._playlist_info_label.configure(
                        text=build_playlist_bar_text(info, new_count=new_count)
                    )
                else:
                    self._playlist_info_label.configure(
                        text=build_playlist_bar_text(info)
                    )
            else:
                self._playlist_info_label.configure(text="Playlist detected")

            if not self._playlist_bar_visible:
                self._playlist_bar.pack(fill="x", pady=(0, 12))
                self._playlist_bar_visible = True
        except Exception:
            pass

    def _check_for_updates_async(self) -> None:
        """Start a background update check."""
        if self._is_closing or self._update_check_started:
            return
        self._update_check_started = True
        self._update_pool.submit(self._check_for_updates_worker)

    def _check_for_updates_worker(self) -> None:
        """Check for updates without blocking the UI."""
        update_info: Optional[UpdateInfo] = None
        try:
            update_info = self._updater.check_for_update()
        except UpdateError as exc:
            print(f"Update check skipped: {exc}")

        self._schedule_on_ui(lambda: self._handle_update_check_result(update_info))

    def _handle_update_check_result(self, update_info: Optional[UpdateInfo]) -> None:
        """Apply update check results on the UI thread."""
        if not update_info or self._is_closing:
            return

        self._available_update = update_info
        action_text = (
            "Update Now"
            if update_info.asset and self._updater.can_replace_current_executable()
            else "Open Release"
        )
        self._update_label.configure(
            text=(
                f"SandSound {update_info.version} is available. "
                f"You are on {update_info.current_version}."
            )
        )
        self._update_action_btn.configure(text=action_text, state="normal")
        self._update_details_btn.configure(state="normal")
        self._update_later_btn.configure(state="normal")

        if not self._update_banner_visible:
            self._update_banner.pack(fill="x", pady=(0, 12))
            self._update_banner_visible = True

    def _dismiss_update_banner(self) -> None:
        """Hide the update banner until the next app launch."""
        if self._update_action_in_progress:
            return
        if self._update_banner_visible and self._update_banner.winfo_exists():
            self._update_banner.pack_forget()
            self._update_banner_visible = False

    def _open_update_release_notes(self) -> None:
        """Open the current release page in the default browser."""
        if self._available_update:
            webbrowser.open(self._available_update.html_url)

    def _start_update_install(self) -> None:
        """Download and apply the latest packaged update when supported."""
        if not self._available_update or self._update_action_in_progress:
            return

        if not (self._available_update.asset and self._updater.can_replace_current_executable()):
            webbrowser.open(self._available_update.html_url)
            return

        if self._is_downloading:
            self._update_label.configure(
                text="Finish or cancel the current download before installing the update."
            )
            return

        self._update_action_in_progress = True
        self._update_label.configure(
            text=f"Downloading SandSound {self._available_update.version}..."
        )
        self._update_action_btn.configure(text="Downloading...", state="disabled")
        self._update_details_btn.configure(state="disabled")
        self._update_later_btn.configure(state="disabled")
        self._update_pool.submit(
            self._download_and_apply_update_worker,
            self._available_update,
        )

    def _download_and_apply_update_worker(self, update_info: UpdateInfo) -> None:
        """Download the update and hand off installation to a helper script."""
        try:
            downloaded_path = self._updater.download_update(update_info)
            self._updater.apply_downloaded_update(downloaded_path)
        except UpdateError as exc:
            self._schedule_on_ui(lambda: self._handle_update_failure(str(exc)))
            return

        self._schedule_on_ui(
            lambda: self._finish_update_install(update_info.version),
        )

    def _handle_update_failure(self, error: str) -> None:
        """Restore banner actions after an update failure."""
        self._update_action_in_progress = False
        self._update_label.configure(text=f"Update failed: {error}")
        self._update_action_btn.configure(text="Update Now", state="normal")
        self._update_details_btn.configure(state="normal")
        self._update_later_btn.configure(state="normal")

    def _finish_update_install(self, version: str) -> None:
        """Close the app so the helper can replace the executable."""
        self._update_label.configure(
            text=f"Installing SandSound {version}. The app will restart."
        )
        self.after(300, self.destroy)

    def _open_playlist_view(self) -> None:
        """Open playlist view dialog."""
        url = self._pending_playlist_url or self._url_input.get_url()
        if not url:
            return

        cached_info = self._downloader.get_cached_video_info(url)
        if (
            cached_info
            and cached_info.is_playlist
            and self._downloader.is_cache_fresh(
                url,
                self.PLAYLIST_DIALOG_CACHE_MAX_AGE_SECONDS,
            )
        ):
            self._apply_video_info(cached_info, url=url)
            self._show_playlist_dialog(cached_info)
            return

        if self._playlist_fetch_in_progress:
            return

        self._playlist_fetch_in_progress = True
        try:
            self._view_playlist_btn.configure(state="disabled", text="Loading...")
        except Exception:
            pass
        self._info_pool.submit(
            self._fetch_and_open_playlist,
            url,
            cached_info if cached_info and cached_info.is_playlist else None,
        )

    def _show_playlist_dialog(self, info: VideoInfo) -> None:
        """Open the playlist dialog with the provided info."""
        downloaded_ids = set()
        if info.playlist_id:
            downloaded_ids = self._history.get_downloaded_video_ids(info.playlist_id)

        videos = []
        if info.entries:
            videos = [
                PlaylistVideo(
                    video_id=entry.video_id,
                    title=entry.title,
                    duration=entry.duration,
                    thumbnail=entry.thumbnail,
                    is_downloaded=entry.video_id in downloaded_ids
                )
                for entry in info.entries
            ]

        self._playlist_dialog = PlaylistViewDialog(
            self,
            playlist_title=info.title,
            playlist_id=info.playlist_id or "",
            videos=videos,
            on_download=self._start_playlist_download,
            on_cancel=self._cancel_playlist_download
        )

    def _fetch_and_open_playlist(
        self,
        url: str,
        cached_fallback: Optional[VideoInfo],
    ) -> None:
        """Fetch playlist info and open dialog when ready."""
        info: Optional[VideoInfo] = None
        try:
            info = self._downloader.get_video_info(
                url,
                allow_cached=False,
                force_refresh=True,
            )
        except Exception:
            info = None

        def finish():
            self._playlist_fetch_in_progress = False
            try:
                self._view_playlist_btn.configure(state="normal", text="View Playlist")
            except Exception:
                pass

            if info and info.is_playlist:
                self._apply_video_info(info, url=url)
                self._show_playlist_dialog(info)
            elif cached_fallback:
                self._apply_video_info(cached_fallback, url=url)
                self._show_playlist_dialog(cached_fallback)
            else:
                self._progress_card.set_error("Error", "Could not load playlist info")
                self._apply_video_info(None, url=url)

        self._schedule_on_ui(finish)

    def _start_playlist_download(self, video_ids: List[str], compare_download: bool) -> None:
        """Start downloading selected playlist videos concurrently."""
        if self._is_downloading or not self._current_video_info:
            return
        
        info = self._current_video_info
        
        # Get videos to download
        if compare_download and info.playlist_id:
            downloaded_ids = self._history.get_downloaded_video_ids(info.playlist_id)
            video_ids = [vid for vid in video_ids if vid not in downloaded_ids]
        
        if not video_ids:
            if self._playlist_dialog:
                self._playlist_dialog.set_downloading(False)
            return
        
        # Reset update buffers for a clean UI state
        with self._task_buffer_lock:
            self._task_update_buffer.clear()
        self._pending_aggregate_update = None
        
        self._is_downloading = True
        if self._playlist_dialog:
            self._playlist_dialog.set_downloading(True)
        self._download_btn.configure(state="disabled", text="Downloading...")
        
        format_type = self._format_selector.get_format()
        quality = self._format_selector.get_quality()
        
        # Build entries map for history tracking
        self._entries_map = {}
        if info.entries:
            self._entries_map = {e.video_id: e for e in info.entries}
        
        # Create download tasks
        tasks = []
        for video_id in video_ids:
            entry = self._entries_map.get(video_id)
            if entry:
                tasks.append(DownloadTask(
                    task_id=video_id,
                    url=entry.url or f"https://www.youtube.com/watch?v={video_id}",
                    title=entry.title,
                    format_type=format_type,
                    quality=quality,
                    playlist_title=info.title if info.is_playlist else None,
                ))
        
        # Create download manager with callbacks
        self._download_manager = DownloadManager(
            downloader=self._downloader,
            max_workers=self._config.concurrent_downloads,
            on_task_update=lambda t: self._queue_task_update(t, info),
            on_aggregate_update=lambda a: self._queue_aggregate_update(a),
            on_batch_complete=lambda: self._schedule_on_ui(self._playlist_download_complete),
        )
        
        # Submit all tasks
        self._download_manager.submit_tasks(tasks)
    
    def _on_task_update(self, task: DownloadTask, info: VideoInfo) -> None:
        """Handle individual task status updates."""
        try:
            if not self._playlist_dialog or not self._playlist_dialog.winfo_exists():
                return
            
            # Map task status to video status
            status_map = {
                TaskStatus.QUEUED: VideoStatus.PENDING,
                TaskStatus.ACTIVE: VideoStatus.DOWNLOADING,
                TaskStatus.COMPLETED: VideoStatus.COMPLETED,
                TaskStatus.FAILED: VideoStatus.FAILED,
                TaskStatus.CANCELLED: VideoStatus.CANCELLED,
            }
            
            video_status = status_map.get(task.status, VideoStatus.PENDING)
            self._playlist_dialog.update_video_status(
                task.task_id, video_status, task.progress
            )
            
            # Record in history when completed
            if task.status == TaskStatus.COMPLETED:
                entry = self._entries_map.get(task.task_id)
                if entry:
                    self._history.add_video_download(
                        video_id=task.task_id,
                        title=entry.title,
                        format_type=task.format_type,
                        quality=task.quality,
                        playlist_id=info.playlist_id,
                        playlist_url=info.url,
                        playlist_title=info.title
                    )
        except Exception:
            # Widget may have been destroyed
            pass
    
    def _on_aggregate_update(self, aggregate: AggregateProgress) -> None:
        """Handle aggregate progress updates for main progress card."""
        try:
            if not self.winfo_exists():
                return
            # Build status text showing concurrent download info
            if aggregate.active_tasks > 0:
                if aggregate.active_tasks == 1:
                    title = aggregate.active_titles[0] if aggregate.active_titles else "Downloading..."
                else:
                    title = f"Downloading {aggregate.active_tasks} songs..."
                
                status = f"{aggregate.completed_tasks}/{aggregate.total_tasks} completed"
                
                self._progress_card.update_progress(
                    title=title,
                    status=status,
                    progress=aggregate.overall_progress,
                    speed=aggregate.total_speed,
                    eta="",
                )
            elif aggregate.completed_tasks == aggregate.total_tasks:
                self._progress_card.set_completed(
                    f"Completed {aggregate.completed_tasks} downloads"
                )
        except Exception:
            # Widget may have been destroyed
            pass

    def _playlist_download_complete(self) -> None:
        """Reset UI after playlist download completes."""
        self._is_downloading = False
        self._reset_download_button()
        if self._playlist_dialog:
            self._playlist_dialog.set_downloading(False)

    def _open_history(self) -> None:
        """Open playlist history dialog."""
        PlaylistHistoryDialog(
            self,
            history=self._history,
            downloader=self._downloader,
            on_open_playlist=self._open_playlist_from_history
        )
    
    def _open_playlist_from_history(self, playlist_url: str) -> None:
        """Open a playlist from history in the URL input."""
        self._url_input.set_url(playlist_url)
        self._pending_playlist_url = playlist_url
        self._open_playlist_view()
    
    def _open_settings(self) -> None:
        """Open settings dialog."""
        SettingsDialog(
            self,
            config=self._config,
            on_save=self._on_settings_saved,
        )

    def _on_settings_saved(self) -> None:
        """Handle settings saved."""
        # Update downloader with new settings
        self._downloader.set_cookie_file(self._config.cookie_file)
        self._downloader.set_download_dir(self._config.download_dir)
        self._downloader.set_ffmpeg_location(self._config.get_ffmpeg_location())

        # Hide warning if cookie is now valid
        if self._config.is_cookie_valid():
            self._warning_frame.pack_forget()
        else:
            self._warning_frame.pack(fill="x", pady=(20, 0))

    def _start_download(self) -> None:
        """Start download in background thread."""
        if self._is_downloading:
            return

        url = self._url_input.get_url()
        if not url:
            self._progress_card.set_error("Error", "Please enter a URL")
            return

        if not Downloader.is_valid_url(url):
            self._progress_card.set_error("Error", "Invalid YouTube URL")
            return

        # If it's a playlist, open playlist view instead
        if "playlist" in url.lower() or (self._current_video_info and self._current_video_info.is_playlist):
            self._pending_playlist_url = url
            self._open_playlist_view()
            return

        self._is_downloading = True
        self._cancel_event = threading.Event()
        self._download_btn.configure(
            state="normal",
            text="Cancel Download",
            fg_color=Colors.ERROR,
            hover_color=Colors.ERROR_DARK,
            command=self._cancel_download,
        )

        format_type = self._format_selector.get_format()
        quality = self._format_selector.get_quality()

        self._download_future = self._download_pool.submit(
            self._download_worker,
            url,
            format_type,
            quality,
        )

    def _download_worker(self, url: str, format_type: str, quality: str) -> None:
        """Download worker thread."""
        def progress_callback(progress: DownloadProgress) -> None:
            # Throttle UI updates - only queue if enough time has passed
            current_time = time.time()
            if current_time - self._last_progress_update >= self._progress_update_interval:
                # Queue update for main thread
                try:
                    self._progress_queue.put_nowait(progress)
                except queue.Full:
                    pass  # Skip if queue is full
                self._last_progress_update = current_time
            else:
                # Store latest progress for next update
                self._pending_progress = progress

        success = self._downloader.download(
            url=url,
            format_type=format_type,
            quality=quality,
            progress_callback=progress_callback,
            cancel_event=self._cancel_event,
        )

        if success and not (self._cancel_event and self._cancel_event.is_set()):
            video_id = extract_video_id(url)
            if video_id:
                cached_info = self._downloader.get_cached_video_info(url)
                self._history.add_video_download(
                    video_id=video_id,
                    title=cached_info.title if cached_info else video_id,
                    format_type=format_type,
                    quality=quality,
                )

        # Reset state on main thread
        self._schedule_on_ui(self._download_complete)
    
    def _cancel_download(self) -> None:
        """Cancel the current single download."""
        if not self._is_downloading or not self._cancel_event:
            return
        self._cancel_event.set()
        self._download_btn.configure(
            state="disabled",
            text="Cancelling...",
            fg_color=Colors.BG_INPUT,
            hover_color=Colors.BG_INPUT,
        )
        self._progress_card.update_progress(
            title="Cancelling...",
            status="Cancelling download...",
            progress=0.0,
            speed="",
            eta="",
        )
    
    def _cancel_playlist_download(self) -> None:
        """Cancel all playlist downloads."""
        if not self._download_manager or not self._is_downloading:
            return
        self._download_manager.cancel_all()
        self._progress_card.update_progress(
            title="Cancelled",
            status="Downloads cancelled",
            progress=0.0,
            speed="",
            eta="",
        )
        self._schedule_on_ui(self._playlist_download_complete)
    
    def _schedule_progress_updates(self) -> None:
        """Schedule periodic progress updates from queue."""
        if self._is_closing:
            return
        current_time = time.time()
        
        # Process progress updates
        if current_time - self._last_progress_update >= self._progress_update_interval:
            updates_processed = 0
            latest_progress = None
            while updates_processed < 5:  # Process max 5 updates per cycle
                try:
                    latest_progress = self._progress_queue.get_nowait()
                    updates_processed += 1
                except queue.Empty:
                    break
            
            if latest_progress:
                self._update_progress(latest_progress)
                self._last_progress_update = current_time
            elif self._pending_progress:
                self._update_progress(self._pending_progress)
                self._pending_progress = None
                self._last_progress_update = current_time
        
        # Process task updates
        if current_time - self._last_task_update >= self._task_update_interval:
            buffered_updates = []
            with self._task_buffer_lock:
                if self._task_update_buffer:
                    # Sort by time inserted to preserve ordering
                    buffered_updates = sorted(
                        self._task_update_buffer.values(),
                        key=lambda item: item[2]
                    )
                    # Keep any overflow for next cycle (process max 30 per tick)
                    remaining = buffered_updates[30:]
                    buffered_updates = buffered_updates[:30]
                    self._task_update_buffer = {
                        task.task_id: (task, info, ts)
                        for task, info, ts in remaining
                    }
            
            if buffered_updates:
                for task, info, _ in buffered_updates:
                    self._on_task_update(task, info)
                self._last_task_update = current_time
    
        # Process aggregate updates
        if current_time - self._last_aggregate_update >= self._aggregate_update_interval:
            latest_aggregate = None
            while True:
                try:
                    latest_aggregate = self._aggregate_update_queue.get_nowait()
                except queue.Empty:
                    break
            
            if latest_aggregate:
                self._on_aggregate_update(latest_aggregate)
                self._last_aggregate_update = current_time
            elif self._pending_aggregate_update:
                self._on_aggregate_update(self._pending_aggregate_update)
                self._pending_aggregate_update = None
                self._last_aggregate_update = current_time
        
        # Schedule next update check
        self._schedule_on_ui(self._schedule_progress_updates, delay_ms=50)
    
    def _queue_task_update(self, task: DownloadTask, info: VideoInfo) -> None:
        """Queue task update for throttled processing."""
        current_time = time.time()
        with self._task_buffer_lock:
            # Keep only the latest update per task to avoid unbounded growth
            self._task_update_buffer[task.task_id] = (task, info, current_time)
    
    def _queue_aggregate_update(self, aggregate: AggregateProgress) -> None:
        """Queue aggregate update for throttled processing."""
        current_time = time.time()
        if current_time - self._last_aggregate_update >= self._aggregate_update_interval:
            try:
                self._aggregate_update_queue.put_nowait(aggregate)
            except queue.Full:
                self._pending_aggregate_update = aggregate
        else:
            self._pending_aggregate_update = aggregate

    def _update_progress(self, progress: DownloadProgress) -> None:
        """Update UI with download progress."""
        status_text = {
            DownloadStatus.PENDING: "Preparing download...",
            DownloadStatus.DOWNLOADING: "Downloading...",
            DownloadStatus.PROCESSING: "Processing audio/video...",
            DownloadStatus.COMPLETED: "Completed",
            DownloadStatus.FAILED: "Failed",
            DownloadStatus.CANCELLED: "Cancelled",
        }

        if progress.status == DownloadStatus.FAILED:
            self._progress_card.set_error(progress.title, progress.error or "Unknown error")
        elif progress.status == DownloadStatus.COMPLETED:
            self._progress_card.set_completed(progress.title)
        else:
            self._progress_card.update_progress(
                title=progress.title,
                status=status_text.get(progress.status, ""),
                progress=progress.progress,
                speed=progress.speed,
                eta=progress.eta,
            )

    def _download_complete(self) -> None:
        """Reset UI after download completes."""
        self._is_downloading = False
        self._download_future = None
        self._cancel_event = None
        self._reset_download_button()
        self._url_input.clear()

    def _reset_download_button(self) -> None:
        """Reset download button to default state."""
        self._download_btn.configure(
            state="normal",
            text="Download",
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_DARK,
            command=self._start_download,
        )

    def destroy(self) -> None:
        """Release background workers and cancel active tasks before closing."""
        if not getattr(self, "_is_closing", False):
            self._is_closing = True
            self._info_request_token += 1

            if self._cancel_event:
                self._cancel_event.set()
            if self._download_manager:
                try:
                    self._download_manager.cancel_all()
                except Exception:
                    pass
                self._download_manager = None

            try:
                self._info_pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            try:
                self._download_pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            try:
                self._update_pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

        try:
            super().destroy()
        except Exception:
            pass
