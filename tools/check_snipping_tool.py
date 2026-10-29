"""Checks for Windows Snipping Tool support.

Covers:
* clipboard image capture (what Win+Shift+S puts on the clipboard),
* cleanup of the temporary clipboard file,
* discovery of the folders Snipping Tool saves into,
* watching several folders at once.

Usage:
    python tools/check_snipping_tool.py
"""

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from screenshot_ai.screenshot_service import (  # noqa: E402
    ScreenshotService,
    common_screenshot_folders,
    remove_temp_file,
)


def make_qimage() -> QImage:
    image = QImage(240, 120, QImage.Format.Format_RGB32)
    image.fill(QColor("#2563eb"))
    painter = QPainter(image)
    painter.setPen(QColor("white"))
    painter.drawText(20, 60, "CLIPBOARD SNIP")
    painter.end()
    return image


def check_clipboard(app: QApplication) -> bool:
    clipboard = app.clipboard()
    mime = clipboard.mimeData()
    had_image = mime.hasImage()
    old_image = clipboard.image() if had_image else None
    old_text = clipboard.text() if mime.hasText() else ""

    try:
        clipboard.setImage(make_qimage())
        path = ScreenshotService().grab_clipboard_image()
        if not path:
            print("FAIL: clipboard image was not detected")
            return False

        temp_path = Path(path)
        print(f"clipboard image saved: {temp_path.name}")
        print(f"  in temp dir: {Path(tempfile.gettempdir()).resolve() in temp_path.parents}")
        print(f"  readable: {Image.open(temp_path).size}")
        remove_temp_file(path)
        print(f"  cleaned up: {not temp_path.exists()}")
        return not temp_path.exists()
    finally:
        if had_image and old_image is not None and not old_image.isNull():
            clipboard.setImage(old_image)
        elif old_text:
            clipboard.setText(old_text)
        else:
            clipboard.clear()


def check_multi_folder_watch() -> bool:
    root = Path(tempfile.mkdtemp())
    first = root / "one"
    second = root / "two"
    first.mkdir()
    second.mkdir()

    seen = []
    service = ScreenshotService()
    service.start_monitoring([str(first), str(second)], seen.append)
    try:
        Image.new("RGB", (80, 60), "green").save(first / "a.png")
        Image.new("RGB", (80, 60), "blue").save(second / "b.jpg")
        deadline = time.monotonic() + 6
        while len(seen) < 2 and time.monotonic() < deadline:
            time.sleep(0.1)
    finally:
        service.stop_monitoring()

    names = sorted(Path(item).name for item in seen)
    print(f"multi-folder events: {names}")
    return names == ["a.png", "b.jpg"]


def main() -> int:
    app = QApplication.instance() or QApplication([])

    folders = common_screenshot_folders()
    print("common screenshot folders:")
    for folder in folders:
        print(f"  {folder}")
    if not folders:
        print("  (none exist on this machine)")

    results = {
        "clipboard": check_clipboard(app),
        "multi-folder watch": check_multi_folder_watch(),
    }
    print("\nsummary:")
    for name, ok in results.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
