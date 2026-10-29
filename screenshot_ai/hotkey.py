"""Configurable global keyboard shortcut for Windows.

Uses the Win32 ``RegisterHotKey`` API, which works system-wide even when the
application does not have focus. No third-party dependency is required.
"""

import ctypes
import re
import sys
from ctypes import wintypes
from typing import Optional, Tuple

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication

WM_HOTKEY = 0x0312

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_MODIFIER_ALIASES = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "alt": MOD_ALT,
    "win": MOD_WIN,
    "windows": MOD_WIN,
    "super": MOD_WIN,
    "meta": MOD_WIN,
}

_VK_NAMES = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "tab": 0x09,
    "backspace": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "ins": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "printscreen": 0x2C,
    "prtsc": 0x2C,
    "prtscr": 0x2C,
    "pause": 0x13,
    "`": 0xC0,
    "~": 0xC0,
    "tilde": 0xC0,
    "grave": 0xC0,
    "-": 0xBD,
    "=": 0xBB,
    "[": 0xDB,
    "]": 0xDD,
    "\\": 0xDC,
    ";": 0xBA,
    "'": 0xDE,
    ",": 0xBC,
    ".": 0xBE,
    "/": 0xBF,
}

_FUNCTION_KEY = re.compile(r"^f([1-9]|1[0-9]|2[0-4])$")


class HotkeyError(Exception):
    """Raised when a shortcut cannot be parsed or registered."""


def parse_hotkey(sequence: str) -> Tuple[int, int]:
    """Convert a shortcut string like ``ctrl+shift+s`` to (modifiers, vk)."""
    if not sequence or not sequence.strip():
        raise HotkeyError("Hotkey is empty. Example: ctrl+shift+s")

    parts = [part.strip().lower() for part in sequence.split("+") if part.strip()]
    if not parts:
        raise HotkeyError(f"Invalid hotkey: {sequence!r}")

    modifiers = 0
    keys = []
    for part in parts:
        if part in _MODIFIER_ALIASES:
            modifiers |= _MODIFIER_ALIASES[part]
        else:
            keys.append(part)

    if len(keys) != 1:
        raise HotkeyError(
            f"Invalid hotkey {sequence!r}. Use one key plus modifiers, e.g. ctrl+shift+s"
        )
    if modifiers == 0:
        raise HotkeyError(
            f"Invalid hotkey {sequence!r}. "
            "At least one modifier (ctrl, alt, shift, win) is required."
        )

    key = keys[0]
    if key in _VK_NAMES:
        vk = _VK_NAMES[key]
    elif _FUNCTION_KEY.match(key):
        vk = 0x70 + int(key[1:]) - 1
    elif len(key) == 1 and (key.isalpha() or key.isdigit()):
        vk = ord(key.upper())
    else:
        raise HotkeyError(f"Unsupported key {key!r} in hotkey {sequence!r}")

    return modifiers, vk


class _HotkeyEventFilter(QAbstractNativeEventFilter):
    """Small adapter so ``GlobalHotkey`` can stay a plain ``QObject``."""

    def __init__(self, hotkey: "GlobalHotkey"):
        QAbstractNativeEventFilter.__init__(self)
        self._hotkey = hotkey

    def nativeEventFilter(self, event_type, message):  # noqa: N802 - Qt override
        return self._hotkey.handle_native_event(event_type, message)


class GlobalHotkey(QObject):
    """System-wide hotkey that emits :attr:`activated` when pressed."""

    activated = Signal()

    _next_id = 0xB000

    def __init__(self, sequence: str, parent: Optional[QObject] = None):
        super().__init__(parent)

        if sys.platform != "win32":
            raise HotkeyError("Global hotkeys are currently supported on Windows only.")

        self._sequence = sequence
        self._modifiers, self._vk = parse_hotkey(sequence)
        self._registered = False
        self._id = GlobalHotkey._next_id
        GlobalHotkey._next_id += 1
        self._id_shift: Optional[int] = None
        if self._vk == 0xC0:
            self._id_shift = GlobalHotkey._next_id
            GlobalHotkey._next_id += 1

        self._filter = _HotkeyEventFilter(self)

        self._user32 = ctypes.windll.user32
        self._user32.RegisterHotKey.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.UINT,
        ]
        self._user32.RegisterHotKey.restype = wintypes.BOOL
        self._user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self._user32.UnregisterHotKey.restype = wintypes.BOOL

    # ------------------------------------------------------------- lifecycle --
    def register(self) -> None:
        if self._registered:
            return
        success = self._user32.RegisterHotKey(
            None, self._id, self._modifiers | MOD_NOREPEAT, self._vk
        )
        if not success:
            raise HotkeyError(
                f"Could not register '{self._sequence}'. "
                "Another application is probably already using this shortcut."
            )
        if self._id_shift is not None:
            # Register alternate Shift state for the tilde key (` / ~) so both
            # Ctrl+` (unshifted) and Ctrl+Shift+` (typed as Ctrl+~) are caught seamlessly.
            alt_mods = self._modifiers ^ MOD_SHIFT
            self._user32.RegisterHotKey(
                None, self._id_shift, alt_mods | MOD_NOREPEAT, self._vk
            )

        app = QApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self._filter)
        self._registered = True

    def unregister(self) -> None:
        if not self._registered:
            return
        self._user32.UnregisterHotKey(None, self._id)
        if self._id_shift is not None:
            self._user32.UnregisterHotKey(None, self._id_shift)
        app = QApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self._filter)
        self._registered = False

    @property
    def sequence(self) -> str:
        return self._sequence

    # --------------------------------------------------------- native events --
    def handle_native_event(self, event_type, message):
        if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                param = int(msg.wParam)
                if param == self._id or (self._id_shift is not None and param == self._id_shift):
                    self.activated.emit()
                    return True, 0
        return False, 0
