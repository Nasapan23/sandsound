"""
Premium reusable UI components for SandSound.
Modern design with animations, gradients, and polished aesthetics.
"""

import customtkinter as ctk
from typing import Callable, Optional, List
from dataclasses import dataclass
from enum import Enum
import time
import threading


# Color Palette - Premium dark theme
class Colors:
    """Application color palette."""
    # Primary gradient
    PRIMARY = "#6366F1"  # Indigo
    PRIMARY_DARK = "#4F46E5"
    PRIMARY_LIGHT = "#818CF8"
    
    # Accent
    ACCENT = "#8B5CF6"  # Purple
    ACCENT_LIGHT = "#A78BFA"
    
    # Success/Error/Warning
    SUCCESS = "#10B981"
    SUCCESS_DARK = "#059669"
    ERROR = "#EF4444"
    ERROR_DARK = "#DC2626"
    WARNING = "#F59E0B"
    
    # Backgrounds (dark theme)
    BG_DARK = "#0F0F14"
    BG_CARD = "#1A1A24"
    BG_CARD_HOVER = "#22222E"
    BG_INPUT = "#252532"
    
    # Text
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#9CA3AF"
    TEXT_MUTED = "#6B7280"
    
    # Borders
    BORDER = "#2D2D3A"
    BORDER_FOCUS = "#6366F1"


class UrlInput(ctk.CTkFrame):
    """Premium URL input field with validation indicator and animations."""

    def __init__(
        self,
        master: ctk.CTk,
        validate_callback: Optional[Callable[[str], bool]] = None,
        on_submit: Optional[Callable[[str], None]] = None,
        on_info_fetched: Optional[Callable[[dict], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            master, 
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            **kwargs
        )

        self._validate_callback = validate_callback
        self._on_submit = on_submit
        self._on_info_fetched = on_info_fetched
        self._is_valid = False

        # Inner padding frame
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=16)

        # Label row
        label_row = ctk.CTkFrame(inner, fg_color="transparent")
        label_row.pack(fill="x", pady=(0, 10))

        label = ctk.CTkLabel(
            label_row,
            text="YouTube URL",
            font=("Segoe UI Semibold", 13),
            text_color=Colors.TEXT_SECONDARY,
        )
        label.pack(side="left")

        self._status_label = ctk.CTkLabel(
            label_row,
            text="",
            font=("Segoe UI", 12),
            text_color=Colors.TEXT_MUTED,
        )
        self._status_label.pack(side="right")

        # Input row
        input_row = ctk.CTkFrame(inner, fg_color="transparent")
        input_row.pack(fill="x")

        # URL Entry with icon placeholder
        self._entry_frame = ctk.CTkFrame(
            input_row,
            fg_color=Colors.BG_INPUT,
            corner_radius=12,
        )
        self._entry_frame.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self._entry = ctk.CTkEntry(
            self._entry_frame,
            placeholder_text="https://youtube.com/watch?v=... or playlist URL",
            height=48,
            font=("Segoe UI", 14),
            corner_radius=12,
            border_width=0,
            fg_color="transparent",
            text_color=Colors.TEXT_PRIMARY,
            placeholder_text_color=Colors.TEXT_MUTED,
        )
        self._entry.pack(fill="x", padx=4, pady=2)
        self._entry.bind("<KeyRelease>", self._on_key_release)
        self._entry.bind("<Return>", self._on_enter)
        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)

        # Paste button with gradient effect
        self._paste_btn = ctk.CTkButton(
            input_row,
            text="Paste",
            width=90,
            height=48,
            font=("Segoe UI Semibold", 13),
            corner_radius=12,
            fg_color=Colors.BG_INPUT,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            command=self._paste_from_clipboard,
        )
        self._paste_btn.pack(side="right")

    def _on_focus_in(self, event) -> None:
        """Handle focus in - highlight border."""
        self._entry_frame.configure(
            fg_color=Colors.BG_INPUT,
            border_color=Colors.BORDER_FOCUS,
        )

    def _on_focus_out(self, event) -> None:
        """Handle focus out."""
        self._entry_frame.configure(
            fg_color=Colors.BG_INPUT,
        )

    def _paste_from_clipboard(self) -> None:
        """Paste URL from clipboard with animation."""
        try:
            clipboard = self.clipboard_get()
            self._entry.delete(0, "end")
            self._entry.insert(0, clipboard)
            self._validate()
        except Exception:
            pass

    def _on_key_release(self, event) -> None:
        """Handle key release for validation."""
        self._validate()

    def _on_enter(self, event) -> None:
        """Handle Enter key press."""
        if self._is_valid and self._on_submit:
            self._on_submit(self.get_url())

    def _validate(self) -> None:
        """Validate current URL and update status."""
        url = self.get_url()
        if not url:
            self._status_label.configure(text="", text_color=Colors.TEXT_MUTED)
            self._is_valid = False
            return

        if self._validate_callback:
            self._is_valid = self._validate_callback(url)
            if self._is_valid:
                if "playlist" in url.lower():
                    self._status_label.configure(
                        text="Playlist detected",
                        text_color=Colors.ACCENT_LIGHT,
                    )
                else:
                    self._status_label.configure(
                        text="Valid URL",
                        text_color=Colors.SUCCESS,
                    )
            else:
                self._status_label.configure(
                    text="Invalid YouTube URL",
                    text_color=Colors.ERROR,
                )

    def get_url(self) -> str:
        """Get current URL text."""
        return self._entry.get().strip()

    def clear(self) -> None:
        """Clear the input field."""
        self._entry.delete(0, "end")
        self._is_valid = False
        self._status_label.configure(text="")

    def is_valid(self) -> bool:
        """Check if current URL is valid."""
        return self._is_valid


