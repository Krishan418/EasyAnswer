"""Manual end-to-end check: draw a fake MCQ screenshot and analyze it.

Usage:
    python tools/check_gemini.py [model]
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from screenshot_ai.gemini_service import GeminiService, GeminiServiceError  # noqa: E402


def _load_font(size: int):
    for candidate in (
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build_sample(path: str) -> None:
    image = Image.new("RGB", (760, 280), "white")
    draw = ImageDraw.Draw(image)
    lines = [
        "Practice question:",
        "Which planet is known as the Red Planet?",
        "A) Venus    B) Mars    C) Jupiter    D) Saturn",
    ]
    y = 24
    for index, line in enumerate(lines):
        draw.text((24, y), line, fill="black", font=_load_font(22 if index else 18))
        y += 48
    image.save(path)


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else "gemini-3.5-flash"
    sample = os.path.join(tempfile.mkdtemp(), "mcq.png")
    build_sample(sample)
    print(f"Sample: {sample}")
    print(f"Model:  {model}")
    try:
        text = GeminiService(model=model).analyze_image(sample)
    except GeminiServiceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"RESULT LENGTH: {len(text)}")
    print(text[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
