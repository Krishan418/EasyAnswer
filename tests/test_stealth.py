import os
import unittest
from unittest import mock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from screenshot_ai.config import Config
from screenshot_ai.notifications import TrayNotifier
from screenshot_ai.popup import create_app
from screenshot_ai.app import ApplicationController


class TestStealthAndTimer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def test_tray_stealth_hidden(self):
        notifier = TrayNotifier(show_tray_icon=False)
        self.assertFalse(notifier._tray.isVisible())

        # Test set_tray_icon_visible
        notifier.set_tray_icon_visible(True)
        # In headless offscreen, isVisible may be false, but internal flag is updated
        self.assertTrue(notifier._show_tray_icon)

        notifier.set_tray_icon_visible(False)
        self.assertFalse(notifier._show_tray_icon)

    @mock.patch("screenshot_ai.app.GlobalHotkey")
    def test_idle_timer_reset_and_timeout(self, mock_hotkey):
        config = Config(
            gemini_api_key="test_key",
            quit_hotkey="ctrl+shift+q",
            show_tray_icon=False,
            auto_exit_minutes=15,
        )
        controller = ApplicationController(self.app, config)
        self.assertTrue(controller._idle_timer.isActive())
        self.assertEqual(controller._idle_timer.interval(), 15 * 60 * 1000)

        # Trigger reset
        controller._reset_idle_timer()
        self.assertTrue(controller._idle_timer.isActive())

        # Test timeout triggers quit
        with mock.patch.object(controller, "quit") as mock_quit:
            controller._on_idle_timeout()
            mock_quit.assert_called_once()
