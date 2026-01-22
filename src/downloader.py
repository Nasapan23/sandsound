"""
YouTube download service using yt-dlp.
Handles video/audio downloading with cookie authentication.
"""

import os
import re
import sys
import threading
from dataclasses import dataclass
from enum import Enum
from io import StringIO
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


class _QuietLogger:
    """Silent logger for yt-dlp to suppress console output."""
    
    def debug(self, msg: str) -> None:
        pass
    
    def info(self, msg: str) -> None:
        pass
    
    def warning(self, msg: str) -> None:
        pass
    
    def error(self, msg: str) -> None:
        pass


class _SuppressStderr:
    """Context manager to suppress stderr output from yt-dlp."""
    
    def __enter__(self):
        self._original_stderr = sys.stderr
        sys.stderr = StringIO()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr = self._original_stderr
        return False


class Downloader:
    """YouTube downloader service using yt-dlp."""

    # Format templates for yt-dlp with fallbacks
    AUDIO_FORMATS = {
        "mp3": "bestaudio/best",
        "m4a": "bestaudio[ext=m4a]/bestaudio/best",
        "opus": "bestaudio[ext=opus]/bestaudio/best",
        "flac": "bestaudio/best",
        "wav": "bestaudio/best",
    }

    VIDEO_FORMATS = {
        "mp4": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio/bestvideo+bestaudio/best[ext=mp4]/best",
        "webm": "bestvideo[ext=webm]+bestaudio[ext=webm]/bestvideo[ext=webm]+bestaudio/bestvideo+bestaudio/best[ext=webm]/best",
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

    def _sanitize_folder_name(self, name: str) -> str:
        """Sanitize a string to be a valid folder name."""
        # Remove or replace invalid characters for Windows/Unix
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, '_', name)
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip(' .')
        # Limit length to avoid path issues
        if len(sanitized) > 200:
            sanitized = sanitized[:200]
        # Ensure it's not empty
        if not sanitized:
            sanitized = "Playlist"
        return sanitized

    def _get_base_options(self, playlist_title: Optional[str] = None) -> dict:
        """Get base yt-dlp options."""
        # Build output template
        if playlist_title:
            # Create folder for playlist
            sanitized_title = self._sanitize_folder_name(playlist_title)
            playlist_folder = self._download_dir / sanitized_title
            try:
                playlist_folder.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                # If folder creation fails, fall back to base directory
                playlist_folder = self._download_dir
            # Convert to absolute path and use forward slashes for yt-dlp template
            # yt-dlp handles forward slashes on all platforms
            folder_str = str(playlist_folder.resolve())
            outtmpl = folder_str.replace("\\", "/") + "/%(title)s.%(ext)s"
        else:
            # Convert to absolute path and use forward slashes for yt-dlp template
            folder_str = str(self._download_dir.resolve())
            outtmpl = folder_str.replace("\\", "/") + "/%(title)s.%(ext)s"
        
        opts = {
            "outtmpl": outtmpl,
            "quiet": False,  # Enable to see errors
            "no_warnings": False,  # Enable to see warnings
            "noprogress": True,
            "ignoreerrors": False,  # We handle errors ourselves
            "extract_flat": False,
            "no_check_certificates": True,
            # Don't suppress logger - we need to see errors
            # "logger": _QuietLogger(),  # Commented out to see errors
            # Use more permissive format selection
            "format_sort": ["res", "ext:mp4:m4a:mp3:webm", "acodec:aac:mp3"],
        }

        if self._cookie_file and Path(self._cookie_file).is_file():
            opts["cookiefile"] = self._cookie_file

        if self._ffmpeg_location:
            opts["ffmpeg_location"] = self._ffmpeg_location

        return opts
    
    def _suppress_stderr(self):
        """Context manager to suppress stderr output."""
        return _SuppressStderr()

    def get_video_info(self, url: str) -> Optional[VideoInfo]:
        """
        Extract video or playlist information without downloading.

        Args:
            url: YouTube URL.

        Returns:
            VideoInfo object or None if extraction fails.
        """
        opts = self._get_base_options(playlist_title=None)
        opts["extract_flat"] = "in_playlist"

        try:
            with self._suppress_stderr():
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
        except Exception:
            return None

    def download(
        self,
        url: str,
        format_type: str = "mp3",
        quality: str = "best",
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        playlist_title: Optional[str] = None,
    ) -> bool:
        """
        Download video or playlist.

        Args:
            url: YouTube URL.
            format_type: Output format (mp3, mp4, etc.).
            quality: Quality setting.
            progress_callback: Callback for progress updates.
            playlist_title: Optional playlist title to create a folder for.

        Returns:
            True if download succeeded, False otherwise.
        """
        self._cancel_flag.clear()

        is_audio = format_type in self.AUDIO_FORMATS
        opts = self._get_base_options(playlist_title=playlist_title)

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
                # Try specific quality first, then fallback to lower qualities and finally best
                opts["format"] = (
                    f"bestvideo[height<={quality_val}]+bestaudio/"
                    f"bestvideo[height<={quality_val}]/"
                    f"best[height<={quality_val}]/"
                    f"bestvideo+bestaudio/best"
                )
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
            # Don't suppress stderr - we need to see errors for debugging
            # with self._suppress_stderr():
            print(f"[DEBUG] Starting download: {url}")
            print(f"[DEBUG] Output template: {opts['outtmpl']}")
            print(f"[DEBUG] Format: {opts.get('format', 'default')}")
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Get title first
                print(f"[DEBUG] Extracting info for: {url}")
                info = ydl.extract_info(url, download=False)
                if info:
                    current_title[0] = info.get("title", "Unknown")
                    print(f"[DEBUG] Video title: {current_title[0]}")

                if progress_callback:
                    progress_callback(DownloadProgress(
                        status=DownloadStatus.PENDING,
                        title=current_title[0],
                        progress=0.0,
                        speed="",
                        eta="",
                        filename="",
                    ))

                print(f"[DEBUG] Starting download...")
                ydl.download([url])
                print(f"[DEBUG] Download completed successfully")

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
            error_type = type(e).__name__
            
            # Print full error to console for debugging
            print(f"[ERROR] Download failed!")
            print(f"[ERROR] Type: {error_type}")
            print(f"[ERROR] Message: {error_msg}")
            import traceback
            print(f"[ERROR] Traceback:")
            traceback.print_exc()
            
            # Log the actual error for debugging (but don't show to user unless needed)
            full_error = f"{error_type}: {error_msg}"
            
            # If format error, try with a simpler fallback format
            if "Requested format is not available" in error_msg or "format is not available" in error_msg.lower():
                try:
                    # Retry with most basic format that should always work
                    fallback_opts = self._get_base_options(playlist_title=playlist_title)
                    if is_audio:
                        # Try "best" which works for any video
                        fallback_opts["format"] = "best"
                        fallback_opts["postprocessors"] = [{
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": format_type,
                            "preferredquality": self.AUDIO_QUALITY_MAP.get(quality, "0"),
                        }]
                    else:
                        fallback_opts["format"] = "best"
                        if format_type in ["mp4", "mkv"]:
                            fallback_opts["merge_output_format"] = format_type
                    
                    fallback_opts["progress_hooks"] = [progress_hook]
                    
                    print(f"[DEBUG] Retrying with fallback format...")
                    # Don't suppress stderr for fallback either
                    with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                        ydl.download([url])
                        print(f"[DEBUG] Fallback download completed successfully")
                    
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
                except Exception as fallback_error:
                    error_msg = f"Video unavailable or requires authentication: {str(fallback_error)}"
            
            # Provide more user-friendly error messages
            if "HTTP Error" in error_msg or "403" in error_msg or "401" in error_msg:
                error_msg = "Video is private or requires authentication. Try adding a cookie file in Settings."
            elif "Video unavailable" in error_msg or "Private video" in error_msg:
                error_msg = "Video is unavailable or private."
            elif "Unsupported URL" in error_msg:
                error_msg = "Unsupported URL format."
            elif not error_msg or len(error_msg) < 10:
                error_msg = f"Download failed: {error_type}"
            
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
