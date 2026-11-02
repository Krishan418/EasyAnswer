import os
from pathlib import Path
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

    def test_get_config_defaults(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = get_config()
            self.assertEqual(cfg.primary_provider, "ovh")
            self.assertTrue(cfg.enable_ovh)
            self.assertEqual(cfg.ovh_model, "Qwen2.5-VL-72B-Instruct")
            self.assertEqual(cfg.hotkey, "ctrl+shift+s")
            self.assertEqual(cfg.auto_exit_minutes, 0)
            self.assertTrue(cfg.auto_show_popup)

    def test_load_env_from_meipass(self):
        import tempfile
        import sys
        from screenshot_ai.config import _load_env

        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("PRIMARY_PROVIDER=openrouter\nOPENROUTER_MODEL=test_model\n", encoding="utf-8")
            with mock.patch.object(sys, "frozen", True, create=True):
                with mock.patch.object(sys, "_MEIPASS", tmpdir, create=True):
                    with mock.patch.dict(os.environ, {}, clear=True):
                        _load_env()
                        self.assertEqual(os.getenv("PRIMARY_PROVIDER"), "openrouter")
                        self.assertEqual(os.getenv("OPENROUTER_MODEL"), "test_model")

    def test_load_env_from_obfuscated_system_dat(self):
        import tempfile
        import sys
        from screenshot_ai.config import _load_env

        with tempfile.TemporaryDirectory() as tmpdir:
            dat_file = Path(tmpdir) / "system.dat"
            content = b"PRIMARY_PROVIDER=ovh\nENABLE_OVH=true\n"
            key = b"EA_RUNTIME_SECRET_KEY_v2"
            obfuscated = bytes(b ^ key[i % len(key)] for i, b in enumerate(content))
            dat_file.write_bytes(obfuscated)

            with mock.patch.object(sys, "frozen", True, create=True):
                with mock.patch.object(sys, "_MEIPASS", tmpdir, create=True):
                    with mock.patch.dict(os.environ, {}, clear=True):
                        _load_env()
                        self.assertEqual(os.getenv("PRIMARY_PROVIDER"), "ovh")
                        self.assertEqual(os.getenv("ENABLE_OVH"), "true")

    def test_get_config_valid(self):
        env_vars = {
            "PRIMARY_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "sk-or-test-key",
            "OPENROUTER_MODEL": "nvidia/nemotron-test",
            "GLM_API_KEY": "test-glm-key",
            "GLM_MODEL": "glm-4.6v",
            "GROQ_API_KEY": "gsk-test-key",
            "GROQ_MODEL": "llama-3.2-vision",
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
            "POPUP_WIDTH": "300",
            "POPUP_HEIGHT": "100",
            "POPUP_OPACITY": "0.85",
        }
        with mock.patch.dict(os.environ, env_vars, clear=True):
            cfg = get_config()
            self.assertEqual(cfg.primary_provider, "openrouter")
            self.assertEqual(cfg.openrouter_api_key, "sk-or-test-key")
            self.assertEqual(cfg.openrouter_model, "nvidia/nemotron-test")
            self.assertEqual(cfg.glm_api_key, "test-glm-key")
            self.assertEqual(cfg.glm_model, "glm-4.6v")
            self.assertEqual(cfg.groq_api_key, "gsk-test-key")
            self.assertEqual(cfg.groq_model, "llama-3.2-vision")
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
            self.assertEqual(cfg.popup_width, 300)
            self.assertEqual(cfg.popup_height, 100)
            self.assertEqual(cfg.popup_opacity, 0.85)


if __name__ == "__main__":
    unittest.main()
