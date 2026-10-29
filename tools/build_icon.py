"""Generate app.ico for Windows packaging using PySide6 and Pillow."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import io
from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication

from screenshot_ai.icons import build_app_icon


def generate_ico(output_path: Path):
    app = QApplication.instance() or QApplication([])

    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for sz in sizes:
        icon = build_app_icon(size=sz)
        pixmap = icon.pixmap(sz, sz)

        # Convert QPixmap to PNG bytes
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        png_bytes = bytes(buffer.data())
        buffer.close()

        img = Image.open(io.BytesIO(png_bytes))
        images.append(img)

    # The largest image saves the .ico containing all sizes
    output_path.parent.mkdir(parents=True, exist_ok=True)
    images[-1].save(
        output_path,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=images[:-1],
    )
    print(f"Icon generated successfully at: {output_path}")


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "screenshot_ai" / "assets" / "app.ico"
    generate_ico(target)
