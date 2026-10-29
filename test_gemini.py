#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from screenshot_ai.gemini_service import analyze_image, GeminiServiceError


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_gemini.py <path_to_image.png/jpg/jpeg>")
        print("\nExample:")
        print("  python test_gemini.py sample.png")
        sys.exit(1)
    
    image_path = sys.argv[1]
    print(f"Analyzing image: {image_path}")
    print("Please wait...\n")
    
    try:
        result = analyze_image(image_path)
        print("=" * 60)
        print("ANALYSIS RESULT:")
        print("=" * 60)
        print(result)
        print("=" * 60)
    except GeminiServiceError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
