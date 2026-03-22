"""
Playlist history view for SandSound.
Shows all downloaded playlists and allows checking for new songs.
"""

import customtkinter as ctk
from typing import Callable, Optional

from ..database import parse_timestamp
from ..history import DownloadHistory, PlaylistRecord
from ..downloader import Downloader
from .components import Colors
from .async_utils import BackgroundTaskPool


class PlaylistHistoryRow(ctk.CTkFrame):
    """Single row in the playlist history table."""
    
    def __init__(
        self,
        master: ctk.CTkFrame,
        playlist: PlaylistRecord,
        on_check: Optional[Callable[[str], None]] = None,
        on_open: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> None:
        super().__init__(
            master,
            fg_color=Colors.BG_CARD,
            corner_radius=8,
            height=60,
            **kwargs
        )
        self.pack_propagate(False)
        
        self._playlist = playlist
        self._on_check = on_check
        self._on_open = on_open
        
        # Main container
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=12, pady=8)
        
        # Left side - Title and info
        left_frame = ctk.CTkFrame(container, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True)
        
        # Title
        title_label = ctk.CTkLabel(
            left_frame,
            text=playlist.title[:60] + "..." if len(playlist.title) > 60 else playlist.title,
            font=("Segoe UI Semibold", 13),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        )
        title_label.pack(side="top", fill="x", anchor="w")
        
        # Info row
        info_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        info_frame.pack(side="top", fill="x", pady=(4, 0))
        
        # Video count
        video_count = playlist.video_count
        count_text = f"{video_count} song{'s' if video_count != 1 else ''} downloaded"
        count_label = ctk.CTkLabel(
            info_frame,
            text=count_text,
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_MUTED
        )
        count_label.pack(side="left")
        
        # Last downloaded date
        try:
            last_dl = parse_timestamp(playlist.last_downloaded)
            date_str = last_dl.strftime("%Y-%m-%d")
        except:
            date_str = "Unknown"
        
        date_label = ctk.CTkLabel(
            info_frame,
            text=f"Last: {date_str}",
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_MUTED
        )
        date_label.pack(side="left", padx=(12, 0))
        
        # New videos indicator (hidden by default)
        self._new_indicator = ctk.CTkLabel(
            info_frame,
            text="",
            font=("Segoe UI Semibold", 11),
            text_color=Colors.SUCCESS
        )
        
        # Right side - Buttons
        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.pack(side="right", padx=(12, 0))
        
        # Check for new button
        self._check_btn = ctk.CTkButton(
            button_frame,
            text="Check for New",
            width=110,
            height=32,
            font=("Segoe UI", 11),
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_DARK,
            corner_radius=6,
            command=self._on_check_click
        )
        self._check_btn.pack(side="left", padx=(0, 8))
        
        # Open button
        self._open_btn = ctk.CTkButton(
            button_frame,
            text="Open",
            width=80,
            height=32,
            font=("Segoe UI", 11),
            fg_color=Colors.BG_INPUT,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=6,
            command=self._on_open_click
        )
        self._open_btn.pack(side="left")
    
    def _on_check_click(self) -> None:
        """Handle check button click."""
        if self._on_check:
            self._on_check(self._playlist.playlist_id)
    
    def _on_open_click(self) -> None:
        """Handle open button click."""
        if self._on_open:
            self._on_open(self._playlist.playlist_id)
    
    def set_new_count(self, count: int) -> None:
        """Update the new videos indicator."""
        if count > 0:
            self._new_indicator.configure(text=f"{count} new song{'s' if count != 1 else ''}")
            self._new_indicator.pack(side="left", padx=(12, 0))
        else:
            self._new_indicator.pack_forget()
    
    def set_checking(self, is_checking: bool) -> None:
        """Update button state during check."""
        if is_checking:
            self._check_btn.configure(text="Checking...", state="disabled")
        else:
            self._check_btn.configure(text="Check for New", state="normal")


