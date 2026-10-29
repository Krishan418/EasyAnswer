# Assets

Static icons or images can live here.

The tray and window icon are currently drawn in code (`screenshot_ai/icons.py`),
so the app has no external asset dependency. `build_icon.py` (added in Stage 8)
generates `app.ico` from that same drawing for PyInstaller.
