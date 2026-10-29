"""Optional "start with Windows" support (per-user registry Run key).

Only the current user's ``HKEY_CURRENT_USER`` hive is touched, so no admin
rights are needed. Works for both ``python -m screenshot_ai.app`` during
development and the packaged ``.exe``.
"""

import sys
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - only possible off Windows
    winreg = None  # type: ignore[assignment]

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "ScreenshotAIAssistant"


class StartupError(Exception):
    """Raised when the Windows startup entry cannot be read or written."""


def _launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'

    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else python
    return f'"{exe}" -m screenshot_ai.app'


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, _VALUE_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    if winreg is None:
        raise StartupError("Windows startup is only supported on Windows.")
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key, _VALUE_NAME, 0, winreg.REG_SZ, _launch_command()
                )
            else:
                try:
                    winreg.DeleteValue(key, _VALUE_NAME)
                except FileNotFoundError:
                    pass
    except OSError as exc:
        raise StartupError(f"Could not update the Windows startup entry: {exc}") from exc
