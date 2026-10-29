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

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_missing_key(self):
        with mock.patch("screenshot_ai.gemini_service.get_config") as mock_cfg:
            mock_cfg.side_effect = ValueError("GEMINI_API_KEY is not set")
            with self.assertRaises(GeminiServiceError) as ctx:
                GeminiService()
            self.assertIn("GEMINI_API_KEY is not set", str(ctx.exception))

    @mock.patch("google.genai.Client")
    def test_init_with_key(self, mock_client_cls):
        service = GeminiService(api_key="explicit_key", model="gemini-test")
        self.assertEqual(service.api_key, "explicit_key")
        self.assertEqual(service.model, "gemini-test")
        mock_client_cls.assert_called_once_with(api_key="explicit_key")

    @mock.patch("google.genai.Client")
    def test_analyze_image_success(self, mock_client_cls):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client

        # Mock streaming response
        mock_chunk = mock.MagicMock()
        mock_chunk.text = "This is Mars, the Red Planet."
        mock_client.models.generate_content_stream.return_value = [mock_chunk]

        # Create valid test image
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(api_key="dummy_key")
        result = service.analyze_image(str(img_path))
        self.assertEqual(result, "This is Mars, the Red Planet.")

    @mock.patch("google.genai.Client")
    def test_analyze_image_candidates_fallback(self, mock_client_cls):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client

        # Stream fails, so it falls back to generate_content
        mock_client.models.generate_content_stream.side_effect = Exception("Protocol error")
        mock_response = mock.MagicMock()
        mock_response.text = "Fallback non-stream answer."
        mock_client.models.generate_content.return_value = mock_response

        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(api_key="dummy_key")
        result = service.analyze_image(str(img_path))
        self.assertEqual(result, "Fallback non-stream answer.")

    @mock.patch("google.genai.Client")
    def test_analyze_image_error_mapping(self, mock_client_cls):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client

        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)
        service = GeminiService(api_key="dummy_key")

        # 404 Model not found
        mock_client.models.generate_content_stream.side_effect = Exception("404 models/gemini-old is not found")
        with self.assertRaises(GeminiServiceError) as ctx:
            service.analyze_image(str(img_path))
        self.assertIn("not found (404)", str(ctx.exception))

        # 429 Quota
        mock_client.models.generate_content_stream.side_effect = Exception("ResourceExhausted: 429 Quota exceeded")
        with self.assertRaises(GeminiServiceError) as ctx:
            service.analyze_image(str(img_path))
        self.assertIn("Rate limit or quota exceeded", str(ctx.exception))

        # Auth
        mock_client.models.generate_content_stream.side_effect = Exception("Invalid API key provided")
        with self.assertRaises(GeminiServiceError) as ctx:
            service.analyze_image(str(img_path))
        self.assertIn("Authentication error", str(ctx.exception))

        # Network
        mock_client.models.generate_content_stream.side_effect = Exception("Connection timeout error")
        with self.assertRaises(GeminiServiceError) as ctx:
            service.analyze_image(str(img_path))

        self.assertIn("Network error", str(ctx.exception))

    @mock.patch("google.genai.Client")
    def test_grok_fallback_on_gemini_error(self, mock_client_cls):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content_stream.side_effect = Exception("Network blocked")

        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(api_key="dummy_key", grok_api_key="xai_test_key")
        with mock.patch.object(service, "_analyze_with_grok", return_value="**Answer: Option B** (Grok)") as mock_grok:
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "**Answer: Option B** (Grok)")
            mock_grok.assert_called_once()

    @mock.patch("google.genai.Client")
    def test_github_models_fallback_on_gemini_error(self, mock_client_cls):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content_stream.side_effect = Exception("Network blocked")

        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(api_key="dummy_key", github_token="ghp_test_token")
        with mock.patch.object(service, "_analyze_with_openai_compatible", return_value="**Answer: Option A** (GitHub)") as mock_fallback:
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "**Answer: Option A** (GitHub)")
            mock_fallback.assert_called_once()
            args, kwargs = mock_fallback.call_args
            self.assertEqual(kwargs.get("provider_name"), "GitHub Models")
            self.assertEqual(kwargs.get("model"), "gpt-4o-mini")

    @mock.patch("google.genai.Client")
    def test_github_models_as_primary_provider(self, mock_client_cls):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client

        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(
            api_key="dummy_key",
            github_token="ghp_test_token",
            primary_provider="github",
        )
        with mock.patch.object(service, "_analyze_with_openai_compatible", return_value="**Answer: Option C** (Direct GitHub)") as mock_gh:
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "**Answer: Option C** (Direct GitHub)")
            mock_gh.assert_called_once()
            # Gemini stream should NOT have been called because GitHub succeeded as primary!
            mock_client.models.generate_content_stream.assert_not_called()

    @mock.patch("google.genai.Client")
    def test_mistral_as_primary_provider(self, mock_client_cls):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client

        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(
            api_key="dummy_key",
            mistral_api_key="test_mistral_key",
            primary_provider="mistral",
        )
        with mock.patch.object(service, "_analyze_with_openai_compatible", return_value="Option D (Mistral)") as mock_mistral:
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "Option D (Mistral)")
            mock_mistral.assert_called_once()
            args, kwargs = mock_mistral.call_args
            self.assertEqual(kwargs.get("provider_name"), "Mistral AI")
            self.assertEqual(kwargs.get("model"), "pixtral-12b-2409")

    @mock.patch("google.genai.Client")
    def test_openrouter_model_auto_fallback(self, mock_client_cls):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client

        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(
            api_key="dummy_key",
            openrouter_api_key="sk-or-v1-dummy",
            primary_provider="openrouter",
        )

        # First call with primary model fails, second call with openrouter/free succeeds
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


if __name__ == "__main__":
    unittest.main()