class FormatSelector(ctk.CTkFrame):
    """Premium format and quality selection with segmented controls."""

    AUDIO_FORMATS = ["MP3", "M4A", "OPUS", "FLAC", "WAV"]
    VIDEO_FORMATS = ["MP4", "WebM", "MKV"]
    AUDIO_QUALITIES = ["128k", "192k", "256k", "320k", "Best"]
    VIDEO_QUALITIES = ["720p", "1080p", "1440p", "4K", "8K", "Best"]

    def __init__(
        self,
        master: ctk.CTk,
        on_change: Optional[Callable[[str, str], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            **kwargs
        )

        self._on_change = on_change

        # Inner padding
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=16)

        # Type selector row
        type_row = ctk.CTkFrame(inner, fg_color="transparent")
        type_row.pack(fill="x", pady=(0, 16))

        type_label = ctk.CTkLabel(
            type_row,
            text="Download Type",
            font=("Segoe UI Semibold", 13),
            text_color=Colors.TEXT_SECONDARY,
        )
        type_label.pack(side="left")

        self._type_var = ctk.StringVar(value="Audio")
        self._type_selector = ctk.CTkSegmentedButton(
            type_row,
            values=["Audio", "Video"],
            variable=self._type_var,
            command=self._on_type_change,
            font=("Segoe UI Semibold", 13),
            fg_color=Colors.BG_INPUT,
            selected_color=Colors.PRIMARY,
            selected_hover_color=Colors.PRIMARY_DARK,
            unselected_color=Colors.BG_INPUT,
            unselected_hover_color=Colors.BG_CARD_HOVER,
            corner_radius=10,
            height=40,
        )
        self._type_selector.pack(side="right")

        # Format and Quality row
        options_row = ctk.CTkFrame(inner, fg_color="transparent")
        options_row.pack(fill="x")

        # Format section
        format_frame = ctk.CTkFrame(options_row, fg_color="transparent")
        format_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))

        format_label = ctk.CTkLabel(
            format_frame,
            text="Format",
            font=("Segoe UI", 12),
            text_color=Colors.TEXT_MUTED,
        )
        format_label.pack(anchor="w", pady=(0, 6))

        self._format_var = ctk.StringVar(value="MP3")
        self._format_dropdown = ctk.CTkComboBox(
            format_frame,
            values=self.AUDIO_FORMATS,
            variable=self._format_var,
            command=self._notify_change,
            font=("Segoe UI", 13),
            dropdown_font=("Segoe UI", 12),
            height=44,
            corner_radius=10,
            fg_color=Colors.BG_INPUT,
            border_color=Colors.BORDER,
            button_color=Colors.BG_CARD_HOVER,
            button_hover_color=Colors.PRIMARY,
            dropdown_fg_color=Colors.BG_CARD,
            dropdown_hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            state="readonly",
        )
        self._format_dropdown.pack(fill="x")

        # Quality section
        quality_frame = ctk.CTkFrame(options_row, fg_color="transparent")
        quality_frame.pack(side="right", fill="x", expand=True, padx=(10, 0))

        quality_label = ctk.CTkLabel(
            quality_frame,
            text="Quality",
            font=("Segoe UI", 12),
            text_color=Colors.TEXT_MUTED,
        )
        quality_label.pack(anchor="w", pady=(0, 6))

        self._quality_var = ctk.StringVar(value="Best")
        self._quality_dropdown = ctk.CTkComboBox(
            quality_frame,
            values=self.AUDIO_QUALITIES,
            variable=self._quality_var,
            command=self._notify_change,
            font=("Segoe UI", 13),
            dropdown_font=("Segoe UI", 12),
            height=44,
            corner_radius=10,
            fg_color=Colors.BG_INPUT,
            border_color=Colors.BORDER,
            button_color=Colors.BG_CARD_HOVER,
            button_hover_color=Colors.PRIMARY,
            dropdown_fg_color=Colors.BG_CARD,
            dropdown_hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            state="readonly",
        )
        self._quality_dropdown.pack(fill="x")

    def _on_type_change(self, value: str) -> None:
        """Handle type change between Audio/Video."""
        if value == "Audio":
            self._format_dropdown.configure(values=self.AUDIO_FORMATS)
            self._format_var.set("MP3")
            self._quality_dropdown.configure(values=self.AUDIO_QUALITIES)
            self._quality_var.set("Best")
        else:
            self._format_dropdown.configure(values=self.VIDEO_FORMATS)
            self._format_var.set("MP4")
            self._quality_dropdown.configure(values=self.VIDEO_QUALITIES)
            self._quality_var.set("Best")

        self._notify_change()

    def _notify_change(self, *args) -> None:
        """Notify parent of format/quality change."""
        if self._on_change:
            self._on_change(self.get_format(), self.get_quality())

    def get_format(self) -> str:
        """Get selected format (lowercase)."""
        return self._format_var.get().lower()

    def get_quality(self) -> str:
        """Get selected quality (normalized)."""
        quality = self._quality_var.get()
        quality_map = {
            "128k": "128", "192k": "192", "256k": "256", "320k": "320",
            "720p": "720", "1080p": "1080", "1440p": "1440",
            "4K": "2160", "8K": "4320", "Best": "best",
        }
        return quality_map.get(quality, "best")

    def is_audio(self) -> bool:
        """Check if audio type is selected."""
        return self._type_var.get() == "Audio"


