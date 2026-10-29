import unittest

from screenshot_ai.hotkey import (
    parse_hotkey,
    HotkeyError,
    MOD_CONTROL,
    MOD_SHIFT,
    MOD_ALT,
    MOD_WIN,
)


class TestHotkey(unittest.TestCase):
    def test_parse_valid_hotkeys(self):
        # ctrl+shift+s
        mods, vk = parse_hotkey("ctrl+shift+s")
        self.assertEqual(mods, MOD_CONTROL | MOD_SHIFT)
        self.assertEqual(vk, ord("S"))

        # alt+enter
        mods, vk = parse_hotkey("alt+enter")
        self.assertEqual(mods, MOD_ALT)
        self.assertEqual(vk, 0x0D)

        # win+f5
        mods, vk = parse_hotkey("win+f5")
        self.assertEqual(mods, MOD_WIN)
        self.assertEqual(vk, 0x74)  # VK_F5 is 0x70 + 4 = 0x74

        # ctrl+~ (tilde)
        mods, vk = parse_hotkey("ctrl+~")
        self.assertEqual(mods, MOD_CONTROL)
        self.assertEqual(vk, 0xC0)

        # ctrl+` (grave)
        mods, vk = parse_hotkey("ctrl+`")
        self.assertEqual(mods, MOD_CONTROL)
        self.assertEqual(vk, 0xC0)

        # ctrl+tilde
        mods, vk = parse_hotkey("ctrl+tilde")
        self.assertEqual(mods, MOD_CONTROL)
        self.assertEqual(vk, 0xC0)

    def test_parse_invalid_hotkeys(self):
        # Empty
        with self.assertRaises(HotkeyError):
            parse_hotkey("")

        # No modifiers
        with self.assertRaises(HotkeyError):
            parse_hotkey("s")

        # Unknown modifier
        with self.assertRaises(HotkeyError):
            parse_hotkey("magic+s")

        # Multiple keys
        with self.assertRaises(HotkeyError):
            parse_hotkey("ctrl+shift+a+b")


if __name__ == "__main__":
    unittest.main()
