import unittest

from src.downloader import PlaylistItem, VideoInfo
from src.ui.playlist_bar import build_playlist_bar_text


class UiAppTests(unittest.TestCase):
    def test_build_playlist_bar_text_truncates_long_titles(self) -> None:
        long_title = (
            "Best spanish songs 2010 2019 Latin Dance Music "
            "Canciones en Espanol 2010s extended collection mix"
        )
        info = VideoInfo(
            url="https://youtube.com/playlist?list=abc",
            title=long_title,
            duration=None,
            thumbnail=None,
            is_playlist=True,
            playlist_id="abc",
            entries=[
                PlaylistItem(video_id="1", title="one"),
                PlaylistItem(video_id="2", title="two"),
                PlaylistItem(video_id="3", title="three"),
            ],
        )

        text = build_playlist_bar_text(info, new_count=2)

        self.assertIn("(2 new / 3 total)", text)
        self.assertIn("...", text)
        self.assertTrue(text.startswith("Playlist: "))
        self.assertLessEqual(len(text), 90)

    def test_build_playlist_bar_text_keeps_short_titles(self) -> None:
        info = VideoInfo(
            url="https://youtube.com/playlist?list=abc",
            title="Road Trip",
            duration=None,
            thumbnail=None,
            is_playlist=True,
        )

        text = build_playlist_bar_text(info)

        self.assertEqual(text, "Playlist: Road Trip")


if __name__ == "__main__":
    unittest.main()
