import tempfile
import unittest
from pathlib import Path

from src.database import SandSoundDatabase
from src.downloader import Downloader, PlaylistItem, VideoInfo


class DownloaderCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.base_path = Path(self._tempdir.name)
        self.db = SandSoundDatabase(
            db_path=str(self.base_path / "sandsound.db"),
            legacy_history_path=str(self.base_path / "download_history.json"),
        )
        self.download_dir = self.base_path / "downloads"
        self.downloader = Downloader(
            download_dir=str(self.download_dir),
            database=self.db,
        )

    def test_get_video_info_uses_cache_until_forced_refresh(self) -> None:
        url = "https://www.youtube.com/playlist?list=PL123"
        cached_payload = {
            "url": url,
            "title": "Cached Playlist",
            "duration": None,
            "thumbnail": None,
            "is_playlist": True,
            "playlist_count": 1,
            "uploader": "Cached Uploader",
            "playlist_id": "PL123",
            "entries": [
                {
                    "video_id": "cached-video",
                    "title": "Cached Song",
                    "duration": 100,
                    "thumbnail": None,
                    "url": "https://www.youtube.com/watch?v=cached-video",
                }
            ],
        }
        self.db.upsert_media_cache(
            url,
            cached_payload,
            fetched_at="2026-03-01T12:00:00Z",
        )

        fresh_info = VideoInfo(
            url=url,
            title="Fresh Playlist",
            duration=None,
            thumbnail=None,
            is_playlist=True,
            playlist_count=1,
            uploader="Fresh Uploader",
            playlist_id="PL123",
            entries=[
                PlaylistItem(
                    video_id="fresh-video",
                    title="Fresh Song",
                    duration=200,
                    thumbnail=None,
                    url="https://www.youtube.com/watch?v=fresh-video",
                )
            ],
        )

        calls: list[str] = []

        def fake_extract_info(target_url: str) -> VideoInfo:
            calls.append(target_url)
            return fresh_info

        self.downloader._extract_video_info = fake_extract_info  # type: ignore[attr-defined]

        cached_result = self.downloader.get_video_info(url)
        self.assertEqual(cached_result.title, "Cached Playlist")
        self.assertEqual(calls, [])
        self.assertFalse(self.downloader.is_cache_fresh(url, 60))

        refreshed_result = self.downloader.get_video_info(
            url,
            allow_cached=False,
            force_refresh=True,
        )
        self.assertEqual(refreshed_result.title, "Fresh Playlist")
        self.assertEqual(calls, [url])
        self.assertEqual(self.downloader.get_cached_video_info(url).title, "Fresh Playlist")
        self.assertTrue(self.downloader.is_cache_fresh(url, 60))


if __name__ == "__main__":
    unittest.main()
