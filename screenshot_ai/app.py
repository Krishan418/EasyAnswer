"""Application entry point.

Run with::

    python -m screenshot_ai.app

The controller owns the popup, the global hotkey, the tray icon and the
optional folder watcher. Automatic uploads only happen after the user
explicitly chooses a folder to watch, and they can be paused at any time.
"""

import ctypes
import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

try:
    from . import startup
    from .config import Config, get_config
    from .hotkey import GlobalHotkey, HotkeyError
    from .icons import build_app_icon
    from .notifications import APP_NAME, TrayNotifier
    from .popup import ResultPopup, create_app
    from .screenshot_service import (
        ScreenshotError,
        common_screenshot_folders,
        screenshot_service,
    )
except (ImportError, ValueError):
    from screenshot_ai import startup
    from screenshot_ai.config import Config, get_config
    from screenshot_ai.hotkey import GlobalHotkey, HotkeyError
    from screenshot_ai.icons import build_app_icon
    from screenshot_ai.notifications import APP_NAME, TrayNotifier
    from screenshot_ai.popup import ResultPopup, create_app
    from screenshot_ai.screenshot_service import (
        ScreenshotError,
        common_screenshot_folders,
        screenshot_service,
    )


_ERROR_ALREADY_EXISTS = 183
_mutex_handle = None  # kept alive for the lifetime of the process


class _MonitorBridge(QObject):
    """Moves watcher-thread events onto the Qt (GUI) thread."""

    file_detected = Signal(str)


