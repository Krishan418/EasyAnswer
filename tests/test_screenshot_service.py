import os
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from screenshot_ai.screenshot_service import (
    ScreenshotService,
    ScreenshotError,
    remove_temp_file,
)


class TestScreenshotService(unittest.TestCase):
    def setUp(self):
        self.service = ScreenshotService()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_validate_screenshot_valid(self):
        img_path = self.temp_path / "valid.png"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(img_path)

        validated = self.service.validate_screenshot(str(img_path))
        self.assertEqual(validated, img_path)

    def test_validate_screenshot_nonexistent(self):
        missing = self.temp_path / "missing.png"
        with self.assertRaises(ScreenshotError) as ctx:
            self.service.validate_screenshot(str(missing))
        self.assertIn("File not found", str(ctx.exception))

    def test_validate_screenshot_directory(self):
        sub_dir = self.temp_path / "subdir"
        sub_dir.mkdir()
        with self.assertRaises(ScreenshotError) as ctx:
            self.service.validate_screenshot(str(sub_dir))
        self.assertIn("Not a file", str(ctx.exception))

    def test_validate_screenshot_unsupported_format(self):
        txt_path = self.temp_path / "test.txt"
        txt_path.write_text("not an image")
        with self.assertRaises(ScreenshotError) as ctx:
            self.service.validate_screenshot(str(txt_path))
        self.assertIn("Unsupported format", str(ctx.exception))

    def test_validate_screenshot_corrupted(self):
        corrupted_path = self.temp_path / "bad.png"
        corrupted_path.write_bytes(b"not a valid png binary stream")
        with self.assertRaises(ScreenshotError) as ctx:
            self.service.validate_screenshot(str(corrupted_path))
        self.assertIn("Unreadable or corrupted image", str(ctx.exception))

    def test_hash_and_processed_tracking(self):
        img_path = self.temp_path / "hash_test.png"
        img = Image.new("RGB", (50, 50), color="red")
        img.save(img_path)

        file_hash = self.service.compute_file_hash(str(img_path))
        self.assertEqual(len(file_hash), 64)

        # Before marking
        self.assertFalse(self.service.is_already_processed(str(img_path)))

        # Mark processed
        self.service.mark_processed(str(img_path))
        self.assertTrue(self.service.is_already_processed(str(img_path)))

    def test_remove_temp_file(self):
        # 1. Allowed temporary file in temp directory with screenshot_ai_ prefix
        handle, temp_file_path = tempfile.mkstemp(prefix="screenshot_ai_", suffix=".png")
        os.close(handle)
        self.assertTrue(Path(temp_file_path).exists())

        remove_temp_file(temp_file_path)
        self.assertFalse(Path(temp_file_path).exists())

        # Calling again on deleted path should not raise
        remove_temp_file(temp_file_path)

        # 2. Guard test: non-matching prefix should NEVER be deleted
        other_file = self.temp_path / "user_important_file.png"
        other_file.write_text("should not delete")
        remove_temp_file(str(other_file))
        self.assertTrue(other_file.exists())



if __name__ == "__main__":
    unittest.main()
