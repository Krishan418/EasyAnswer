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
        else:
            self.api_key = api_key
            self.model = model or "gemini-3.5-flash"
            self.grok_api_key = grok_api_key
            self.grok_model = grok_model or "grok-2-vision-1212"
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

        try:
            # Load image and ensure underlying file handle is closed
            with Image.open(image_path_obj) as img:
                img.load()
                image = img.copy()
            contents = [prompt, image]

            full_text = []
            try:
                # Fast real-time stream
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

                # Fallback to non-streaming only for stream protocol issues
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

        except Exception as e:
            if getattr(self, "grok_api_key", None):
                print(
                    f"[failover] Gemini request failed ({e}). Trying Grok Vision fallback...",
                    file=sys.stderr,
                )
                try:
                    return self._analyze_with_grok(image_path_obj, prompt, callback)
                except Exception as grok_err:
                    print(f"[failover] Grok fallback also failed: {grok_err}", file=sys.stderr)

            if isinstance(e, GeminiServiceError):
                raise

            # Map common errors
            err_str = str(e).lower()
            if "api key" in err_str or "unauthorized" in err_str or "permission" in err_str:
                raise GeminiServiceError(f"Authentication error: {e}")
            if "rate" in err_str or "quota" in err_str or "429" in err_str:
                raise GeminiServiceError(f"Rate limit or quota exceeded: {e}")
            if "404" in err_str or "not found" in err_str:
                raise GeminiServiceError(
                    f"Model '{self.model}' not found (404). Run 'python tools/list_models.py' "
                    f"to see models supported by your API key and update GEMINI_MODEL in .env: {e}"
                )
            if "network" in err_str or "timeout" in err_str or "connection" in err_str:
                raise GeminiServiceError(f"Network error: {e}")
            raise GeminiServiceError(f"Gemini API error: {e}")

    def _analyze_with_grok(
        self,
        image_path: Path,
        prompt: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Fallback to xAI Grok Vision API if Gemini is blocked or fails."""
        import base64
        import json
        import httpx

        ext = image_path.suffix.lstrip(".").lower()
        if ext == "jpg":
            ext = "jpeg"

        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        headers = {
            "Authorization": f"Bearer {self.grok_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.grok_model,
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
        with httpx.Client(timeout=30.0) as client:
            with client.stream(
                "POST", "https://api.x.ai/v1/chat/completions", headers=headers, json=payload
            ) as response:
                if response.status_code != 200:
                    err_body = response.read().decode("utf-8", errors="replace")
                    raise GeminiServiceError(f"Grok API error ({response.status_code}): {err_body}")

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
            raise GeminiServiceError("Empty response from Grok API")
        return result

    def analyze_image(self, image_path: str, prompt: Optional[str] = None) -> str:
        """Analyze a screenshot/image using Gemini (or Grok fallback) and return the full text."""
        return self.analyze_image_stream(image_path, prompt=prompt)




# Convenience function
def analyze_image(image_path: str, prompt: Optional[str] = None) -> str:
    service = GeminiService()
    return service.analyze_image(image_path, prompt)
