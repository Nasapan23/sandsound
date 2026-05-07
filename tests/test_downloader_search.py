import tempfile
import unittest
from pathlib import Path

from src.database import SandSoundDatabase
from src.downloader import Downloader


class DownloaderSearchTests(unittest.TestCase):
    def test_build_search_results_limits_and_normalizes_entries(self) -> None:
        info = {
            "entries": [
                {
                    "id": "aaaaaaaaaaa",
                    "url": "aaaaaaaaaaa",
                    "title": "First Result",
                    "duration": "185",
                    "thumbnails": [
                        {"url": "https://img.example/small.jpg"},
                        {"url": "https://img.example/large.jpg"},
                    ],
                    "channel": "Channel One",
                },
                {
                    "url": "https://youtu.be/bbbbbbbbbbb",
                    "title": "Second Result",
                    "duration": 240,
                    "thumbnail": "https://img.example/thumb.jpg",
                    "uploader": "Uploader Two",
                },
                {
                    "id": "bad",
                    "title": "Invalid Result",
                },
                {
                    "id": "ccccccccccc",
                    "title": "Third Result",
                    "duration": "unknown",
                },
                {
                    "id": "ddddddddddd",
                    "title": "Fourth Result",
                },
            ]
        }

        results = Downloader._build_search_results(info, max_results=3)

        self.assertEqual([result.video_id for result in results], [
            "aaaaaaaaaaa",
            "bbbbbbbbbbb",
            "ccccccccccc",
        ])
        self.assertEqual(
            results[0].url,
            "https://www.youtube.com/watch?v=aaaaaaaaaaa",
        )
        self.assertEqual(results[0].duration, 185)
        self.assertEqual(results[0].thumbnail, "https://img.example/large.jpg")
        self.assertEqual(results[0].uploader, "Channel One")
        self.assertEqual(results[1].url, "https://youtu.be/bbbbbbbbbbb")
        self.assertIsNone(results[2].duration)
        self.assertEqual(
            results[2].thumbnail,
            "https://i.ytimg.com/vi/ccccccccccc/hqdefault.jpg",
        )

    def test_search_videos_ignores_empty_queries(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            base_path = Path(tempdir)
            database = SandSoundDatabase(
                db_path=str(base_path / "sandsound.db"),
                legacy_history_path=str(base_path / "download_history.json"),
            )
            downloader = Downloader(
                download_dir=str(base_path / "downloads"),
                database=database,
            )

            self.assertEqual(downloader.search_videos("   "), [])

    def test_playlist_url_detection_parses_youtube_playlist_links(self) -> None:
        self.assertTrue(
            Downloader.is_playlist_url(
                "https://www.youtube.com/playlist?list=PLi0jJ9mextr97so5xUA15uzIn2cuSDGhg"
            )
        )
        self.assertTrue(
            Downloader.is_playlist_url(
                "www.youtube.com/playlist?list=PLi0jJ9mextr97so5xUA15uzIn2cuSDGhg"
            )
        )
        self.assertFalse(
            Downloader.is_playlist_url(
                "https://www.youtube.com/watch?v=aaaaaaaaaaa"
            )
        )


if __name__ == "__main__":
    unittest.main()
