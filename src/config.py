"""
Configuration management for SandSound.
Handles persistent settings storage and retrieval.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Any, Optional


class Config:
    """Manages application configuration with JSON persistence."""

    DEFAULT_CONFIG = {
        "download_dir": str(Path.home() / "Downloads" / "SandSound"),
        "cookie_file": "",
        "ffmpeg_path": "",  # Empty means auto-detect from PATH
        "default_format": "mp3",
        "default_quality": "best",
        "theme": "dark",
        "concurrent_downloads": 3,
    }

    AUDIO_QUALITIES = ["128", "192", "256", "320", "best"]
    VIDEO_QUALITIES = ["480", "720", "1080", "1440", "2160", "4320", "best"]
    FORMATS = ["mp3", "mp4", "m4a", "webm", "opus", "flac", "wav", "mkv"]

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Initialize configuration manager.

        Args:
            config_path: Path to config file. Defaults to user config directory.
        """
        if config_path:
            self._config_path = Path(config_path)
        else:
            config_dir = Path.home() / ".sandsound"
            config_dir.mkdir(parents=True, exist_ok=True)
            self._config_path = config_dir / "config.json"

        self._config: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load configuration from file or create with defaults."""
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                # Merge with defaults for any missing keys
                for key, value in self.DEFAULT_CONFIG.items():
                    if key not in self._config:
                        self._config[key] = value
            except (json.JSONDecodeError, IOError):
                self._config = self.DEFAULT_CONFIG.copy()
        else:
            self._config = self.DEFAULT_CONFIG.copy()
            self._save()

        # Ensure download directory exists
        download_dir = Path(self._config["download_dir"])
        download_dir.mkdir(parents=True, exist_ok=True)

    def _save(self) -> None:
        """Persist configuration to file."""
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
        except IOError as e:
            print(f"Failed to save configuration: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key.
            default: Default value if key not found.

        Returns:
            Configuration value or default.
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value and persist.

        Args:
            key: Configuration key.
            value: Value to set.
        """
        self._config[key] = value
        self._save()

    def get_all(self) -> dict[str, Any]:
        """Get all configuration values."""
        return self._config.copy()

    @property
    def download_dir(self) -> str:
        """Get download directory path."""
        return self._config["download_dir"]

    @download_dir.setter
    def download_dir(self, value: str) -> None:
        """Set download directory path."""
        Path(value).mkdir(parents=True, exist_ok=True)
        self.set("download_dir", value)

    @property
    def cookie_file(self) -> str:
        """Get cookie file path."""
        return self._config["cookie_file"]

    @cookie_file.setter
    def cookie_file(self, value: str) -> None:
        """Set cookie file path."""
        self.set("cookie_file", value)

    @property
    def default_format(self) -> str:
        """Get default download format."""
        return self._config["default_format"]

    @default_format.setter
    def default_format(self, value: str) -> None:
        """Set default download format."""
        self.set("default_format", value)

    @property
    def default_quality(self) -> str:
        """Get default quality setting."""
        return self._config["default_quality"]

    @default_quality.setter
    def default_quality(self, value: str) -> None:
        """Set default quality setting."""
        self.set("default_quality", value)

    @property
    def theme(self) -> str:
        """Get UI theme."""
        return self._config["theme"]

    @theme.setter
    def theme(self, value: str) -> None:
        """Set UI theme."""
        self.set("theme", value)

    def is_cookie_valid(self) -> bool:
        """Check if configured cookie file exists and is readable."""
        cookie_path = self.cookie_file
        if not cookie_path:
            return False
        return Path(cookie_path).is_file()

    @property
    def ffmpeg_path(self) -> str:
        """Get FFmpeg path."""
        return self._config.get("ffmpeg_path", "")

    @ffmpeg_path.setter
    def ffmpeg_path(self, value: str) -> None:
        """Set FFmpeg path."""
        self.set("ffmpeg_path", value)

    def get_ffmpeg_location(self) -> Optional[str]:
        """
        Get the FFmpeg location to use.
        Returns configured path if set, otherwise None (use system PATH).
        """
        if self.ffmpeg_path and Path(self.ffmpeg_path).exists():
            return self.ffmpeg_path
        return None

    def is_ffmpeg_available(self) -> bool:
        """
        Check if FFmpeg is available (either in PATH or configured).
        """
        # Check configured path first
        if self.ffmpeg_path:
            ffmpeg_exe = Path(self.ffmpeg_path)
            if ffmpeg_exe.is_file():
                return True
            # Check if it's a directory containing ffmpeg
            ffmpeg_in_dir = ffmpeg_exe / "ffmpeg.exe"
            if ffmpeg_in_dir.is_file():
                return True
        
        # Check system PATH
        return shutil.which("ffmpeg") is not None
