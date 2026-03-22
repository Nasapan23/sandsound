"""
Download history management for SandSound.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Set

from .database import SandSoundDatabase


@dataclass
class DownloadedVideo:
    """Record of a downloaded video."""

    video_id: str
    title: str
    downloaded_at: str
    format: str
    quality: str


@dataclass
class PlaylistRecord:
    """Record of a downloaded playlist."""

    playlist_id: str
    playlist_url: str
    title: str
    last_downloaded: str
    videos: Dict[str, DownloadedVideo] = field(default_factory=dict)
    video_count: int = 0

    def to_dict(self) -> dict:
        """Convert to a dictionary compatible with legacy JSON history."""
        return {
            "playlist_id": self.playlist_id,
            "playlist_url": self.playlist_url,
            "title": self.title,
            "last_downloaded": self.last_downloaded,
            "videos": {video_id: asdict(video) for video_id, video in self.videos.items()},
            "video_count": self.video_count or len(self.videos),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "PlaylistRecord":
        """Create a playlist record from a serialized payload."""
        videos = {
            video_id: DownloadedVideo(**video_data)
            for video_id, video_data in payload.get("videos", {}).items()
        }
        return cls(
            playlist_id=payload["playlist_id"],
            playlist_url=payload.get("playlist_url", ""),
            title=payload.get("title", "Unknown Playlist"),
            last_downloaded=payload.get("last_downloaded", ""),
            videos=videos,
            video_count=payload.get("video_count", len(videos)),
        )


class DownloadHistory:
    """
    SQLite-backed download history facade.
    """

    def __init__(
        self,
        database: Optional[SandSoundDatabase] = None,
        db_path: Optional[str] = None,
        legacy_history_path: Optional[str] = None,
    ) -> None:
        self._database = database or SandSoundDatabase(
            db_path=db_path,
            legacy_history_path=legacy_history_path,
        )

    @property
    def db_path(self) -> str:
        """Return the backing SQLite database path."""
        return str(self._database.db_path)

    def add_video_download(
        self,
        video_id: str,
        title: str,
        format_type: str,
        quality: str,
        playlist_id: Optional[str] = None,
        playlist_url: Optional[str] = None,
        playlist_title: Optional[str] = None,
    ) -> None:
        """Record a video download."""
        self._database.add_video_download(
            video_id=video_id,
            title=title,
            format_type=format_type,
            quality=quality,
            playlist_id=playlist_id,
            playlist_url=playlist_url,
            playlist_title=playlist_title,
        )

    def get_downloaded_video_ids(self, playlist_id: str) -> Set[str]:
        """Get all downloaded video IDs for a playlist."""
        return self._database.get_downloaded_video_ids(playlist_id)

    def get_new_videos(
        self,
        playlist_id: str,
        current_video_ids: List[str],
    ) -> List[str]:
        """Return the subset of current playlist items not yet downloaded."""
        downloaded_ids = self.get_downloaded_video_ids(playlist_id)
        return [video_id for video_id in current_video_ids if video_id not in downloaded_ids]

    def is_video_downloaded(
        self,
        video_id: str,
        playlist_id: Optional[str] = None,
    ) -> bool:
        """Check whether a video has been downloaded."""
        return self._database.is_video_downloaded(video_id, playlist_id=playlist_id)

    def get_playlist_record(
        self,
        playlist_id: str,
        include_videos: bool = False,
    ) -> Optional[PlaylistRecord]:
        """Get a playlist record if it exists."""
        summary = self._database.get_playlist_summary(playlist_id)
        if not summary:
            return None

        videos: Dict[str, DownloadedVideo] = {}
        if include_videos:
            videos = self._build_downloaded_videos(
                self._database.get_playlist_downloads(playlist_id)
            )

        return PlaylistRecord(
            playlist_id=summary["playlist_id"],
            playlist_url=summary["playlist_url"],
            title=summary["title"],
            last_downloaded=summary["last_downloaded"],
            videos=videos,
            video_count=summary["video_count"],
        )

    def clear_playlist(self, playlist_id: str) -> None:
        """Remove a playlist from history."""
        self._database.clear_playlist(playlist_id)

    def clear_all(self) -> None:
        """Clear all stored download history."""
        self._database.clear_all_history()

    def get_all_playlists(self) -> List[PlaylistRecord]:
        """Return all playlist summaries, newest first."""
        return [
            PlaylistRecord(
                playlist_id=summary["playlist_id"],
                playlist_url=summary["playlist_url"],
                title=summary["title"],
                last_downloaded=summary["last_downloaded"],
                video_count=summary["video_count"],
            )
            for summary in self._database.get_playlist_summaries()
        ]

    def check_for_new_videos(
        self,
        playlist_id: str,
        current_video_ids: List[str],
    ) -> tuple[List[str], int]:
        """Return new video IDs and a count for a playlist."""
        new_videos = self.get_new_videos(playlist_id, current_video_ids)
        return new_videos, len(new_videos)

    @staticmethod
    def _build_downloaded_videos(
        payload: dict[str, dict],
    ) -> Dict[str, DownloadedVideo]:
        """Convert raw rows into DownloadedVideo objects."""
        return {
            video_id: DownloadedVideo(**video_data)
            for video_id, video_data in payload.items()
        }

