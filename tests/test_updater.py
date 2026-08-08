import unittest
from pathlib import Path
import tempfile
from unittest import mock

import src.updater as updater_module
from src.updater import AppUpdater, is_newer_version, normalize_version, parse_version


class UpdaterTests(unittest.TestCase):
    def test_normalize_and_parse_version(self) -> None:
        self.assertEqual(normalize_version(" v1.2.3 "), "1.2.3")
        self.assertEqual(parse_version("1.2"), (1, 2, 0))
        self.assertEqual(parse_version("v1.2.10"), (1, 2, 10))

    def test_is_newer_version_handles_multi_digit_segments(self) -> None:
        self.assertTrue(is_newer_version("1.0.9", "1.0.10"))
        self.assertFalse(is_newer_version("1.0.10", "1.0.10"))
        self.assertFalse(is_newer_version("1.1.0", "1.0.9"))

    def test_build_update_info_returns_none_when_current_is_latest(self) -> None:
        updater = AppUpdater("1.0.4")

        payload = {
            "tag_name": "v1.0.4",
            "html_url": "https://example.com/release",
            "assets": [],
        }

        self.assertIsNone(updater._build_update_info(payload))

    def test_build_update_info_selects_expected_windows_installer_asset(self) -> None:
        updater = AppUpdater("1.0.4")

        payload = {
            "tag_name": "v1.0.5",
            "name": "Release v1.0.5",
            "html_url": "https://example.com/release",
            "assets": [
                {
                    "name": "source.zip",
                    "browser_download_url": "https://example.com/source.zip",
                },
                {
                    "name": "SandSound-Windows-1.0.5.exe",
                    "browser_download_url": "https://example.com/SandSound-Windows-1.0.5.exe",
                    "size": 512,
                },
                {
                    "name": "SandSound-Setup-1.0.5.exe",
                    "browser_download_url": "https://example.com/SandSound-Setup-1.0.5.exe",
                    "size": 1024,
                },
            ],
        }

        update_info = updater._build_update_info(payload)

        self.assertIsNotNone(update_info)
        assert update_info is not None
        self.assertEqual(update_info.version, "1.0.5")
        self.assertIsNotNone(update_info.asset)
        assert update_info.asset is not None
        self.assertEqual(update_info.asset.name, "SandSound-Setup-1.0.5.exe")

    def test_build_update_info_ignores_standalone_exe_without_installer(self) -> None:
        updater = AppUpdater("1.0.4")

        payload = {
            "tag_name": "v1.0.5",
            "html_url": "https://example.com/release",
            "assets": [
                {
                    "name": "SandSound-Windows-1.0.5.exe",
                    "browser_download_url": "https://example.com/SandSound-Windows-1.0.5.exe",
                },
            ],
        }

        update_info = updater._build_update_info(payload)

        self.assertIsNotNone(update_info)
        assert update_info is not None
        self.assertIsNone(update_info.asset)

    def test_can_install_update_requires_windows(self) -> None:
        updater = AppUpdater("1.0.4")

        with mock.patch("src.updater.sys.platform", "win32"):
            self.assertTrue(updater.supports_installer_update())
            self.assertTrue(updater.can_install_update())

        with mock.patch("src.updater.sys.platform", "linux"):
            self.assertFalse(updater.supports_installer_update())
            self.assertFalse(updater.can_install_update())

    def test_launch_downloaded_installer_starts_silent_setup(self) -> None:
        updater = AppUpdater("1.0.4")

        with tempfile.TemporaryDirectory() as tempdir:
            installer = Path(tempdir) / "SandSound-Setup-1.0.5.exe"
            installer.write_bytes(b"setup")

            with mock.patch("src.updater.sys.platform", "win32"), \
                 mock.patch.object(updater_module.subprocess, "Popen") as popen:
                updater.launch_downloaded_installer(installer)

        command = popen.call_args.args[0]
        self.assertEqual(command[0], str(installer))
        self.assertIn("/VERYSILENT", command)
        self.assertIn("/CLOSEAPPLICATIONS", command)


if __name__ == "__main__":
    unittest.main()
