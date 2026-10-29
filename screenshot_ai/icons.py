"""Programmatically drawn application icon.

Drawing the icon in code keeps the repository free of binary files and means
PyInstaller does not have to bundle an extra asset for the tray icon.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap


def build_app_icon(size: int = 64) -> QIcon:
    """Return the app icon (blue rounded square with a white 'AI')."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Rounded blue tile
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#2563eb"))
    margin = max(1.0, size * 0.03)
    painter.drawRoundedRect(
        QRectF(margin, margin, size - 2 * margin, size - 2 * margin),
        size * 0.24,
        size * 0.24,
    )

    # Small "screen" ring to hint at screenshots
    ring_margin = size * 0.18
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(255, 255, 255, 90), max(1.0, size * 0.035)))
    painter.drawRoundedRect(
        QRectF(ring_margin, ring_margin, size - 2 * ring_margin, size - 2 * ring_margin),
        size * 0.12,
        size * 0.12,
    )

    # Letters
    font = QFont("Segoe UI", max(6, int(size * 0.34)))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(
        QRectF(0, size * 0.02, size, size),
        Qt.AlignmentFlag.AlignCenter,
        "AI",
    )
    painter.end()

    return QIcon(pixmap)
