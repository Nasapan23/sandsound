# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


block_cipher = None

project_root = Path(SPECPATH).parent

datas = []
datas += collect_data_files("customtkinter")

hiddenimports = sorted(
    set(
        [
            "customtkinter",
            "tkinter",
            "tkinter.filedialog",
            "PIL",
            "PIL._tkinter_finder",
            "yt_dlp",
        ]
        + collect_submodules("customtkinter")
        + collect_submodules("yt_dlp.downloader")
        + collect_submodules("yt_dlp.extractor")
        + collect_submodules("yt_dlp.postprocessor")
    )
)

a = Analysis(
    ["src/main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SandSound" if sys.platform != "win32" else "SandSound",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