class DownloadButton(ctk.CTkFrame):
    """Premium download button with loading animation."""

    def __init__(
        self,
        master: ctk.CTk,
        command: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self._command = command
        self._is_loading = False

        # Main button with gradient
        self._button = ctk.CTkButton(
            self,
            text="Download",
            height=56,
            font=("Segoe UI Semibold", 16),
            corner_radius=14,
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_DARK,
            text_color=Colors.TEXT_PRIMARY,
            command=self._on_click,
        )
        self._button.pack(fill="x")

    def _on_click(self) -> None:
        """Handle button click."""
        if not self._is_loading and self._command:
            self._command()

    def set_loading(self, loading: bool) -> None:
        """Set loading state."""
        self._is_loading = loading
        if loading:
            self._button.configure(
                text="Downloading...",
                fg_color=Colors.BG_INPUT,
                hover_color=Colors.BG_INPUT,
                state="disabled",
            )
        else:
            self._button.configure(
                text="Download",
                fg_color=Colors.PRIMARY,
                hover_color=Colors.PRIMARY_DARK,
                state="normal",
            )

    def set_cancel_mode(self, cancel_callback: Callable[[], None]) -> None:
        """Switch to cancel mode."""
        self._button.configure(
            text="Cancel Download",
            fg_color=Colors.ERROR,
            hover_color=Colors.ERROR_DARK,
            state="normal",
            command=cancel_callback,
        )
        self._is_loading = True

    def reset(self) -> None:
        """Reset to default state."""
        self._is_loading = False
        self._button.configure(
            text="Download",
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_DARK,
            state="normal",
            command=self._on_click,
        )


class ProgressCard(ctk.CTkFrame):
    """Premium download progress card with animations."""

    def __init__(self, master: ctk.CTk, **kwargs) -> None:
        super().__init__(
            master,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            **kwargs
        )

        # Inner padding
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=16)

        # Header row
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))

        # Status indicator dot
        self._status_dot = ctk.CTkLabel(
            header,
            text="",
            width=10,
            height=10,
            corner_radius=5,
            fg_color=Colors.TEXT_MUTED,
        )
        self._status_dot.pack(side="left", padx=(0, 10))

        # Title
        self._title_label = ctk.CTkLabel(
            header,
            text="Ready to download",
            font=("Segoe UI Semibold", 15),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        )
        self._title_label.pack(side="left", fill="x", expand=True)

        # Percentage
        self._percent_label = ctk.CTkLabel(
            header,
            text="",
            font=("Segoe UI Semibold", 14),
            text_color=Colors.PRIMARY_LIGHT,
        )
        self._percent_label.pack(side="right")

        # Status text
        self._status_label = ctk.CTkLabel(
            inner,
            text="Paste a YouTube URL to begin downloading",
            font=("Segoe UI", 13),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
        )
        self._status_label.pack(fill="x", pady=(0, 14))

        # Progress bar container
        progress_container = ctk.CTkFrame(
            inner,
            fg_color=Colors.BG_INPUT,
            corner_radius=6,
            height=12,
        )
        progress_container.pack(fill="x", pady=(0, 12))
        progress_container.pack_propagate(False)

        self._progress = ctk.CTkProgressBar(
            progress_container,
            height=12,
            corner_radius=6,
            fg_color=Colors.BG_INPUT,
            progress_color=Colors.PRIMARY,
        )
        self._progress.pack(fill="both", expand=True)
        self._progress.set(0)

        # Stats row
        stats_row = ctk.CTkFrame(inner, fg_color="transparent")
        stats_row.pack(fill="x")

        self._speed_label = ctk.CTkLabel(
            stats_row,
            text="",
            font=("Segoe UI", 12),
            text_color=Colors.TEXT_MUTED,
        )
        self._speed_label.pack(side="left")

        self._eta_label = ctk.CTkLabel(
            stats_row,
            text="",
            font=("Segoe UI", 12),
            text_color=Colors.TEXT_MUTED,
        )
        self._eta_label.pack(side="right")

    def update_progress(
        self,
        title: str = "",
        status: str = "",
        progress: float = 0.0,
        speed: str = "",
        eta: str = "",
    ) -> None:
        """Update progress display with animation."""
        if title:
            # Truncate long titles
            display_title = title[:50] + "..." if len(title) > 50 else title
            self._title_label.configure(text=display_title)
        if status:
            self._status_label.configure(text=status)

        self._progress.set(progress / 100.0)
        self._percent_label.configure(text=f"{progress:.0f}%")
        self._speed_label.configure(text=speed)
        self._eta_label.configure(text=f"ETA {eta}" if eta else "")
        
        # Animate status dot
        self._status_dot.configure(fg_color=Colors.PRIMARY)

    def reset(self) -> None:
        """Reset to initial state."""
        self._title_label.configure(text="Ready to download")
        self._status_label.configure(text="Paste a YouTube URL to begin downloading")
        self._progress.set(0)
        self._percent_label.configure(text="")
        self._speed_label.configure(text="")
        self._eta_label.configure(text="")
        self._status_dot.configure(fg_color=Colors.TEXT_MUTED)

    def set_completed(self, title: str) -> None:
        """Set completed state with success styling."""
        display_title = title[:50] + "..." if len(title) > 50 else title
        self._title_label.configure(text=display_title)
        self._status_label.configure(text="Download completed successfully")
        self._progress.set(1.0)
        self._progress.configure(progress_color=Colors.SUCCESS)
        self._percent_label.configure(text="100%", text_color=Colors.SUCCESS)
        self._speed_label.configure(text="")
        self._eta_label.configure(text="")
        self._status_dot.configure(fg_color=Colors.SUCCESS)

    def set_error(self, title: str, error: str) -> None:
        """Set error state with error styling."""
        display_title = title[:50] + "..." if len(title) > 50 else title
        self._title_label.configure(text=display_title)
        error_display = error[:60] + "..." if len(error) > 60 else error
        self._status_label.configure(text=f"Error: {error_display}")
        self._progress.set(0)
        self._progress.configure(progress_color=Colors.ERROR)
        self._percent_label.configure(text="", text_color=Colors.ERROR)
        self._speed_label.configure(text="")
        self._eta_label.configure(text="")
        self._status_dot.configure(fg_color=Colors.ERROR)

    def set_processing(self) -> None:
        """Set processing state."""
        self._status_label.configure(text="Processing and converting media...")
        self._progress.configure(progress_color=Colors.ACCENT)


