from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional


# 程序所在目录（打包后为 exe 目录，开发时为项目根目录）
def get_app_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _load_config_ffmpeg_path() -> Optional[str]:
    config_file = get_app_root() / "config.json"
    if config_file.exists():
        try:
            with config_file.open("r", encoding="utf-8") as f:
                config = json.load(f)
            ffmpeg = config.get("ffmpeg_path", "").strip()
            if ffmpeg:
                ffmpeg_path = Path(ffmpeg).expanduser()
                if not ffmpeg_path.is_absolute():
                    ffmpeg_path = get_app_root() / ffmpeg_path
                if ffmpeg_path.exists():
                    return str(ffmpeg_path)
        except Exception:
            pass
    return None


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []

    if getattr(sys, 'frozen', False):
        executable_root = Path(sys.executable).resolve().parent
        roots.append(executable_root)
        roots.append(executable_root / '_internal')
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            roots.append(Path(meipass))

    roots.append(Path.cwd())
    roots.append(Path.cwd() / '_internal')
    roots.append(Path(__file__).resolve().parents[2])

    seen: set[str] = set()
    ordered: list[Path] = []
    for root in roots:
        key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(root)
    return ordered


def _search_roots() -> list[Path]:
    roots: list[Path] = []
    for root in _candidate_roots():
        roots.append(root)
        roots.append(root / "tools")

    seen: set[str] = set()
    ordered: list[Path] = []
    for root in roots:
        key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(root)
    return ordered


def resolve_tool_path(
    name: str,
    env_var: Optional[str] = None,
    *,
    include_system_path: bool = True,
) -> Optional[str]:
    if env_var:
        configured = os.environ.get(env_var)
        if configured:
            configured_path = Path(configured).expanduser()
            if configured_path.exists():
                return str(configured_path)

    executable_names = [name]
    if sys.platform.startswith('win') and not name.lower().endswith('.exe'):
        executable_names.insert(0, f'{name}.exe')

    for root in _search_roots():
        for executable_name in executable_names:
            candidate = root / executable_name
            if candidate.exists():
                return str(candidate)

    if include_system_path:
        for executable_name in executable_names:
            found = shutil.which(executable_name)
            if found:
                return found

    return None


def resolve_ffmpeg_path() -> Optional[str]:
    bundled_path = resolve_tool_path(
        'ffmpeg',
        env_var='BENCHMARK_TOOL_FFMPEG',
        include_system_path=False,
    )
    if bundled_path:
        return bundled_path

    config_path = _load_config_ffmpeg_path()
    if config_path:
        return config_path

    return resolve_tool_path('ffmpeg', env_var='BENCHMARK_TOOL_FFMPEG')


def resolve_ffprobe_path() -> Optional[str]:
    return resolve_tool_path('ffprobe', env_var='BENCHMARK_TOOL_FFPROBE')
