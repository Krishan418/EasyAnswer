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

    @mock.patch("screenshot_ai.app.GlobalHotkey")
    def test_auto_show_popup_false_keeps_popup_hidden_on_hotkey(self, mock_hotkey):
        config = Config(
            auto_show_popup=False,
            clipboard_on_hotkey=True,
            show_tray_icon=False,
        )
        controller = ApplicationController(self.app, config)
        self.assertFalse(controller.popup.isVisible())

        # Mock clipboard image
        with mock.patch.object(controller, "_read_clipboard_image", return_value="dummy_img.png"):
            with mock.patch.object(controller.popup, "analyze_file") as mock_analyze:
                with mock.patch.object(controller.popup, "show_and_analyze") as mock_show_analyze:
                    controller._on_hotkey()
                    mock_analyze.assert_called_once_with(
                        "dummy_img.png",
                        source_label="Clipboard image",
                        cleanup_after=True,
                    )
                    mock_show_analyze.assert_not_called()
                    self.assertFalse(controller.popup.isVisible())

    def test_payload_transformation_reversibility(self):
        from screenshot_ai.config import _transform_payload
        raw = b"NVIDIA_API_KEY=nvapi-secret123\nPRIMARY_PROVIDER=nvidia"
        encrypted = _transform_payload(raw)
        self.assertNotEqual(raw, encrypted)
        self.assertNotIn(b"nvapi", encrypted)
        decrypted = _transform_payload(encrypted)
        self.assertEqual(raw, decrypted)

    def test_debugger_guard(self):
        from screenshot_ai.app import _check_debugger_present
        # Should execute cleanly and return a boolean
        res = _check_debugger_present()
        self.assertIsInstance(res, bool)

    @mock.patch("screenshot_ai.app.GlobalHotkey")
    def test_start_keeps_popup_hidden_in_stealth(self, mock_hotkey):
        config = Config(
            auto_show_popup=False,
            start_minimized=True,
            show_tray_icon=False,
            enable_notifications=False,
        )
        controller = ApplicationController(self.app, config)
        controller.start()
        self.assertFalse(controller.popup.isVisible())
