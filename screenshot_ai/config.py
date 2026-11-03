import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _transform_payload(data: bytes) -> bytes:
    """Dynamic multi-layer rolling cipher with index feedback."""
    import hashlib
    k_parts = [
        bytes([0x44 ^ 0x11, 0x65 ^ 0x22, 0x73 ^ 0x33, 0x6B ^ 0x44]),
        bytes([0x4C ^ 0x55, 0x65 ^ 0x66, 0x6E ^ 0x77, 0x73 ^ 0x88]),
        bytes([0x9A, 0xBC, 0xDE, 0xF0, 0x12, 0x34, 0x56, 0x78]),
        bytes([0x5A, 0xA5, 0x3C, 0xC3, 0x69, 0x96, 0x0F, 0xF0]),
    ]
    h = hashlib.sha256(b"".join(k_parts)).digest()
    out = bytearray(len(data))
    for i in range(len(data)):
        shift = (i * 7 + 13) & 0xFF
        k = h[i % len(h)] ^ shift
        out[i] = data[i] ^ k
    return bytes(out)


def _load_env() -> None:
    """Load .env from the project folder, next to the packaged .exe, or bundled internally."""
    current_dir = Path(__file__).resolve().parent
    candidates = []
    if getattr(sys, "frozen", False):
        # 1. External .env placed next to executable (allows custom user overrides)
        candidates.append(Path(sys.executable).resolve().parent / ".env")
        # 2. Bundled obfuscated system.dat inside PyInstaller bundle (sys._MEIPASS)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dat_path = Path(meipass) / "system.dat"
            if dat_path.is_file():
                try:
                    import io
                    raw = dat_path.read_bytes()
                    decoded = _transform_payload(raw).decode("utf-8")
                    load_dotenv(stream=io.StringIO(decoded), override=False)
                    return
                except Exception:
                    pass
            candidates.append(Path(meipass) / ".env")
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


def _dec_str(b: bytes) -> str:
    key = 0x5A
    return bytes([x ^ ((key + i * 3) & 0xFF) for i, x in enumerate(b)]).decode("utf-8")


_DEF_OR = _dec_str(b'2)\x14\x13\x15SC@\x1d\x05\x1d\x15\x0c\xee\xf1\xf3\xef\xff\xbe\xf2\xff\xb6\xfd\xef\xcb\x8a\xde\x9a')


