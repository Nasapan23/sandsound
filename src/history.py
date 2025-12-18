"""
Download history management for SandSound.
Tracks downloaded videos to enable smart re-downloading of playlists.
"""

import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set


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
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "playlist_id": self.playlist_id,
            "playlist_url": self.playlist_url,
            "title": self.title,
            "last_downloaded": self.last_downloaded,
            "videos": {vid: asdict(v) for vid, v in self.videos.items()}
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PlaylistRecord":
        """Create from dictionary."""
        videos = {}
        for vid, v_data in data.get("videos", {}).items():
            videos[vid] = DownloadedVideo(**v_data)
        return cls(
            playlist_id=data["playlist_id"],
            playlist_url=data["playlist_url"],
            title=data["title"],
            last_downloaded=data["last_downloaded"],
            videos=videos
        )


class DownloadHistory:
    """
    Manages download history with JSON persistence.
    Tracks which videos have been downloaded from which playlists
    to enable smart re-downloading.
    """
    
    def __init__(self, history_path: Optional[str] = None) -> None:
        """
        Initialize history manager.
        
        Args:
            history_path: Path to history file. Defaults to ~/.sandsound/download_history.json
        """
        if history_path:
            self._history_path = Path(history_path)
        else:
            history_dir = Path.home() / ".sandsound"
            history_dir.mkdir(parents=True, exist_ok=True)
            self._history_path = history_dir / "download_history.json"
        
        self._playlists: Dict[str, PlaylistRecord] = {}
        self._single_videos: Dict[str, DownloadedVideo] = {}
        self._load()
    
    def _load(self) -> None:
        """Load history from file."""
        if self._history_path.exists():
            try:
                with open(self._history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Load playlists
                for pid, p_data in data.get("playlists", {}).items():
                    self._playlists[pid] = PlaylistRecord.from_dict(p_data)
                
                # Load single videos
                for vid, v_data in data.get("single_videos", {}).items():
                    self._single_videos[vid] = DownloadedVideo(**v_data)
                    
            except (json.JSONDecodeError, IOError, KeyError) as e:
                print(f"Failed to load history: {e}")
                self._playlists = {}
                self._single_videos = {}
    
    def _save(self) -> None:
        """Persist history to file."""
        try:
            data = {
                "playlists": {pid: p.to_dict() for pid, p in self._playlists.items()},
                "single_videos": {vid: asdict(v) for vid, v in self._single_videos.items()}
            }
            with open(self._history_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Failed to save history: {e}")
    
    def add_video_download(
        self,
        video_id: str,
        title: str,
        format_type: str,
        quality: str,
        playlist_id: Optional[str] = None,
        playlist_url: Optional[str] = None,
        playlist_title: Optional[str] = None
    ) -> None:
        """
        Record a video download.
        
        Args:
            video_id: YouTube video ID
            title: Video title
            format_type: Download format (mp3, mp4, etc.)
            quality: Quality setting
            playlist_id: Optional playlist ID if part of playlist
            playlist_url: Optional playlist URL
            playlist_title: Optional playlist title
        """
        now = datetime.now().isoformat()
        video = DownloadedVideo(
            video_id=video_id,
            title=title,
            downloaded_at=now,
            format=format_type,
            quality=quality
        )
        
        if playlist_id:
            # Add to playlist record
            if playlist_id not in self._playlists:
                self._playlists[playlist_id] = PlaylistRecord(
                    playlist_id=playlist_id,
                    playlist_url=playlist_url or "",
                    title=playlist_title or "Unknown Playlist",
                    last_downloaded=now,
                    videos={}
                )
            self._playlists[playlist_id].videos[video_id] = video
            self._playlists[playlist_id].last_downloaded = now
        else:
            # Single video download
            self._single_videos[video_id] = video
        
        self._save()
    
    def get_downloaded_video_ids(self, playlist_id: str) -> Set[str]:
        """
        Get set of video IDs already downloaded from a playlist.
        
        Args:
            playlist_id: Playlist ID
            
        Returns:
            Set of video IDs that have been downloaded
        """
        if playlist_id in self._playlists:
            return set(self._playlists[playlist_id].videos.keys())
        return set()
    
    def get_new_videos(
        self,
        playlist_id: str,
        current_video_ids: List[str]
    ) -> List[str]:
        """
        Get list of video IDs that haven't been downloaded yet.
        
        Args:
            playlist_id: Playlist ID
            current_video_ids: List of current video IDs in playlist
            
        Returns:
            List of video IDs not yet downloaded
        """
        downloaded = self.get_downloaded_video_ids(playlist_id)
        return [vid for vid in current_video_ids if vid not in downloaded]
    
    def is_video_downloaded(
        self,
        video_id: str,
        playlist_id: Optional[str] = None
    ) -> bool:
        """
        Check if a video has been downloaded.
        
        Args:
            video_id: Video ID to check
            playlist_id: Optional playlist context
            
        Returns:
            True if video was previously downloaded
        """
        if playlist_id and playlist_id in self._playlists:
            return video_id in self._playlists[playlist_id].videos
        return video_id in self._single_videos
    
    def get_playlist_record(self, playlist_id: str) -> Optional[PlaylistRecord]:
        """Get the record for a playlist if it exists."""
        return self._playlists.get(playlist_id)
    
    def clear_playlist(self, playlist_id: str) -> None:
        """Remove a playlist from history."""
        if playlist_id in self._playlists:
            del self._playlists[playlist_id]
            self._save()
    
    def clear_all(self) -> None:
        """Clear all history."""
        self._playlists = {}
        self._single_videos = {}
        self._save()
