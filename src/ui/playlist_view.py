"""
Playlist view components for SandSound.
Displays playlist contents in a tabular format with per-video status.
"""

import customtkinter as ctk
from typing import Callable, Optional, List, Dict
from dataclasses import dataclass
from enum import Enum

from .components import Colors


class VideoStatus(Enum):
    """Status of a video in the playlist."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass  
class PlaylistVideo:
    """Video item in a playlist."""
    video_id: str
    title: str
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    status: VideoStatus = VideoStatus.PENDING
    progress: float = 0.0
    is_downloaded: bool = False  # Previously downloaded


class PlaylistTableRow(ctk.CTkFrame):
    """Single row in the playlist table."""
    
    def __init__(
        self,
        master: ctk.CTkFrame,
        index: int,
        video: PlaylistVideo,
        on_toggle: Optional[Callable[[str, bool], None]] = None,
        **kwargs
    ) -> None:
        super().__init__(
            master,
            fg_color=Colors.BG_INPUT if index % 2 == 0 else Colors.BG_CARD,
            corner_radius=0,
            height=48,
            **kwargs
        )
        self.pack_propagate(False)
        
        self._video = video
        self._on_toggle = on_toggle
        self._selected = not video.is_downloaded  # Default: select if not downloaded
        
        # Checkbox
        self._checkbox = ctk.CTkCheckBox(
            self,
            text="",
            width=24,
            height=24,
            checkbox_width=20,
            checkbox_height=20,
            corner_radius=4,
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_DARK,
            border_color=Colors.BORDER,
            command=self._on_check_change
        )
        self._checkbox.pack(side="left", padx=(12, 8))
        if self._selected:
            self._checkbox.select()
        
        # Index number
        self._index_label = ctk.CTkLabel(
            self,
            text=f"{index + 1}",
            width=36,
            font=("Segoe UI", 12),
            text_color=Colors.TEXT_MUTED,
            anchor="w"
        )
        self._index_label.pack(side="left", padx=(0, 8))
        
        # Title (expandable)
        title_text = video.title[:55] + "..." if len(video.title) > 55 else video.title
        self._title_label = ctk.CTkLabel(
            self,
            text=title_text,
            font=("Segoe UI", 12),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        )
        self._title_label.pack(side="left", fill="x", expand=True, padx=(0, 12))
        
        # Duration
        duration_text = self._format_duration(video.duration) if video.duration else "--:--"
        self._duration_label = ctk.CTkLabel(
            self,
            text=duration_text,
            width=60,
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_MUTED,
            anchor="e"
        )
        self._duration_label.pack(side="left", padx=(0, 12))
        
        # Status indicator
        self._status_frame = ctk.CTkFrame(self, fg_color="transparent", width=100)
        self._status_frame.pack(side="right", padx=(0, 12))
        self._status_frame.pack_propagate(False)
        
        self._status_label = ctk.CTkLabel(
            self._status_frame,
            text=self._get_status_text(),
            font=("Segoe UI", 11),
            text_color=self._get_status_color(),
            anchor="e"
        )
        self._status_label.pack(side="right")
        
        # Progress bar (hidden by default)
        self._progress_bar = ctk.CTkProgressBar(
            self._status_frame,
            height=6,
            width=80,
            corner_radius=3,
            fg_color=Colors.BG_CARD_HOVER,
            progress_color=Colors.PRIMARY
        )
        self._progress_bar.set(0)
    
    def _format_duration(self, seconds: int) -> str:
        """Format seconds to MM:SS or HH:MM:SS."""
        if seconds >= 3600:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours}:{mins:02d}:{secs:02d}"
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}:{secs:02d}"
    
    def _get_status_text(self) -> str:
        """Get display text for current status."""
        status_map = {
            VideoStatus.PENDING: "Pending",
            VideoStatus.DOWNLOADING: "Downloading...",
            VideoStatus.PROCESSING: "Processing...",
            VideoStatus.COMPLETED: "✓ Done",
            VideoStatus.SKIPPED: "Skipped",
            VideoStatus.FAILED: "✗ Failed"
        }
        if self._video.is_downloaded and self._video.status == VideoStatus.PENDING:
            return "✓ Downloaded"
        return status_map.get(self._video.status, "Pending")
    
    def _get_status_color(self) -> str:
        """Get color for current status."""
        color_map = {
            VideoStatus.PENDING: Colors.TEXT_MUTED,
            VideoStatus.DOWNLOADING: Colors.PRIMARY_LIGHT,
            VideoStatus.PROCESSING: Colors.ACCENT_LIGHT,
            VideoStatus.COMPLETED: Colors.SUCCESS,
            VideoStatus.SKIPPED: Colors.TEXT_MUTED,
            VideoStatus.FAILED: Colors.ERROR
        }
        if self._video.is_downloaded and self._video.status == VideoStatus.PENDING:
            return Colors.SUCCESS
        return color_map.get(self._video.status, Colors.TEXT_MUTED)
    
    def _on_check_change(self) -> None:
        """Handle checkbox toggle."""
        self._selected = self._checkbox.get() == 1
        if self._on_toggle:
            self._on_toggle(self._video.video_id, self._selected)
    
    def set_status(self, status: VideoStatus, progress: float = 0.0) -> None:
        """Update the status display."""
        self._video.status = status
        self._video.progress = progress
        
        if status == VideoStatus.DOWNLOADING:
            self._status_label.pack_forget()
            self._progress_bar.pack(side="right")
            self._progress_bar.set(progress / 100.0)
        else:
            self._progress_bar.pack_forget()
            self._status_label.pack(side="right")
            self._status_label.configure(
                text=self._get_status_text(),
                text_color=self._get_status_color()
            )
    
    def update_progress(self, progress: float) -> None:
        """Update download progress."""
        self._video.progress = progress
        self._progress_bar.set(progress / 100.0)
    
    def is_selected(self) -> bool:
        """Check if this video is selected for download."""
        return self._selected
    
    def set_selected(self, selected: bool) -> None:
        """Set selection state."""
        self._selected = selected
        if selected:
            self._checkbox.select()
        else:
            self._checkbox.deselect()


class PlaylistTable(ctk.CTkScrollableFrame):
    """Scrollable table displaying playlist videos."""
    
    def __init__(
        self,
        master: ctk.CTkFrame,
        videos: List[PlaylistVideo],
        on_selection_change: Optional[Callable[[int], None]] = None,
        **kwargs
    ) -> None:
        super().__init__(
            master,
            fg_color=Colors.BG_CARD,
            corner_radius=12,
            **kwargs
        )
        
        self._videos = videos
        self._rows: Dict[str, PlaylistTableRow] = {}
        self._on_selection_change = on_selection_change
        
        # Header row
        header = ctk.CTkFrame(self, fg_color=Colors.BG_CARD_HOVER, height=40)
        header.pack(fill="x", pady=(0, 2))
        header.pack_propagate(False)
        
        # Header labels
        ctk.CTkLabel(
            header, text="", width=44,
            font=("Segoe UI Semibold", 11),
            text_color=Colors.TEXT_SECONDARY
        ).pack(side="left", padx=(12, 8))
        
        ctk.CTkLabel(
            header, text="#", width=36,
            font=("Segoe UI Semibold", 11),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        ).pack(side="left", padx=(0, 8))
        
        ctk.CTkLabel(
            header, text="Title",
            font=("Segoe UI Semibold", 11),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        ).pack(side="left", fill="x", expand=True, padx=(0, 12))
        
        ctk.CTkLabel(
            header, text="Duration", width=60,
            font=("Segoe UI Semibold", 11),
            text_color=Colors.TEXT_SECONDARY,
            anchor="e"
        ).pack(side="left", padx=(0, 12))
        
        ctk.CTkLabel(
            header, text="Status", width=100,
            font=("Segoe UI Semibold", 11),
            text_color=Colors.TEXT_SECONDARY,
            anchor="e"
        ).pack(side="right", padx=(0, 12))
        
        # Create rows for each video
        for i, video in enumerate(videos):
            row = PlaylistTableRow(
                self,
                index=i,
                video=video,
                on_toggle=self._on_row_toggle
            )
            row.pack(fill="x", pady=1)
            self._rows[video.video_id] = row
    
    def _on_row_toggle(self, video_id: str, selected: bool) -> None:
        """Handle row selection toggle."""
        if self._on_selection_change:
            self._on_selection_change(self.get_selected_count())
    
    def get_selected_count(self) -> int:
        """Get count of selected videos."""
        return sum(1 for row in self._rows.values() if row.is_selected())
    
    def get_selected_ids(self) -> List[str]:
        """Get list of selected video IDs."""
        return [vid for vid, row in self._rows.items() if row.is_selected()]
    
    def select_all(self) -> None:
        """Select all videos."""
        for row in self._rows.values():
            row.set_selected(True)
        if self._on_selection_change:
            self._on_selection_change(len(self._rows))
    
    def deselect_all(self) -> None:
        """Deselect all videos."""
        for row in self._rows.values():
            row.set_selected(False)
        if self._on_selection_change:
            self._on_selection_change(0)
    
    def select_new_only(self) -> None:
        """Select only videos that haven't been downloaded."""
        for video in self._videos:
            row = self._rows.get(video.video_id)
            if row:
                row.set_selected(not video.is_downloaded)
        if self._on_selection_change:
            self._on_selection_change(self.get_selected_count())
    
    def update_video_status(
        self,
        video_id: str,
        status: VideoStatus,
        progress: float = 0.0
    ) -> None:
        """Update status for a specific video."""
        if video_id in self._rows:
            self._rows[video_id].set_status(status, progress)
    
    def update_video_progress(self, video_id: str, progress: float) -> None:
        """Update download progress for a specific video."""
        if video_id in self._rows:
            self._rows[video_id].update_progress(progress)


