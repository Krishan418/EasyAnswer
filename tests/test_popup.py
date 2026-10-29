import os
import unittest
from unittest import mock

# Set offscreen platform for headless Qt testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from screenshot_ai.popup import AnalysisWorker, ResultPopup, create_app


class TestPopup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def test_popup_init_compact(self):
        popup = ResultPopup()
        # Ensure default size is compact
        self.assertLessEqual(popup.width(), 360)
        self.assertLessEqual(popup.height(), 220)
        self.assertTrue(popup.copy_button is not None)
        self.assertFalse(popup.copy_button.isEnabled())
        self.assertFalse(popup.progress_bar.isVisible())

    def test_position_bottom_right(self):
        popup = ResultPopup()
        # Should not raise exception
        popup.position_bottom_right()
        self.assertGreater(popup.x(), 0)
        self.assertGreater(popup.y(), 0)

    def test_on_chunk_received(self):
        popup = ResultPopup()
        self.assertEqual(popup.last_result, "")
        popup._on_chunk_received("**Answer: Option A**\n")
        self.assertEqual(popup.last_result, "**Answer: Option A**\n")
        self.assertTrue(popup.copy_button.isEnabled())

        # Second chunk
        popup._on_chunk_received("• Detailed reason")
        self.assertEqual(popup.last_result, "**Answer: Option A**\n• Detailed reason")

    def test_analysis_worker_streaming(self):
        mock_service = mock.MagicMock()
        mock_service.analyze_image_stream.side_effect = lambda path, callback: (
            callback("Option A"),
            "Option A",
        )[1]

        worker = AnalysisWorker("test.png", service=mock_service)
        chunks = []
        worker.chunk_received.connect(chunks.append)
        worker.run()

        self.assertEqual(chunks, ["Option A"])
