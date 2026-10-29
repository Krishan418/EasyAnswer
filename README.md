# EasyAnswer (Screenshot AI Assistant)

A lightweight, high-performance Windows desktop application that instantly captures and analyzes screenshots using **Google Gemini Vision** and displays explanations, step-by-step reasoning, and solutions in a sleek, non-intrusive floating popup.

---

## ✨ Features

- **Gemini Vision Powered**: Sends screenshots directly to Google Gemini for accurate visual reasoning, diagram comprehension, code analysis, and MCQ solving.
- **Windows Snipping Tool Integration**:
  - `Win+Shift+S` &rarr; copy snip &rarr; press hotkey (`Ctrl+Shift+S`): automatically analyzes the clipboard image.
  - System Tray &rarr; **Analyze clipboard image** analyzes on demand.
  - Optional auto-watch for folders the Windows Snipping Tool saves into (`Pictures\Screenshots`, `OneDrive`, `Desktop`).
- **Global Shortcut (No Third-Party Hooks)**: Native Win32 `RegisterHotKey` implementation for instant activation even when another window is focused.
- **Non-blocking UI**: Analysis requests execute on background worker threads (`QThread`), keeping the UI responsive with real-time feedback.
- **Smart Duplicate Prevention**: SHA-256 image hashing avoids re-uploading duplicate screenshots, preserving API quota.
- **Privacy & Security**:
  - Clipboard images are saved to a temporary file, analyzed, and deleted immediately.
  - Opt-in folder monitoring (off by default).
  - API keys are loaded via `.env` and never bundled or committed.
- **System Tray Controls**:
  - Run at Windows login (per-user registry, no administrator privileges required).
  - Pause/Resume automatic uploads.
  - Quick file picker and window toggle.
- **Pure Code Assets**: App icons are procedurally drawn via `QPainter` in memory—no extra binary image files required.

---

## 📁 Project Layout

```
EasyAnswer/
├── screenshot_ai/               # Core application package
│   ├── app.py                   # Main controller (tray, hotkey, watcher, single-instance)
│   ├── config.py                # Environment configuration loader (.env)
│   ├── gemini_service.py        # Gemini client wrapper, prompt tuning, and error mapping
│   ├── screenshot_service.py    # Image validation, hashing, clipboard reader, folder watcher
│   ├── popup.py                 # PySide6 popup dialog & background QThread worker
│   ├── hotkey.py                # Win32 RegisterHotKey global shortcut implementation
│   ├── notifications.py         # System tray icon and native Windows notifications
│   ├── startup.py               # Windows registry (HKCU Run) startup manager
│   ├── icons.py                 # Procedural icon generator
│   ├── requirements.txt         # Package dependencies
│   └── .env.example             # Template for configuration settings
├── tests/                       # Automated test suite (unittest / pytest)
│   ├── test_config.py           # Configuration parsing & validation tests
│   ├── test_hotkey.py           # Hotkey parsing & keycode tests
│   ├── test_screenshot_service.py # Image validation, SHA-256 deduplication, cleanup tests
│   └── test_gemini_service.py   # Gemini API client, response parsing & error mapping tests
├── tools/                       # Diagnostic and helper tools
│   ├── check_gemini.py          # Synthetic MCQ test to verify Gemini API connection
│   ├── check_snipping_tool.py   # Verifies clipboard image capture and folder watching
│   └── list_models.py           # Lists Gemini models supported by your API key
├── test_gemini.py               # CLI tool to analyze an image file directly
├── test_screenshot.py           # CLI tool to test image hashing and validation
└── README.md                    # Project documentation
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+ (Python 3.11 or 3.12 recommended) on Windows.
- A free Google Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).

### 2. Installation

Clone the repository and set up a virtual environment:

```powershell
# Navigate to the project directory
cd "d:\Education Works\GitHub Works\EasyAnswer"

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r screenshot_ai\requirements.txt
```

### 3. Configure `.env`

Copy the template configuration file:

```powershell
copy screenshot_ai\.env.example .env
```

Open `.env` and insert your Gemini API key:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash
HOTKEY=ctrl+shift+s
```

> **Tip:** You can run `python tools\list_models.py` at any time to list all active models supported by your API key.

### 4. Run the Application

```powershell
python -m screenshot_ai.app
```

The application will start, open the floating popup, and register itself in the Windows System Tray.

---

## ⌨️ How to Use & Shortcuts

