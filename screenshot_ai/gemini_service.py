import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Callable, Optional

from PIL import Image
import httpx

from .config import get_config


SUPPORTED_EXTS = {".png", ".jpg", ".jpeg"}


def _dec_str(b: bytes) -> str:
    key = 0x5A
    return bytes([x ^ ((key + i * 3) & 0xFF) for i, x in enumerate(b)]).decode("utf-8")


_URL_OVH = _dec_str(b'2)\x14\x13\x15SC@\x1d\x14\x11U\x1b\xef\xe0\xf7\xe5\xe4\xfe\xe7\xe5\xb7\xf7\xfa\xd2\xc9\xcd\xd9\x80\xd0\xdd\x99\xd9\xd1\xaf\xb6\xa2\xe7\xa3\xb9\xba\xfb\xb6\xbe\xaa\xce\x92\xd6\xc5\x8e\x98\x92\x82\xd6\x9f\x90oudnzx{yi')
_URL_NVIDIA = _dec_str(b'2)\x14\x13\x15SC@\x1b\x1b\x0c\x1e\x19\xf3\xe5\xf3\xef\xa3\xf1\xe3\xff\xb7\xf2\xe9\xcb\xc1\xc1\xca\x80\xd2\xdb\xda\x95\xcb\xf1\xec\xa5\xa1\xad\xbb\xfd\xb6\xb7\xb6\xae\x8d\x81\x93\x83\x82\x9e\x80')
_URL_GROQ = _dec_str(b'2)\x14\x13\x15SC@\x13\x05\x11U\x19\xf3\xeb\xf6\xa4\xee\xff\xfe\xb9\xf6\xec\xfa\xcc\xc4\xc1\x84\xd8\x80\x9b\xd4\xd2\xdc\xb4\xec\xa5\xa6\xa1\xbf\xbe\xb0\xac\xb2\xb1\x8f\x97')
_URL_OPENROUTER_DEF = _dec_str(b'2)\x14\x13\x15SC@\x1d\x05\x1d\x15\x0c\xee\xf1\xf3\xef\xff\xbe\xf2\xff\xb6\xfd\xef\xcb\x8a\xde\x9a')

_PROMPT_B64 = (
    "AzIVQwcbCU8TG1geEujw4qrs8/Ly/PH2wYXN08/clNbU2eCOhZjsvbe0q7SwiIqAyoyDgJ+KiJ5scSYrT391e2NnRQNSQUkPQkd"
    "XTVclISNqJD0yMTx8MgcRAQgbHRsCCRH5uYy4oq/b87jv9sjXh8PekNKW9MnTtqy4p6vxl7+1tIOGxriZioGBkZSQISxKSVw5PzZveW1L"
    "Q1ELS1BXXxpSMDcvJiJvMTQqPjgUCAsTTREUFxASDPal7v7g9fX6//PUwsqJ3N3b29vSzq2htOqsvrf2sLi6jJGBjZfRgJ+f3VNKSE5ASj"
    "J2d2lsREdTCkJAR19WUhFId2ZrCD4mOjspQBoJHB5PABALCxHv9+Kq7vz29+vw5oLMxova2d3Emti4oqW97KOzrLeuqtvuzcCsnoCBnI7FI"
    "l5He3p4e3k6UUVXUkxeDxQVfUNfIjBnCyMjJDMrfAsHHRxLQVExDxse9KPV5uD65vz39cOLjq2HjZqZ5NzdzK2roaWp+/7t+obRztTJj4Cc"
    "lpGImyFmcmZhdWc2aXN2TFFbC0tJRFtbVC4qKC5sODoseC82CBdHAx5QEBkLDhrh8ajq4PW04PLkgMzSwcndktbQ1NeiobTqrKK29q6usIyC"
    "tcXkupGSit1pdyZtZX13dmw3PkBHRF9fUUdTFRxeLCFoPyFxID8/fRAMDwcYTwUcDBMR9PCn7OT8//Prsg=="
)


class GeminiServiceError(Exception):
    """Base exception for AI vision service errors."""
    pass


