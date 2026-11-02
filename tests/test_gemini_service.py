import tempfile
import unittest
from pathlib import Path
from unittest import mock
from PIL import Image

from screenshot_ai.gemini_service import (
    GeminiService,
    GeminiServiceError,
)


class TestGeminiService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        GeminiService._failed_providers.clear()

    def tearDown(self):
        self.temp_dir.cleanup()
        GeminiService._failed_providers.clear()

    def test_init_defaults(self):
        service = GeminiService(primary_provider="ovh", enable_ovh=True)
        self.assertEqual(service.primary_provider, "ovh")
        self.assertTrue(service.enable_ovh)
        self.assertEqual(service.ovh_model, "Qwen2.5-VL-72B-Instruct")

    def test_ovh_as_primary_provider(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(
            primary_provider="ovh",
            enable_ovh=True,
        )
        with mock.patch.object(service, "_analyze_with_openai_compatible", return_value="**Answer: Option B** (Queue)") as mock_ovh:
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "**Answer: Option B** (Queue)")
            mock_ovh.assert_called_once()
            args, kwargs = mock_ovh.call_args
            self.assertEqual(kwargs.get("provider_name"), "OVHcloud Kepler")
            self.assertEqual(kwargs.get("model"), "Qwen2.5-VL-72B-Instruct")
            self.assertIsNone(kwargs.get("api_key"))

    def test_openrouter_as_primary_provider(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(
            primary_provider="openrouter",
            openrouter_api_key="sk-or-test-key",
            openrouter_model="nvidia/nemotron-3.5-super-vl:free",
        )
        with mock.patch.object(service, "_analyze_with_openai_compatible", return_value="**Answer: Option A**") as mock_or:
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "**Answer: Option A**")
            mock_or.assert_called_once()
            args, kwargs = mock_or.call_args
            self.assertEqual(kwargs.get("provider_name"), "OpenRouter")
            self.assertEqual(kwargs.get("api_key"), "sk-or-test-key")
            self.assertEqual(kwargs.get("model"), "nvidia/nemotron-3.5-super-vl:free")

    def test_openrouter_model_auto_fallback(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(
            primary_provider="openrouter",
            openrouter_api_key="sk-or-v1-dummy",
            openrouter_model="nvidia/nemotron-custom",
        )

        calls = []
        def side_effect(*args, **kwargs):
            model = kwargs.get("model")
            calls.append(model)
            if model != "openrouter/free":
                raise Exception("429 Rate Limit on primary model")
            return "Option A (Free Router)"

        with mock.patch.object(service, "_analyze_with_openai_compatible", side_effect=side_effect):
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "Option A (Free Router)")
            self.assertIn("openrouter/free", calls)

    def test_failover_to_ovh_when_primary_fails(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(
            primary_provider="groq",
            groq_api_key="expired_groq_key",
            enable_ovh=True,
        )

        def mock_call(*args, **kwargs):
            p_name = kwargs.get("provider_name")
            if "Groq" in p_name:
                raise Exception("403 Forbidden")
            elif "OVH" in p_name:
                return "**Answer: Option D** (OVH Fallback)"
            raise Exception("Unknown provider")

        with mock.patch.object(service, "_analyze_with_openai_compatible", side_effect=mock_call):
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "**Answer: Option D** (OVH Fallback)")

    def test_image_optimization_resizes_and_compresses(self):
        service = GeminiService()
        # Create a large 3000x2000 RGBA image
        img_path = self.temp_path / "huge.png"
        Image.new("RGBA", (3000, 2000), (255, 0, 0, 128)).save(img_path)

        opt_path = service._optimize_image_for_ai(img_path)
        self.assertTrue(opt_path.exists())
        self.assertNotEqual(opt_path, img_path)

        with Image.open(opt_path) as opt_img:
            # Max dimension must not exceed 2048
            self.assertLessEqual(max(opt_img.size), 2048)
            self.assertEqual(opt_img.format, "JPEG")
            self.assertEqual(opt_img.mode, "RGB")

        # Cleanup
        opt_path.unlink()

    def test_circuit_breaker_deprioritizes_failed_provider(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        GeminiService._failed_providers.clear()

        service = GeminiService(
            primary_provider="groq",
            groq_api_key="dummy_groq_key",
            enable_ovh=True,
        )

        # First call: Groq fails, falls back to OVH and marks Groq as failed
        calls = []
        def mock_call_1(*args, **kwargs):
            p = kwargs.get("provider_name")
            calls.append(p)
            if "Groq" in p:
                raise Exception("Groq temporary failure")
            return "Option B (OVH)"

        with mock.patch.object(service, "_analyze_with_openai_compatible", side_effect=mock_call_1):
            res1 = service.analyze_image(str(img_path))
            self.assertEqual(res1, "Option B (OVH)")
            self.assertIn("groq", GeminiService._failed_providers)

        # Second call: circuit breaker puts healthy OVH ahead of failed Groq
        calls.clear()
        def mock_call_2(*args, **kwargs):
            p = kwargs.get("provider_name")
            calls.append(p)
            return "Option B (OVH Instant)"

        with mock.patch.object(service, "_analyze_with_openai_compatible", side_effect=mock_call_2):
            res2 = service.analyze_image(str(img_path))
            self.assertEqual(res2, "Option B (OVH Instant)")
            # First provider called should be OVH because Groq is in cooldown
            self.assertEqual(calls[0], "OVHcloud Kepler")

    def test_image_not_found(self):
        service = GeminiService()
        with self.assertRaises(GeminiServiceError) as ctx:
            service.analyze_image(str(self.temp_path / "nonexistent.png"))
        self.assertIn("Image not found", str(ctx.exception))

    def test_analyze_image_stream(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)
        service = GeminiService()

        tokens = []
        with mock.patch.object(service, "_analyze_with_openai_compatible", return_value="Result Stream") as mock_call:
            res = service.analyze_image_stream(str(img_path), callback=tokens.append)
            self.assertEqual(res, "Result Stream")
            mock_call.assert_called_once()

    def test_unsupported_image_format(self):
        txt_file = self.temp_path / "test.txt"
        txt_file.write_text("hello")
        service = GeminiService()
        with self.assertRaises(GeminiServiceError) as ctx:
            service.analyze_image(str(txt_file))
        self.assertIn("Unsupported image format", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
