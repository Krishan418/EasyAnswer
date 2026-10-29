"""PySide6 popup window for displaying Gemini analysis results."""

import atexit
import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .gemini_service import GeminiService, GeminiServiceError
from .icons import build_app_icon
from .screenshot_service import (
    ScreenshotError,
    remove_temp_file,
    screenshot_service,
)


# Keep finished-but-still-running workers alive until the process exits, so Qt
# never destroys a running QThread during shutdown.
_ORPHANED_WORKERS: list = []
_hard_exit_registered = False


def _register_hard_exit() -> None:
    """Last-resort clean exit if a network call outlives shutdown."""
    global _hard_exit_registered
    if not _hard_exit_registered:
        atexit.register(lambda: os._exit(0))
        _hard_exit_registered = True


POPUP_STYLESHEET = """
QDialog {
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
}
QLabel#titleLabel {
    color: #0f172a;
    font-size: 11px;
    font-weight: 700;
}
QLabel#subtitleLabel {
    color: #64748b;
    font-size: 9px;
}
QProgressBar#progressBar {
    border: none;
    background-color: #e2e8f0;
    height: 2px;
    border-radius: 1px;
}
QProgressBar#progressBar::chunk {
    background-color: #2563eb;
    border-radius: 1px;
}
QTextBrowser {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 5px;
    padding: 6px 8px;
    color: #0f172a;
    font-size: 11px;
    selection-background-color: #bfdbfe;
}
QPushButton {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 2px 7px;
    color: #334155;
    font-size: 10px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #f1f5f9;
    border-color: #94a3b8;
}
QPushButton:pressed {
    background-color: #e2e8f0;
}
QPushButton:disabled {
    color: #cbd5e1;
    border-color: #f1f5f9;
}
QPushButton#closeButton {
    background-color: transparent;
    border: none;
    color: #94a3b8;
    font-size: 14px;
    font-weight: bold;
    padding: 0px;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
    border-radius: 9px;
}
QPushButton#closeButton:hover {
    background-color: #fee2e2;
    color: #ef4444;
}
QLabel#statusLabel {
    color: #2563eb;
    font-size: 9px;
}
QLabel#errorLabel {
    color: #dc2626;
    font-size: 9px;
}
"""



class AnalysisWorker(QThread):
    """Runs the Gemini analysis off the UI thread with real-time streaming."""

    chunk_received = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, image_path: str, service: Optional[GeminiService] = None):
        super().__init__()
        self.image_path = image_path
        self.service = service

    def run(self) -> None:
        try:
            service = self.service or GeminiService()
            result = service.analyze_image_stream(
                self.image_path,
                callback=self.chunk_received.emit,
            )
            self.finished_ok.emit(result)
        except GeminiServiceError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - surface anything to the UI
            self.failed.emit(f"Unexpected error: {exc}")


