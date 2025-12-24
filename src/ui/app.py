"""
Main application window for SandSound.
"""

import threading
import customtkinter as ctk
from typing import Optional, List

from ..config import Config
from ..downloader import Downloader, DownloadProgress, DownloadStatus, VideoInfo
from ..download_manager import DownloadManager, DownloadTask, AggregateProgress, TaskStatus
from ..history import DownloadHistory
from .components import UrlInput, FormatSelector, ProgressCard, Colors
from .playlist_view import PlaylistViewDialog, PlaylistVideo, VideoStatus
from .settings import SettingsDialog


class SandSoundApp(ctk.CTk):
    """Main application window."""

    def __init__(self, config: Config) -> None:
        super().__init__()

        self._config = config
        self._downloader = Downloader(
            download_dir=config.download_dir,
            cookie_file=config.cookie_file if config.is_cookie_valid() else None,
            ffmpeg_location=config.get_ffmpeg_location(),
        )
        self._history = DownloadHistory()
        self._download_manager: Optional[DownloadManager] = None
        self._download_thread: Optional[threading.Thread] = None
        self._is_downloading = False
        self._current_video_info: Optional[VideoInfo] = None
        self._playlist_dialog: Optional[PlaylistViewDialog] = None
        self._entries_map: dict = {}  # For tracking entries during concurrent download

        self._setup_window()
        self._create_widgets()
        self._apply_theme()

    def _setup_window(self) -> None:
        """Configure main window."""
        self.title("SandSound - YouTube Downloader")
        self.geometry("700x600")
        self.minsize(600, 550)

        # Center window on screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

    def _apply_theme(self) -> None:
        """Apply configured theme."""
        ctk.set_appearance_mode(self._config.theme)
        ctk.set_default_color_theme("blue")

    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        # Main container with padding
        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(fill="both", expand=True, padx=30, pady=30)

        # Header
        self._create_header()

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

        # Settings button
        settings_btn = ctk.CTkButton(
            header,
            text="Settings",
            width=100,
            height=35,
            corner_radius=8,
            fg_color="transparent",
            border_width=2,
            command=self._open_settings,
        )
        settings_btn.pack(side="right")

    def _create_url_section(self) -> None:
        """Create URL input section."""
        url_label = ctk.CTkLabel(
            self._container,
            text="YouTube URL",
            font=("Segoe UI", 13, "bold"),
        )
        url_label.pack(anchor="w", pady=(0, 8))

        self._url_input = UrlInput(
            self._container,
            validate_callback=self._on_url_validate,
            on_submit=lambda url: self._start_download(),
        )
        self._url_input.pack(fill="x", pady=(0, 15))

    def _create_playlist_info_bar(self) -> None:
        """Create playlist info bar (shown when playlist detected)."""
        self._playlist_bar = ctk.CTkFrame(
            self._container,
            fg_color=Colors.BG_CARD,
            corner_radius=10,
            height=50
        )
        # Don't pack yet - will be shown when playlist detected
        
        inner = ctk.CTkFrame(self._playlist_bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=15, pady=10)
        
        self._playlist_icon = ctk.CTkLabel(
            inner,
            text="🎵",
            font=("Segoe UI", 16),
        )
        self._playlist_icon.pack(side="left", padx=(0, 10))
        
        self._playlist_info_label = ctk.CTkLabel(
            inner,
            text="Playlist detected",
            font=("Segoe UI", 13),
            text_color=Colors.TEXT_SECONDARY
        )
        self._playlist_info_label.pack(side="left")
        
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
        self._view_playlist_btn.pack(side="right")

    def _create_format_section(self) -> None:
        """Create format/quality selection section."""
        format_label = ctk.CTkLabel(
            self._container,
            text="Output Format",
            font=("Segoe UI", 13, "bold"),
        )
        format_label.pack(anchor="w", pady=(0, 8))

        self._format_selector = FormatSelector(self._container)
        self._format_selector.pack(fill="x", pady=(0, 25))

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

    def _on_url_validate(self, url: str) -> bool:
        """Validate URL and fetch info if playlist."""
        is_valid = Downloader.is_valid_url(url)
        
        if is_valid:
            # Check for playlist in background
            threading.Thread(
                target=self._fetch_video_info,
                args=(url,),
                daemon=True
            ).start()
        else:
            self._current_video_info = None
            self._playlist_bar.pack_forget()
        
        return is_valid

    def _fetch_video_info(self, url: str) -> None:
        """Fetch video info in background."""
        info = self._downloader.get_video_info(url)
        self._current_video_info = info
        
        if info and info.is_playlist:
            # Update UI on main thread
            self.after(0, lambda: self._show_playlist_bar(info))
        else:
            self.after(0, lambda: self._playlist_bar.pack_forget())

    def _show_playlist_bar(self, info: VideoInfo) -> None:
        """Show playlist info bar."""
        # Count new videos
        if info.playlist_id and info.entries:
            downloaded_ids = self._history.get_downloaded_video_ids(info.playlist_id)
            new_count = sum(1 for e in info.entries if e.video_id not in downloaded_ids)
            total = len(info.entries)
            
            if new_count == total:
                text = f"Playlist: {info.title} ({total} videos)"
            else:
                text = f"Playlist: {info.title} ({new_count} new / {total} total)"
            
            self._playlist_info_label.configure(text=text)
        else:
            self._playlist_info_label.configure(text=f"Playlist: {info.title}")
        
        # Show the bar
        self._playlist_bar.pack(fill="x", pady=(0, 15), after=self._url_input)

    def _open_playlist_view(self) -> None:
        """Open playlist view dialog."""
        if not self._current_video_info or not self._current_video_info.is_playlist:
            return
        
        info = self._current_video_info
        
        # Build video list with download status
        videos = []
        downloaded_ids = set()
        if info.playlist_id:
            downloaded_ids = self._history.get_downloaded_video_ids(info.playlist_id)
        
        if info.entries:
            for entry in info.entries:
                videos.append(PlaylistVideo(
                    video_id=entry.video_id,
                    title=entry.title,
                    duration=entry.duration,
                    thumbnail=entry.thumbnail,
                    is_downloaded=entry.video_id in downloaded_ids
                ))
        
        # Open dialog
        self._playlist_dialog = PlaylistViewDialog(
            self,
            playlist_title=info.title,
            playlist_id=info.playlist_id or "",
            videos=videos,
            on_download=self._start_playlist_download
        )

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
                ))
        
        # Create download manager with callbacks
        self._download_manager = DownloadManager(
            downloader=self._downloader,
            max_workers=4,  # Download 4 songs simultaneously
            on_task_update=lambda t: self.after(0, lambda: self._on_task_update(t, info)),
            on_aggregate_update=lambda a: self.after(0, lambda: self._on_aggregate_update(a)),
            on_batch_complete=lambda: self.after(0, self._playlist_download_complete),
        )
        
        # Submit all tasks
        self._download_manager.submit_tasks(tasks)
    
    def _on_task_update(self, task: DownloadTask, info: VideoInfo) -> None:
        """Handle individual task status updates."""
        if not self._playlist_dialog:
            return
        
        # Map task status to video status
        status_map = {
            TaskStatus.QUEUED: VideoStatus.PENDING,
            TaskStatus.ACTIVE: VideoStatus.DOWNLOADING,
            TaskStatus.COMPLETED: VideoStatus.COMPLETED,
            TaskStatus.FAILED: VideoStatus.FAILED,
            TaskStatus.CANCELLED: VideoStatus.FAILED,
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
    
    def _on_aggregate_update(self, aggregate: AggregateProgress) -> None:
        """Handle aggregate progress updates for main progress card."""
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

    def _playlist_download_complete(self) -> None:
        """Reset UI after playlist download completes."""
        self._is_downloading = False
        self._download_btn.configure(state="normal", text="Download")
        if self._playlist_dialog:
            self._playlist_dialog.set_downloading(False)

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
        if self._current_video_info and self._current_video_info.is_playlist:
            self._open_playlist_view()
            return

        self._is_downloading = True
        self._download_btn.configure(state="disabled", text="Downloading...")

        format_type = self._format_selector.get_format()
        quality = self._format_selector.get_quality()

        self._download_thread = threading.Thread(
            target=self._download_worker,
            args=(url, format_type, quality),
            daemon=True,
        )
        self._download_thread.start()

    def _download_worker(self, url: str, format_type: str, quality: str) -> None:
        """Download worker thread."""
        def progress_callback(progress: DownloadProgress) -> None:
            # Schedule UI update on main thread
            self.after(0, lambda: self._update_progress(progress))

        success = self._downloader.download(
            url=url,
            format_type=format_type,
            quality=quality,
            progress_callback=progress_callback,
        )

        # Reset state on main thread
        self.after(0, self._download_complete)

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
        self._download_btn.configure(state="normal", text="Download")
        self._url_input.clear()