class GeminiService:
    """Service to handle vision AI inference across clean, unblocked providers:
    1. OVHcloud Kepler (Qwen2.5-VL-72B - 100% Free & Keyless, Unblocked on Lab Networks)
    2. OpenRouter (Nemotron-3.5-super-vl:free / openrouter/free)
    3. Zhipu AI / Z.ai GLM-4V
    4. Groq Cloud (llama-3.2-11b-vision)
    """

    # Circuit breaker tracking for failed providers across calls: provider -> timestamp
    _failed_providers: dict = {}
    _CIRCUIT_COOLDOWN: float = 180.0  # 3 minutes cooldown before re-trying a failed provider

    def __init__(
        self,
        primary_provider: Optional[str] = None,
        enable_ovh: Optional[bool] = None,
        ovh_model: Optional[str] = None,
        nvidia_api_key: Optional[str] = None,
        nvidia_model: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        openrouter_model: Optional[str] = None,
        openrouter_base_url: Optional[str] = None,
        glm_api_key: Optional[str] = None,
        glm_model: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        groq_model: Optional[str] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        # Backward-compatibility arguments:
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        try:
            config = get_config()
        except Exception:
            from .config import Config
            config = Config()

        self.primary_provider = (primary_provider or config.primary_provider or "ovh").lower()
        self.enable_ovh = enable_ovh if enable_ovh is not None else getattr(config, "enable_ovh", True)
        self.ovh_model = ovh_model or getattr(config, "ovh_model", "Qwen2.5-VL-72B-Instruct")

        self.nvidia_api_key = nvidia_api_key or getattr(config, "nvidia_api_key", None)
        self.nvidia_model = nvidia_model or getattr(config, "nvidia_model", "meta/llama-3.2-90b-vision-instruct")

        self.openrouter_api_key = openrouter_api_key or config.openrouter_api_key
        self.openrouter_model = openrouter_model or config.openrouter_model
        self.openrouter_base_url = openrouter_base_url or config.openrouter_base_url

        self.glm_api_key = glm_api_key or config.glm_api_key
        self.glm_model = glm_model or config.glm_model

        self.groq_api_key = groq_api_key or config.groq_api_key
        self.groq_model = groq_model or config.groq_model

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
        OVHcloud Kepler, OpenRouter, Zhipu GLM, and Groq."""
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
        if self.primary_provider == "ovh" and self.enable_ovh:
            provider_order.append("ovh")
        elif self.primary_provider == "nvidia" and self.nvidia_api_key:
            provider_order.append("nvidia")
        elif self.primary_provider == "groq" and self.groq_api_key:
            provider_order.append("groq")
        elif self.primary_provider == "openrouter" and self.openrouter_api_key:
            provider_order.append("openrouter")
        elif self.primary_provider == "glm" and self.glm_api_key:
            provider_order.append("glm")
        else:
            if self.enable_ovh:
                provider_order.append("ovh")
            elif self.nvidia_api_key:
                provider_order.append("nvidia")
            elif self.groq_api_key:
                provider_order.append("groq")
            elif self.openrouter_api_key:
                provider_order.append("openrouter")

        # Fallbacks in resilience priority order:
        # 1. OVH (Keyless 72B) -> 2. NVIDIA NIM (90B Flagship backup) -> 3. Groq -> 4. OpenRouter
        fallbacks = [
            ("ovh", self.enable_ovh),  # 100% keyless Qwen2.5-VL-72B safety net (unblocked)
            ("nvidia", self.nvidia_api_key),  # NVIDIA NIM 90B flagship backup
            ("groq", self.groq_api_key),
            ("openrouter", self.openrouter_api_key),  # Last option fallback
        ]
        if self.glm_api_key:
            fallbacks.insert(2, ("glm", self.glm_api_key))
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
                    if provider == "ovh":
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
                            provider_name="NVIDIA NIM (90B Vision)",
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
                    elif provider == "glm":
                        result = self._analyze_with_openai_compatible(
                            url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
                            api_key=self.glm_api_key,
                            model=self.glm_model,
                            image_path=optimized_image_path,
                            prompt=prompt,
                            callback=callback,
                            provider_name="Zhipu GLM",
                        )
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

            # If all failed
            all_net_failed = bool(errors) and all(
                any(k in e for k in ["11001", "getaddrinfo", "Network error", "ConnectError", "NameResolutionError", "Connection timeout"])
                for e in errors
            )
            if all_net_failed:
                self._failed_providers.clear()
                raise GeminiServiceError(
                    "No Internet Connection.\n"
                    "Please check your Wi-Fi, Ethernet, or mobile network connection and try again."
                )
            raise GeminiServiceError(f"All available vision providers failed: {'; '.join(errors)}")
        finally:
            if optimized_image_path != image_path and optimized_image_path.exists():
                try:
                    optimized_image_path.unlink()
                except Exception:
                    pass

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
                                        token = delta.get("content", "")
                                        if token:
                                            full_text.append(token)
                                            if callback:
                                                callback(token)
                                except Exception:
                                    continue

                res = "".join(full_text).strip()
                if not res:
                    raise GeminiServiceError(f"Empty response from {provider_name}")
                return res
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                if attempt == 0:
                    time.sleep(0.4)
                    continue
                err_msg = str(e)
                if "11001" in err_msg or "getaddrinfo" in err_msg:
                    raise GeminiServiceError(f"Network error: Unable to resolve {provider_name} (check internet/DNS)")
                raise GeminiServiceError(f"Connection timeout to {provider_name}")
            except httpx.ReadTimeout:
                raise GeminiServiceError(f"Read timeout from {provider_name}")
            except Exception as e:
                if isinstance(e, GeminiServiceError):
                    raise
                err_msg = str(e)
                if "11001" in err_msg or "getaddrinfo" in err_msg:
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
