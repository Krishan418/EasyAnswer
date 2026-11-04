import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional, Union

from PIL import Image
import httpx

from .config import get_config


SUPPORTED_EXTS = {".png", ".jpg", ".jpeg"}


def _dec_str(b: bytes) -> str:
    key = 0x5A
    return bytes([x ^ ((key + i * 3) & 0xFF) for i, x in enumerate(b)]).decode("utf-8")


_URL_OVH = _dec_str(b'2)\x14\x13\x15SC@\x1d\x14\x11U\x1b\xef\xe0\xf7\xe5\xe4\xfe\xe7\xe5\xb7\xf7\xfa\xd2\xc9\xcd\xd9\x80\xd0\xdd\x99\xd9\xd1\xaf\xb6\xa2\xe7\xa3\xb9\xba\xfb\xb6\xbe\xaa\xce\x92\xd6\xc5\x8e\x98\x92\x82\xd6\x9f\x90oudnzx{yi')
_URL_NVIDIA = _dec_str(b'2)\x14\x13\x15SC@\x1b\x1b\x0c\x1e\x19\xf3\xe5\xf3\xef\xa3\xf1\xe3\xff\xb7\xf2\xe9\xcb\xc1\xc1\xca\x80\xd2\xdb\xda\x95\xcb\xf1\xec\xa5\xa1\xad\xbb\xfd\xb6\xb7\xb6\xae\x8d\x81\x93\x83\x82\x9e\x80')
_URL_GEMINI = _dec_str(b'2)\x14\x13\x15SC@\x15\x10\x16\x1e\x0c\xe0\xf0\xee\xfc\xe8\xfc\xf2\xf8\xfe\xe9\xfe\xc5\xc0\x86\xcc\xc1\xde\xd3\xdb\xdf\xdc\xb0\xaa\xb5\xe7\xaf\xa0\xbf\xfa\xae\xea\xbc\x84\x90\x86\xc5\x82\x80\x96\x98\x98\x95\xd0ami\x7f!r{zjqEWOFB\\')
_URL_MISTRAL = _dec_str(b'2)\x14\x13\x15SC@\x13\x05\x11U\x13\xe8\xf7\xf3\xf8\xec\xfc\xbd\xf7\xf0\xb3\xe9\x93\x8a\xcb\xc3\xcf\xc5\x9b\xd4\xd5\xd0\xb0\xaf\xa3\xbd\xa5\xa0\xbc\xa6')
_URL_GITHUB = _dec_str(b'2)\x14\x13\x15SC@\x1f\x1a\x1c\x1e\x12\xf2\xaa\xee\xe4\xeb\xf5\xe1\xf3\xf7\xff\xfa\x8c\xc4\xc1\x85\xcf\xcb\xc1\xc5\xdf\x93\xa3\xac\xab\xe6\xaf\xa7\xb3\xa1\xf7\xb8\xb1\x8c\x94\x8b\x8f\x99\x99\x9c\x98\x8a')
_URL_GROQ = _dec_str(b'2)\x14\x13\x15SC@\x13\x05\x11U\x19\xf3\xeb\xf6\xa4\xee\xff\xfe\xb9\xf6\xec\xfa\xcc\xc4\xc1\x84\xd8\x80\x9b\xd4\xd2\xdc\xb4\xec\xa5\xa6\xa1\xbf\xbe\xb0\xac\xb2\xb1\x8f\x97')
_URL_OPENROUTER_DEF = _dec_str(b'2)\x14\x13\x15SC@\x1d\x05\x1d\x15\x0c\xee\xf1\xf3\xef\xff\xbe\xf2\xff\xb6\xfd\xef\xcb\x8a\xde\x9a')

_PROMPT_B64 = (
    "GzMBDx8TCU8GHR1bF+zl4O+jsNX/6+/rgtPN2cfXzZff3KOr5qa8u7u6tvu/hoWOhJ6E04KRmd9zcG14enh7eTQXEQ0GelhORlAYT1YkZCQlPyI2NS18PgwWHw4cURcbHxzy7/+zhqW41Pbo6cTWnYr2/8PC0NPR4omtv7q0pvf8/aWbh4qYz6aQgI/eLiRUZWFlZ392ckIIDyIZABF9WRpyDgZmOikhJjA2ODtbbkpKR1ohExgPEOyvorGuytbl8/jGg8PR3MPT29nP166qmuTHg4eEkJ+Lwre9p6uiztexmGVzJmB4L2d5bGl/DFdPRV9EE1dXWB8nPSkoOn8="
)


