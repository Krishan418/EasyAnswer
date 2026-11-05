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
        self.assertTrue(popup.result_view.font().bold())
        self.assertEqual(popup.result_view.font().pointSize(), 11)

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

    def test_extract_clean_answer(self):
        # Case 1: Already clean answer
        self.assertEqual(
            ResultPopup._extract_clean_answer("**Answer: C) 21**"),
            "**Answer: C) 21**",
        )
        # Case 2: Multi-line with reasoning before answer
        multi = "Step 1: Check prime\nStep 2: Conclude\n**Answer: C) 21**\nDone"
        self.assertEqual(
            ResultPopup._extract_clean_answer(multi),
            "**Answer: C) 21**",
        )
        # Case 3: Plain Answer: without asterisks
        self.assertEqual(
            ResultPopup._extract_clean_answer("Answer: B) 100"),
            "**Answer: B) 100**",
        )

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

    def test_preemption_when_new_analysis_starts(self):
        popup = ResultPopup()
        mock_worker1 = mock.MagicMock()
        mock_worker1.isRunning.return_value = True

        popup._worker = mock_worker1
        popup._current_image = "old.png"
        popup._cleanup_after = False

        with mock.patch("screenshot_ai.popup.AnalysisWorker") as MockWorkerClass, \
             mock.patch("screenshot_ai.popup.screenshot_service.validate_screenshot"):
            new_worker = mock.MagicMock()
            MockWorkerClass.return_value = new_worker

            popup.analyze_file("new.png")

            # Old worker should have its signals disconnected, interruption requested, and detached
            mock_worker1.requestInterruption.assert_called_once()
            # New worker should be created and started
            new_worker.start.assert_called_once()
            self.assertEqual(popup._current_image, "new.png")
