import os
import unittest
from unittest import mock

from screenshot_ai.config import _env_bool, _env_int, get_config, Config


class TestConfig(unittest.TestCase):
    def test_env_bool(self):
        with mock.patch.dict(os.environ, {"TEST_BOOL": "true"}):
            self.assertTrue(_env_bool("TEST_BOOL", False))
        with mock.patch.dict(os.environ, {"TEST_BOOL": "1"}):
            self.assertTrue(_env_bool("TEST_BOOL", False))
        with mock.patch.dict(os.environ, {"TEST_BOOL": "yes"}):
            self.assertTrue(_env_bool("TEST_BOOL", False))
        with mock.patch.dict(os.environ, {"TEST_BOOL": "false"}):
            self.assertFalse(_env_bool("TEST_BOOL", True))
        with mock.patch.dict(os.environ, {"TEST_BOOL": "0"}):
            self.assertFalse(_env_bool("TEST_BOOL", True))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(_env_bool("UNSET_KEY", True))
            self.assertFalse(_env_bool("UNSET_KEY", False))

    def test_env_int(self):
        with mock.patch.dict(os.environ, {"TEST_INT": "5000"}):
            self.assertEqual(_env_int("TEST_INT", 1000), 5000)
        with mock.patch.dict(os.environ, {"TEST_INT": "not_an_int"}):
            self.assertEqual(_env_int("TEST_INT", 1000), 1000)
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_env_int("UNSET_INT", 4000), 4000)

    def test_get_config_missing_api_key_raises(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=True):
            with mock.patch("screenshot_ai.config._get_default_key", return_value=""):
                with self.assertRaises(ValueError) as ctx:
                    get_config()
                self.assertIn("GEMINI_API_KEY is not set", str(ctx.exception))

    def test_get_config_fallback_to_default_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("screenshot_ai.config._get_default_key", return_value="fallback_key_abc"):
                cfg = get_config()
                self.assertEqual(cfg.gemini_api_key, "fallback_key_abc")


    def test_get_config_valid(self):
        env_vars = {
            "GEMINI_API_KEY": "test_fake_api_key_123",
            "GEMINI_MODEL": "gemini-test-model",
            "HOTKEY": "ctrl+alt+a",
            "TOGGLE_HOTKEY": "ctrl+~",
            "QUIT_HOTKEY": "ctrl+shift+q",
            "SHOW_TRAY_ICON": "true",
            "AUTO_EXIT_MINUTES": "20",
            "ENABLE_NOTIFICATIONS": "false",
            "NOTIFICATION_DURATION_MS": "3000",
            "WATCH_FOLDER": "C:\\Screenshots",
            "START_MINIMIZED": "true",
            "CLIPBOARD_ON_HOTKEY": "false",
            "WATCH_COMMON_FOLDERS": "true",
            "GROK_API_KEY": "xai-test-key",
            "GROK_MODEL": "grok-2-vision-1212",
        }
        with mock.patch.dict(os.environ, env_vars, clear=True):
            cfg = get_config()
            self.assertEqual(cfg.gemini_api_key, "test_fake_api_key_123")
            self.assertEqual(cfg.gemini_model, "gemini-test-model")
            self.assertEqual(cfg.hotkey, "ctrl+alt+a")
            self.assertEqual(cfg.toggle_hotkey, "ctrl+~")
            self.assertEqual(cfg.quit_hotkey, "ctrl+shift+q")
            self.assertTrue(cfg.show_tray_icon)
            self.assertEqual(cfg.auto_exit_minutes, 20)
            self.assertFalse(cfg.enable_notifications)
            self.assertEqual(cfg.notification_duration_ms, 3000)
            self.assertEqual(cfg.watch_folder, "C:\\Screenshots")
            self.assertTrue(cfg.start_minimized)
            self.assertFalse(cfg.clipboard_on_hotkey)
            self.assertTrue(cfg.watch_common_folders)
            self.assertEqual(cfg.grok_api_key, "xai-test-key")
            self.assertEqual(cfg.grok_model, "grok-2-vision-1212")


if __name__ == "__main__":
    unittest.main()
