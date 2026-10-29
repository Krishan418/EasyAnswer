import os
import sys
from pathlib import Path
from typing import Callable, Optional

from google import genai
from google.genai import types
from PIL import Image

from .config import get_config


SUPPORTED_EXTS = {".png", ".jpg", ".jpeg"}


class GeminiServiceError(Exception):
    """Base exception for Gemini service errors."""
    pass


class GeminiService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        grok_api_key: Optional[str] = None,
        grok_model: Optional[str] = None,
        github_token: Optional[str] = None,
        github_model: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        openrouter_model: Optional[str] = None,
        perplexity_api_key: Optional[str] = None,
        perplexity_model: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        groq_model: Optional[str] = None,
        mistral_api_key: Optional[str] = None,
        mistral_model: Optional[str] = None,
        cloudflare_account_id: Optional[str] = None,
        cloudflare_api_token: Optional[str] = None,
        cloudflare_model: Optional[str] = None,
        huggingface_api_token: Optional[str] = None,
        huggingface_model: Optional[str] = None,
        primary_provider: Optional[str] = None,
    ):
        if api_key is None:
            try:
                config = get_config()
            except ValueError as exc:
                raise GeminiServiceError(str(exc)) from exc
            self.api_key = config.gemini_api_key
            self.model = model or config.gemini_model
            self.grok_api_key = grok_api_key or config.grok_api_key
            self.grok_model = grok_model or config.grok_model
            self.github_token = github_token or config.github_token
            self.github_model = github_model or config.github_model
            self.openrouter_api_key = openrouter_api_key or config.openrouter_api_key
            self.openrouter_model = openrouter_model or config.openrouter_model
            self.perplexity_api_key = perplexity_api_key or config.perplexity_api_key
            self.perplexity_model = perplexity_model or config.perplexity_model
            self.groq_api_key = groq_api_key or config.groq_api_key
            self.groq_model = groq_model or config.groq_model
            self.mistral_api_key = mistral_api_key or config.mistral_api_key
            self.mistral_model = mistral_model or config.mistral_model
            self.cloudflare_account_id = cloudflare_account_id or config.cloudflare_account_id
            self.cloudflare_api_token = cloudflare_api_token or config.cloudflare_api_token
            self.cloudflare_model = cloudflare_model or config.cloudflare_model
            self.huggingface_api_token = huggingface_api_token or config.huggingface_api_token
            self.huggingface_model = huggingface_model or config.huggingface_model
            self.primary_provider = primary_provider or config.primary_provider
        else:
            self.api_key = api_key
            self.model = model or "gemini-3.5-flash"
            self.grok_api_key = grok_api_key
            self.grok_model = grok_model or "grok-2-vision-1212"
            self.github_token = github_token
            self.github_model = github_model or "gpt-4o-mini"
            self.openrouter_api_key = openrouter_api_key
            self.openrouter_model = openrouter_model or "nvidia/nemotron-3.5-super-vl:free"
            self.perplexity_api_key = perplexity_api_key
            self.perplexity_model = perplexity_model or "sonar"
            self.groq_api_key = groq_api_key
            self.groq_model = groq_model or "llama-3.2-11b-vision-preview"
            self.mistral_api_key = mistral_api_key
            self.mistral_model = mistral_model or "pixtral-12b-2409"
            self.cloudflare_account_id = cloudflare_account_id
            self.cloudflare_api_token = cloudflare_api_token
            self.cloudflare_model = cloudflare_model or "@cf/meta/llama-3.2-11b-vision-instruct"
            self.huggingface_api_token = huggingface_api_token
            self.huggingface_model = huggingface_model or "meta-llama/Llama-3.2-11B-Vision-Instruct"
            self.primary_provider = primary_provider or ("openrouter" if openrouter_api_key else ("github" if github_token else "gemini"))
        # Initialize client
        self.client = genai.Client(api_key=self.api_key)

    def _validate_image(self, image_path: str) -> Path:
        path = Path(image_path)
        if not path.exists():
            raise GeminiServiceError(f"Image file not found: {path}")
        if not path.is_file():
            raise GeminiServiceError(f"Path is not a file: {path}")
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTS:
            raise GeminiServiceError(
                f"Unsupported image format '{ext}'. Supported formats: PNG, JPG, JPEG"
            )
        # Try to open with PIL to validate
        try:
            with Image.open(path) as img:
                img.verify()  # verify file is intact
        except Exception as e:
            raise GeminiServiceError(f"Unreadable or corrupted image: {e}")
        return path

    def analyze_image_stream(
        self,
        image_path: str,
        prompt: Optional[str] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Analyze an image and stream chunks as they arrive.
        Calls callback(chunk_text) and returns the full text.
        """
        image_path_obj = self._validate_image(image_path)

        if prompt is None:
            prompt = (
                "You are a fast, concise assistant analyzing this screenshot. "
                "Give the direct answer first in 1 line (e.g. **Answer: Option X** or direct solution). "
                "If needed, follow with at most 1-2 brief bullet points explaining why. "
                "Keep the entire response compact, short, and to the point without filler or large headers."
            )

        # Determine execution order based on primary_provider
        provider_order = []
        if self.primary_provider == "openrouter" and self.openrouter_api_key:
            provider_order.append("openrouter")
        elif self.primary_provider == "mistral" and self.mistral_api_key:
            provider_order.append("mistral")
        elif self.primary_provider == "cloudflare" and self.cloudflare_api_token:
            provider_order.append("cloudflare")
        elif self.primary_provider == "huggingface" and self.huggingface_api_token:
            provider_order.append("huggingface")
        elif self.primary_provider == "perplexity" and self.perplexity_api_key:
            provider_order.append("perplexity")
        elif self.primary_provider == "groq" and self.groq_api_key:
            provider_order.append("groq")
        elif self.primary_provider == "github" and self.github_token:
            provider_order.append("github")
        else:
            provider_order.append("gemini")

        # Add remaining configured providers in priority order
        fallbacks = [
            ("openrouter", self.openrouter_api_key),
            ("mistral", self.mistral_api_key),
            ("cloudflare", self.cloudflare_api_token and self.cloudflare_account_id),
            ("huggingface", self.huggingface_api_token),
            ("perplexity", self.perplexity_api_key),
            ("groq", self.groq_api_key),
            ("github", self.github_token),
            ("gemini", True),
            ("grok", self.grok_api_key),
        ]
        for name, key in fallbacks:
            if key and name not in provider_order:
                provider_order.append(name)

        errors = []
        for provider in provider_order:
            try:
                if provider == "github":
                    return self._analyze_with_openai_compatible(
                        url="https://models.github.ai/inference/chat/completions",
                        api_key=self.github_token,
                        model=self.github_model,
                        image_path=image_path_obj,
                        prompt=prompt,
                        callback=callback,
                        provider_name="GitHub Models",
                    )
                elif provider == "gemini":
                    return self._analyze_with_gemini(image_path_obj, prompt, callback)
                elif provider == "openrouter":
                    try:
                        return self._analyze_with_openai_compatible(
                            url="https://openrouter.ai/api/v1/chat/completions",
                            api_key=self.openrouter_api_key,
                            model=self.openrouter_model,
                            image_path=image_path_obj,
                            prompt=prompt,
                            callback=callback,
                            provider_name="OpenRouter",
                            extra_headers={
                                "HTTP-Referer": "https://github.com/Krishan418/EasyAnswer",
                                "X-Title": "EasyAnswer",
                            },
                        )
                    except Exception as or_err:
                        # If primary model is down, automatically fallback to openrouter/free
                        if self.openrouter_model != "openrouter/free":
                            print(f"[openrouter] {self.openrouter_model} failed ({or_err}). Trying openrouter/free...")
                            return self._analyze_with_openai_compatible(
                                url="https://openrouter.ai/api/v1/chat/completions",
                                api_key=self.openrouter_api_key,
                                model="openrouter/free",
                                image_path=image_path_obj,
                                prompt=prompt,
                                callback=callback,
                                provider_name="OpenRouter (free router)",
                                extra_headers={
                                    "HTTP-Referer": "https://github.com/Krishan418/EasyAnswer",
                                    "X-Title": "EasyAnswer",
                                },
                            )
                        raise
                elif provider == "mistral":
                    return self._analyze_with_openai_compatible(
                        url="https://api.mistral.ai/v1/chat/completions",
                        api_key=self.mistral_api_key,
                        model=self.mistral_model,
                        image_path=image_path_obj,
                        prompt=prompt,
                        callback=callback,
                        provider_name="Mistral AI",
                    )
                elif provider == "cloudflare":
                    url = f"https://api.cloudflare.com/client/v4/accounts/{self.cloudflare_account_id}/ai/v1/chat/completions"
                    return self._analyze_with_openai_compatible(
                        url=url,
                        api_key=self.cloudflare_api_token,
                        model=self.cloudflare_model,
                        image_path=image_path_obj,
                        prompt=prompt,
                        callback=callback,
                        provider_name="Cloudflare Workers AI",
                    )
                elif provider == "huggingface":
                    url = f"https://api-inference.huggingface.co/models/{self.huggingface_model}/v1/chat/completions"
                    return self._analyze_with_openai_compatible(
                        url=url,
                        api_key=self.huggingface_api_token,
                        model=self.huggingface_model,
                        image_path=image_path_obj,
                        prompt=prompt,
                        callback=callback,
                        provider_name="Hugging Face",
                    )
                elif provider == "perplexity":
                    return self._analyze_with_openai_compatible(
                        url="https://api.perplexity.ai/chat/completions",
                        api_key=self.perplexity_api_key,
                        model=self.perplexity_model,
                        image_path=image_path_obj,
                        prompt=prompt,
                        callback=callback,
                        provider_name="Perplexity AI",
                    )
                elif provider == "groq":
                    return self._analyze_with_openai_compatible(
                        url="https://api.groq.com/openai/v1/chat/completions",
                        api_key=self.groq_api_key,
                        model=self.groq_model,
                        image_path=image_path_obj,
                        prompt=prompt,
                        callback=callback,
                        provider_name="Groq Cloud",
                    )
                elif provider == "grok":
                    return self._analyze_with_grok(image_path_obj, prompt, callback)
            except Exception as exc:
                errors.append(f"{provider}: {exc}")
                print(f"[failover] {provider} failed ({exc}). Trying next provider...", file=sys.stderr)

        # Map common errors if all failed
        last_err = errors[-1] if errors else "No AI provider available."
        err_str = last_err.lower()
        if "api key" in err_str or "unauthorized" in err_str or "permission" in err_str:
            raise GeminiServiceError(f"Authentication error: {last_err}")
        if "rate" in err_str or "quota" in err_str or "429" in err_str:
            raise GeminiServiceError(f"Rate limit or quota exceeded: {last_err}")
        if "404" in err_str or "not found" in err_str:
            raise GeminiServiceError(
                f"Model '{self.model}' not found (404). Run 'python tools/list_models.py' "
                f"to see models supported by your API key and update GEMINI_MODEL in .env: {last_err}"
            )
        if "network" in err_str or "timeout" in err_str or "connection" in err_str:
            raise GeminiServiceError(f"Network error: {last_err}")
        raise GeminiServiceError(f"All AI providers failed: {last_err}")

    def _analyze_with_gemini(
        self,
        image_path_obj: Path,
        prompt: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        with Image.open(image_path_obj) as img:
            img.load()
            image = img.copy()
        contents = [prompt, image]

        full_text = []
        try:
            stream = self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
            )
            for chunk in stream:
                text = getattr(chunk, "text", None)
                if text:
                    full_text.append(text)
                    if callback:
                        callback(text)
        except Exception as stream_err:
            err_str = str(stream_err).lower()
            if any(k in err_str for k in ("404", "not found", "quota", "rate", "429", "api key", "unauthorized", "permission", "network", "timeout", "connection")):
                raise

            if not full_text:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                )
                text = getattr(response, "text", None) or ""
                if text:
                    full_text.append(text)
                    if callback:
                        callback(text)

        result = "".join(full_text).strip()
        if not result:
            raise GeminiServiceError("Empty response from Gemini API")
        return result

    def _analyze_with_openai_compatible(
        self,
        url: str,
        api_key: str,
        model: str,
        image_path: Path,
        prompt: str,
        callback: Optional[Callable[[str], None]] = None,
        provider_name: str = "Fallback Provider",
        extra_headers: Optional[dict] = None,
    ) -> str:
        """Unified fallback to any OpenAI-compatible Vision API (GitHub Models, Grok, OpenRouter, etc.)."""
        import base64
        import json
        import httpx

        ext = image_path.suffix.lstrip(".").lower()
        if ext == "jpg":
            ext = "jpeg"

        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{ext};base64,{b64_data}"
                            },
                        },
                    ],
                }
            ],
            "stream": True,
        }

        full_text = []
        with httpx.Client(timeout=35.0) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_body = response.read().decode("utf-8", errors="replace")
                    raise GeminiServiceError(f"{provider_name} API error ({response.status_code}): {err_body}")

                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        line = line[6:].strip()
                    if line == "[DONE]":
                        break
                    try:
                        chunk = json.loads(line)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_text.append(content)
                                if callback:
                                    callback(content)
                    except Exception:
                        continue

        result = "".join(full_text).strip()
        if not result:
            raise GeminiServiceError(f"Empty response from {provider_name}")
        return result

    def _analyze_with_grok(
        self,
        image_path: Path,
        prompt: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Backward-compatible helper for Grok fallback."""
        return self._analyze_with_openai_compatible(
            url="https://api.x.ai/v1/chat/completions",
            api_key=self.grok_api_key or "",
            model=self.grok_model,
            image_path=image_path,
            prompt=prompt,
            callback=callback,
            provider_name="Grok Vision",
        )

    def analyze_image(self, image_path: str, prompt: Optional[str] = None) -> str:
        """Analyze a screenshot/image using Gemini (or Grok fallback) and return the full text."""
        return self.analyze_image_stream(image_path, prompt=prompt)




# Convenience function
def analyze_image(image_path: str, prompt: Optional[str] = None) -> str:
    service = GeminiService()
    return service.analyze_image(image_path, prompt)
