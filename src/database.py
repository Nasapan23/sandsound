"""
SQLite persistence and metadata cache for SandSound.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


DEFAULT_APP_DIRNAME = ".sandsound"
DEFAULT_DB_FILENAME = "sandsound.db"
DEFAULT_HISTORY_FILENAME = "download_history.json"
SCHEMA_VERSION = 1
TRACKING_QUERY_PARAMS = {
    "app",
    "feature",
    "index",
    "pp",
    "si",
    "start",
    "t",
}


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def parse_timestamp(value: str) -> datetime:
    """Parse ISO timestamps stored by the app."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def is_timestamp_fresh(value: str, max_age_seconds: int) -> bool:
    """Check whether a cached timestamp is still fresh."""
    if max_age_seconds <= 0:
        return False
    try:
        timestamp = parse_timestamp(value)
    except ValueError:
        return False
    return datetime.utcnow() - timestamp <= timedelta(seconds=max_age_seconds)


def normalize_media_url(url: str) -> str:
    """Normalize URLs so equivalent links resolve to the same cache entry."""
    raw_url = url.strip()
    parsed = urlparse(raw_url)

    scheme = parsed.scheme or "https"
    netloc = (parsed.netloc or "www.youtube.com").lower()
    if netloc.startswith("m."):
        netloc = netloc[2:]
    if netloc == "music.youtube.com":
        netloc = "www.youtube.com"

    path = parsed.path.rstrip("/") or "/"
    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        if key in TRACKING_QUERY_PARAMS:
            continue
        query_pairs.append((key, value))

    normalized_query = urlencode(sorted(query_pairs))
    return urlunparse((scheme, netloc, path, "", normalized_query, ""))


def extract_video_id(url: str) -> Optional[str]:
    """Extract a YouTube video ID when present."""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path.strip("/")
    query = dict(parse_qsl(parsed.query, keep_blank_values=False))

    if netloc.endswith("youtu.be") and path:
        return path.split("/", 1)[0]
    if path == "watch":
        return query.get("v")
    if path.startswith("shorts/"):
        return path.split("/", 1)[1]
    if path.startswith("embed/"):
        return path.split("/", 1)[1]
    return None


def canonicalize_media_identifier(
    url: str,
    *,
    is_playlist: bool = False,
    playlist_id: Optional[str] = None,
) -> tuple[str, str]:
    """
    Build a stable cache key and normalized URL for a media URL.
    """
    normalized_url = normalize_media_url(url)
    parsed = urlparse(normalized_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=False))

    if is_playlist and playlist_id:
        return f"playlist:{playlist_id}", normalized_url

    list_id = query.get("list")
    path = parsed.path.strip("/")
    if list_id and (path == "playlist" or not query.get("v")):
        return f"playlist:{list_id}", normalized_url

    video_id = extract_video_id(normalized_url)
    if video_id:
        return f"video:{video_id}", normalized_url

    return f"url:{normalized_url}", normalized_url