class ApplicationController:
    """Wires the UI, hotkey, tray controls and folder monitoring together."""

    def __init__(self, app: QApplication, config: Config):
        self.app = app
        self.config = config

        self.popup = ResultPopup()
        self.popup.analysis_completed.connect(self._on_analysis_completed)
        self.popup.analysis_failed.connect(self._on_analysis_failed)

        self.notifier = TrayNotifier(
            duration_ms=config.notification_duration_ms,
            enabled=config.enable_notifications,
            show_tray_icon=config.show_tray_icon,
        )
        self.notifier.activated.connect(self.toggle_window)

        self.hotkey: Optional[GlobalHotkey] = None
        self.toggle_hotkey: Optional[GlobalHotkey] = None
        self.quit_hotkey: Optional[GlobalHotkey] = None
        self._paused = False
        self._pending: List[str] = []
        self._custom_folder: Optional[str] = None
        self._common_enabled = False

        self._idle_timer = QTimer(self.app)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle_timeout)
        self._reset_idle_timer()

        self._watch_action = None
        self._stop_watch_action = None
        self._common_action = None
        self._pause_action = None
        self._startup_action = None

        self.bridge = _MonitorBridge()
        self.bridge.file_detected.connect(self._on_file_detected)
        self.popup.worker_finished.connect(self._drain_pending)
        self.popup.analysis_started.connect(lambda _path: self._reset_idle_timer())

        self._build_tray_menu()
        self._register_hotkey()

    # ---------------------------------------------------------------- startup --
    def _build_tray_menu(self) -> None:
        menu = self.notifier.menu
        self.notifier.add_action(
            f"Toggle window ({self.config.toggle_hotkey})", self.toggle_window
        )
        self.notifier.add_action(
            f"Analyze screenshot ({self.config.hotkey})", self.choose_screenshot
        )
        self.notifier.add_action(
            "Analyze clipboard image", self.analyze_clipboard
        )
        menu.addSeparator()

        self._watch_action = self.notifier.add_action(
            "Watch a folder\u2026", self.choose_watch_folder
        )
        self._stop_watch_action = self.notifier.add_action(
            "Stop watching folders", self.stop_watching
        )
        self._stop_watch_action.setEnabled(False)
        self._common_action = self.notifier.add_action(
            "Watch common screenshot folders", self.toggle_common_folders
        )
        self._common_action.setCheckable(True)

        self._pause_action = self.notifier.add_action(
            "Pause processing", self.toggle_pause
        )

        menu.addSeparator()
        self._startup_action = self.notifier.add_action(
            "Run at Windows login", self.toggle_startup
        )
        self._startup_action.setCheckable(True)
        self._startup_action.setChecked(startup.is_enabled())

        menu.addSeparator()
        self.notifier.add_action("Exit", self.quit)

        self._update_watch_actions()

    def _register_hotkey(self) -> None:
        try:
            self.hotkey = GlobalHotkey(self.config.hotkey)
            self.hotkey.register()
            self.hotkey.activated.connect(self._on_hotkey)
        except HotkeyError as exc:
            self.hotkey = None
            message = (
                f"{exc}\n\n"
                "You can change HOTKEY in your .env file (for example ctrl+alt+a). "
                "You can still open the window from the tray icon."
            )
            print(f"[hotkey] {message}", file=sys.stderr)
            QMessageBox.warning(None, "Shortcut not available", message)

        if getattr(self.config, "toggle_hotkey", None):
            try:
                self.toggle_hotkey = GlobalHotkey(self.config.toggle_hotkey)
                self.toggle_hotkey.register()
                self.toggle_hotkey.activated.connect(self.toggle_window)
            except HotkeyError as exc:
                self.toggle_hotkey = None
                print(f"[toggle_hotkey] Could not register {self.config.toggle_hotkey}: {exc}", file=sys.stderr)

        if getattr(self.config, "quit_hotkey", None):
            try:
                self.quit_hotkey = GlobalHotkey(self.config.quit_hotkey)
                self.quit_hotkey.register()
                self.quit_hotkey.activated.connect(self.quit)
            except HotkeyError as exc:
                self.quit_hotkey = None
                print(f"[quit_hotkey] Could not register {self.config.quit_hotkey}: {exc}", file=sys.stderr)

    # ----------------------------------------------------------------- timer --
    def _reset_idle_timer(self) -> None:
        """Reset the inactivity countdown to prevent auto-exit while active."""
        if getattr(self, "_idle_timer", None) and getattr(self.config, "auto_exit_minutes", 0) > 0:
            self._idle_timer.start(self.config.auto_exit_minutes * 60 * 1000)

    def _on_idle_timeout(self) -> None:
        """Automatically close the app after the inactivity period expires."""
        print(
            f"[idle] Inactive for {self.config.auto_exit_minutes} minutes. Auto-closing.",
            file=sys.stderr,
        )
        self.quit()

    def start(self) -> None:
        self._custom_folder = self.config.watch_folder
        self._common_enabled = bool(self.config.watch_common_folders)
        self._update_watch_actions()

        if self._custom_folder or self._common_enabled:
            self._apply_watch_set(announce=False)

        if not self.config.start_minimized:
            self.open_popup()

        hint = f"Press {self.config.toggle_hotkey} to toggle, or {self.config.hotkey} after a snip."
        self.notifier.notify(
            f"Running in the background. {hint}",
            title=f"{APP_NAME} is ready",
        )

    # ----------------------------------------------------------------- window --
    def open_popup(self) -> None:
        self._reset_idle_timer()
        if self.popup.isMinimized():
            self.popup.showNormal()
        if not getattr(self.popup, "_has_positioned", False):
            self.popup.position_bottom_right()
            self.popup._has_positioned = True
        self.popup.show()
        self.popup.raise_()
        self.popup.activateWindow()

    def toggle_window(self) -> None:
        """Toggle the popup window visibility system-wide."""
        self._reset_idle_timer()
        if self.popup.isVisible():
            self.popup.hide()
        else:
            if not getattr(self.popup, "_has_positioned", False):
                self.popup.position_bottom_right()
                self.popup._has_positioned = True
            if self.popup.isMinimized():
                self.popup.showNormal()
            else:
                self.popup.show()
            self.popup.raise_()

    def _on_hotkey(self) -> None:
        """Clipboard-first action: analyze a copied snip, else open the window."""
        self._reset_idle_timer()
        if self.popup.is_busy:
            self.open_popup()
            return

        if self.config.clipboard_on_hotkey:
            clipboard_image = self._read_clipboard_image(silent=True)
            if clipboard_image:
                self.popup.show_and_analyze(
                    clipboard_image,
                    source_label="Clipboard image",
                    cleanup_after=True,
                )
                return

        self.open_popup()

    def choose_screenshot(self) -> None:
        self._reset_idle_timer()
        try:
            file_path = screenshot_service.select_screenshot_file(self.popup)
        except ScreenshotError as exc:
            QMessageBox.warning(self.popup, "Cannot use this file", str(exc))
            return
        if not file_path:
            return
        if self.popup.is_busy:
            self.notifier.notify("An analysis is already running. Please wait.")
            return
        # Manual picks are always analyzed, even if the same file was used before.
        self.popup.show_and_analyze(file_path)

    def analyze_clipboard(self) -> None:
        self._reset_idle_timer()
        if self.popup.is_busy:
            self.notifier.notify("An analysis is already running. Please wait.")
            return

        clipboard_image = self._read_clipboard_image(silent=False)
        if not clipboard_image:
            self.notifier.notify(
                "No image found in the clipboard. Copy a snip first."
            )
            return

        self.popup.show_and_analyze(
            clipboard_image,
            source_label="Clipboard image",
            cleanup_after=True,
        )

    def _read_clipboard_image(self, silent: bool) -> Optional[str]:
        try:
            return screenshot_service.grab_clipboard_image()
        except ScreenshotError as exc:
            print(f"[clipboard] {exc}", file=sys.stderr)
            if not silent:
                QMessageBox.warning(self.popup, "Clipboard", str(exc))
            return None

    # --------------------------------------------------------------- watching --
    def choose_watch_folder(self) -> None:
        start_dir = self._custom_folder
        if not start_dir:
            pictures = Path.home() / "Pictures" / "Screenshots"
            start_dir = str(pictures if pictures.is_dir() else Path.home())

        folder = QFileDialog.getExistingDirectory(
            self.popup,
            "Choose a folder to watch for screenshots",
            start_dir,
        )
        if folder:
            self._custom_folder = folder
            self._apply_watch_set()

    def toggle_common_folders(self) -> None:
        enable = self._common_action.isChecked()
        if enable and not common_screenshot_folders():
            self._common_enabled = False
            self._update_watch_actions()
            QMessageBox.information(
                self.popup,
                "No screenshot folders found",
                "Pictures\\Screenshots and Desktop were not found. "
                "Use \"Watch a folder...\" instead.",
            )
            return

        self._common_enabled = enable
        self._apply_watch_set()

    def _watched_folders(self) -> List[str]:
        folders: List[str] = []
        if self._custom_folder:
            folders.append(self._custom_folder)
        if self._common_enabled:
            for folder in common_screenshot_folders():
                if folder.lower() not in {item.lower() for item in folders}:
                    folders.append(folder)
        return folders

    def _apply_watch_set(self, announce: bool = True) -> None:
        if self._custom_folder and not Path(self._custom_folder).is_dir():
            print(
                f"[watch] Watched folder no longer exists: {self._custom_folder}",
                file=sys.stderr,
            )
            self._custom_folder = None

        wanted = self._watched_folders()
        existing = [folder for folder in wanted if Path(folder).is_dir()]
        missing = [folder for folder in wanted if folder not in existing]

        for folder in missing:
            print(f"[watch] Skipping missing folder: {folder}", file=sys.stderr)

        if existing:
            try:
                screenshot_service.start_monitoring(
                    existing, self.bridge.file_detected.emit
                )
            except ScreenshotError as exc:
                screenshot_service.stop_monitoring()
                print(f"[watch] {exc}", file=sys.stderr)
                if announce:
                    QMessageBox.warning(
                        self.popup, "Cannot watch these folders", str(exc)
                    )
                self._update_watch_actions()
                return
        else:
            screenshot_service.stop_monitoring()

        self._update_watch_actions()

        if announce:
            if existing:
                self.notifier.notify(
                    f"Watching {len(existing)} folder(s). "
                    "New screenshots are analyzed automatically.",
                    title="Folder monitoring is on",
                )
            else:
                self.notifier.notify("No screenshot folders are being watched.")

    def stop_watching(self, notify_user: bool = True) -> None:
        self._custom_folder = None
        self._common_enabled = False
        self._pending.clear()
        screenshot_service.stop_monitoring()
        self._update_watch_actions()
        if notify_user:
            self.notifier.notify("Folder monitoring stopped.")

    def toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._pause_action is not None:
            self._pause_action.setText(
                "Resume processing" if self._paused else "Pause processing"
            )
        self._update_tooltip()
        if self._paused:
            self.notifier.notify(
                "Automatic processing paused. Manual analysis still works."
            )
        else:
            self.notifier.notify("Automatic processing resumed.")
            self._drain_pending()

    def _update_watch_actions(self) -> None:
        if self._watch_action is not None:
            self._watch_action.setText(
                "Change watched folder\u2026"
                if self._custom_folder
                else "Watch a folder\u2026"
            )
        if self._stop_watch_action is not None:
            self._stop_watch_action.setEnabled(
                bool(self._custom_folder or self._common_enabled)
            )
        if self._common_action is not None:
            self._common_action.setChecked(self._common_enabled)
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        state = "Paused" if self._paused else "Running"
        folders = self._watched_folders()
        if folders:
            listing = "\n".join(f"  {folder}" for folder in folders)
            text = f"{APP_NAME} - {state}\nWatching:\n{listing}"
        else:
            text = f"{APP_NAME} - {state}\nNo folder monitoring"
        self.notifier.set_tooltip(text)

    # -------------------------------------------------------------- processing --
    def _on_file_detected(self, file_path: str) -> None:
        if self._paused or self.popup.is_busy:
            self._enqueue(file_path)
            return
        self._analyze_file(file_path)

    def _analyze_file(self, file_path: str) -> None:
        if screenshot_service.is_already_processed(file_path):
            return
        if self.popup.is_busy:
            self._enqueue(file_path)
            return
        self.popup.show_and_analyze(file_path)

    def _enqueue(self, file_path: str) -> None:
        if file_path in self._pending:
            return
        self._pending.append(file_path)
        # Keep only the newest handful so a busy folder cannot grow forever.
        self._pending = self._pending[-10:]

    def _drain_pending(self) -> None:
        if self._paused:
            return
        while self._pending and not self.popup.is_busy:
            file_path = self._pending.pop(0)
            if screenshot_service.is_already_processed(file_path):
                continue
            if not Path(file_path).is_file():
                continue
            self._analyze_file(file_path)
            return

    def _on_analysis_completed(self, _text: str) -> None:
        if not self.popup.isVisible():
            self.notifier.notify(
                "Analysis complete. Click to view the result."
            )

    def _on_analysis_failed(self, _message: str) -> None:
        if not self.popup.isVisible():
            self.notifier.notify("Analysis failed. Click to see the details.")

    # ----------------------------------------------------------------- startup --
    def toggle_startup(self) -> None:
        wanted = self._startup_action.isChecked()
        try:
            startup.set_enabled(wanted)
        except startup.StartupError as exc:
            self._startup_action.setChecked(startup.is_enabled())
            QMessageBox.warning(self.popup, "Startup setting", str(exc))
            return
        self.notifier.notify(
            "The app will start with Windows." if wanted
            else "The app will no longer start with Windows."
        )

    # -------------------------------------------------------------------- quit --
    def quit(self) -> None:
        if getattr(self, "_idle_timer", None) is not None:
            self._idle_timer.stop()
        if self.hotkey is not None:
            self.hotkey.unregister()
            self.hotkey = None
        if self.toggle_hotkey is not None:
            self.toggle_hotkey.unregister()
            self.toggle_hotkey = None
        if getattr(self, "quit_hotkey", None) is not None:
            self.quit_hotkey.unregister()
            self.quit_hotkey = None
        screenshot_service.stop_monitoring()
        self.popup.shutdown(3000)
        self.popup.close()
        self.notifier.hide()
        self.app.quit()


def _single_instance_guard() -> bool:
    """Return False when another copy is already running."""
    global _mutex_handle
    kernel32 = ctypes.windll.kernel32
    kernel32.SetLastError(0)
    _mutex_handle = kernel32.CreateMutexW(
        None, False, "Local\\ScreenshotAIAssistantMutex"
    )
    return kernel32.GetLastError() != _ERROR_ALREADY_EXISTS


def main() -> int:
    app = create_app(quit_on_last_window_closed=False)
    app.setWindowIcon(build_app_icon())

    if not _single_instance_guard():
        QMessageBox.information(
            None,
            APP_NAME,
            "Screenshot AI Assistant is already running.\n"
            "Look for its icon in the system tray.",
        )
        return 0

    try:
        config = get_config()
    except ValueError as exc:
        QMessageBox.critical(None, "Configuration error", str(exc))
        return 1

    controller = ApplicationController(app, config)
    controller.start()

    exit_code = app.exec()
    controller.quit()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
