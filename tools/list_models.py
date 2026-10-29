"""List Gemini models your API key can use for content generation.

Usage:
    python tools/list_models.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from screenshot_ai.config import get_config  # noqa: E402


def main() -> int:
    from google import genai

    client = genai.Client(api_key=get_config().gemini_api_key)
    for model in client.models.list():
        actions = getattr(model, "supported_actions", None) or []
        if not actions or "generateContent" in actions:
            print(model.name.removeprefix("models/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
