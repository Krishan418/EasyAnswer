import tempfile
import unittest
from pathlib import Path
from unittest import mock
from PIL import Image

from screenshot_ai.gemini_service import (
    GeminiService,
    GeminiServiceError,
    analyze_image,
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

    def test_cloudflare_as_primary_provider(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(
            primary_provider="cloudflare",
            cloudflare_account_id="test_acc_123",
            cloudflare_api_token="test_token_456",
            cloudflare_model="@cf/meta/llama-3.2-11b-vision-instruct",
        )
        with mock.patch.object(service, "_analyze_with_cloudflare", return_value="**Answer: Option C**") as mock_cf:
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "**Answer: Option C**")
            mock_cf.assert_called_once()
            args, kwargs = mock_cf.call_args
            self.assertEqual(kwargs.get("model"), "@cf/meta/llama-3.2-11b-vision-instruct")
            self.assertEqual(kwargs.get("api_token"), "test_token_456")
            self.assertEqual(kwargs.get("account_id"), "test_acc_123")

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

    def test_nvidia_as_primary_provider(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(
            primary_provider="nvidia",
            nvidia_api_key="nvapi-test-key",
            nvidia_model="meta/llama-3.2-11b-vision-instruct",
        )
        with mock.patch.object(service, "_analyze_with_openai_compatible", return_value="**Answer: Option B** (NVIDIA 11B)") as mock_nv:
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "**Answer: Option B** (NVIDIA 11B)")
            mock_nv.assert_called_once()
            args, kwargs = mock_nv.call_args
            self.assertEqual(kwargs.get("provider_name"), "NVIDIA NIM (11B Vision)")
            self.assertEqual(kwargs.get("api_key"), "nvapi-test-key")
            self.assertEqual(kwargs.get("model"), "meta/llama-3.2-11b-vision-instruct")

    def test_gemini_as_primary_provider(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(
            primary_provider="gemini",
            gemini_api_key="AIzaSy-test-key",
            gemini_model="gemini-2.5-flash",
        )
        with mock.patch.object(service, "_analyze_with_openai_compatible", return_value="**Answer: Option C** (Gemini 2.5)") as mock_gemini:
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "**Answer: Option C** (Gemini 2.5)")
            mock_gemini.assert_called_once()
            args, kwargs = mock_gemini.call_args
            self.assertIn("Google Gemini", kwargs.get("provider_name"))
            self.assertEqual(kwargs.get("api_key"), "AIzaSy-test-key")
            self.assertEqual(kwargs.get("model"), "gemini-2.5-flash")

    def test_github_as_provider(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(
            primary_provider="github",
            github_token="ghp_test_token_123",
            github_model="gpt-4o-mini",
        )
        with mock.patch.object(service, "_analyze_with_openai_compatible", return_value="**Answer: Option A** (GitHub)") as mock_gh:
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "**Answer: Option A** (GitHub)")
            mock_gh.assert_called_once()
            args, kwargs = mock_gh.call_args
            self.assertIn("GitHub Models", kwargs.get("provider_name"))
            self.assertEqual(kwargs.get("api_key"), "ghp_test_token_123")
            self.assertEqual(kwargs.get("model"), "gpt-4o-mini")

    def test_module_level_analyze_image(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        with mock.patch.object(GeminiService, "analyze_screenshot", return_value="**Answer: Option A** (Module)") as mock_method:
            result = analyze_image(str(img_path))
            self.assertEqual(result, "**Answer: Option A** (Module)")
            mock_method.assert_called_once()

    def test_mistral_as_provider(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)

        service = GeminiService(
            primary_provider="mistral",
            mistral_api_key="mistral-test-key",
            mistral_model="pixtral-12b-2409",
        )
        with mock.patch.object(service, "_analyze_with_openai_compatible", return_value="**Answer: Option B** (Mistral)") as mock_mistral:
            result = service.analyze_image(str(img_path))
            self.assertEqual(result, "**Answer: Option B** (Mistral)")
            mock_mistral.assert_called_once()
            args, kwargs = mock_mistral.call_args
            self.assertIn("Mistral AI", kwargs.get("provider_name"))
            self.assertEqual(kwargs.get("api_key"), "mistral-test-key")

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
            gemini_api_key="",
            cloudflare_account_id="",
            cloudflare_api_token="",
            nvidia_api_key="",
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

    def test_all_net_failed_clean_error(self):
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)
        service = GeminiService(primary_provider="nvidia", nvidia_api_key="key", enable_ovh=True)

        def mock_offline(*args, **kwargs):
            raise GeminiServiceError("Network error: Unable to resolve (getaddrinfo failed)")

        with mock.patch.object(service, "_analyze_with_openai_compatible", side_effect=mock_offline):
            with self.assertRaises(GeminiServiceError) as ctx:
                service.analyze_image(str(img_path))
            self.assertIn("No Internet Connection", str(ctx.exception))
            # Circuit breaker should be reset
            self.assertEqual(len(service._failed_providers), 0)

    def test_concise_prompt_and_max_tokens_payload(self):
        import base64
        from screenshot_ai.gemini_service import _dec_str, _PROMPT_B64
        decoded_prompt = _dec_str(base64.b64decode(_PROMPT_B64))
        self.assertIn("verify each option against the question", decoded_prompt)
        self.assertIn("ONE sentence", decoded_prompt)
        self.assertIn("ultra-short and exact", decoded_prompt)

        # Test that _analyze_with_openai_compatible sets max_tokens = 120
        img_path = self.temp_path / "test.png"
        Image.new("RGB", (20, 20), "white").save(img_path)
        service = GeminiService(primary_provider="nvidia", nvidia_api_key="nvapi-test", enable_ovh=False)

        captured_payloads = []
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [
            'data: {"choices": [{"delta": {"content": "**Answer: Option A**"}}]}',
            "data: [DONE]",
        ]

        cm = mock.MagicMock()
        cm.__enter__.return_value = mock_resp
        cm.__exit__.return_value = None

        mock_client = mock.MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None

        def fake_stream(method, url, **kwargs):
            captured_payloads.append(kwargs.get("json"))
            return cm

        mock_client.stream.side_effect = fake_stream

        with mock.patch("httpx.Client", return_value=mock_client):
            res = service.analyze_image(str(img_path))
            self.assertEqual(res, "**Answer: Option A**")
            self.assertTrue(len(captured_payloads) > 0)
            self.assertEqual(captured_payloads[0].get("max_tokens"), 600)


if __name__ == "__main__":
    unittest.main()
