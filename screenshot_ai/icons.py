"""Application icon provider for DeskLens."""

import sys
from pathlib import Path
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap


def build_app_icon(size: int = 64) -> QIcon:
    """Return the DeskLens app icon from assets, or fallback to programmatically drawn icon."""
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "assets" / "app.ico")
            candidates.append(Path(meipass) / "assets" / "logo.png")
            candidates.append(Path(meipass) / "app.ico")

    current_dir = Path(__file__).resolve().parent
    candidates.append(current_dir / "assets" / "app.ico")
    candidates.append(current_dir / "assets" / "logo.png")

    for icon_path in candidates:
        if icon_path.is_file():
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                return icon

    # Fallback: sleek dark tile with cyan-teal lens circle
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    margin = max(1.0, size * 0.04)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#0f172a"))  # Deep slate dark
    painter.drawRoundedRect(
        QRectF(margin, margin, size - 2 * margin, size - 2 * margin),
        size * 0.22,
        size * 0.22,
    )

    # Cyan ring
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("#00d2ff"), max(1.5, size * 0.08)))
    ring_margin = size * 0.20
    painter.drawEllipse(QRectF(ring_margin, ring_margin, size - 2 * ring_margin, size - 2 * ring_margin))

    painter.end()
    return QIcon(pixmap)
