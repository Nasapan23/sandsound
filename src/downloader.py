"""
YouTube download service using yt-dlp.
Handles video/audio downloading with cookie authentication.
"""

import os
import re
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional

import yt_dlp


class DownloadStatus(Enum):
    """Status of a download task."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadProgress:
    """Progress information for a download."""
    status: DownloadStatus
    title: str
    progress: float  # 0.0 to 100.0
    speed: str
    eta: str
    filename: str
    error: Optional[str] = None


@dataclass
class PlaylistItem:
    """Information about a single video in a playlist."""
    video_id: str
    title: str
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    url: Optional[str] = None


@dataclass
class VideoInfo:
    """Information about a video or playlist."""
    url: str
    title: str
    duration: Optional[int]
    thumbnail: Optional[str]
    is_playlist: bool
    playlist_count: int = 1
    uploader: Optional[str] = None
    playlist_id: Optional[str] = None
    entries: Optional[List[PlaylistItem]] = None


class Downloader:
    """YouTube downloader service using yt-dlp."""

    # Format templates for yt-dlp
    AUDIO_FORMATS = {
        "mp3": "bestaudio/best",
        "m4a": "bestaudio[ext=m4a]/bestaudio/best",
        "opus": "bestaudio[ext=opus]/bestaudio/best",
        "flac": "bestaudio/best",
        "wav": "bestaudio/best",
    }

    VIDEO_FORMATS = {
        "mp4": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "webm": "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best",
        "mkv": "bestvideo+bestaudio/best",
    }

    QUALITY_MAP = {
        "480": "480",
        "720": "720",
        "1080": "1080",
        "1440": "1440",
        "2160": "2160",  # 4K
        "4320": "4320",  # 8K Ultra HD
        "best": None,
    }

    AUDIO_QUALITY_MAP = {
        "128": "128",
        "192": "192",
        "256": "256",
        "320": "320",
        "best": "0",  # Best quality in yt-dlp
    }

    def __init__(
        self,
        download_dir: str,
        cookie_file: Optional[str] = None,
        ffmpeg_location: Optional[str] = None,
    ) -> None:
        """
        Initialize downloader.

        Args:
            download_dir: Directory to save downloaded files.
            cookie_file: Path to Netscape format cookies file.
            ffmpeg_location: Path to FFmpeg executable or directory.
        """
        self._download_dir = Path(download_dir)
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._cookie_file = cookie_file
        self._ffmpeg_location = ffmpeg_location
        self._cancel_flag = threading.Event()

    def set_cookie_file(self, cookie_file: str) -> None:
        """Update the cookie file path."""
        self._cookie_file = cookie_file

    def set_download_dir(self, download_dir: str) -> None:
        """Update the download directory."""
        self._download_dir = Path(download_dir)
        self._download_dir.mkdir(parents=True, exist_ok=True)

    def set_ffmpeg_location(self, ffmpeg_location: Optional[str]) -> None:
        """Update the FFmpeg location."""
        self._ffmpeg_location = ffmpeg_location

    def _get_base_options(self) -> dict:
        """Get base yt-dlp options."""
        opts = {
            "outtmpl": str(self._download_dir / "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        if self._cookie_file and Path(self._cookie_file).is_file():
            opts["cookiefile"] = self._cookie_file

        if self._ffmpeg_location:
            opts["ffmpeg_location"] = self._ffmpeg_location

        return opts

    def get_video_info(self, url: str) -> Optional[VideoInfo]:
        """
        Extract video or playlist information without downloading.

        Args:
            url: YouTube URL.

        Returns:
            VideoInfo object or None if extraction fails.
        """
        opts = self._get_base_options()
        opts["extract_flat"] = "in_playlist"

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if info is None:
                    return None

                is_playlist = info.get("_type") == "playlist"
                raw_entries = info.get("entries", [])
                
                # Build playlist entries with video info
                entries = None
                if is_playlist and raw_entries:
                    entries = []
                    for entry in raw_entries:
                        if entry:  # Skip None entries
                            video_id = entry.get("id") or entry.get("url", "").split("=")[-1]
                            entries.append(PlaylistItem(
                                video_id=video_id,
                                title=entry.get("title", "Unknown"),
                                duration=entry.get("duration"),
                                thumbnail=entry.get("thumbnail"),
                                url=f"https://www.youtube.com/watch?v={video_id}"
                            ))

                return VideoInfo(
                    url=url,
                    title=info.get("title", "Unknown"),
                    duration=info.get("duration"),
                    thumbnail=info.get("thumbnail"),
                    is_playlist=is_playlist,
                    playlist_count=len(entries) if entries else 1,
                    uploader=info.get("uploader"),
                    playlist_id=info.get("id") if is_playlist else None,
                    entries=entries
                )
        except Exception as e:
            print(f"Failed to extract info: {e}")
            return None

    def download(
        self,
        url: str,
        format_type: str = "mp3",
        quality: str = "best",
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
    ) -> bool:
        """
        Download video or playlist.

        Args:
            url: YouTube URL.
            format_type: Output format (mp3, mp4, etc.).
            quality: Quality setting.
            progress_callback: Callback for progress updates.

        Returns:
            True if download succeeded, False otherwise.
        """
        self._cancel_flag.clear()

        is_audio = format_type in self.AUDIO_FORMATS
        opts = self._get_base_options()

        # Set format based on type
        if is_audio:
            opts["format"] = self.AUDIO_FORMATS.get(format_type, "bestaudio/best")
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": format_type,
                "preferredquality": self.AUDIO_QUALITY_MAP.get(quality, "0"),
            }]
        else:
            base_format = self.VIDEO_FORMATS.get(format_type, "bestvideo+bestaudio/best")
            quality_val = self.QUALITY_MAP.get(quality)

            if quality_val:
                opts["format"] = f"bestvideo[height<={quality_val}]+bestaudio/best[height<={quality_val}]"
            else:
                opts["format"] = base_format

            if format_type in ["mp4", "mkv"]:
                opts["merge_output_format"] = format_type

        # Progress hook
        current_title = ["Unknown"]

        def progress_hook(d: dict) -> None:
            if self._cancel_flag.is_set():
                raise Exception("Download cancelled")

            if progress_callback is None:
                return

            status = DownloadStatus.DOWNLOADING
            if d["status"] == "finished":
                status = DownloadStatus.PROCESSING
            elif d["status"] == "error":
                status = DownloadStatus.FAILED

            progress = 0.0
            if "downloaded_bytes" in d and "total_bytes" in d:
                if d["total_bytes"] > 0:
                    progress = (d["downloaded_bytes"] / d["total_bytes"]) * 100
            elif "downloaded_bytes" in d and "total_bytes_estimate" in d:
                if d["total_bytes_estimate"] and d["total_bytes_estimate"] > 0:
                    progress = (d["downloaded_bytes"] / d["total_bytes_estimate"]) * 100

            speed = d.get("speed")
            speed_str = ""
            if speed:
                if speed > 1024 * 1024:
                    speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                elif speed > 1024:
                    speed_str = f"{speed / 1024:.1f} KB/s"
                else:
                    speed_str = f"{speed:.0f} B/s"

            eta = d.get("eta")
            eta_str = ""
            if eta:
                mins, secs = divmod(int(eta), 60)
                eta_str = f"{mins}:{secs:02d}"

            progress_callback(DownloadProgress(
                status=status,
                title=current_title[0],
                progress=progress,
                speed=speed_str,
                eta=eta_str,
                filename=d.get("filename", ""),
            ))

        opts["progress_hooks"] = [progress_hook]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Get title first
                info = ydl.extract_info(url, download=False)
                if info:
                    current_title[0] = info.get("title", "Unknown")

                if progress_callback:
                    progress_callback(DownloadProgress(
                        status=DownloadStatus.PENDING,
                        title=current_title[0],
                        progress=0.0,
                        speed="",
                        eta="",
                        filename="",
                    ))

                ydl.download([url])

                if progress_callback:
                    progress_callback(DownloadProgress(
                        status=DownloadStatus.COMPLETED,
                        title=current_title[0],
                        progress=100.0,
                        speed="",
                        eta="",
                        filename="",
                    ))

                return True

        except Exception as e:
            error_msg = str(e)
            if progress_callback:
                progress_callback(DownloadProgress(
                    status=DownloadStatus.FAILED,
                    title=current_title[0],
                    progress=0.0,
                    speed="",
                    eta="",
                    filename="",
                    error=error_msg,
                ))
            return False

    def cancel(self) -> None:
        """Cancel the current download."""
        self._cancel_flag.set()

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """
        Check if URL is a valid YouTube URL.

        Args:
            url: URL to validate.

        Returns:
            True if valid YouTube URL.
        """
        youtube_patterns = [
            r"^(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+",
            r"^(https?://)?(www\.)?youtube\.com/playlist\?list=[\w-]+",
            r"^(https?://)?(www\.)?youtu\.be/[\w-]+",
            r"^(https?://)?(music\.)?youtube\.com/watch\?v=[\w-]+",
        ]

        for pattern in youtube_patterns:
            if re.match(pattern, url):
                return True
        return False
