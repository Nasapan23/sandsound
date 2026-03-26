"""
Application update checks and Windows self-update support.
"""

from __future__ import annotations

import json
import os
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
    """Checks GitHub releases and applies Windows executable updates."""

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

    def supports_self_update(self) -> bool:
        """Return True when this runtime can replace its own executable."""
        executable = Path(sys.executable)
        return (
            sys.platform == "win32"
            and bool(getattr(sys, "frozen", False))
            and executable.suffix.lower() == ".exe"
        )

    def can_replace_current_executable(self) -> bool:
        """Best-effort writability check for packaged installations."""
        if not self.supports_self_update():
            return False
        return os.access(Path(sys.executable).parent, os.W_OK)

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

        asset = self._select_windows_asset(payload.get("assets") or [], latest_version)
        return UpdateInfo(
            version=latest_version,
            current_version=self.current_version,
            html_url=str(payload.get("html_url") or self.latest_release_page),
            release_name=str(payload.get("name") or f"Release v{latest_version}"),
            published_at=str(payload.get("published_at") or ""),
            asset=asset,
        )

    @staticmethod
    def _select_windows_asset(assets: list[dict], version: str) -> Optional[ReleaseAsset]:
        expected_name = f"SandSound-Windows-{version}.exe".lower()
        windows_assets: list[ReleaseAsset] = []

        for asset in assets:
            name = str(asset.get("name") or "")
            download_url = str(asset.get("browser_download_url") or "")
            if not name or not download_url or not name.lower().endswith(".exe"):
                continue
            windows_assets.append(
                ReleaseAsset(
                    name=name,
                    download_url=download_url,
                    size=int(asset.get("size") or 0),
                )
            )

        for asset in windows_assets:
            if asset.name.lower() == expected_name:
                return asset

        for asset in windows_assets:
            if asset.name.lower().startswith("sandsound-windows-"):
                return asset

        return windows_assets[0] if windows_assets else None

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

    def apply_downloaded_update(self, downloaded_path: Path) -> None:
        """Spawn a helper process that replaces the current executable after exit."""
        if not self.can_replace_current_executable():
            raise UpdateError("Self-update is not available in this installation.")

        target_exe = Path(sys.executable).resolve()
        script_path = downloaded_path.parent / "apply_sandsound_update.ps1"
        script_path.write_text(self._build_windows_update_script(), encoding="utf-8")

        creation_flags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-TargetExe",
            str(target_exe),
            "-DownloadedExe",
            str(downloaded_path),
            "-ParentPid",
            str(os.getpid()),
        ]

        try:
            subprocess.Popen(
                command,
                creationflags=creation_flags,
                close_fds=True,
            )
        except OSError as exc:
            raise UpdateError("Could not start the updater process.") from exc

    @staticmethod
    def _build_windows_update_script() -> str:
        return """param(
    [Parameter(Mandatory=$true)][string]$TargetExe,
    [Parameter(Mandatory=$true)][string]$DownloadedExe,
    [Parameter(Mandatory=$true)][int]$ParentPid
)

$ErrorActionPreference = "Stop"
$backupPath = "$TargetExe.bak"

try {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if (-not (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue)) {
            break
        }
        Start-Sleep -Seconds 1
    }

    Start-Sleep -Milliseconds 750

    if (Test-Path -LiteralPath $backupPath) {
        Remove-Item -LiteralPath $backupPath -Force
    }

    if (Test-Path -LiteralPath $TargetExe) {
        Move-Item -LiteralPath $TargetExe -Destination $backupPath -Force
    }

    Move-Item -LiteralPath $DownloadedExe -Destination $TargetExe -Force
    Start-Process -FilePath $TargetExe -WorkingDirectory (Split-Path -Parent $TargetExe)

    if (Test-Path -LiteralPath $backupPath) {
        Remove-Item -LiteralPath $backupPath -Force
    }
}
catch {
    if ((Test-Path -LiteralPath $backupPath) -and -not (Test-Path -LiteralPath $TargetExe)) {
        Move-Item -LiteralPath $backupPath -Destination $TargetExe -Force
    }
}
finally {
    Start-Sleep -Milliseconds 500
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}
"""
