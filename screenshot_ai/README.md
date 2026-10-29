# Screenshot AI Assistant

A lightweight Windows desktop app that sends a user-selected screenshot to
Google Gemini and shows the explanation in a compact popup.

## Features

- Analyze PNG and JPG/JPEG screenshots with Gemini.
- **Windows Snipping Tool support:**
  - `Win+Shift+S` → copy → press the hotkey: the clipboard snip is analyzed.
  - Tray → **Analyze clipboard image** does the same on demand.
  - Optional tray toggle watches the folders the Snipping Tool saves into.
- MCQ-aware prompt: step-by-step reasoning plus the best-supported option.
- Compact PySide6 popup with copy / analyze-another / close buttons.
- Configurable system-wide hotkey (default `Ctrl+Shift+S`).
- System tray with **Open**, **Analyze a screenshot**, **Watch a folder**,
  **Pause/Resume processing**, **Run at Windows login**, and **Exit**.
- Optional folder monitoring: only a folder you explicitly choose is watched,
  and automatic uploads can be paused at any time.
- System notifications (click the toast or tray icon to open results).
- Network requests run on a worker thread, so the UI never freezes.
- Clear error messages for unreadable images, auth problems, quota limits and
  network failures.
- SHA-256 duplicate tracking plus an in-flight queue, so the same screenshot is
  not analyzed or uploaded twice.
- Single-instance guard: a second launch cannot double-upload screenshots.
- API key stays in `.env`; it is never hardcoded or bundled into the `.exe`.

## Project layout

```
screenshot_ai/
  app.py                 # entry point + controller (popup, hotkey, tray, watcher)
  config.py              # loads .env and validates settings
  gemini_service.py      # Gemini client, image validation, error mapping
  screenshot_service.py  # file picker, validation, duplicate tracking, folder watchdog
  popup.py               # PySide6 result window + background analysis thread
  hotkey.py              # Win32 RegisterHotKey global shortcut
  notifications.py       # system tray icon + native notifications
  startup.py             # optional "Run at Windows login" registry entry
  icons.py               # icon drawn in code
  requirements.txt
  .env.example
  .gitignore
  README.md
  assets/
```

## Setup

1. Install Python 3.10+ (3.11/3.12 recommended) from
   <https://www.python.org/downloads/windows/>. Tick **Add python.exe to PATH**.
