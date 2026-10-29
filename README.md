# EasyAnswer

A minimalist, high-efficiency Windows productivity tool that instantly captures and analyzes screen content (code snippets, diagrams, mathematical formulas, and text) using multi-provider Vision AI models, presenting clear answers and explanations in a non-intrusive, semi-translucent floating widget.

Designed for developers, researchers, and students who need quick visual explanations and problem-solving without breaking focus or cluttering their workspace.

---

## ✨ Features

- ⚡ **Zero-Interruption Background Workflow (`AUTO_SHOW_POPUP=false`)**:
  - Pressing `Ctrl + Shift + S` sends your clipboard snip for background AI processing without popping up a distracting window.
  - Continue reading or typing uninterrupted.
  - Press **`Ctrl + ~`** on demand whenever you want to check the explanation, and press it again (or `Esc`) to dismiss.
- 🛡️ **Multi-Provider AI Resilience & Auto-Failover**:
  - Connects to high-speed vision AI providers to ensure continuous availability:
    - **OpenRouter (`nvidia/nemotron-3.5-super-vl:free`)** &mdash; Fast, accurate visual reasoning.
    - **OpenRouter Dynamic Meta-Router (`openrouter/free`)** &mdash; Automatic fallback if the primary model is busy or rate-limited.
    - **Cloudflare Workers AI (`@cf/meta/llama-3.2-11b-vision-instruct`)** &mdash; Ultra-fast edge AI inference powered by Cloudflare's global network.
    - **Mistral AI (`pixtral-12b-2409`)** &mdash; Advanced reasoning for complex technical diagrams and code.
    - **Google Gemini (`gemini-3.5-flash`)** &mdash; High-throughput multimodal reasoning.
    - Also supports Groq Cloud, Perplexity AI, GitHub Models, and xAI Grok.
- 🪟 **Minimalist Frosted Translucent UI**:
  - Compact **`260 × 85 px`** frameless design that floats cleanly above your active windows.
  - Semi-translucent frosted styling (**`POPUP_OPACITY=0.82`**) with high-contrast text (`#111827`) so your underlying documents and IDEs remain visible.
  - **Draggable anywhere**: simply click and drag to place the widget anywhere on your desktop.
  - Smooth rounded corners with no bulky borders or OS chrome.
- 📋 **Seamless Snipping Tool Integration**:
  - Integrates natively with the standard Windows Snipping Tool (`Win + Shift + S`).
  - Automatically captures and processes the clipboard image when you press the shortcut.
- 🛑 **Quick Exit Shortcut (`Ctrl + Shift + Q`)**:
  - Instantly closes the application and releases system resources.
- ⏳ **Smart Inactivity Timer**:
  - Automatically shuts down after 15 minutes of inactivity (`AUTO_EXIT_MINUTES=15`) to conserve system memory and battery.
- 🔒 **Privacy & Resource Friendly**:
  - No background telemetry.
  - Temporary snip files are wiped immediately after analysis.
  - SHA-256 deduplication avoids redundant API calls.
  - Available as a portable standalone executable (`dist/EasyAnswer.exe`) with zero runtime dependencies.

---

## ⌨️ Global Shortcuts

| Shortcut | Action | Description |
|---|---|---|
| **`Win + Shift + S`** | **Capture Area** | Windows Snipping Tool shortcut to select any region on your screen. |
| **`Ctrl + Shift + S`** | **Analyze Clipboard** | Silently reads clipboard image and analyzes it in the background. |
| **`Ctrl + ~`** | **Toggle Explanation** | Shows or hides the floating answer window on demand. |
| **`Ctrl + Shift + Q`** | **Quick Exit** | Closes and terminates the background application. |
| **`Esc`** | **Dismiss Window** | Immediately closes the floating popup when focused. |

> **Tip:** The `~` (tilde) key is the backtick key located directly above `Tab` and to the left of `1`.

---

## 🚀 Portable Executable (`.exe`) Quick Start

EasyAnswer comes pre-compiled as a standalone Windows executable. You do **not** need Python installed on your computer.

