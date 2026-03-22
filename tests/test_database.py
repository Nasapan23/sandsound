import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.database import SandSoundDatabase, canonicalize_media_identifier
from src.history import DownloadHistory


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.base_path = Path(self._tempdir.name)
        self.db_path = self.base_path / "sandsound.db"
        self.legacy_history_path = self.base_path / "download_history.json"

    def _make_database(self) -> SandSoundDatabase:
        return SandSoundDatabase(
            db_path=str(self.db_path),
            legacy_history_path=str(self.legacy_history_path),
        )

    def _make_history(self) -> DownloadHistory:
        return DownloadHistory(
            db_path=str(self.db_path),
            legacy_history_path=str(self.legacy_history_path),
        )

    def test_bootstrap_creates_schema(self) -> None:
        database = self._make_database()

        self.assertTrue(database.db_path.exists())

        with sqlite3.connect(database.db_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertGreaterEqual(user_version, 1)
        self.assertTrue(
            {
                "playlists",
                "playlist_downloads",
                "single_video_downloads",
                "media_cache",
                "playlist_cache_entries",
            }.issubset(tables)
        )

    def test_migrates_legacy_json_and_preserves_backup(self) -> None:
        self.legacy_history_path.write_text(
            json.dumps(
                {
                    "playlists": {
                        "playlist-1": {
                            "playlist_id": "playlist-1",
                            "playlist_url": "https://www.youtube.com/playlist?list=playlist-1",
                            "title": "Migrated Playlist",
                            "last_downloaded": "2026-03-22T10:00:00",
                            "videos": {
                                "video-1": {
                                    "video_id": "video-1",
                                    "title": "Song 1",
                                    "downloaded_at": "2026-03-22T10:00:00",
                                    "format": "mp3",
                                    "quality": "best",
                                }
                            },
                        }
                    },
                    "single_videos": {
                        "single-1": {
                            "video_id": "single-1",
                            "title": "Single Song",
                            "downloaded_at": "2026-03-21T08:00:00",
                            "format": "m4a",
                            "quality": "192",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        history = self._make_history()
        playlist = history.get_playlist_record("playlist-1", include_videos=True)

        self.assertIsNotNone(playlist)
        self.assertEqual(playlist.title, "Migrated Playlist")
        self.assertEqual(playlist.video_count, 1)
        self.assertTrue(history.is_video_downloaded("single-1"))
        self.assertFalse(self.legacy_history_path.exists())
        self.assertTrue((self.base_path / "download_history.json.bak").exists())

    def test_playlist_order_counts_and_clear_behavior(self) -> None:
        history = self._make_history()
        history.add_video_download(
            video_id="video-a",
            title="Song A",
            format_type="mp3",
            quality="best",
            playlist_id="playlist-a",
            playlist_url="https://www.youtube.com/playlist?list=playlist-a",
            playlist_title="Playlist A",
        )
        history.add_video_download(
            video_id="video-b",
            title="Song B",
            format_type="mp3",
            quality="best",
            playlist_id="playlist-a",
            playlist_url="https://www.youtube.com/playlist?list=playlist-a",
            playlist_title="Playlist A",
        )
        history.add_video_download(
            video_id="video-c",
            title="Song C",
            format_type="mp3",
            quality="best",
            playlist_id="playlist-b",
            playlist_url="https://www.youtube.com/playlist?list=playlist-b",
            playlist_title="Playlist B",
        )
        history.add_video_download(
            video_id="single-video",
            title="Standalone",
            format_type="m4a",
            quality="192",
        )

        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "UPDATE playlists SET last_downloaded = ? WHERE playlist_id = ?",
                ("2026-03-20T10:00:00Z", "playlist-a"),
            )
            connection.execute(
                "UPDATE playlists SET last_downloaded = ? WHERE playlist_id = ?",
                ("2026-03-21T10:00:00Z", "playlist-b"),
            )
            connection.commit()

        playlists = history.get_all_playlists()
        self.assertEqual([playlist.playlist_id for playlist in playlists], ["playlist-b", "playlist-a"])
        self.assertEqual(playlists[0].video_count, 1)
        self.assertEqual(playlists[1].video_count, 2)
        self.assertEqual(
            history.get_downloaded_video_ids("playlist-a"),
            {"video-a", "video-b"},
        )
        self.assertTrue(history.is_video_downloaded("single-video"))

        history.clear_playlist("playlist-a")
        self.assertIsNone(history.get_playlist_record("playlist-a"))
        self.assertEqual(history.get_downloaded_video_ids("playlist-a"), set())

        history.clear_all()
        self.assertEqual(history.get_all_playlists(), [])
        self.assertFalse(history.is_video_downloaded("single-video"))

    def test_media_cache_round_trip_and_playlist_entries(self) -> None:
        database = self._make_database()
        url = "https://www.youtube.com/playlist?list=PL123"
        payload = {
            "url": url,
            "title": "Cached Playlist",
            "duration": None,
            "thumbnail": "https://img.example/1.jpg",
            "is_playlist": True,
            "playlist_count": 2,
            "uploader": "Uploader",
            "playlist_id": "PL123",
            "entries": [
                {
                    "video_id": "video-1",
                    "title": "Song 1",
                    "duration": 120,
                    "thumbnail": None,
                    "url": "https://www.youtube.com/watch?v=video-1",
                },
                {
                    "video_id": "video-2",
                    "title": "Song 2",
                    "duration": 180,
                    "thumbnail": None,
                    "url": "https://www.youtube.com/watch?v=video-2",
                },
            ],
        }

        database.upsert_media_cache(
            url,
            payload,
            fetched_at="2026-03-22T12:00:00Z",
        )
        cached = database.get_cached_media(url)

        self.assertIsNotNone(cached)
        self.assertEqual(cached["payload"]["title"], "Cached Playlist")
        self.assertEqual(len(cached["payload"]["entries"]), 2)

        with sqlite3.connect(self.db_path) as connection:
            entry_count = connection.execute(
                "SELECT COUNT(*) FROM playlist_cache_entries"
            ).fetchone()[0]

        self.assertEqual(entry_count, 2)

    def test_canonical_key_handles_equivalent_video_urls(self) -> None:
        watch_key, _ = canonicalize_media_identifier(
            "https://www.youtube.com/watch?v=abc123&feature=share"
        )
        short_key, _ = canonicalize_media_identifier(
            "https://youtu.be/abc123?t=30"
        )

        self.assertEqual(watch_key, "video:abc123")
        self.assertEqual(short_key, "video:abc123")


if __name__ == "__main__":
    unittest.main()
