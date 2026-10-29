# EasyAnswer (Stealth Screenshot AI Assistant)

A lightweight, ultra-discreet Windows desktop application designed to instantly capture and solve screenshots, code, diagrams, and MCQs using a **multi-provider vision AI failover chain** (OpenRouter, Cloudflare Workers AI, Google Gemini, and more) wrapped in a **frosted translucent, frameless stealth popup**.

Built specifically for high-stakes lab, exam, and restricted academic network environments where popular AI services (ChatGPT, Gemini, Grok) are firewalled.

---

## ✨ Key Capabilities

- 👻 **Ultimate Ghost Mode (`AUTO_SHOW_POPUP=false`)**:
  - Pressing `Ctrl + Shift + S` analyzes the clipboard snip **100% silently in the background**.
  - **Zero unprompted popups** appear on screen during analysis—nobody walking past will notice any window or loading animation.
  - Press **`Ctrl + ~`** (or your custom toggle key) whenever it is safe to peek at the answer, and press it again or `Esc` to instantly vanish.
- 🛡️ **Multi-Provider AI Resilience & Auto-Failover**:
  - **Primary: OpenRouter (`nvidia/nemotron-3.5-super-vl:free`)** &mdash; 100% free vision, ~2s response time, unblocked on campus/lab firewalls.
  - **Failover 1: OpenRouter Dynamic Pool (`openrouter/free`)** &mdash; Automatically routes to active free models if the primary model is busy or rate-limited.
  - **Failover 2: Cloudflare Workers AI (`@cf/meta/llama-3.2-11b-vision-instruct`)** &mdash; 10,000 requests/day completely free; Cloudflare global CDN domains are never blocked on university networks.
  - **Failover 3: Mistral AI (`pixtral-12b-2409`)** &mdash; High-accuracy academic vision model.
  - **Failover 4: Hugging Face Serverless Vision** &mdash; Free open-source inference token.
  - **Failover 5: Google Gemini (`gemini-3.5-flash`)** &mdash; Built-in backup (ideal via mobile hotspot / USB tethering).
  - Also supports Groq Cloud, Perplexity AI, GitHub Models, and xAI Grok.
- 🪟 **Frosted Translucent Stealth UI**:
  - Ultra-compact **`260 × 85 px`** frameless design.
  - Soft, see-through frosted white translucency (**`POPUP_OPACITY=0.82`**) with crisp dark charcoal text (`#111827`) that is readable yet inconspicuous from an angle.
  - **Click-and-drag anywhere** on the popup to reposition it effortlessly.
  - Minimalistic: no bulky titlebars or unnecessary buttons.
- ⚡ **Windows Snipping Tool Integration**:
  - `Win + Shift + S` &rarr; snip question &rarr; `Ctrl + Shift + S` &rarr; background analysis.
- 🚨 **Emergency Panic Quit (`Ctrl + Shift + Q`)**:
  - Instantly kills the application and background processes without leaving traces.
- ⏳ **Auto-Exit Safety Timer**:
  - Automatically terminates after 15 minutes of inactivity (`AUTO_EXIT_MINUTES=15`).
- 🔒 **Privacy & Security**:
  - Tray icon hidden by default (`SHOW_TRAY_ICON=false`).
  - Temporary snip files are wiped immediately after analysis.
  - SHA-256 deduplication avoids duplicate API calls.
  - No Python runtime required on target machines when using `dist/EasyAnswer.exe`.

---

## ⌨️ Global Shortcuts

| Shortcut | Action | Description |
|---|---|---|
| **`Win + Shift + S`** | **Snip Question** | Standard Windows Snipping Tool shortcut to select any area of your screen. |
| **`Ctrl + Shift + S`** | **Silent AI Capture** | Silently reads the clipboard snip and initiates background AI analysis. *(No popup shown).* |
| **`Ctrl + ~`** | **Toggle Reveal / Hide** | Shows the translucent popup with the ready answer. Press again or `Esc` to instantly hide. |
| **`Ctrl + Shift + Q`** | **Emergency Panic Quit** | Instantly closes and exits the entire application. |
| **`Esc`** | **Quick Hide** | Hides the popup immediately when it is visible. |

> **Note on `Ctrl + ~`:** On standard keyboards, the `~` (tilde) key is the backtick key located directly above `Tab` and to the left of `1`.

---

## 🚀 Portable Executable (`.exe`) Quick Start

EasyAnswer comes pre-compiled as a standalone Windows executable. You do **not** need Python installed.

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
4. Press `Win + Shift + S` &rarr; Snip &rarr; `Ctrl + Shift + S` &rarr; wait 2s &rarr; `Ctrl + ~` to view the answer!

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
| `AUTO_SHOW_POPUP` | `false` | When `false` (Ghost Mode), analysis runs silently in the background; press `Ctrl + ~` to view |
| `HOTKEY` | `ctrl+shift+s` | Shortcut to trigger clipboard capture and AI analysis |
| `TOGGLE_HOTKEY` | `ctrl+~` | Shortcut to toggle answer window visibility |
| `QUIT_HOTKEY` | `ctrl+shift+q` | Emergency instant exit shortcut |
| `POPUP_WIDTH` | `260` | Popup width in pixels (minimum 180) |
| `POPUP_HEIGHT` | `85` | Popup height in pixels (minimum 50) |
| `POPUP_OPACITY` | `0.82` | Window opacity (`0.20` to `1.00`). Lower values are more transparent |
| `SHOW_TRAY_ICON` | `false` | Hide system tray icon for maximum stealth |
| `ENABLE_NOTIFICATIONS` | `false` | Suppress all Windows notification toast alerts |
| `AUTO_EXIT_MINUTES` | `15` | Minutes of inactivity before auto-closing (0 to disable) |
| `CLIPBOARD_ON_HOTKEY` | `true` | Automatically grab images from the clipboard on hotkey |
| `OPENROUTER_API_KEY` | *(Configured)* | OpenRouter API Key for free vision models |
| `OPENROUTER_MODEL` | `nvidia/nemotron-3.5-super-vl:free` | Primary OpenRouter vision model |
| `CLOUDFLARE_ACCOUNT_ID` | *(Optional)* | Cloudflare Account ID for Workers AI |
| `CLOUDFLARE_API_TOKEN` | *(Optional)* | Cloudflare Workers AI API Token (10k free requests/day) |
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

## ⚖️ License & Ethical Use

This project is licensed under the MIT License. Developed strictly for educational assistance, accessibility, and productivity. Users are responsible for complying with the policies and codes of conduct of their respective institutions or examination bodies.
