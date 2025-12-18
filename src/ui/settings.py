"""
Settings dialog for SandSound.
"""

import customtkinter as ctk
import webbrowser
from pathlib import Path
from tkinter import filedialog
from typing import Callable, Optional

from ..config import Config
from .components import Colors


class SettingsDialog(ctk.CTkToplevel):
    """Settings configuration dialog."""

    FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

    def __init__(
        self,
        master: ctk.CTk,
        config: Config,
        on_save: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)

        self._config = config
        self._on_save = on_save

        # Window setup
        self.title("Settings")
        self.geometry("550x700")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - 550) // 2
        y = master.winfo_y() + (master.winfo_height() - 700) // 2
        self.geometry(f"+{x}+{y}")

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create dialog widgets."""
        # Scrollable main container
        container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title = ctk.CTkLabel(
            container,
            text="Settings",
            font=("Segoe UI", 24, "bold"),
        )
        title.pack(anchor="w", pady=(0, 20))

        # FFmpeg section (most important - at top)
        self._create_ffmpeg_section(container)

        # Cookie section
        self._create_cookie_section(container)

        # Download directory section
        self._create_download_section(container)

        # Theme section
        self._create_theme_section(container)

        # Buttons
        self._create_buttons(container)

    def _create_ffmpeg_section(self, container: ctk.CTkFrame) -> None:
        """Create FFmpeg configuration section."""
        ffmpeg_frame = ctk.CTkFrame(container, corner_radius=10)
        ffmpeg_frame.pack(fill="x", pady=(0, 15))

        # Header with status
        header = ctk.CTkFrame(ffmpeg_frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 5))

        ffmpeg_label = ctk.CTkLabel(
            header,
            text="FFmpeg",
            font=("Segoe UI", 13, "bold"),
        )
        ffmpeg_label.pack(side="left")

        # Status indicator
        is_available = self._config.is_ffmpeg_available()
        self._ffmpeg_status = ctk.CTkLabel(
            header,
            text="✓ Available" if is_available else "✗ Not found",
            font=("Segoe UI", 11),
            text_color=Colors.SUCCESS if is_available else Colors.ERROR
        )
        self._ffmpeg_status.pack(side="right")

        # Info text
        info_text = "FFmpeg is required for audio conversion (MP3, etc.)"
        if not is_available:
            info_text = "⚠️ FFmpeg not found! Required for audio conversion."
        
        info_label = ctk.CTkLabel(
            ffmpeg_frame,
            text=info_text,
            font=("Segoe UI", 11),
            text_color=Colors.WARNING if not is_available else Colors.TEXT_MUTED
        )
        info_label.pack(anchor="w", padx=15, pady=(0, 8))

        # Path input
        path_frame = ctk.CTkFrame(ffmpeg_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=15, pady=(0, 10))

        self._ffmpeg_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text="Leave empty to auto-detect, or set path...",
            height=40,
            font=("Segoe UI", 12),
        )
        self._ffmpeg_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        if self._config.ffmpeg_path:
            self._ffmpeg_entry.insert(0, self._config.ffmpeg_path)

        browse_btn = ctk.CTkButton(
            path_frame,
            text="Browse",
            width=80,
            height=40,
            command=self._browse_ffmpeg
        )
        browse_btn.pack(side="right")

        # Download button
        download_frame = ctk.CTkFrame(ffmpeg_frame, fg_color="transparent")
        download_frame.pack(fill="x", padx=15, pady=(0, 15))

        download_btn = ctk.CTkButton(
            download_frame,
            text="📥 Download FFmpeg",
            height=36,
            font=("Segoe UI Semibold", 12),
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_DARK,
            corner_radius=8,
            command=self._download_ffmpeg
        )
        download_btn.pack(side="left")

        help_label = ctk.CTkLabel(
            download_frame,
            text="Extract and point to ffmpeg.exe",
            font=("Segoe UI", 10),
            text_color=Colors.TEXT_MUTED
        )
        help_label.pack(side="left", padx=(12, 0))

    def _create_cookie_section(self, container: ctk.CTkFrame) -> None:
        """Create cookie configuration section."""
        cookie_frame = ctk.CTkFrame(container, corner_radius=10)
        cookie_frame.pack(fill="x", pady=(0, 15))

        cookie_header = ctk.CTkFrame(cookie_frame, fg_color="transparent")
        cookie_header.pack(fill="x", padx=15, pady=(15, 5))

        cookie_label = ctk.CTkLabel(
            cookie_header,
            text="YouTube Cookies",
            font=("Segoe UI", 13, "bold"),
        )
        cookie_label.pack(side="left")

        self._cookie_status = ctk.CTkLabel(
            cookie_header,
            text="✓ Saved" if self._config.is_cookie_valid() else "Not configured",
            font=("Segoe UI", 11),
            text_color=Colors.SUCCESS if self._config.is_cookie_valid() else Colors.TEXT_MUTED
        )
        self._cookie_status.pack(side="right")

        cookie_hint = ctk.CTkLabel(
            cookie_frame,
            text="Paste cookies below (Netscape format from browser extension)",
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_MUTED
        )
        cookie_hint.pack(anchor="w", padx=15, pady=(0, 8))

        self._cookie_text = ctk.CTkTextbox(
            cookie_frame,
            height=100,
            font=("Consolas", 11),
            corner_radius=8,
        )
        self._cookie_text.pack(fill="x", padx=15, pady=(0, 10))

        if self._config.is_cookie_valid():
            try:
                with open(self._config.cookie_file, "r", encoding="utf-8") as f:
                    self._cookie_text.insert("1.0", f.read())
            except Exception:
                pass

        clear_btn = ctk.CTkButton(
            cookie_frame,
            text="Clear Cookies",
            width=100,
            height=30,
            font=("Segoe UI", 11),
            fg_color=Colors.BG_INPUT,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=6,
            command=self._clear_cookies
        )
        clear_btn.pack(anchor="w", padx=15, pady=(0, 15))

    def _create_download_section(self, container: ctk.CTkFrame) -> None:
        """Create download directory section."""
        download_frame = ctk.CTkFrame(container, corner_radius=10)
        download_frame.pack(fill="x", pady=(0, 15))

        download_label = ctk.CTkLabel(
            download_frame,
            text="Download Directory",
            font=("Segoe UI", 13, "bold"),
        )
        download_label.pack(anchor="w", padx=15, pady=(15, 5))

        download_input_frame = ctk.CTkFrame(download_frame, fg_color="transparent")
        download_input_frame.pack(fill="x", padx=15, pady=(0, 15))

        self._download_entry = ctk.CTkEntry(
            download_input_frame,
            placeholder_text="Select download folder...",
            height=40,
            font=("Segoe UI", 12),
        )
        self._download_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._download_entry.insert(0, self._config.download_dir)

        download_browse = ctk.CTkButton(
            download_input_frame,
            text="Browse",
            width=80,
            height=40,
            command=self._browse_download,
        )
        download_browse.pack(side="right")

    def _create_theme_section(self, container: ctk.CTkFrame) -> None:
        """Create theme selection section."""
        theme_frame = ctk.CTkFrame(container, corner_radius=10)
        theme_frame.pack(fill="x", pady=(0, 15))

        theme_label = ctk.CTkLabel(
            theme_frame,
            text="Theme",
            font=("Segoe UI", 13, "bold"),
        )
        theme_label.pack(anchor="w", padx=15, pady=(15, 5))

        self._theme_var = ctk.StringVar(value=self._config.theme.capitalize())
        theme_selector = ctk.CTkSegmentedButton(
            theme_frame,
            values=["Light", "Dark", "System"],
            variable=self._theme_var,
            font=("Segoe UI", 12),
        )
        theme_selector.pack(fill="x", padx=15, pady=(0, 15))

    def _create_buttons(self, container: ctk.CTkFrame) -> None:
        """Create action buttons."""
        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.pack(fill="x", pady=(20, 0))

        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            width=100,
            height=40,
            fg_color="transparent",
            border_width=2,
            command=self.destroy,
        )
        cancel_btn.pack(side="left")

        save_btn = ctk.CTkButton(
            button_frame,
            text="Save",
            width=100,
            height=40,
            command=self._save,
        )
        save_btn.pack(side="right")

    def _browse_ffmpeg(self) -> None:
        """Open file browser for FFmpeg."""
        filepath = filedialog.askopenfilename(
            title="Select FFmpeg Executable",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if filepath:
            self._ffmpeg_entry.delete(0, "end")
            self._ffmpeg_entry.insert(0, filepath)

    def _download_ffmpeg(self) -> None:
        """Open FFmpeg download page in browser."""
        webbrowser.open(self.FFMPEG_DOWNLOAD_URL)

    def _clear_cookies(self) -> None:
        """Clear the cookies text area."""
        self._cookie_text.delete("1.0", "end")

    def _browse_download(self) -> None:
        """Open folder browser for download directory."""
        dirpath = filedialog.askdirectory(title="Select Download Folder")
        if dirpath:
            self._download_entry.delete(0, "end")
            self._download_entry.insert(0, dirpath)

    def _save(self) -> None:
        """Save settings and close dialog."""
        # Save FFmpeg path
        ffmpeg_path = self._ffmpeg_entry.get().strip()
        self._config.ffmpeg_path = ffmpeg_path

        # Save cookies to file
        cookie_content = self._cookie_text.get("1.0", "end").strip()
        if cookie_content:
            cookie_dir = Path.home() / ".sandsound"
            cookie_dir.mkdir(parents=True, exist_ok=True)
            cookie_path = cookie_dir / "cookies.txt"
            
            try:
                with open(cookie_path, "w", encoding="utf-8") as f:
                    f.write(cookie_content)
                self._config.cookie_file = str(cookie_path)
            except Exception as e:
                print(f"Failed to save cookies: {e}")
        else:
            self._config.cookie_file = ""

        # Save download directory
        download_dir = self._download_entry.get().strip()
        if download_dir:
            self._config.download_dir = download_dir

        # Save theme
        theme = self._theme_var.get().lower()
        self._config.theme = theme
        ctk.set_appearance_mode(theme)

        if self._on_save:
            self._on_save()

        self.destroy()
