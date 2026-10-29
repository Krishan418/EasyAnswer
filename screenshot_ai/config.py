import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _load_env() -> None:
    """Load .env from the project folder or next to the packaged .exe."""
    current_dir = Path(__file__).resolve().parent
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / ".env")
    candidates.extend(
        [
            current_dir.parent / ".env",
            current_dir / ".env",
            Path.cwd() / ".env",
        ]
    )
    for env_path in candidates:
        if env_path.is_file():
            load_dotenv(dotenv_path=env_path, override=False)
            return
    load_dotenv()


_load_env()


@dataclass
class Config:
    gemini_api_key: str
    gemini_model: str = "gemini-3.5-flash"
    hotkey: str = "ctrl+shift+s"
    toggle_hotkey: str = "ctrl+~"
    quit_hotkey: str = "ctrl+shift+q"
    show_tray_icon: bool = False
    auto_exit_minutes: int = 15
    enable_notifications: bool = True
    notification_duration_ms: int = 4000
    watch_folder: Optional[str] = None
    start_minimized: bool = False
    clipboard_on_hotkey: bool = True
    watch_common_folders: bool = False
    grok_api_key: Optional[str] = None
    grok_model: str = "grok-2-vision-1212"
    github_token: Optional[str] = None
    github_model: str = "gpt-4o-mini"
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "nvidia/nemotron-3.5-super-vl:free"
    primary_provider: str = "gemini"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


import base64

# Built-in fallback API key for standalone deployment across PCs without .env
_DEFAULT_KEY_B64 = "QVEuQWI4Uk42SmVsY0tKak1UNzQtaFRwV3AzeVFnZjZsRFFRai1tU0RKbnhjTHpZNWFDeVE="


def _get_default_key() -> str:
    try:
        return base64.b64decode(_DEFAULT_KEY_B64).decode("utf-8")
    except Exception:
        return ""


def get_config() -> Config:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        api_key = _get_default_key()

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. "
            "Create a .env file (copy from .env.example) and add your Gemini API key from Google AI Studio."
        )


    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash"
    hotkey = os.getenv("HOTKEY", "ctrl+shift+s").strip() or "ctrl+shift+s"
    toggle_hotkey = os.getenv("TOGGLE_HOTKEY", "ctrl+~").strip() or "ctrl+~"
    quit_hotkey = os.getenv("QUIT_HOTKEY", "ctrl+shift+q").strip() or "ctrl+shift+q"
    watch_folder = os.getenv("WATCH_FOLDER", "").strip() or None
    grok_api_key = os.getenv("GROK_API_KEY", "").strip() or None
    grok_model = os.getenv("GROK_MODEL", "grok-2-vision-1212").strip() or "grok-2-vision-1212"
    github_token = os.getenv("GITHUB_TOKEN", "").strip() or None
    github_model = os.getenv("GITHUB_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip() or None
    openrouter_model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-super-vl:free").strip() or "nvidia/nemotron-3.5-super-vl:free"
    primary_provider = os.getenv("PRIMARY_PROVIDER", "").strip().lower()
    if not primary_provider:
        primary_provider = "openrouter" if openrouter_api_key else ("github" if github_token else "gemini")

    return Config(
        gemini_api_key=api_key,
        gemini_model=model,
        hotkey=hotkey,
        toggle_hotkey=toggle_hotkey,
        quit_hotkey=quit_hotkey,
        show_tray_icon=_env_bool("SHOW_TRAY_ICON", False),
        auto_exit_minutes=max(0, _env_int("AUTO_EXIT_MINUTES", 15)),
        enable_notifications=_env_bool("ENABLE_NOTIFICATIONS", True),
        notification_duration_ms=max(1000, _env_int("NOTIFICATION_DURATION_MS", 4000)),
        watch_folder=watch_folder,
        start_minimized=_env_bool("START_MINIMIZED", False),
        clipboard_on_hotkey=_env_bool("CLIPBOARD_ON_HOTKEY", True),
        watch_common_folders=_env_bool("WATCH_COMMON_FOLDERS", False),
        grok_api_key=grok_api_key,
        grok_model=grok_model,
        github_token=github_token,
        github_model=github_model,
        openrouter_api_key=openrouter_api_key,
        openrouter_model=openrouter_model,
        primary_provider=primary_provider,
    )


# Singleton config instance for convenience
try:
    CONFIG = get_config()
except Exception:
    # Don't crash on import if env not set yet; will be validated when used
    CONFIG = None  # type: ignore
