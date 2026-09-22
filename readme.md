<div align="center">
  <img src="config/logo.png" width="180" alt="LUCY Logo" />
  <h1>LUCY</h1>
  <p><strong>Cross-Platform Real-Time Desktop AI Assistant</strong></p>
</div>

LUCY is a cross-platform, real-time desktop AI assistant that can hear, see, speak, and interact with your computer. Built with Python, PyQt6, and the Gemini Live API, LUCY provides low-latency bi-directional voice conversation, computer automation, visual perception, persistent memory, and a customizable futuristic desktop interface.

Website: [https://lucy-net.ai.studio/](https://lucy-net.ai.studio/)

---

## Features

### AI Assistant
* **Real-Time Conversational AI**: Ultra-low-latency voice conversation powered by the Gemini Live API.
* **Autonomous Task Agent**: High-level task planner capable of multi-step problem solving and developer workflows.
* **Dynamic Self-Awareness**: Runtime system inspection allowing LUCY to dynamically adapt to her host OS, active tools, and capabilities at session boot.
* **Proactive Intelligence**: Time-aware check-ins, morning briefings (time, weather, headlines recap), and daily topic monitoring.
* **Tool Discovery**: Auto-discovery of modular tools and drop-in extensions with single-file definitions.

### Voice / Speech
* **Native Audio Streaming**: Bi-directional audio pipeline using PyAudio and Gemini Live PCM audio without external TTS delay.
* **Offline Wake Word**: Local wake-word gating (`hey_jarvis` model via openWakeWord) allowing hands-free activation with zero audio transmission while asleep.
* **Voice Activity Detection & Barge-In**: Real-time speech interruption (ESC key / interrupt button / voice detection) that discards queued audio instantly.
* **Self-Echo Suppression**: Discards assistant echo from speakers to prevent the microphone from feeding back into itself.
* **Voice Options**: Live switching between Gemini Live prebuilt voices (Puck, Charon, Kore, Fenrir, Aoede).
* **Double-Clap Activation**: Acoustic trigger to wake or grab attention.
* **Push-to-Talk**: Optional push-to-talk mode (`Ctrl+Space`).

### Desktop Automation
* **App Launcher**: Searches and launches installed applications across Windows, macOS, and Linux.
* **System Controls**: Control system audio volume, screen brightness, Wi-Fi status, and system power states (sleep, restart, shutdown).
* **Window & Desktop Control**: Desktop manipulation, active window tracking, keystroke automation, and shortcut execution.
* **Safety Confirmation Gate**: Reversible/irreversible action safeguards requiring explicit user confirmation before executing critical operations.

### Browser Automation
* **Headless & Headful Web Control**: Fast, resilient web automation powered by Playwright across Chromium and Firefox.
* **Web Navigation & Search**: Query execution on DuckDuckGo, Google, and direct URL navigation.
* **Page Interaction**: Text extraction, element clicking, form entry, and page reading.

### Memory
* **Long-Term Memory**: Persistent store for user preferences, personal context, habits, and ongoing projects across sessions.
* **Memory Dashboard**: Floating UI panel to inspect, search, and delete stored memories in one click.
* **Context Summarization**: Session summaries that condense long conversation histories without losing critical facts.

### Screen / Perception
* **Desktop Screen Capture**: Captures desktop displays for instant visual analysis and troubleshooting.
* **Webcam Vision**: Streams webcam frames into Gemini for real-time visual question answering and physical scene understanding.
* **Source Labeling**: Distinguishes screen captures (computer state) from webcam frames (user/room state).

### Integrations
* **Gmail Automation**: Reads incoming emails, summarizes unread threads, drafts replies, and sends messages.
* **WhatsApp Automation**: Web-based WhatsApp messaging automation with linked session persistence.
* **Media & Information**: YouTube video transcript fetching and summarization, flight searches, and real-time weather reports.

### Security
* **Safe Boundaries**: Explicit user-confirmation safeguards for destructive actions (system shutdown, Wi-Fi disconnection).
* **Local Processing for Sensitive Data**: Wake-word and audio levels processed locally on-device.
* **Credential Isolation**: Encrypted or local JSON configuration storage ignored by version control.

### Quick Assistant
* **Clipboard Monitor Panel**: Floating HUD shortcut panel that triggers contextual actions when text is copied.
* **Global Hotkeys**: Quick-stop interruption, push-to-talk, and full-screen HUD toggle.

### Settings & Customization
* **Personality Modes**: Select between three distinct real-time personality modes (`GF`, `JARVIS`, and `ASSISTANT`):
  * **GF**: Friendly, warm, playful, and slightly teasing girlfriend-style companion AI that can joke and banter while strictly executing all requested tasks without refusal.
  * **JARVIS**: Classic LUCY operator persona — level-headed, authoritative, dry humor, and grounded in concrete facts.
  * **ASSISTANT**: Professional, concise, direct, and task-oriented with zero fluff and no unnecessary confirmation questions.
* **Name & Addressing**: Configurable assistant name and user title.
* **Live HUD Theming**: Dynamic theme color picker supporting full UI recoloring and custom hex values.
* **Holographic Wireframe Face & HUD Modes**: Switch between the futuristic Wireframe Face and the Arc Reactor Core centerpiece:
  * **Real-Time Lip-Sync**: Anatomically synchronized mouth movement reacting to actual TTS playback audio and visemes; lips part naturally, revealing subtle holographic oral depth, and smoothly return to neutral closed lips when silent or interrupted.
  * **Natural Eye Dynamics**: Living green eyes with organic randomized blinking, subtle micro-saccades, and state-driven gaze shifts (focused gaze when listening, thoughtful look-away when thinking).
* **Audio Device Selector**: In-app selection of preferred microphone and output speaker hardware.

### System & Desktop Integration
* **System Metrics Monitor**: Real-time CPU, RAM, and GPU load visualizers.
* **OS Shortcuts**: One-click generation of native Desktop and Start Menu shortcuts.
* **Auto-Start on Boot**: Cross-platform autostart toggle via Windows Registry, macOS LaunchAgents, or Linux desktop autostart.

### Remote Features
* **Encrypted Web Companion**: Built-in local HTTPS/WSS server providing a mobile and remote browser interface.
* **QR Code Pairing**: Instant pairing between mobile phones and the desktop instance without manual IP configuration.
* **AES-256 GCM Transport**: End-to-end payload encryption for remote commands.

---

## Setup

### Option A: Windows 1-Click Launch (Recommended for Windows 10 / 11)
*No manual Python installation required.*

1. **Clone or download the repository**:
   ```cmd
   git clone https://github.com/sorecake12-dotcom/lucy-ai.git
   cd lucy-ai
   ```

2. **Run setup**:
   Double-click `setup.bat` or run:
   ```cmd
   setup.bat
   ```
   * On first run, `setup.bat` automatically provisions a dedicated portable Python 3.11 runtime, installs required dependencies, compiles the native `LUCY.exe` launcher, and starts the assistant.
   * On subsequent launches, launch LUCY instantly via `LUCY.exe` or `setup.bat`.

---

### Option B: Cross-Platform & Developer Setup (Windows / macOS / Linux)

#### Prerequisites
* **Python**: 3.11 to 3.13 (Python 3.11+ required).
* **Gemini API Key**: A valid Google Gemini API key.

#### Installation
1. **Clone the repository**:
   ```bash
   git clone https://github.com/sorecake12-dotcom/lucy-ai.git
   cd lucy-ai
   ```

2. **Run automated environment setup**:
   ```bash
   python setup.py
   ```
   This script installs Python dependencies and downloads Playwright browsers (Chromium and Firefox).

3. **Launch LUCY**:
   ```bash
   python main.py
   ```
   On first launch, enter your Gemini API key in the initialization overlay.

---

## Standalone Distribution & Packaging

To create a self-contained, standalone Windows distribution package for deployment:

```bash
python build_dist.py
```

This generates:
* `dist/LUCY/`: Standalone application directory with embedded Python runtime.
* `dist/LUCY.zip`: Compressed release archive for end users.
* `dist/SHA256SUMS.txt`: Cryptographic SHA-256 integrity checksums.

---

## Architecture

* **`main.py`**: Application entrypoint and `JarvisLive` orchestration loop managing WebSocket connections, audio pipelines, tool dispatch, and event handling.
* **`ui.py`**: PyQt6 GUI implementation featuring the holographic avatar canvas, audio visualizers, settings overlays, logs, and system trays.
* **`setup.bat`**: 1-click Windows zero-dependency environment bootstrapper and launcher compiler.
* **`build_dist.py`**: Standalone distribution packaging pipeline creating self-contained releases with checksum verification.
* **`launcher/`**: Native Windows launcher source (`LUCY_launcher.cs`) compiled on-demand into `LUCY.exe`.
* **`core/`**: Fundamental engine utilities:
  * `personality.py`: Multi-personality system engine and dynamic prompt injectors for GF, JARVIS, and ASSISTANT modes.
  * `avatar.py`: Software-rendered 3D holographic head, phonetic viseme mapping, and lip-sync.
  * `llm_client.py`: Gemini Live API client with continuous streaming and context compression.
  * `wake_word.py`: Local openWakeWord detection thread.
  * `audio_devices.py`: Hardware device discovery and audio configuration.
  * `plugin_loader.py` & `action_loader.py`: Dynamic tool registration.
* **`actions/`**: Built-in automation modules:
  * `desktop.py` & `computer_control.py`: Windows/OS keyboard, mouse, and process management.
  * `code_helper.py` & `dev_agent.py`: Autonomous code execution, refactoring, and developer assistance.
  * `browser_control.py`: Playwright web automation engine.
  * `screen_processor.py`: Screen and webcam capture pipelines.
  * `email_automation.py` & `whatsapp.py`: Communications automations.
  * `computer_settings.py`: Volume, brightness, Wi-Fi, and power controls.
  * `reminder.py`: Background scheduler and native notifications.
* **`memory/`**: Memory subsystem:
  * `memory_manager.py`: Long-term fact extraction, SQLite vector/text search, and persistence.
  * `config_manager.py`: Settings, theme, and API key management.
* **`dashboard/`**: Mobile remote control backend:
  * `server.py`: FastAPI / Uvicorn WebSocket server with TLS and AES-256 encryption.
  * `static/`: Mobile web application client (`app.html`, `login.html`, `crypto.js`).
* **`plugins/`**: Drop-in extension folder for custom community tools.

---

## Configuration

LUCY stores runtime configuration inside `config/api_keys.json` (auto-created on first run and excluded from git):

```json
{
    "gemini_api_key": "YOUR_GEMINI_API_KEY",
    "assistant_name": "LUCY",
    "user_name": "boss",
    "voice_name": "Puck",
    "ui_color": "#00ff27",
    "hud_style": "face",
    "wake_word_enabled": true
}
```

* Sensitive tokens, OAuth secrets, and personal memory databases are strictly kept in the local `config/` and `memory/` folders and ignored via `.gitignore`.

---

## Current Status

LUCY is actively under development. Features, automation capabilities, and integrations are continuously refined.

---

## Branding

The application is officially named **LUCY**.
