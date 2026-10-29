"""System tray icon and Windows notification helpers.

``QSystemTrayIcon`` is used because it gives us three things in one place:
a tray icon, native Windows notifications, and a ``messageClicked`` signal so
clicking the notification can open the result popup.
"""

from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .icons import build_app_icon

APP_NAME = "Screenshot AI Assistant"


class TrayNotifier(QObject):
    """Owns the tray icon, its menu, and the "analysis finished" toasts."""

    activated = Signal()

    def __init__(
        self,
        duration_ms: int = 4000,
        enabled: bool = True,
        show_tray_icon: bool = True,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._enabled = enabled
        self._show_tray_icon = show_tray_icon
        self._duration_ms = max(1000, int(duration_ms))
        self._available = QSystemTrayIcon.isSystemTrayAvailable()

        self._tray = QSystemTrayIcon(build_app_icon(), self)
        self._tray.setToolTip(APP_NAME)
        self._tray.messageClicked.connect(self.activated)
        self._tray.activated.connect(self._on_tray_activated)

        self._menu = QMenu()
        self._tray.setContextMenu(self._menu)

        if self._available and self._show_tray_icon:
            self._tray.show()

    # -------------------------------------------------------------- properties --
    @property
    def available(self) -> bool:
        return self._available

    @property
    def menu(self) -> QMenu:
        return self._menu

    @property
    def icon(self) -> QIcon:
        return build_app_icon()

    # ----------------------------------------------------------------- actions --
    def add_action(self, text: str, callback) -> QAction:
        action = QAction(text, self._menu)
        action.triggered.connect(callback)
        self._menu.addAction(action)
        return action

    def set_notifications_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def notify(
        self,
        message: str,
        title: str = APP_NAME,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Show a short native notification (no-op if unsupported/disabled/stealth)."""
        if not self._available or not self._enabled or not self._show_tray_icon:
            return
        timeout = self._duration_ms if duration_ms is None else max(1000, int(duration_ms))
        self._tray.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            timeout,
        )

    def set_tray_icon_visible(self, visible: bool) -> None:
        self._show_tray_icon = visible
        if visible and self._available:
            self._tray.show()
        else:
            self._tray.hide()

    def set_tooltip(self, text: str) -> None:
        self._tray.setToolTip(text)

    def hide(self) -> None:
        self._tray.hide()

    # ------------------------------------------------------------------ events --
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.activated.emit()