class PlaylistViewDialog(ctk.CTkToplevel):
    """Dialog for viewing and downloading playlist contents."""
    
    def __init__(
        self,
        master: ctk.CTk,
        playlist_title: str,
        playlist_id: str,
        videos: List[PlaylistVideo],
        on_download: Callable[[List[str], bool], None],
        **kwargs
    ) -> None:
        super().__init__(master, **kwargs)
        
        self._playlist_id = playlist_id
        self._videos = videos
        self._on_download = on_download
        self._compare_download = True  # Default: skip already downloaded
        
        # Window setup
        self.title(f"Playlist: {playlist_title}")
        self.geometry("800x600")
        self.minsize(600, 400)
        self.configure(fg_color=Colors.BG_DARK)
        
        # Make modal
        self.transient(master)
        self.grab_set()
        
        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - 800) // 2
        y = master.winfo_y() + (master.winfo_height() - 600) // 2
        self.geometry(f"+{x}+{y}")
        
        self._create_widgets(playlist_title)
    
    def _create_widgets(self, playlist_title: str) -> None:
        """Create dialog widgets."""
        # Main container
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        
        title_label = ctk.CTkLabel(
            header,
            text=playlist_title,
            font=("Segoe UI Semibold", 18),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        )
        title_label.pack(side="left")
        
        # Count stats
        new_count = sum(1 for v in self._videos if not v.is_downloaded)
        total_count = len(self._videos)
        stats_text = f"{new_count} new / {total_count} total videos"
        
        stats_label = ctk.CTkLabel(
            header,
            text=stats_text,
            font=("Segoe UI", 13),
            text_color=Colors.TEXT_SECONDARY
        )
        stats_label.pack(side="right")
        
        # Selection controls row
        controls = ctk.CTkFrame(container, fg_color="transparent")
        controls.pack(fill="x", pady=(0, 12))
        
        # Compare download checkbox
        self._compare_var = ctk.BooleanVar(value=True)
        self._compare_check = ctk.CTkCheckBox(
            controls,
            text="Skip already downloaded",
            variable=self._compare_var,
            font=("Segoe UI", 12),
            text_color=Colors.TEXT_SECONDARY,
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_DARK,
            border_color=Colors.BORDER,
            command=self._on_compare_toggle
        )
        self._compare_check.pack(side="left")
        
        # Selection buttons
        btn_frame = ctk.CTkFrame(controls, fg_color="transparent")
        btn_frame.pack(side="right")
        
        self._select_all_btn = ctk.CTkButton(
            btn_frame,
            text="Select All",
            width=90,
            height=32,
            font=("Segoe UI", 12),
            fg_color=Colors.BG_INPUT,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=8,
            command=self._select_all
        )
        self._select_all_btn.pack(side="left", padx=(0, 8))
        
        self._select_new_btn = ctk.CTkButton(
            btn_frame,
            text="Select New Only",
            width=110,
            height=32,
            font=("Segoe UI", 12),
            fg_color=Colors.BG_INPUT,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=8,
            command=self._select_new
        )
        self._select_new_btn.pack(side="left", padx=(0, 8))
        
        self._deselect_btn = ctk.CTkButton(
            btn_frame,
            text="Deselect All",
            width=90,
            height=32,
            font=("Segoe UI", 12),
            fg_color=Colors.BG_INPUT,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=8,
            command=self._deselect_all
        )
        self._deselect_btn.pack(side="left")
        
        # Playlist table
        self._table = PlaylistTable(
            container,
            videos=self._videos,
            on_selection_change=self._on_selection_change
        )
        self._table.pack(fill="both", expand=True, pady=(0, 16))
        
        # Bottom action bar
        action_bar = ctk.CTkFrame(container, fg_color="transparent")
        action_bar.pack(fill="x")
        
        # Selection count label
        self._selection_label = ctk.CTkLabel(
            action_bar,
            text=f"{self._table.get_selected_count()} videos selected",
            font=("Segoe UI", 12),
            text_color=Colors.TEXT_MUTED
        )
        self._selection_label.pack(side="left")
        
        # Download button
        self._download_btn = ctk.CTkButton(
            action_bar,
            text="Download Selected",
            width=160,
            height=44,
            font=("Segoe UI Semibold", 14),
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_DARK,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=10,
            command=self._start_download
        )
        self._download_btn.pack(side="right")
        
        # Cancel button
        self._cancel_btn = ctk.CTkButton(
            action_bar,
            text="Cancel",
            width=90,
            height=44,
            font=("Segoe UI", 14),
            fg_color=Colors.BG_INPUT,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=10,
            command=self.destroy
        )
        self._cancel_btn.pack(side="right", padx=(0, 12))
    
    def _on_compare_toggle(self) -> None:
        """Handle compare download checkbox toggle."""
        self._compare_download = self._compare_var.get()
        if self._compare_download:
            self._table.select_new_only()
    
    def _select_all(self) -> None:
        """Select all videos."""
        self._table.select_all()
    
    def _select_new(self) -> None:
        """Select only new videos."""
        self._table.select_new_only()
    
    def _deselect_all(self) -> None:
        """Deselect all videos."""
        self._table.deselect_all()
    
    def _on_selection_change(self, count: int) -> None:
        """Handle selection count change."""
        self._selection_label.configure(text=f"{count} videos selected")
    
    def _start_download(self) -> None:
        """Start downloading selected videos."""
        selected_ids = self._table.get_selected_ids()
        if selected_ids:
            self._on_download(selected_ids, self._compare_download)
    
    def update_video_status(
        self,
        video_id: str,
        status: VideoStatus,
        progress: float = 0.0
    ) -> None:
        """Update status for a video in the table."""
        self._table.update_video_status(video_id, status, progress)
    
    def update_video_progress(self, video_id: str, progress: float) -> None:
        """Update progress for a video in the table."""
        self._table.update_video_progress(video_id, progress)
    
    def set_downloading(self, is_downloading: bool) -> None:
        """Set UI state during download."""
        if is_downloading:
            self._download_btn.configure(
                text="Downloading...",
                state="disabled",
                fg_color=Colors.BG_INPUT
            )
            self._cancel_btn.configure(text="Cancel Download")
        else:
            self._download_btn.configure(
                text="Download Selected",
                state="normal",
                fg_color=Colors.PRIMARY
            )
            self._cancel_btn.configure(text="Close")