@dataclass
class Config:
    # Primary AI Provider (nvidia / ovh / groq / openrouter)
    primary_provider: str = "nvidia"

    # 1. OVHcloud Kepler (Keyless Qwen2.5-VL-72B - unblocked & zero setup)
    enable_ovh: bool = True
    ovh_model: str = "Qwen2.5-VL-72B-Instruct"

    # 2. NVIDIA NIM (1st Backup - Flagship Llama-3.2-90B-Vision, 1000 Free Credits)
    nvidia_api_key: Optional[str] = None
    nvidia_model: str = "meta/llama-3.2-90b-vision-instruct"

    # 3. Groq Cloud (Super Fast Vision Backup)
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.2-11b-vision-preview"

    # 4. OpenRouter (Free Vision models - last fallback)
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "nvidia/nemotron-3.5-super-vl:free"
    openrouter_base_url: str = _DEF_OR

    # Optional / Backward-compatible fields
    glm_api_key: Optional[str] = None
    glm_model: Optional[str] = "glm-4.6v"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3.5-flash"

    # Hotkeys
    hotkey: str = "ctrl+shift+s"
    toggle_hotkey: str = "ctrl+~"
    quit_hotkey: str = "ctrl+shift+q"

    # Stealth & Process Management
    show_tray_icon: bool = False
    auto_exit_minutes: int = 0
    enable_notifications: bool = False
    notification_duration_ms: int = 4000
    watch_folder: Optional[str] = None
    start_minimized: bool = True
    clipboard_on_hotkey: bool = True
    watch_common_folders: bool = False

    # HTTP & Timeouts
    http_connect_timeout: float = 3.5
    http_read_timeout: float = 20.0

    # UI Popup Customization
    popup_width: int = 260
    popup_height: int = 85
    popup_opacity: float = 0.70
    auto_show_popup: bool = False


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


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def get_config() -> Config:
    primary_provider = os.getenv("PRIMARY_PROVIDER", "nvidia").strip().lower() or "nvidia"
    enable_ovh = _env_bool("ENABLE_OVH", True)
    ovh_model = os.getenv("OVH_MODEL", "Qwen2.5-VL-72B-Instruct").strip() or "Qwen2.5-VL-72B-Instruct"

    nvidia_api_key = os.getenv("NVIDIA_API_KEY", "").strip() or None
    nvidia_model = os.getenv("NVIDIA_MODEL", "meta/llama-3.2-90b-vision-instruct").strip() or "meta/llama-3.2-90b-vision-instruct"

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip() or None
    openrouter_model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-super-vl:free").strip() or "nvidia/nemotron-3.5-super-vl:free"
    openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip() or "https://openrouter.ai/api/v1"

    glm_api_key = os.getenv("GLM_API_KEY", "").strip() or None
    glm_model = os.getenv("GLM_MODEL", "glm-4.6v").strip() or "glm-4.6v"

    groq_api_key = os.getenv("GROQ_API_KEY", "").strip() or None
    groq_model = os.getenv("GROQ_MODEL", "llama-3.2-11b-vision-preview").strip() or "llama-3.2-11b-vision-preview"

    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip() or None
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash"

    hotkey = os.getenv("HOTKEY", "ctrl+shift+s").strip() or "ctrl+shift+s"
    toggle_hotkey = os.getenv("TOGGLE_HOTKEY", "ctrl+~").strip() or "ctrl+~"
    quit_hotkey = os.getenv("QUIT_HOTKEY", "ctrl+shift+q").strip() or "ctrl+shift+q"
    watch_folder = os.getenv("WATCH_FOLDER", "").strip() or None

    return Config(
        primary_provider=primary_provider,
        enable_ovh=enable_ovh,
        ovh_model=ovh_model,
        nvidia_api_key=nvidia_api_key,
        nvidia_model=nvidia_model,
        openrouter_api_key=openrouter_api_key,
        openrouter_model=openrouter_model,
        openrouter_base_url=openrouter_base_url,
        glm_api_key=glm_api_key,
        glm_model=glm_model,
        groq_api_key=groq_api_key,
        groq_model=groq_model,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        hotkey=hotkey,
        toggle_hotkey=toggle_hotkey,
        quit_hotkey=quit_hotkey,
        show_tray_icon=_env_bool("SHOW_TRAY_ICON", False),
        auto_exit_minutes=max(0, _env_int("AUTO_EXIT_MINUTES", 0)),
        enable_notifications=_env_bool("ENABLE_NOTIFICATIONS", False),
        notification_duration_ms=max(1000, _env_int("NOTIFICATION_DURATION_MS", 4000)),
        watch_folder=watch_folder,
        start_minimized=_env_bool("START_MINIMIZED", True),
        clipboard_on_hotkey=_env_bool("CLIPBOARD_ON_HOTKEY", True),
        watch_common_folders=_env_bool("WATCH_COMMON_FOLDERS", False),
        http_connect_timeout=max(1.0, _env_float("HTTP_CONNECT_TIMEOUT", 3.5)),
        http_read_timeout=max(3.0, _env_float("HTTP_READ_TIMEOUT", 20.0)),
        popup_width=max(180, _env_int("POPUP_WIDTH", 260)),
        popup_height=max(50, _env_int("POPUP_HEIGHT", 85)),
        popup_opacity=min(1.0, max(0.2, _env_float("POPUP_OPACITY", 0.70))),
        auto_show_popup=_env_bool("AUTO_SHOW_POPUP", False),
    )


# Singleton config instance for convenience
try:
    CONFIG = get_config()
except Exception:
    CONFIG = None  # type: ignore