class SandSoundDatabase:
    """SQLite-backed persistence for download history and metadata cache."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        legacy_history_path: Optional[str] = None,
    ) -> None:
        if db_path:
            self._db_path = Path(db_path)
        else:
            app_dir = Path.home() / DEFAULT_APP_DIRNAME
            app_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = app_dir / DEFAULT_DB_FILENAME

        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        if legacy_history_path:
            self._legacy_history_path = Path(legacy_history_path)
        else:
            self._legacy_history_path = self._db_path.parent / DEFAULT_HISTORY_FILENAME

        self._bootstrap()

    @property
    def db_path(self) -> Path:
        """Return the SQLite database path."""
        return self._db_path

    @property
    def legacy_history_path(self) -> Path:
        """Return the legacy JSON history path."""
        return self._legacy_history_path

    def connect(self) -> sqlite3.Connection:
        """Create a configured SQLite connection."""
        connection = sqlite3.connect(self._db_path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _bootstrap(self) -> None:
        """Initialize schema and migrate any legacy history."""
        with self.connect() as connection:
            self._create_schema(connection)
            current_version = int(
                connection.execute("PRAGMA user_version").fetchone()[0]
            )
            if current_version < SCHEMA_VERSION:
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

            if self._should_migrate_legacy_history(connection):
                self._migrate_legacy_history(connection)

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        """Create the SQLite schema if it does not already exist."""
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS playlists (
                playlist_id TEXT PRIMARY KEY,
                playlist_url TEXT NOT NULL,
                title TEXT NOT NULL,
                last_downloaded TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS playlist_downloads (
                playlist_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT NOT NULL,
                downloaded_at TEXT NOT NULL,
                format TEXT NOT NULL,
                quality TEXT NOT NULL,
                PRIMARY KEY (playlist_id, video_id),
                FOREIGN KEY (playlist_id) REFERENCES playlists (playlist_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS single_video_downloads (
                video_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                downloaded_at TEXT NOT NULL,
                format TEXT NOT NULL,
                quality TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS media_cache (
                cache_key TEXT PRIMARY KEY,
                canonical_url TEXT NOT NULL,
                original_url TEXT NOT NULL,
                video_id TEXT,
                playlist_id TEXT,
                title TEXT NOT NULL,
                duration INTEGER,
                thumbnail TEXT,
                is_playlist INTEGER NOT NULL,
                playlist_count INTEGER NOT NULL,
                uploader TEXT,
                fetched_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS playlist_cache_entries (
                cache_key TEXT NOT NULL,
                entry_index INTEGER NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT NOT NULL,
                duration INTEGER,
                thumbnail TEXT,
                url TEXT,
                PRIMARY KEY (cache_key, entry_index),
                FOREIGN KEY (cache_key) REFERENCES media_cache (cache_key) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_playlist_downloads_playlist
                ON playlist_downloads (playlist_id);
            CREATE INDEX IF NOT EXISTS idx_playlists_last_downloaded
                ON playlists (last_downloaded DESC);
            CREATE INDEX IF NOT EXISTS idx_media_cache_canonical_url
                ON media_cache (canonical_url);
            CREATE INDEX IF NOT EXISTS idx_media_cache_playlist_id
                ON media_cache (playlist_id);
            """
        )

    def _should_migrate_legacy_history(self, connection: sqlite3.Connection) -> bool:
        """Determine whether legacy JSON history should be imported."""
        if not self._legacy_history_path.exists():
            return False

        playlist_count = int(
            connection.execute("SELECT COUNT(*) FROM playlists").fetchone()[0]
        )
        single_count = int(
            connection.execute("SELECT COUNT(*) FROM single_video_downloads").fetchone()[0]
        )
        return playlist_count == 0 and single_count == 0

    def _migrate_legacy_history(self, connection: sqlite3.Connection) -> None:
        """Import legacy JSON history into SQLite and preserve a backup."""
        try:
            with open(self._legacy_history_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Failed to migrate history: {exc}")
            return

        try:
            with connection:
                for playlist_id, playlist_data in payload.get("playlists", {}).items():
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO playlists (
                            playlist_id,
                            playlist_url,
                            title,
                            last_downloaded
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            playlist_id,
                            playlist_data.get("playlist_url", ""),
                            playlist_data.get("title", "Unknown Playlist"),
                            playlist_data.get("last_downloaded", utcnow_iso()),
                        ),
                    )

                    for video_id, video_data in playlist_data.get("videos", {}).items():
                        connection.execute(
                            """
                            INSERT OR REPLACE INTO playlist_downloads (
                                playlist_id,
                                video_id,
                                title,
                                downloaded_at,
                                format,
                                quality
                            ) VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                playlist_id,
                                video_id,
                                video_data.get("title", "Unknown"),
                                video_data.get("downloaded_at", utcnow_iso()),
                                video_data.get("format", "mp3"),
                                video_data.get("quality", "best"),
                            ),
                        )

                for video_id, video_data in payload.get("single_videos", {}).items():
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO single_video_downloads (
                            video_id,
                            title,
                            downloaded_at,
                            format,
                            quality
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            video_id,
                            video_data.get("title", "Unknown"),
                            video_data.get("downloaded_at", utcnow_iso()),
                            video_data.get("format", "mp3"),
                            video_data.get("quality", "best"),
                        ),
                    )
        except sqlite3.DatabaseError as exc:
            print(f"Failed to migrate history: {exc}")
            return

        backup_path = Path(str(self._legacy_history_path) + ".bak")
        try:
            self._legacy_history_path.replace(backup_path)
        except OSError as exc:
            print(f"Failed to preserve history backup: {exc}")

    def add_video_download(
        self,
        *,
        video_id: str,
        title: str,
        format_type: str,
        quality: str,
        playlist_id: Optional[str] = None,
        playlist_url: Optional[str] = None,
        playlist_title: Optional[str] = None,
    ) -> None:
        """Persist a single downloaded video."""
        timestamp = utcnow_iso()
        with self.connect() as connection, connection:
            if playlist_id:
                connection.execute(
                    """
                    INSERT INTO playlists (
                        playlist_id,
                        playlist_url,
                        title,
                        last_downloaded
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(playlist_id) DO UPDATE SET
                        playlist_url = excluded.playlist_url,
                        title = excluded.title,
                        last_downloaded = excluded.last_downloaded
                    """,
                    (
                        playlist_id,
                        playlist_url or "",
                        playlist_title or "Unknown Playlist",
                        timestamp,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO playlist_downloads (
                        playlist_id,
                        video_id,
                        title,
                        downloaded_at,
                        format,
                        quality
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(playlist_id, video_id) DO UPDATE SET
                        title = excluded.title,
                        downloaded_at = excluded.downloaded_at,
                        format = excluded.format,
                        quality = excluded.quality
                    """,
                    (
                        playlist_id,
                        video_id,
                        title,
                        timestamp,
                        format_type,
                        quality,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO single_video_downloads (
                        video_id,
                        title,
                        downloaded_at,
                        format,
                        quality
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(video_id) DO UPDATE SET
                        title = excluded.title,
                        downloaded_at = excluded.downloaded_at,
                        format = excluded.format,
                        quality = excluded.quality
                    """,
                    (video_id, title, timestamp, format_type, quality),
                )

    def get_downloaded_video_ids(self, playlist_id: str) -> set[str]:
        """Return all downloaded video IDs for a playlist."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT video_id
                FROM playlist_downloads
                WHERE playlist_id = ?
                """,
                (playlist_id,),
            ).fetchall()
        return {row["video_id"] for row in rows}

    def is_video_downloaded(
        self,
        video_id: str,
        playlist_id: Optional[str] = None,
    ) -> bool:
        """Return whether a video has already been downloaded."""
        query = """
            SELECT 1
            FROM playlist_downloads
            WHERE playlist_id = ? AND video_id = ?
            LIMIT 1
        """
        params: tuple[Any, ...]
        if playlist_id:
            params = (playlist_id, video_id)
        else:
            query = """
                SELECT 1
                FROM single_video_downloads
                WHERE video_id = ?
                LIMIT 1
            """
            params = (video_id,)

        with self.connect() as connection:
            return connection.execute(query, params).fetchone() is not None

    def get_playlist_summaries(self) -> list[dict[str, Any]]:
        """Return playlist summaries ordered by most recent download."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    playlists.playlist_id,
                    playlists.playlist_url,
                    playlists.title,
                    playlists.last_downloaded,
                    COUNT(playlist_downloads.video_id) AS video_count
                FROM playlists
                LEFT JOIN playlist_downloads
                    ON playlist_downloads.playlist_id = playlists.playlist_id
                GROUP BY
                    playlists.playlist_id,
                    playlists.playlist_url,
                    playlists.title,
                    playlists.last_downloaded
                ORDER BY playlists.last_downloaded DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_playlist_summary(self, playlist_id: str) -> Optional[dict[str, Any]]:
        """Return a single playlist summary."""
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    playlists.playlist_id,
                    playlists.playlist_url,
                    playlists.title,
                    playlists.last_downloaded,
                    COUNT(playlist_downloads.video_id) AS video_count
                FROM playlists
                LEFT JOIN playlist_downloads
                    ON playlist_downloads.playlist_id = playlists.playlist_id
                WHERE playlists.playlist_id = ?
                GROUP BY
                    playlists.playlist_id,
                    playlists.playlist_url,
                    playlists.title,
                    playlists.last_downloaded
                """,
                (playlist_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_playlist_downloads(self, playlist_id: str) -> dict[str, dict[str, Any]]:
        """Return all stored downloads for a playlist."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    video_id,
                    title,
                    downloaded_at,
                    format,
                    quality
                FROM playlist_downloads
                WHERE playlist_id = ?
                ORDER BY downloaded_at DESC, video_id ASC
                """,
                (playlist_id,),
            ).fetchall()

        return {
            row["video_id"]: {
                "video_id": row["video_id"],
                "title": row["title"],
                "downloaded_at": row["downloaded_at"],
                "format": row["format"],
                "quality": row["quality"],
            }
            for row in rows
        }

    def clear_playlist(self, playlist_id: str) -> None:
        """Delete a playlist and all of its download history."""
        with self.connect() as connection, connection:
            connection.execute(
                "DELETE FROM playlists WHERE playlist_id = ?",
                (playlist_id,),
            )

    def clear_all_history(self) -> None:
        """Delete all persisted history without touching the cache."""
        with self.connect() as connection, connection:
            connection.execute("DELETE FROM playlist_downloads")
            connection.execute("DELETE FROM playlists")
            connection.execute("DELETE FROM single_video_downloads")

    def get_cached_media(self, url: str) -> Optional[dict[str, Any]]:
        """Return cached metadata for a URL if present."""
        cache_key, normalized_url = canonicalize_media_identifier(url)
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    cache_key,
                    canonical_url,
                    fetched_at,
                    payload_json
                FROM media_cache
                WHERE cache_key = ? OR canonical_url = ?
                ORDER BY
                    CASE WHEN cache_key = ? THEN 0 ELSE 1 END,
                    fetched_at DESC
                LIMIT 1
                """,
                (cache_key, normalized_url, cache_key),
            ).fetchone()

        if not row:
            return None

        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            return None

        return {
            "cache_key": row["cache_key"],
            "canonical_url": row["canonical_url"],
            "fetched_at": row["fetched_at"],
            "payload": payload,
        }

    def upsert_media_cache(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        fetched_at: Optional[str] = None,
    ) -> None:
        """Insert or update cached metadata for a URL."""
        timestamp = fetched_at or utcnow_iso()
        cache_key, normalized_url = canonicalize_media_identifier(
            url,
            is_playlist=bool(payload.get("is_playlist")),
            playlist_id=payload.get("playlist_id"),
        )
        entries = payload.get("entries") or []

        with self.connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO media_cache (
                    cache_key,
                    canonical_url,
                    original_url,
                    video_id,
                    playlist_id,
                    title,
                    duration,
                    thumbnail,
                    is_playlist,
                    playlist_count,
                    uploader,
                    fetched_at,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    canonical_url = excluded.canonical_url,
                    original_url = excluded.original_url,
                    video_id = excluded.video_id,
                    playlist_id = excluded.playlist_id,
                    title = excluded.title,
                    duration = excluded.duration,
                    thumbnail = excluded.thumbnail,
                    is_playlist = excluded.is_playlist,
                    playlist_count = excluded.playlist_count,
                    uploader = excluded.uploader,
                    fetched_at = excluded.fetched_at,
                    payload_json = excluded.payload_json
                """,
                (
                    cache_key,
                    normalized_url,
                    url,
                    extract_video_id(url),
                    payload.get("playlist_id"),
                    payload.get("title", "Unknown"),
                    payload.get("duration"),
                    payload.get("thumbnail"),
                    1 if payload.get("is_playlist") else 0,
                    payload.get("playlist_count", 1),
                    payload.get("uploader"),
                    timestamp,
                    json.dumps(payload, separators=(",", ":"), sort_keys=True),
                ),
            )

            connection.execute(
                "DELETE FROM playlist_cache_entries WHERE cache_key = ?",
                (cache_key,),
            )
            for index, entry in enumerate(entries):
                connection.execute(
                    """
                    INSERT INTO playlist_cache_entries (
                        cache_key,
                        entry_index,
                        video_id,
                        title,
                        duration,
                        thumbnail,
                        url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cache_key,
                        index,
                        entry.get("video_id", ""),
                        entry.get("title", "Unknown"),
                        entry.get("duration"),
                        entry.get("thumbnail"),
                        entry.get("url"),
                    ),
                )