1. Navigate to the `dist\` folder:
   ```
   EasyAnswer/
   └── dist/
       ├── EasyAnswer.exe    <-- Standalone executable
       └── .env              <-- Configuration & API keys
   ```
2. Ensure your `.env` file exists next to `EasyAnswer.exe` with your preferred provider:
   ```env
   PRIMARY_PROVIDER=openrouter
   OPENROUTER_API_KEY=your_openrouter_key_here
   OPENROUTER_MODEL=nvidia/nemotron-3.5-super-vl:free

   AUTO_SHOW_POPUP=false
   SHOW_TRAY_ICON=false
   POPUP_OPACITY=0.82
   ```
3. Double-click `EasyAnswer.exe`. The app starts silently in the background.
4. Press `Win + Shift + S` &rarr; Snip &rarr; `Ctrl + Shift + S` &rarr; wait 2s &rarr; `Ctrl + ~` to view the explanation!

---

## 🛠️ Building from Source

### Prerequisites
- Windows 10 or 11
- Python 3.10+ (Python 3.11 / 3.12 recommended)

### Setup & Run
```powershell
# 1. Clone repository
git clone https://github.com/Krishan418/EasyAnswer.git
cd EasyAnswer

# 2. Set up virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r screenshot_ai\requirements.txt

# 4. Copy configuration template
copy screenshot_ai\.env.example .env

# 5. Run the application
python -m screenshot_ai.app
```

### Build Single-File `.exe`
To compile the standalone portable binary yourself:
```powershell
cmd /c build.bat
```
The resulting binary will be created at `dist\EasyAnswer.exe`.

---

## ⚙️ Configuration Reference (`.env`)

All parameters can be configured in `.env` (in the project root during development, or next to `EasyAnswer.exe` in production):

| Setting | Default | Description |
|---|---|---|
| `PRIMARY_PROVIDER` | `openrouter` | Primary AI engine (`openrouter`, `cloudflare`, `mistral`, `gemini`, `groq`, `perplexity`, `github`, `grok`) |
| `AUTO_SHOW_POPUP` | `false` | When `false`, processes silently in the background; press `Ctrl + ~` to view on demand |
| `HOTKEY` | `ctrl+shift+s` | Shortcut to trigger clipboard capture and AI analysis |
| `TOGGLE_HOTKEY` | `ctrl+~` | Shortcut to toggle answer window visibility |
| `QUIT_HOTKEY` | `ctrl+shift+q` | Quick exit shortcut |
| `POPUP_WIDTH` | `260` | Popup width in pixels (minimum 180) |
| `POPUP_HEIGHT` | `85` | Popup height in pixels (minimum 50) |
| `POPUP_OPACITY` | `0.82` | Window opacity (`0.20` to `1.00`). Lower values are more translucent |
| `SHOW_TRAY_ICON` | `false` | Show or hide icon in the Windows system tray |
| `ENABLE_NOTIFICATIONS` | `false` | Show native Windows notification toasts when analysis completes |
| `AUTO_EXIT_MINUTES` | `15` | Minutes of inactivity before auto-closing (0 to disable) |
| `CLIPBOARD_ON_HOTKEY` | `true` | Automatically grab images from the clipboard on hotkey |
| `OPENROUTER_API_KEY` | *(Configured)* | OpenRouter API Key for vision models |
| `OPENROUTER_MODEL` | `nvidia/nemotron-3.5-super-vl:free` | Primary OpenRouter vision model |
| `CLOUDFLARE_ACCOUNT_ID` | *(Optional)* | Cloudflare Account ID for Workers AI |
| `CLOUDFLARE_API_TOKEN` | *(Optional)* | Cloudflare Workers AI API Token |
| `CLOUDFLARE_MODEL` | `@cf/meta/llama-3.2-11b-vision-instruct` | Cloudflare vision model |
| `GEMINI_API_KEY` | *(Configured)* | Google AI Studio Gemini API key |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Google Gemini model identifier |
| `MISTRAL_API_KEY` | *(Optional)* | Mistral AI API key (`pixtral-12b-2409`) |
| `HUGGINGFACE_API_TOKEN`| *(Optional)* | Hugging Face user token for serverless vision |

---

## 🧪 Testing

Run the automated test suite (30 unit tests covering all services, configurations, hotkey parsing, and failover routing):

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

---

## ⚖️ License

This project is licensed under the MIT License. Developed for developer productivity, visual assistance, and educational research.