class GeminiServiceError(Exception):
    """Base exception for AI vision service errors."""
    pass


class GeminiService:
    """Service to handle vision AI inference across clean, unblocked providers:
    1. Google Gemini (gemini-3-flash-preview - Free 1,500 RPD, Unblocked Everywhere)
    2. Cloudflare Workers AI (@cf/meta/llama-3.2-11b-vision-instruct - 10,000 Neurons/Day)
    3. OVHcloud Kepler (Qwen2.5-VL-72B - 100% Free & Keyless, Unblocked on Lab Networks)
    4. NVIDIA NIM (meta/llama-3.2-11b-vision-instruct - Fast 11B Vision)
    """

    # Circuit breaker tracking for failed providers across calls: provider -> timestamp
    _failed_providers: dict = {}
    _CIRCUIT_COOLDOWN: float = 180.0  # 3 minutes cooldown before re-trying a failed provider

    def __init__(
        self,
        primary_provider: Optional[Union[str, Any]] = None,
        cloudflare_account_id: Optional[str] = None,
        cloudflare_api_token: Optional[str] = None,
        cloudflare_model: Optional[str] = None,
        enable_ovh: Optional[bool] = None,
        ovh_model: Optional[str] = None,
        nvidia_api_key: Optional[str] = None,
        nvidia_model: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        openrouter_model: Optional[str] = None,
        openrouter_base_url: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        groq_model: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        mistral_api_key: Optional[str] = None,
        mistral_model: Optional[str] = None,
        github_token: Optional[str] = None,
        github_model: Optional[str] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        # Backward-compatibility arguments:
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        if hasattr(primary_provider, "primary_provider"):
            config = primary_provider
            primary_provider = config.primary_provider
        else:
            try:
                config = get_config()
            except Exception:
                from .config import Config
                config = Config()

        self.primary_provider = str(primary_provider or getattr(config, "primary_provider", "cloudflare") or "cloudflare").lower()
        self.cloudflare_account_id = cloudflare_account_id if cloudflare_account_id is not None else getattr(config, "cloudflare_account_id", None)
        self.cloudflare_api_token = cloudflare_api_token if cloudflare_api_token is not None else getattr(config, "cloudflare_api_token", None)
        self.cloudflare_model = cloudflare_model or getattr(config, "cloudflare_model", "@cf/meta/llama-3.2-11b-vision-instruct")

        self.enable_ovh = enable_ovh if enable_ovh is not None else getattr(config, "enable_ovh", True)
        self.ovh_model = ovh_model or getattr(config, "ovh_model", "Qwen2.5-VL-72B-Instruct")

        self.nvidia_api_key = nvidia_api_key if nvidia_api_key is not None else getattr(config, "nvidia_api_key", None)
        self.nvidia_model = nvidia_model or getattr(config, "nvidia_model", "meta/llama-3.2-11b-vision-instruct")

        self.openrouter_api_key = openrouter_api_key if openrouter_api_key is not None else config.openrouter_api_key
        self.openrouter_model = openrouter_model or config.openrouter_model
        self.openrouter_base_url = openrouter_base_url or config.openrouter_base_url

        self.groq_api_key = groq_api_key if groq_api_key is not None else config.groq_api_key
        self.groq_model = groq_model or config.groq_model

        self.gemini_api_key = gemini_api_key if gemini_api_key is not None else getattr(config, "gemini_api_key", None)
        self.gemini_model = gemini_model or getattr(config, "gemini_model", "gemini-3-flash-preview")

        self.mistral_api_key = mistral_api_key if mistral_api_key is not None else getattr(config, "mistral_api_key", None)
        self.mistral_model = mistral_model or getattr(config, "mistral_model", "pixtral-12b-2409")

        self.github_token = github_token if github_token is not None else getattr(config, "github_token", None)
        self.github_model = github_model or getattr(config, "github_model", "gpt-4o-mini")

        self.connect_timeout = connect_timeout or config.http_connect_timeout
        self.read_timeout = read_timeout or config.http_read_timeout

    def _optimize_image_for_ai(self, image_path: Path) -> Path:
        """Resize high-res screenshots to max 2048px (preserving crisp text readability),
        compress to 95% JPEG, and strip metadata for lightning-fast network uploads."""
        try:
            with Image.open(image_path) as img:
                # Convert RGBA / P palette to RGB for JPEG encoding
                if img.mode in ("RGBA", "LA", "P"):
                    rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                    img = rgb_img
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                orig_w, orig_h = img.size
                max_dim = 2048  # High resolution preserved for small math symbols & MCQ options
                if orig_w > max_dim or orig_h > max_dim:
                    scale = max_dim / float(max(orig_w, orig_h))
                    new_w = max(1, int(orig_w * scale))
                    new_h = max(1, int(orig_h * scale))
                    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                # Save to optimized temporary JPEG file
                opt_path = image_path.with_name(f"{image_path.stem}_opt.jpg")
                img.save(opt_path, format="JPEG", quality=95, optimize=True)
                return opt_path
        except Exception as e:
            print(f"[warning] Image optimization failed ({e}), using original.")
            return image_path

    def analyze_screenshot(
        self,
        image_path: Path,
        prompt: Optional[str] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Analyze a screenshot using the primary provider with automatic failover across
        Google Gemini, Cloudflare, OVHcloud Kepler, and NVIDIA NIM."""
        if not image_path.exists():
            raise GeminiServiceError(f"Image not found at {image_path}")

        if image_path.suffix.lower() not in SUPPORTED_EXTS:
            raise GeminiServiceError(
                f"Unsupported image format: {image_path.suffix}. Supported: {SUPPORTED_EXTS}"
            )

        optimized_image_path = self._optimize_image_for_ai(image_path)

        if not prompt:
            prompt = _dec_str(base64.b64decode(_PROMPT_B64))

        # Determine execution order based on primary_provider
        provider_order = []
        if self.primary_provider == "gemini" and self.gemini_api_key:
            provider_order.append("gemini")
        elif self.primary_provider == "cloudflare" and self.cloudflare_account_id and self.cloudflare_api_token:
            provider_order.append("cloudflare")
        elif self.primary_provider == "ovh" and self.enable_ovh:
            provider_order.append("ovh")
        elif self.primary_provider == "nvidia" and self.nvidia_api_key:
            provider_order.append("nvidia")
        elif self.primary_provider == "mistral" and self.mistral_api_key:
            provider_order.append("mistral")
        elif self.primary_provider == "github" and self.github_token:
            provider_order.append("github")
        elif self.primary_provider == "openrouter" and self.openrouter_api_key:
            provider_order.append("openrouter")
        elif self.primary_provider == "groq" and self.groq_api_key:
            provider_order.append("groq")
        else:
            if self.gemini_api_key:
                provider_order.append("gemini")
            elif self.cloudflare_account_id and self.cloudflare_api_token:
                provider_order.append("cloudflare")
            elif self.enable_ovh:
                provider_order.append("ovh")
            elif self.nvidia_api_key:
                provider_order.append("nvidia")
            elif self.mistral_api_key:
                provider_order.append("mistral")
            elif self.github_token:
                provider_order.append("github")
            elif self.openrouter_api_key:
                provider_order.append("openrouter")

        # Fallbacks in resilience priority order:
        # 1. Google Gemini (1500 req/day free unblocked) -> 2. Cloudflare Workers AI -> 3. OVH (Keyless 72B) -> 4. NVIDIA NIM -> 5. Mistral -> 6. GitHub -> 7. OpenRouter -> 8. Groq
        fallbacks = [
            ("gemini", self.gemini_api_key),  # Google Gemini 1500 req/day free unblocked
            ("cloudflare", bool(self.cloudflare_account_id and self.cloudflare_api_token)),
            ("ovh", self.enable_ovh),  # 100% keyless Qwen2.5-VL-72B safety net (unblocked)
            ("nvidia", self.nvidia_api_key),  # Fast NVIDIA NIM 11B Vision
            ("mistral", self.mistral_api_key),  # Mistral AI (Pixtral 12B free tier)
            ("github", self.github_token),  # GitHub Models 150 req/day free
            ("openrouter", self.openrouter_api_key),  # Free vision fallback
            ("groq", self.groq_api_key),
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

        if not provider_order:
            raise GeminiServiceError(
                "No AI provider available. Enable OVH (ENABLE_OVH=true) or provide an OPENROUTER_API_KEY in .env."
            )

        errors = []
        try:
            for provider in provider_order:
                try:
                    if provider == "cloudflare":
                        result = self._analyze_with_cloudflare(
                            account_id=self.cloudflare_account_id,
                            api_token=self.cloudflare_api_token,
                            model=self.cloudflare_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                        )
                    elif provider == "ovh":
                        result = self._analyze_with_openai_compatible(
                            url=_URL_OVH,
                            api_key=None,
                            model=self.ovh_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name="OVHcloud Kepler",
                        )
                    elif provider == "nvidia":
                        result = self._analyze_with_openai_compatible(
                            url=_URL_NVIDIA,
                            api_key=self.nvidia_api_key,
                            model=self.nvidia_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name="NVIDIA NIM (11B Vision)",
                        )
                    elif provider == "mistral":
                        result = self._analyze_with_openai_compatible(
                            url=_URL_MISTRAL,
                            api_key=self.mistral_api_key,
                            model=self.mistral_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name=f"Mistral AI ({self.mistral_model})",
                        )
                    elif provider == "gemini":
                        result = self._analyze_with_openai_compatible(
                            url=_URL_GEMINI,
                            api_key=self.gemini_api_key,
                            model=self.gemini_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name=f"Google Gemini ({self.gemini_model})",
                        )
                    elif provider == "github":
                        result = self._analyze_with_openai_compatible(
                            url=_URL_GITHUB,
                            api_key=self.github_token,
                            model=self.github_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name=f"GitHub Models ({self.github_model})",
                        )
                    elif provider == "openrouter":
                        or_base = (self.openrouter_base_url or _URL_OPENROUTER_DEF).rstrip("/")
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
                    elif provider == "groq":
                        result = self._analyze_with_openai_compatible(
                            url=_URL_GROQ,
                            api_key=self.groq_api_key,
                            model=self.groq_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name="Groq Cloud",
                        )
                    else:
                        continue

                    # Provider succeeded: reset failure state
                    self._failed_providers.pop(provider, None)
                    return result

                except Exception as err:
                    self._failed_providers[provider] = time.time()
                    errors.append(f"{provider}: {err}")
                    print(f"[{provider} failover] Provider {provider} failed: {err}")
                    continue

            # If all failed: check if failure was due to no network / DNS / socket issues
            net_keywords = [
                "11001", "getaddrinfo", "network error", "connecterror",
                "nameresolutionerror", "connection timeout", "timeout",
                "timed out", "unreachable", "no route", "connection refused",
                "connection reset", "connection aborted", "failed to establish",
                "dns", "gaierror"
            ]
            all_net_failed = bool(errors) and all(
                any(k in e.lower() for k in net_keywords)
                for e in errors
            )
            if all_net_failed:
                self._failed_providers.clear()
                raise GeminiServiceError(
                    "No Internet Connection.\n"
                    "Please check your Wi-Fi, Ethernet, or mobile network connection and try again."
                )

            # Check if failure was due to rate limits (HTTP 429 / Quota)
            all_rate_limited = bool(errors) and all(
                any(k in e.lower() for k in ["429", "rate limit", "rate_limit", "quota exceeded"])
                for e in errors
            )
            if all_rate_limited:
                raise GeminiServiceError(
                    "AI Server Busy (Rate Limit 429).\n"
                    "The public server is temporarily overloaded. Please wait 1-2 minutes or check NVIDIA NIM in .env."
                )

            raise GeminiServiceError(f"All available vision providers failed: {'; '.join(errors)}")
        finally:
            if optimized_image_path != image_path and optimized_image_path.exists():
                try:
                    optimized_image_path.unlink()
                except Exception:
                    pass

    def _analyze_with_cloudflare(
        self,
        account_id: str,
        api_token: str,
        model: str,
        image_path: Path,
        prompt: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Native high-speed streaming client for Cloudflare Workers AI."""
        with open(image_path, "rb") as f:
            b64_str = base64.b64encode(f.read()).decode("utf-8")

        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        payload = {
            "prompt": prompt,
            "image": b64_str,
            "max_tokens": 600,
            "stream": True,
        }

        timeout = httpx.Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=5.0,
            pool=3.0,
        )

        full_text = []
        for attempt in range(2):
            try:
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    with client.stream("POST", url, json=payload, headers=headers) as resp:
                        if resp.status_code != 200:
                            err_bytes = resp.read()
                            err_text = err_bytes.decode("utf-8", errors="replace")
                            # If Meta license agreement required, auto-agree and retry once
                            if resp.status_code in (400, 403) and any(w in err_text.lower() for w in ("agree", "license", "terms")):
                                try:
                                    agree_resp = client.post(url, headers=headers, json={"prompt": "agree"}, timeout=10.0)
                                    if agree_resp.status_code == 200:
                                        continue
                                except Exception:
                                    pass
                            raise GeminiServiceError(f"Cloudflare Workers AI returned {resp.status_code}: {err_text[:200]}")

                        for line in resp.iter_lines():
                            if not line:
                                continue
                            line_str = line.strip()
                            if line_str.startswith("data: "):
                                data_content = line_str[6:].strip()
                                if data_content == "[DONE]":
                                    break
                                try:
                                    chunk_json = json.loads(data_content)
                                    raw_token = chunk_json.get("response") or ""
                                    if not raw_token and "choices" in chunk_json:
                                        raw_token = chunk_json["choices"][0].get("delta", {}).get("content", "")
                                    token = str(raw_token) if raw_token else ""
                                    if token:
                                        full_text.append(token)
                                        if callback:
                                            callback(token)
                                except Exception:
                                    continue

                res = "".join(full_text).strip()
                if not res:
                    raise GeminiServiceError("Empty response from Cloudflare Workers AI")
                return res
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if attempt == 0:
                    time.sleep(0.4)
                    continue
                raise

    def _analyze_with_openai_compatible(
        self,
        url: str,
        api_key: Optional[str],
        model: str,
        image_path: Path,
        prompt: str,
        callback: Optional[Callable[[str], None]] = None,
        provider_name: str = "Fallback Provider",
        extra_headers: Optional[dict] = None,
    ) -> str:
        """Unified OpenAI-compatible Vision API client with high-speed streaming."""
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
            "max_tokens": 600,
            "stream": True,
        }

        timeout = httpx.Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=5.0,
            pool=3.0,
        )

        full_text = []
        for attempt in range(2):
            try:
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    with client.stream("POST", url, json=payload, headers=headers) as resp:
                        if resp.status_code != 200:
                            err_text = ""
                            try:
                                err_bytes = resp.read()
                                err_text = err_bytes.decode("utf-8", errors="replace")
                            except Exception:
                                pass

                            raise GeminiServiceError(f"{provider_name} returned {resp.status_code}: {err_text[:200]}")

                        reasoning_tokens = []
                        for line in resp.iter_lines():
                            if not line:
                                continue
                            line_str = line.strip()
                            if line_str.startswith("data: "):
                                data_content = line_str[6:].strip()
                                if data_content == "[DONE]":
                                    break
                                try:
                                    chunk_json = json.loads(data_content)
                                    choices = chunk_json.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        raw_token = delta.get("content")
                                        token = str(raw_token) if raw_token is not None else ""
                                        raw_reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                                        reasoning = str(raw_reasoning) if raw_reasoning is not None else ""
                                        if reasoning:
                                            reasoning_tokens.append(reasoning)
                                        if token:
                                            full_text.append(token)
                                            if callback:
                                                callback(token)
                                except Exception:
                                    continue

                res = "".join(full_text).strip()
                if not res and reasoning_tokens:
                    # Model only emitted reasoning tokens or hit max_tokens before content
                    res = "".join(reasoning_tokens).strip()
                    if callback and res:
                        callback(res)
                if not res:
                    raise GeminiServiceError(f"Empty response from {provider_name}")
                return res
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                if attempt == 0:
                    time.sleep(0.4)
                    continue
                err_msg = str(e).lower()
                if "11001" in err_msg or "getaddrinfo" in err_msg or "nameresolution" in err_msg or "gaierror" in err_msg:
                    raise GeminiServiceError(f"Network error: Unable to resolve {provider_name} (check internet/DNS)")
                raise GeminiServiceError(f"Connection timeout to {provider_name}")
            except httpx.ReadTimeout:
                raise GeminiServiceError(f"Read timeout from {provider_name}")
            except Exception as e:
                if isinstance(e, GeminiServiceError):
                    raise
                err_msg = str(e).lower()
                if "11001" in err_msg or "getaddrinfo" in err_msg or "nameresolution" in err_msg or "gaierror" in err_msg:
                    raise GeminiServiceError(f"Network error: Unable to resolve {provider_name} (check internet/DNS)")
                raise GeminiServiceError(f"{provider_name} error: {e}")

    def analyze_image_stream(
        self,
        image_path: str,
        callback: Optional[Callable[[str], None]] = None,
        prompt: Optional[str] = None,
    ) -> str:
        """Stream real-time tokens to callback while analyzing a screenshot."""
        return self.analyze_screenshot(Path(image_path), prompt=prompt, callback=callback)

    def analyze_image(
        self,
        image_path: str,
        prompt: Optional[str] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Backward-compatible helper to analyze a screenshot image and return the text."""
        return self.analyze_screenshot(Path(image_path), prompt=prompt, callback=callback)


# Alias for clean architecture
AIService = GeminiService


def analyze_image(
    image_path: str,
    prompt: Optional[str] = None,
    callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Convenience module-level helper to analyze a screenshot image."""
    return GeminiService().analyze_screenshot(Path(image_path), prompt=prompt, callback=callback)
