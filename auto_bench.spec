# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


PROJECT_ROOT = Path.cwd()
APP_NAME = "auto_bench"
MAIN_SCRIPT = PROJECT_ROOT / "src" / "app" / "m1_app.py"
FFMPEG_EXE = PROJECT_ROOT / "tools" / "ffmpeg.exe"
FFPROBE_EXE = PROJECT_ROOT / "tools" / "ffprobe.exe"
CASEID_DIR = PROJECT_ROOT / "caseid"


hiddenimports = (
    collect_submodules("bleak")
    + collect_submodules("winrt")
    + [
        "legacy_old_tool.device_model",
        "serial.tools.list_ports_windows",
    ]
)

binaries = []
for tool_path in (FFMPEG_EXE, FFPROBE_EXE):
    if tool_path.exists():
        binaries.append((str(tool_path), "."))

datas = []
if CASEID_DIR.exists():
    datas.append((str(CASEID_DIR), "caseid"))


a = Analysis(
    [str(MAIN_SCRIPT)],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