| Shortcut / Action | Function | Description |
|---|---|---|
| **`Win + Shift + S` &rarr; `Ctrl + Shift + S`** | **Analyze Screenshot** | Snip area with Windows Snipping Tool, then press `Ctrl+Shift+S` to analyze directly from clipboard. |
| **`Ctrl + ~`** | **Toggle Window** | Show or hide the answer window instantly without needing to click or select the app. |
| **`Ctrl + Shift + Q`** | **Emergency Panic Quit** | Instantly closes and kills the application cleanly. |
| **Manual Selection** | **File Picker** | Click **Analyze another…** in the popup to choose any local image file. |

---

## ⚙️ Configuration Reference

| Environment Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(Required)* | Google AI Studio API key |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Gemini vision model identifier (e.g. `gemini-3.5-flash`, `gemini-2.5-flash`) |
| `HOTKEY` | `ctrl+shift+s` | Global screenshot analysis shortcut |
| `TOGGLE_HOTKEY` | `ctrl+~` | Global shortcut to toggle popup visibility |
| `QUIT_HOTKEY` | `ctrl+shift+q` | Global emergency exit shortcut |
| `SHOW_TRAY_ICON` | `false` | Stealth mode: hide icon from Windows system tray |
| `AUTO_EXIT_MINUTES` | `15` | Minutes of inactivity before automatically closing (0 to disable) |
| `ENABLE_NOTIFICATIONS` | `true` | Show native Windows notification when analysis completes (suppressed in stealth mode) |
| `NOTIFICATION_DURATION_MS` | `4000` | Toast notification duration in milliseconds |
| `CLIPBOARD_ON_HOTKEY` | `true` | Analyze clipboard snip on hotkey press if an image is present |
| `WATCH_COMMON_FOLDERS` | `false` | Automatically monitor `Pictures\Screenshots`, `OneDrive`, and `Desktop` |
| `GROK_API_KEY` | *(Optional)* | xAI Grok API key for automatic vision fallback if Gemini is blocked |
| `GROK_MODEL` | `grok-2-vision-1212` | Model identifier used for Grok Vision fallback |

---

## 🧪 Testing & Verification

Run the automated unit test suite:

```powershell
python -m unittest discover -s tests -v
```

Run manual end-to-end integration checks:

```powershell
# Verify Gemini API connectivity (generates and analyzes a test MCQ)
python tools\check_gemini.py

# Verify Windows Snipping Tool clipboard extraction & folder watching
python tools\check_snipping_tool.py

# List active Gemini models for your API key
python tools\list_models.py
```

---

## 📦 Building Standalone Executable (.exe)

You can compile EasyAnswer into a standalone Windows `.exe` application that runs without requiring Python to be installed.

Run the one-click build script:

```powershell
.\build.bat
```

Once the build finishes, your executable will be located in the `dist/` directory:
```
dist/
├── EasyAnswer.exe     # Standalone application
└── .env.example       # Example configuration file
```

> **Running the .exe:** Place your `.env` file containing your `GEMINI_API_KEY` in the same directory as `EasyAnswer.exe` (or set the system environment variable `GEMINI_API_KEY`), then double-click `EasyAnswer.exe` to run!

---

## 🗺️ Development Roadmap

- [x] **Phase 1: Foundation & Stability**
  - [x] Win32 global hotkeys & system tray integration.
  - [x] Multimodal Gemini Vision client with error categorization (404, 429, auth).
  - [x] Non-blocking `QThread` UI with Markdown rendering.
  - [x] SHA-256 duplicate image detection & temp file cleanup.
  - [x] Automated unit test suite (`tests/`).
- [ ] **Phase 2: Enhanced User Experience & Stealth**
  - [x] Global window toggle (`Ctrl+~`) & emergency killswitch (`Ctrl+Shift+Q`).
  - [x] Stealth mode (hidden tray icon) & 15-minute inactivity auto-exit timer.
  - [x] Automatic Grok-2 Vision streaming fallback when Gemini is blocked or fails.
  - [ ] Built-in screen region selection overlay (direct click-and-drag snip on hotkey).
  - [ ] Mini follow-up chat input inside the popup to ask clarifying questions.
  - [ ] Presets/Task modes (MCQ Solver, Code Explainer, Translator/Summarizer).
- [ ] **Phase 3: Visuals & History**
  - [ ] Local history drawer / SQLite storage for past screenshots and solutions.
  - [ ] Syntax-highlighted code blocks and LaTeX math equation rendering.
  - [ ] Dark / Light theme toggle.
- [ ] **Phase 4: Distribution & Packaging**
  - [x] One-click PyInstaller standalone `.exe` build script (`build.bat`).
  - [x] Windows custom icon packaging (`app.ico` generation).
  - [ ] Windows installer with automated desktop & startup shortcuts.


---

## 📄 License

MIT License. Feel free to use, modify, and distribute.
