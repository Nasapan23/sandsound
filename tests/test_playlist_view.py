import unittest

from src.ui.playlist_view import PlaylistTableRow


class PlaylistViewTests(unittest.TestCase):
    def test_duration_format_accepts_decimal_values(self) -> None:
        self.assertEqual(PlaylistTableRow._format_duration(None, 120.9), "2:00")

    def test_duration_format_handles_invalid_values(self) -> None:
        self.assertEqual(PlaylistTableRow._format_duration(None, None), "--:--")


if __name__ == "__main__":
    unittest.main()
