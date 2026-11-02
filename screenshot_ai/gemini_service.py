import os
import sys
import time
from pathlib import Path
from typing import Callable, Optional

from google import genai
from google.genai import types
from PIL import Image
import httpx

from .config import get_config


SUPPORTED_EXTS = {".png", ".jpg", ".jpeg"}


class GeminiServiceError(Exception):
    """Base exception for Gemini service errors."""
    pass


class GeminiService:
    # Circuit breaker tracking for failed providers across calls: provider -> timestamp
    _failed_providers: dict = {}
    _CIRCUIT_COOLDOWN: float = 180.0  # 3 minutes cooldown before re-trying a failed provider

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
        openrouter_base_url: Optional[str] = None,
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
        glm_api_key: Optional[str] = None,
        glm_model: Optional[str] = None,
        enable_ovh: Optional[bool] = None,
        primary_provider: Optional[str] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
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
            self.openrouter_base_url = openrouter_base_url or getattr(config, "openrouter_base_url", "https://openrouter.ai/api/v1")
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
            self.glm_api_key = glm_api_key or getattr(config, "glm_api_key", None)
            self.glm_model = glm_model or getattr(config, "glm_model", "glm-4v-flash")
            self.enable_ovh = enable_ovh if enable_ovh is not None else getattr(config, "enable_ovh", True)
            self.primary_provider = primary_provider or config.primary_provider
            self.connect_timeout = connect_timeout if connect_timeout is not None else getattr(config, "http_connect_timeout", 3.5)
            self.read_timeout = read_timeout if read_timeout is not None else getattr(config, "http_read_timeout", 12.0)
        else:
            self.api_key = api_key
            self.model = model or "gemini-3.5-flash"
            self.grok_api_key = grok_api_key
            self.grok_model = grok_model or "grok-2-vision-1212"
            self.github_token = github_token
            self.github_model = github_model or "gpt-4o-mini"
            self.openrouter_api_key = openrouter_api_key
            self.openrouter_model = openrouter_model or "nvidia/nemotron-3.5-super-vl:free"
            self.openrouter_base_url = openrouter_base_url or "https://openrouter.ai/api/v1"
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
            self.glm_api_key = glm_api_key
            self.glm_model = glm_model or "glm-4v-flash"
            self.enable_ovh = enable_ovh if enable_ovh is not None else False
            self.primary_provider = primary_provider or ("openrouter" if openrouter_api_key else ("github" if github_token else "gemini"))
            self.connect_timeout = connect_timeout if connect_timeout is not None else 3.5
            self.read_timeout = read_timeout if read_timeout is not None else 12.0
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

    def _optimize_image_for_ai(self, image_path: Path) -> Path:
        """
        Optimize screenshot in memory: preserves crisp, un-downscaled 100% resolution
        for 1080p and standard displays (up to 2048px), and saves with high quality (95)
        so fine text, math symbols, and code are never blurred or distorted.
        """
        import tempfile
        try:
            with Image.open(image_path) as img:
                w, h = img.size
                max_dim = 2048
                scale = min(1.0, max_dim / max(w, h)) if max(w, h) > max_dim else 1.0
                new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))

                # Handle transparency (RGBA, LA, P) cleanly onto white background
                if img.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", (w, h), (255, 255, 255))
                    converted = img.convert("RGBA") if img.mode == "P" else img
                    alpha = converted.split()[-1] if converted.mode in ("RGBA", "LA") else None
                    bg.paste(converted, mask=alpha)
                    rgb_img = bg
                elif img.mode != "RGB":
                    rgb_img = img.convert("RGB")
                else:
                    rgb_img = img.copy()

                if scale < 1.0:
                    rgb_img = rgb_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                # Save as high-quality optimized JPEG (quality=95 prevents text ringing/blur)
                handle, temp_path = tempfile.mkstemp(prefix="ea_opt_", suffix=".jpg")
                os.close(handle)
                rgb_img.save(temp_path, format="JPEG", quality=95, optimize=True)
                return Path(temp_path)
        except Exception:
            # Fallback to original image if compression fails
            return image_path

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
        optimized_image_path = self._optimize_image_for_ai(image_path_obj)
        cleanup_optimized = (optimized_image_path != image_path_obj)

        if prompt is None:
            prompt = (
                "You are an expert exam and problem-solving assistant analyzing this screenshot. "
                "Carefully examine the question, any diagrams, formulas, or code, and all answer choices. "
                "Double-check your logic to ensure 100% accuracy and avoid common trick choices.\n\n"
                "Format your response concisely:\n"
                "**Answer: [Option Letter & Exact Answer Text / Exact Solution]**\n"
                "- **Reasoning**: [1-2 concise bullet points explaining why this is correct and why other choices are wrong].\n"
                "Keep it direct, accurate, and to the point without filler."
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
        elif self.primary_provider == "glm" and self.glm_api_key:
            provider_order.append("glm")
        else:
            provider_order.append("gemini")

        # Add remaining configured providers in priority order (Fast & resilient first)
        fallbacks = [
            ("gemini", True),
            ("glm", self.glm_api_key),
            ("openrouter", self.openrouter_api_key),
            ("ovh", self.enable_ovh),  # Keyless OVHcloud Kepler (Qwen2.5-VL-72B) safety net
            ("github", self.github_token),
            ("cloudflare", self.cloudflare_api_token and self.cloudflare_account_id),
            ("mistral", self.mistral_api_key),
            ("huggingface", self.huggingface_api_token),
            ("groq", self.groq_api_key),
            ("perplexity", self.perplexity_api_key),
            ("grok", self.grok_api_key),
        ]
        for name, key in fallbacks:
            if key and name not in provider_order:
                provider_order.append(name)

        # Circuit breaker: prioritize healthy providers over recently failed ones
        now = time.time()
        healthy = []
        cooling_down = []
        for p in provider_order:
            failed_at = self._failed_providers.get(p, 0)
            if (now - failed_at) < self._CIRCUIT_COOLDOWN:
                cooling_down.append(p)
            else:
                healthy.append(p)
        provider_order = healthy + cooling_down

        errors = []
        try:
            for provider in provider_order:
                try:
                    if provider == "github":
                        result = self._analyze_with_openai_compatible(
                            url="https://models.github.ai/inference/chat/completions",
                            api_key=self.github_token,
                            model=self.github_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name="GitHub Models",
                        )
                    elif provider == "gemini":
                        result = self._analyze_with_gemini(optimized_image_path, prompt, callback)
                    elif provider == "openrouter":
                        or_base = (self.openrouter_base_url or "https://openrouter.ai/api/v1").rstrip("/")
                        or_url = f"{or_base}/chat/completions"
                        try:
                            result = self._analyze_with_openai_compatible(
                                url=or_url,
                                api_key=self.openrouter_api_key,
                                model=self.openrouter_model,
                                image_path=optimized_image_path,
                                prompt=prompt,
                                callback=callback,
                                provider_name="OpenRouter",
                                extra_headers={
                                    "HTTP-Referer": "https://www.google.com",
                                    "X-Title": "SystemHost",
                                },
                            )
                        except Exception as or_err:
                            # If primary model is down, automatically fallback to openrouter/free
                            if self.openrouter_model != "openrouter/free":
                                print(f"[openrouter] {self.openrouter_model} failed ({or_err}). Trying openrouter/free...")
                                result = self._analyze_with_openai_compatible(
                                    url=or_url,
                                    api_key=self.openrouter_api_key,
                                    model="openrouter/free",
                                    image_path=optimized_image_path,
                                    prompt=prompt,
                                    callback=callback,
                                    provider_name="OpenRouter (free router)",
                                    extra_headers={
                                        "HTTP-Referer": "https://www.google.com",
                                        "X-Title": "SystemHost",
                                    },
                                )
                            else:
                                raise
                    elif provider == "ovh":
                        result = self._analyze_with_openai_compatible(
                            url="https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions",
                            api_key=None,
                            model="Qwen2.5-VL-72B-Instruct",
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name="OVHcloud Kepler",
                        )
                    elif provider == "glm":
                        result = self._analyze_with_openai_compatible(
                            url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
                            api_key=self.glm_api_key,
                            model=self.glm_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name="Zhipu GLM-4V",
                        )
                    elif provider == "mistral":
                        result = self._analyze_with_openai_compatible(
                            url="https://api.mistral.ai/v1/chat/completions",
                            api_key=self.mistral_api_key,
                            model=self.mistral_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name="Mistral AI",
                        )
                    elif provider == "cloudflare":
                        result = self._analyze_with_cloudflare(optimized_image_path, prompt, callback)
                    elif provider == "huggingface":
                        url = f"https://api-inference.huggingface.co/models/{self.huggingface_model}/v1/chat/completions"
                        result = self._analyze_with_openai_compatible(
                            url=url,
                            api_key=self.huggingface_api_token,
                            model=self.huggingface_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name="Hugging Face",
                        )
                    elif provider == "perplexity":
                        result = self._analyze_with_openai_compatible(
                            url="https://api.perplexity.ai/chat/completions",
                            api_key=self.perplexity_api_key,
                            model=self.perplexity_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name="Perplexity AI",
                        )
                    elif provider == "groq":
                        result = self._analyze_with_openai_compatible(
                            url="https://api.groq.com/openai/v1/chat/completions",
                            api_key=self.groq_api_key,
                            model=self.groq_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name="Groq Cloud",
                        )
                    elif provider == "grok":
                        result = self._analyze_with_grok(optimized_image_path, prompt, callback)
                    else:
                        continue

                    # Provider succeeded! Remove any failure timestamp
                    self._failed_providers.pop(provider, None)
                    return result
                except Exception as exc:
                    self._failed_providers[provider] = time.time()
                    errors.append(f"{provider}: {exc}")
                    print(f"[failover] {provider} failed ({exc}). Trying next provider...", file=sys.stderr)
        finally:
            if cleanup_optimized and optimized_image_path.exists():
                try:
                    optimized_image_path.unlink()
                except OSError:
                    pass

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
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
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

        timeout = httpx.Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=5.0,
            pool=3.0,
        )
        full_text = []
        with httpx.Client(timeout=timeout) as client:
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

    def _analyze_with_cloudflare(
        self,
        image_path: Path,
        prompt: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Call Cloudflare Workers AI with vision support and real-time streaming."""
        import json
        url = f"https://api.cloudflare.com/client/v4/accounts/{self.cloudflare_account_id}/ai/run/{self.cloudflare_model}"
        headers = {
            "Authorization": f"Bearer {self.cloudflare_api_token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        with open(image_path, "rb") as f:
            img_bytes = list(f.read())

        payload = {
            "prompt": prompt,
            "image": img_bytes,
            "stream": True,
        }

        timeout = httpx.Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=5.0,
            pool=3.0,
        )

        full_text = []
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    err_text = resp.read().decode("utf-8", errors="replace")
                    raise GeminiServiceError(f"Cloudflare Workers AI error ({resp.status_code}): {err_text}")

                content_type = resp.headers.get("content-type", "")
                if "text/event-stream" in content_type:
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            line = line[6:].strip()
                        if line == "[DONE]":
                            break
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("response", "")
                            if token:
                                full_text.append(token)
                                if callback:
                                    callback(token)
                        except Exception:
                            continue
                else:
                    body = resp.read().decode("utf-8", errors="replace")
                    data = json.loads(body)
                    token = data.get("result", {}).get("response", "").strip()
                    if token:
                        full_text.append(token)
                        if callback:
                            callback(token)

        result = "".join(full_text).strip()
        if not result:
            raise GeminiServiceError("Empty response from Cloudflare Workers AI")
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