2. Create and activate a virtual environment:

   ```bat
   cd "D:\Education Works\GitHub Works\EasyAnswer"
   py -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies:

   ```bat
   pip install --upgrade pip
   pip install -r screenshot_ai\requirements.txt
   ```

4. Create your local config (never commit it):

   ```bat
   copy screenshot_ai\.env.example .env
   ```

5. Edit `.env` and set `GEMINI_API_KEY` from
   <https://aistudio.google.com/apikey>.

## Run

```bat
python -m screenshot_ai.app
```

The popup opens. Choose a screenshot, or close the window and press your hotkey
later. The app keeps running in the system tray.

Quick Gemini-only smoke test (draws a sample MCQ and analyzes it):

```bat
python tools\check_gemini.py
```

## Tray controls

| Action | What it does |
|---|---|
| Open window | Same as pressing the hotkey |
| Analyze a screenshot... | Manual picker; always allowed, even while paused |
| Analyze clipboard image | Analyzes a snip copied with `Win+Shift+S` |
| Watch a folder... | Starts monitoring only that folder |
| Watch common screenshot folders | Toggles `Pictures\Screenshots`, `OneDrive\Pictures\Screenshots` and `Desktop` |
| Stop watching folders | Stops monitoring and clears queued files |
| Pause / Resume processing | Pauses automatic uploads and queues new files |
| Run at Windows login | Adds/removes a per-user registry `Run` entry |
| Exit | Unregisters the hotkey and exits cleanly |

## Snipping Tool

There are two ways to capture with the Snipping Tool, and both are supported:

1. **`Win+Shift+S` then copy** (the default): the snip is only on the
   clipboard. Press your configured hotkey (default `Ctrl+Shift+S`); if an
   image is on the clipboard it is analyzed immediately and the popup subtitle
   says **Clipboard image**. If the clipboard has no image, the popup opens
   normally. Turn this off with `CLIPBOARD_ON_HOTKEY=false`.
2. **Save / Auto-save in Snipping Tool**: enable
   **Watch common screenshot folders** in the tray, or set
   `WATCH_COMMON_FOLDERS=true`. The app then watches the folders the tool saves
   into and analyzes new images as they appear.

Clipboard images are copied to a temporary file, hashed for duplicate
protection, and deleted after the analysis finishes. The clipboard is never
polled in the background; it is read only when you press the hotkey or choose
the tray action.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | required | Google AI Studio key |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Gemini model for image analysis |
| `HOTKEY` | `ctrl+shift+s` | Global shortcut; needs one modifier + one key |
| `ENABLE_NOTIFICATIONS` | `true` | Show a toast when analysis finishes |
| `NOTIFICATION_DURATION_MS` | `4000` | Toast duration hint (Windows may ignore it) |
| `WATCH_FOLDER` | empty | Folder to watch; empty = manual only |
| `WATCH_COMMON_FOLDERS` | `false` | Watch the Snipping Tool save folders |
| `CLIPBOARD_ON_HOTKEY` | `true` | Analyze a clipboard image when the hotkey is pressed |
| `START_MINIMIZED` | `false` | Start in the tray without opening the popup |

> **Model note:** `gemini-2.5-flash` now returns `404` for new accounts. The app
> defaults to `gemini-3.5-flash`, which supports image input. If Google changes
> model access again, list what your key can use with
> `python tools\list_models.py` and set `GEMINI_MODEL` accordingly.

Supported hotkeys: `ctrl`, `alt`, `shift`, `win` plus a letter, digit, `F1`-`F24`,
or keys such as `space`, `enter`, `esc`, `printscreen`.

## Security and consent

- The image **is uploaded to Google Gemini** for analysis. The popup says so,
  and folder monitoring is off unless you choose a folder yourself.
- Clipboard content is read only on the hotkey or the tray action, never in the
  background, and only images are used.
- `WATCH_FOLDER` is opt-in. While monitoring, use **Pause processing** to stop
  automatic uploads; manual picks still work.
- `.env` is listed in `.gitignore`. Keep it that way.
- The executable reads `GEMINI_API_KEY` from the environment; it does not embed
  a private key. Each user supplies their own key.
- Anyone with your key can spend your quota. If a key leaks, revoke it in
  Google AI Studio and create a new one.

## Troubleshooting

- **`GEMINI_API_KEY is not set`** - `.env` must be in the repo root or in
  `screenshot_ai\`.
- **`Could not register 'ctrl+shift+s'`** - another app owns that shortcut.
  Change `HOTKEY` in `.env`.
- **`ModuleNotFoundError: screenshot_ai`** - run commands from the repo root.
- **Qt platform plugin error** - `pip install --force-reinstall PySide6`.
- **`404 NOT_FOUND` from Gemini** - the configured model is closed to your
  account. Run `python tools\list_models.py` and set `GEMINI_MODEL` to a listed
  flash model.
- **Nothing happens when saving a screenshot into the watched folder** - check
  that monitoring is not paused, the folder is the same one shown in the tray
  tooltip, and the file is `.png`, `.jpg`, or `.jpeg`.
- **Hotkey opens the window instead of analyzing my snip** - the clipboard did
  not contain an image (some tools copy a file list, or the snip was only saved
  to disk). Use **Analyze clipboard image** or enable the common-folder watch.
- **"No image found in the clipboard"** - copy the snip again with
  `Win+Shift+S` → **Copy**, or save it and pick the file.
- **A stale image was analyzed** - the clipboard still held an older snip.
  Clear the clipboard before pressing the hotkey, or set
  `CLIPBOARD_ON_HOTKEY=false` and use the tray action deliberately.
- **Startup entry does not work** - the registry path points at the current
  Python/`.exe` location. Toggle **Run at Windows login** off and on again after
  moving the project or rebuilding the exe.

## Roadmap

- [x] Stage 1 - environment setup
- [x] Stage 2 - Gemini integration
- [x] Stage 3 - screenshot handling / duplicates
- [x] Stage 4 - popup UI
- [x] Stage 5 - hotkey + notifications
- [x] Stage 6 - tray controls, pause/resume, folder monitoring, startup
- [ ] Stage 7 - testing
- [ ] Stage 8 - PyInstaller build
