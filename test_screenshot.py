#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from screenshot_ai.screenshot_service import screenshot_service, ScreenshotError


def test_validation():
    print("Testing screenshot validation...")
    if len(sys.argv) < 2:
        print("Usage: python test_screenshot.py <path_to_image>")
        return
    try:
        path = screenshot_service.validate_screenshot(sys.argv[1])
        print(f"Valid: {path}")
        h = screenshot_service.compute_file_hash(sys.argv[1])
        print(f"Hash: {h[:16]}...")
        print(f"Already processed: {screenshot_service.is_already_processed(sys.argv[1])}")
        screenshot_service.mark_processed(sys.argv[1])
        print(f"After marking - Already processed: {screenshot_service.is_already_processed(sys.argv[1])}")
    except ScreenshotError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_validation()