class ResultPopup(QDialog):
    """Compact floating popup that shows the AI analysis."""

    analysis_started = Signal(str)
    analysis_completed = Signal(str)
    analysis_failed = Signal(str)
    worker_finished = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._worker: Optional[AnalysisWorker] = None
        self._current_image: Optional[str] = None
        self._last_result: str = ""
        self._cleanup_after = False
        self._has_positioned = False

        self.setWindowTitle("EasyAnswer")
        self.setWindowIcon(build_app_icon())
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet(POPUP_STYLESHEET)
        self.resize(340, 180)
        self.setMinimumSize(250, 120)

        self._build_ui()
        self._reset_view()

    # ------------------------------------------------------------------ UI --
    def position_bottom_right(self) -> None:
        """Position window neatly at the bottom-right corner above taskbar."""
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        margin = 16
        x = geo.right() - self.width() - margin
        y = geo.bottom() - self.height() - margin
        self.move(x, y)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        """Press Esc to instantly close the popup."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(5)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)

        self.title_label = QLabel("EasyAnswer")
        self.title_label.setObjectName("titleLabel")

        self.subtitle_label = QLabel("Ready")
        self.subtitle_label.setObjectName("subtitleLabel")
        self.subtitle_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)
        header.addLayout(title_box, 1)

        self.analyze_button = QPushButton("Pick\u2026")
        self.analyze_button.setToolTip("Select an image file to analyze")
        self.analyze_button.clicked.connect(self.choose_and_analyze)
        header.addWidget(self.analyze_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.copy_button = QPushButton("Copy")
        self.copy_button.clicked.connect(self.copy_result)
        self.copy_button.setEnabled(False)
        header.addWidget(self.copy_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.close_button = QPushButton("\u00d7")
        self.close_button.setObjectName("closeButton")
        self.close_button.setToolTip("Close (Esc)")
        self.close_button.clicked.connect(self.close)
        header.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)

        root.addLayout(header)

        # Thin animated progress bar for loading
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        # Status / error strip
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setVisible(False)
        root.addWidget(self.status_label)

        # Result area
        self.result_view = QTextBrowser()
        self.result_view.setOpenExternalLinks(True)
        self.result_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self.result_view, 1)

    # ---------------------------------------------------------------- state --
    def _reset_view(self) -> None:
        self.result_view.clear()
        self.result_view.setPlaceholderText(
            "Copy a snip with Win+Shift+S, then press Ctrl+Shift+S.\n"
            "The direct answer will appear here instantly."
        )
        self.copy_button.setEnabled(False)
        self.analyze_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._set_status(None)
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.analyze_button.setEnabled(not busy)
        self.copy_button.setEnabled(not busy and bool(self._last_result))
        if busy:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setVisible(True)
            self.result_view.setHtml(
                "<p style='color:#64748b; font-size:11px;'>⚡ Analyzing screenshot with Gemini&hellip;</p>"
            )
        else:
            self.progress_bar.setVisible(False)

    def _set_status(self, message: Optional[str], error: bool = False) -> None:

        if not message:
            self.status_label.setVisible(False)
            self.status_label.setText("")
            return
        self.status_label.setObjectName("errorLabel" if error else "statusLabel")
        self.status_label.setText(message)
        self.status_label.setVisible(True)
        # Re-apply stylesheet so the objectName change takes effect
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    # -------------------------------------------------------------- actions --
    def choose_and_analyze(self) -> None:
        file_filter = (
            "Images (*.png *.jpg *.jpeg);;"
            "PNG (*.png);;"
            "JPEG (*.jpg *.jpeg);;"
            "All Files (*.*)"
        )
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Screenshot", "", file_filter
        )
        if file_path:
            self.analyze_file(file_path)

    @Slot(str)
    def analyze_file(
        self,
        file_path: str,
        source_label: Optional[str] = None,
        cleanup_after: bool = False,
    ) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        try:
            screenshot_service.validate_screenshot(file_path)
        except ScreenshotError as exc:
            if cleanup_after:
                remove_temp_file(file_path)
            self._last_result = ""
            self.result_view.setHtml(
                f"<p style='color:#b91c1c;'><b>Cannot use this file.</b><br>{_html_escape(str(exc))}</p>"
            )
            self._set_status(str(exc), error=True)
            self._set_busy(False)
            return

        self._current_image = file_path
        self._last_result = ""
        self._cleanup_after = cleanup_after
        self.subtitle_label.setText(source_label or _short_filename(file_path))
        self.subtitle_label.setToolTip(file_path)
        self._set_status("Uploading image to Google Gemini\u2026")
        self._set_busy(True)

        self._worker = AnalysisWorker(file_path)
        self._worker.chunk_received.connect(self._on_chunk_received)
        self._worker.finished_ok.connect(self._on_analysis_ok)
        self._worker.failed.connect(self._on_analysis_failed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()
        self.analysis_started.emit(file_path)

    def analyze_current_again(self) -> None:
        if self._current_image:
            self.analyze_file(self._current_image)

    @property
    def last_result(self) -> str:
        return self._last_result

    @property
    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def show_and_analyze(
        self,
        file_path: str,
        source_label: Optional[str] = None,
        cleanup_after: bool = False,
    ) -> None:
        """Show the popup at bottom-right without focus stealing and stream results."""
        if not self.isVisible() or not self._has_positioned:
            self.position_bottom_right()
            self._has_positioned = True
        self.show()
        self.raise_()
        self.analyze_file(
            file_path, source_label=source_label, cleanup_after=cleanup_after
        )

    def _cleanup_temp(self) -> None:
        if self._cleanup_after:
            remove_temp_file(self._current_image)
            self._cleanup_after = False

    @Slot(str)
    def _on_chunk_received(self, chunk: str) -> None:
        if not self._last_result:
            self.result_view.clear()
            self.progress_bar.setVisible(False)
            self._set_status("Streaming response\u2026")
        self._last_result += chunk
        self.result_view.setMarkdown(self._last_result)
        self.result_view.moveCursor(QTextCursor.MoveOperation.End)
        self.copy_button.setEnabled(True)

    @Slot(str)
    def _on_analysis_ok(self, text: str) -> None:
        self._last_result = text
        self.progress_bar.setVisible(False)
        self.result_view.setMarkdown(text)
        self.result_view.moveCursor(QTextCursor.MoveOperation.Start)
        self._set_status("Done")
        screenshot_service.mark_processed(self._current_image or "")
        self.copy_button.setEnabled(True)
        self._cleanup_temp()
        self.analysis_completed.emit(text)

    @Slot(str)
    def _on_analysis_failed(self, message: str) -> None:
        self._last_result = ""
        self.progress_bar.setVisible(False)
        self.result_view.setHtml(
            f"<p style='color:#b91c1c; font-size:11px;'><b>Analysis failed.</b><br>{_html_escape(message)}</p>"
        )
        self._set_status(message, error=True)
        self._cleanup_temp()
        self.analysis_failed.emit(message)

    @Slot()
    def _on_worker_finished(self) -> None:
        self._worker = None
        self._set_busy(False)
        self.copy_button.setEnabled(bool(self._last_result))
        self.worker_finished.emit()

    def copy_result(self) -> None:
        if not self._last_result:
            return
        QGuiApplication.clipboard().setText(self._last_result)
        original = self.copy_button.text()
        self.copy_button.setText("Copied!")
        self._set_status("Result copied to clipboard")
        # Restore label after a short delay without blocking the UI
        QTimer.singleShot(1500, lambda: self.copy_button.setText(original))

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        self.raise_()

    def shutdown(self, timeout_ms: int = 3000) -> None:
        """Ask the worker to stop and wait briefly; never destroy it running."""
        worker = self._worker
        self._worker = None
        if worker is None:
            return
        if worker.isRunning():
            worker.requestInterruption()
            if not worker.wait(timeout_ms):
                # The network call cannot be cancelled; keep the thread alive
                # until the interpreter exits instead of aborting on teardown.
                _ORPHANED_WORKERS.append(worker)
                _register_hard_exit()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(1500)
        super().closeEvent(event)


# ----------------------------------------------------------------- helpers --
def _short_filename(path: str, limit: int = 48) -> str:
    name = Path(path).name
    if len(name) <= limit:
        return name
    return name[: limit - 1] + "\u2026"


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )


def create_app(
    argv: Optional[list] = None, quit_on_last_window_closed: bool = True
) -> QApplication:
    """Create (or reuse) the QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Screenshot AI Assistant")
    app.setQuitOnLastWindowClosed(quit_on_last_window_closed)
    return app


def run_popup(image_path: Optional[str] = None) -> int:
    """Standalone helper to open the popup (used for testing)."""
    app = create_app()
    popup = ResultPopup()
    popup.show()
    if image_path:
        popup.analyze_file(image_path)
    return app.exec()


if __name__ == "__main__":
    image = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(run_popup(image))
