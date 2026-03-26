"""
Helpers for formatting playlist bar text.
"""

from __future__ import annotations

from typing import Optional

from ..downloader import VideoInfo


PLAYLIST_BAR_TITLE_MAX_LENGTH = 52


def truncate_text(text: str, max_length: int) -> str:
    """Clamp text to a single readable line."""
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    if max_length <= 3:
        return normalized[:max_length]
    return normalized[: max_length - 3].rstrip() + "..."


def build_playlist_bar_text(info: VideoInfo, new_count: Optional[int] = None) -> str:
    """Build playlist status text without letting long titles hide the action button."""
    title = truncate_text(info.title or "Playlist", PLAYLIST_BAR_TITLE_MAX_LENGTH)
    if info.playlist_id and info.entries:
        total = len(info.entries)
        if new_count is None:
            new_count = total

        if new_count == total:
            return f"Playlist: {title} ({total} videos)"
        return f"Playlist: {title} ({new_count} new / {total} total)"

    return f"Playlist: {title}"