@dataclass
class DownloadItem:
    """Represents a download queue item."""
    url: str
    title: str
    format: str
    quality: str
    status: str = "pending"
    progress: float = 0.0


class DownloadQueue(ctk.CTkScrollableFrame):
    """Download queue/history display."""

    def __init__(self, master: ctk.CTk, **kwargs) -> None:
        super().__init__(
            master,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            **kwargs
        )

        self._items: List[ctk.CTkFrame] = []

        # Header
        self._header = ctk.CTkLabel(
            self,
            text="Download Queue",
            font=("Segoe UI Semibold", 14),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
        )
        self._header.pack(fill="x", padx=20, pady=(16, 12))

        # Empty state
        self._empty_label = ctk.CTkLabel(
            self,
            text="No downloads yet",
            font=("Segoe UI", 13),
            text_color=Colors.TEXT_MUTED,
        )
        self._empty_label.pack(pady=20)

    def add_item(self, title: str, format_type: str) -> ctk.CTkFrame:
        """Add a new download item to the queue."""
        self._empty_label.pack_forget()

        item_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_INPUT,
            corner_radius=10,
            height=60,
        )
        item_frame.pack(fill="x", padx=16, pady=(0, 8))
        item_frame.pack_propagate(False)

        inner = ctk.CTkFrame(item_frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=10)

        # Title
        title_label = ctk.CTkLabel(
            inner,
            text=title[:40] + "..." if len(title) > 40 else title,
            font=("Segoe UI Semibold", 12),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        )
        title_label.pack(fill="x")

        # Status row
        status_row = ctk.CTkFrame(inner, fg_color="transparent")
        status_row.pack(fill="x")

        format_label = ctk.CTkLabel(
            status_row,
            text=format_type.upper(),
            font=("Segoe UI", 11),
            text_color=Colors.ACCENT_LIGHT,
        )
        format_label.pack(side="left")

        status_label = ctk.CTkLabel(
            status_row,
            text="Pending",
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_MUTED,
        )
        status_label.pack(side="right")

        self._items.append(item_frame)
        return item_frame

    def clear(self) -> None:
        """Clear all items from queue."""
        for item in self._items:
            item.destroy()
        self._items.clear()
        self._empty_label.pack(pady=20)


class Toast(ctk.CTkFrame):
    """Toast notification component."""

    def __init__(
        self,
        master: ctk.CTk,
        message: str,
        toast_type: str = "info",
        duration: int = 3000,
        **kwargs,
    ) -> None:
        colors = {
            "info": Colors.PRIMARY,
            "success": Colors.SUCCESS,
            "error": Colors.ERROR,
            "warning": Colors.WARNING,
        }

        super().__init__(
            master,
            fg_color=colors.get(toast_type, Colors.PRIMARY),
            corner_radius=10,
            **kwargs
        )

        label = ctk.CTkLabel(
            self,
            text=message,
            font=("Segoe UI Semibold", 13),
            text_color=Colors.TEXT_PRIMARY,
        )
        label.pack(padx=20, pady=12)

        # Auto-dismiss
        self.after(duration, self.destroy)