class PlaylistHistoryDialog(ctk.CTkToplevel):
    """Dialog for viewing playlist history and checking for new songs."""

    MAX_HISTORY_CHECK_WORKERS = 2
    
    def __init__(
        self,
        master: ctk.CTk,
        history: DownloadHistory,
        downloader: Downloader,
        on_open_playlist: Callable[[str], None],
        **kwargs
    ) -> None:
        super().__init__(master, **kwargs)
        
        self._history = history
        self._downloader = downloader
        self._on_open_playlist = on_open_playlist
        self._rows: dict[str, PlaylistHistoryRow] = {}
        self._checking_playlists: set[str] = set()
        self._history_pool = BackgroundTaskPool(self.MAX_HISTORY_CHECK_WORKERS)
        
        # Window setup
        self.title("Playlist History")
        self.geometry("800x600")
        self.minsize(700, 500)
        self.configure(fg_color=Colors.BG_DARK)
        
        # Make modal
        self.transient(master)
        self.grab_set()
        
        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - 800) // 2
        y = master.winfo_y() + (master.winfo_height() - 600) // 2
        self.geometry(f"+{x}+{y}")
        
        self._create_widgets()
        self._refresh_playlists()
    
    def _create_widgets(self) -> None:
        """Create dialog widgets."""
        # Main container
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        
        title_label = ctk.CTkLabel(
            header,
            text="Downloaded Playlists",
            font=("Segoe UI Semibold", 20),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        )
        title_label.pack(side="left")
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            header,
            text="Refresh All",
            width=100,
            height=32,
            font=("Segoe UI", 11),
            fg_color=Colors.BG_INPUT,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=6,
            command=self._refresh_all
        )
        refresh_btn.pack(side="right")
        
        # Scrollable frame for playlists
        self._scroll_frame = ctk.CTkScrollableFrame(
            container,
            fg_color=Colors.BG_CARD,
            corner_radius=12
        )
        self._scroll_frame.pack(fill="both", expand=True, pady=(0, 16))
        
        # Empty state label
        self._empty_label = ctk.CTkLabel(
            self._scroll_frame,
            text="No playlists in history yet.\nDownload a playlist to see it here.",
            font=("Segoe UI", 14),
            text_color=Colors.TEXT_MUTED,
            justify="center"
        )
        
        # Close button
        close_btn = ctk.CTkButton(
            container,
            text="Close",
            width=120,
            height=40,
            font=("Segoe UI Semibold", 13),
            fg_color=Colors.BG_INPUT,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=8,
            command=self.destroy
        )
        close_btn.pack()
    
    def _refresh_playlists(self) -> None:
        """Refresh the playlist list."""
        # Clear existing rows
        for row in self._rows.values():
            row.destroy()
        self._rows.clear()
        
        # Get all playlists
        playlists = self._history.get_all_playlists()
        
        if not playlists:
            self._empty_label.pack(pady=50)
            return
        
        self._empty_label.pack_forget()
        
        # Create rows
        for playlist in playlists:
            row = PlaylistHistoryRow(
                self._scroll_frame,
                playlist=playlist,
                on_check=self._check_playlist,
                on_open=self._open_playlist
            )
            row.pack(fill="x", pady=4)
            self._rows[playlist.playlist_id] = row
    
    def _check_playlist(self, playlist_id: str) -> None:
        """Check a playlist for new videos."""
        if playlist_id in self._checking_playlists:
            return
        
        playlist = self._history.get_playlist_record(playlist_id)
        if not playlist or not playlist.playlist_url:
            return
        
        self._checking_playlists.add(playlist_id)
        row = self._rows.get(playlist_id)
        if row:
            row.set_checking(True)
        
        self._history_pool.submit(
            self._check_playlist_worker,
            playlist_id,
            playlist.playlist_url,
        )
    
    def _check_playlist_worker(self, playlist_id: str, playlist_url: str) -> None:
        """Worker thread to check playlist for new videos."""
        try:
            # Get current playlist info
            info = self._downloader.get_video_info(
                playlist_url,
                allow_cached=False,
                force_refresh=True,
            )
            
            if not info or not info.is_playlist or not info.entries:
                self.after(0, lambda: self._check_complete(playlist_id, 0))
                return
            
            # Get current video IDs
            current_ids = [e.video_id for e in info.entries if e.video_id]
            
            # Check for new videos
            new_videos, new_count = self._history.check_for_new_videos(
                playlist_id,
                current_ids
            )
            
            # Update UI on main thread
            self.after(0, lambda: self._check_complete(playlist_id, new_count))
            
        except Exception as e:
            print(f"Error checking playlist: {e}")
            self.after(0, lambda: self._check_complete(playlist_id, 0))
    
    def _check_complete(self, playlist_id: str, new_count: int) -> None:
        """Handle check completion."""
        self._checking_playlists.discard(playlist_id)
        
        row = self._rows.get(playlist_id)
        if row:
            row.set_checking(False)
            row.set_new_count(new_count)
    
    def _open_playlist(self, playlist_id: str) -> None:
        """Open a playlist for viewing/downloading."""
        playlist = self._history.get_playlist_record(playlist_id)
        if not playlist or not playlist.playlist_url:
            return
        
        # Close this dialog and open the playlist
        self.destroy()
        self._on_open_playlist(playlist.playlist_url)
    
    def _refresh_all(self) -> None:
        """Check all playlists for new videos."""
        playlists = self._history.get_all_playlists()
        for playlist in playlists:
            if playlist.playlist_url:
                self._check_playlist(playlist.playlist_id)

    def destroy(self) -> None:
        """Release background resources before closing the dialog."""
        self._history_pool.shutdown()
        super().destroy()
