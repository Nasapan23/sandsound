"""
Application update checks and Windows installer update support.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


REPO_OWNER = "Nasapan23"
REPO_NAME = "sandsound"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
LATEST_RELEASE_PAGE = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest"
DEFAULT_REQUEST_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "SandSound-Updater",
    "X-GitHub-Api-Version": "2022-11-28",
}


class UpdateError(RuntimeError):
    """Raised when update checks or installation fail."""


@dataclass(frozen=True)
class ReleaseAsset:
    """A downloadable release asset."""

    name: str
    download_url: str
    size: int = 0


@dataclass(frozen=True)
class UpdateInfo:
    """Metadata describing an available application update."""

    version: str
    current_version: str
    html_url: str
    release_name: str
    published_at: str = ""
    asset: Optional[ReleaseAsset] = None


def normalize_version(value: str) -> str:
    """Normalize semantic version text for comparisons."""
    return value.strip().lstrip("vV")


def parse_version(value: str) -> tuple[int, ...]:
    """Parse a semantic-ish version string into a comparable tuple."""
    normalized = normalize_version(value)
    if not normalized:
        return (0, 0, 0)

    parts: list[int] = []
    for raw_part in normalized.split("."):
        digits = "".join(ch for ch in raw_part if ch.isdigit())
        parts.append(int(digits) if digits else 0)

    while len(parts) < 3:
        parts.append(0)

    return tuple(parts)


def is_newer_version(current: str, candidate: str) -> bool:
    """Return True when candidate is newer than current."""
    return parse_version(candidate) > parse_version(current)


class AppUpdater:
    """Checks GitHub releases and launches Windows installer updates."""

    def __init__(
        self,
        current_version: str,
        *,
        latest_release_api: str = LATEST_RELEASE_API,
        latest_release_page: str = LATEST_RELEASE_PAGE,
        request_headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.current_version = normalize_version(current_version)
        self.latest_release_api = latest_release_api
        self.latest_release_page = latest_release_page
        self.request_headers = dict(request_headers or DEFAULT_REQUEST_HEADERS)

    def supports_installer_update(self) -> bool:
        """Return True when this runtime can launch a Windows installer update."""
        return sys.platform == "win32"

    def can_install_update(self) -> bool:
        """Return True when in-app installer updates are supported."""
        return self.supports_installer_update()

    def check_for_update(self, timeout: int = 5) -> Optional[UpdateInfo]:
        """Fetch the latest release metadata and compare versions."""
        payload = self._load_latest_release_payload(timeout=timeout)
        return self._build_update_info(payload)

    def _load_latest_release_payload(self, timeout: int) -> dict:
        request = urllib.request.Request(
            self.latest_release_api,
            headers=self.request_headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            raise UpdateError("Could not check for updates.") from exc

    def _build_update_info(self, payload: dict) -> Optional[UpdateInfo]:
        latest_version = normalize_version(str(payload.get("tag_name") or ""))
        if not latest_version:
            return None
        if not is_newer_version(self.current_version, latest_version):
            return None

        asset = self._select_windows_installer_asset(
            payload.get("assets") or [],
            latest_version,
        )
        return UpdateInfo(
            version=latest_version,
            current_version=self.current_version,
            html_url=str(payload.get("html_url") or self.latest_release_page),
            release_name=str(payload.get("name") or f"Release v{latest_version}"),
            published_at=str(payload.get("published_at") or ""),
            asset=asset,
        )

    @staticmethod
    def _select_windows_installer_asset(
        assets: list[dict],
        version: str,
    ) -> Optional[ReleaseAsset]:
        expected_name = f"SandSound-Setup-{version}.exe".lower()
        installer_assets: list[ReleaseAsset] = []

        for asset in assets:
            name = str(asset.get("name") or "")
            download_url = str(asset.get("browser_download_url") or "")
            if not name or not download_url or not name.lower().endswith(".exe"):
                continue
            if "setup" not in name.lower() and "installer" not in name.lower():
                continue
            installer_assets.append(
                ReleaseAsset(
                    name=name,
                    download_url=download_url,
                    size=int(asset.get("size") or 0),
                )
            )

        for asset in installer_assets:
            if asset.name.lower() == expected_name:
                return asset

        for asset in installer_assets:
            if asset.name.lower().startswith("sandsound-setup-"):
                return asset

        return installer_assets[0] if installer_assets else None

    def download_update(
        self,
        update_info: UpdateInfo,
        *,
        timeout: int = 30,
        chunk_size: int = 256 * 1024,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Download the update asset to a temporary file and return its path."""
        if not update_info.asset:
            raise UpdateError("No downloadable update asset is available for this release.")

        download_dir = Path(tempfile.mkdtemp(prefix="sandsound-update-"))
        destination = download_dir / update_info.asset.name
        request = urllib.request.Request(
            update_info.asset.download_url,
            headers=self.request_headers,
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                total_size = int(
                    response.headers.get("Content-Length")
                    or update_info.asset.size
                    or 0
                )
                bytes_downloaded = 0

                with open(destination, "wb") as handle:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        handle.write(chunk)
                        bytes_downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(bytes_downloaded, total_size)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise UpdateError("Could not download the update.") from exc

        if not destination.exists() or destination.stat().st_size == 0:
            raise UpdateError("Downloaded update is empty.")

        return destination

    def launch_downloaded_installer(self, downloaded_path: Path) -> None:
        """Launch a downloaded Inno Setup installer in silent update mode."""
        if not self.can_install_update():
            raise UpdateError("Installer updates are only available on Windows.")
        if not downloaded_path.is_file():
            raise UpdateError("Downloaded installer is missing.")

        creation_flags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

        command = [
            str(downloaded_path),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/SP-",
            "/CLOSEAPPLICATIONS",
        ]

        try:
            subprocess.Popen(
                command,
                creationflags=creation_flags,
                close_fds=True,
            )
        except OSError as exc:
            raise UpdateError("Could not start the installer.") from exc
