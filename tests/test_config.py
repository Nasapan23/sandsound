import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
