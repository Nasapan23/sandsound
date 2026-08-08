import tempfile
import unittest
from unittest import mock
import os
from pathlib import Path

from src.config import Config


class ConfigTests(unittest.TestCase):
    def test_concurrent_downloads_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            config_path = Path(tempdir) / "config.json"
            config = Config(config_path=str(config_path))

            config.concurrent_downloads = 99
            self.assertEqual(config.concurrent_downloads, Config.MAX_CONCURRENT_DOWNLOADS)

            config.concurrent_downloads = 0
            self.assertEqual(config.concurrent_downloads, Config.MIN_CONCURRENT_DOWNLOADS)

            config.concurrent_downloads = 4
            self.assertEqual(config.concurrent_downloads, 4)

    def test_ffmpeg_location_prefers_bundled_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            base_path = Path(tempdir)
            executable_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
            bundled = base_path / "ffmpeg" / "bin" / executable_name
            configured = base_path / "custom-ffmpeg.exe"
            bundled.parent.mkdir(parents=True)
            bundled.write_bytes(b"ffmpeg")
            configured.write_bytes(b"custom")

            config = Config(config_path=str(base_path / "config.json"))
            config.ffmpeg_path = str(configured)

            with mock.patch.object(Config, "_app_base_dir", return_value=base_path):
                self.assertEqual(config.get_ffmpeg_location(), str(bundled))
                self.assertTrue(config.is_ffmpeg_available())

    def test_ffmpeg_location_uses_configured_path_without_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            base_path = Path(tempdir)
            configured = base_path / "custom-ffmpeg.exe"
            configured.write_bytes(b"custom")

            config = Config(config_path=str(base_path / "config.json"))
            config.ffmpeg_path = str(configured)

            with mock.patch.object(Config, "_app_base_dir", return_value=base_path):
                self.assertEqual(config.get_ffmpeg_location(), str(configured))

    def test_ffmpeg_available_uses_path_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            base_path = Path(tempdir)
            config = Config(config_path=str(base_path / "config.json"))

            with mock.patch.object(Config, "_app_base_dir", return_value=base_path), \
                 mock.patch("src.config.shutil.which", return_value="ffmpeg.exe"):
                self.assertIsNone(config.get_ffmpeg_location())
                self.assertTrue(config.is_ffmpeg_available())


if __name__ == "__main__":
    unittest.main()
