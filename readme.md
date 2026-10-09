<div align="center">
  <img src="config/logo.png" width="180" alt="LUCY Logo" />
  <h1>LUCY</h1>
  <p><strong>Autonomous Real-Time Voice & Desktop Operating System Assistant</strong></p>
  <p>
    <a href="https://github.com/sorecake12-dotcom/lucy-ai/actions"><img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build Status"></a>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
    <a href="https://github.com/sorecake12-dotcom/lucy-ai/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
    <a href="https://github.com/sorecake12-dotcom/lucy-ai"><img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg" alt="Platform"></a>
  </p>
</div>

LUCY is a cross-platform, low-latency desktop AI assistant and computer automation platform. Engineered with Python, PyQt6, and the Gemini Live bi-directional WebSocket API, LUCY operates with native audio streaming, computer vision, self-healing operating system automation, a procedural 3D particle visualizer, and a production-grade API protection architecture.

---

## Architecture Overview

```
lucy-ai/
├── actions/                  # Modular tool & automation plugins
│   ├── browser_control.py    # Playwright browser interaction engine
│   ├── code_helper.py        # Code generation, syntax analysis & linting
│   ├── computer_control.py   # Keyboard, mouse, and self-healing input dispatch
│   ├── computer_settings.py  # System volume, brightness, power & state control
│   ├── date_time_location.py # System timezone, local time & geolocation resolution
│   ├── desktop.py            # Window snapping, workplace tiling & focus control
│   ├── dev_agent.py          # Autonomous multi-step software developer loop
│   ├── file_controller.py    # File search, directory indexing & disk management
│   ├── open_app.py           # Cross-platform application discovery & launcher
│   ├── particle_visualizer.py# Natural-language 3D particle shape director
│   ├── reminder.py           # Native OS task scheduling & notifications
│   ├── weather_report.py     # Open-Meteo real-time meteorological reports
│   ├── web_search.py         # DuckDuckGo rate-controlled search scraper
│   └── youtube_video.py      # Audio extraction & transcript analysis
├── core/                     # Core system engines & runtime drivers
│   ├── action_loader.py      # Dynamic tool scanner & JSON schema generator
│   ├── animated_shapes.py    # Procedural 3D particle generator & pure-Python OBJ engine
│   ├── api_guard.py          # Production security, rate limiter, quotas & kill switch
│   ├── audio_devices.py      # PortAudio hardware discovery & ring buffers
│   ├── avatar.py             # 3D software-rendered wireframe face & viseme mouth sync
│   ├── gemini.py             # Low-latency Gemini Live WebSocket streaming client
│   ├── geo_time.py           # OS local clock synchronization & IP geolocation
│   ├── llm_client.py         # REST fallback client with exponential backoff & jitter
│   ├── particle_blob.py      # Living organic particle sphere simulation
│   ├── personality.py        # Multi-personality prompt matrix (GF, JARVIS, ASSISTANT)
│   ├── platform_adapter.py   # Cross-platform OS abstraction (Windows, macOS, Linux)
│   ├── self_healing_control.py# Automated failure diagnosis & UI focus recovery
│   └── wake_word.py          # Offline openWakeWord acoustic gating thread
├── memory/                   # State, memory & configuration
│   ├── config_manager.py     # Schema validator & preferences management
│   └── memory_manager.py     # Long-term semantic store with SQLite persistence
├── tests/                    # Subsystem test suites
│   ├── test_api_guard.py     # Rate limiting, circuit breakers & secret scrubbing
│   ├── test_geo_time.py      # Local time sync & geolocation resolution
│   ├── test_platform.py      # Cross-platform capabilities & OS detection
│   ├── test_self_healing.py  # Failure diagnosis & window recovery
│   ├── test_shapes.py        # 3D procedural geometries & OBJ mesh validation
│   └── test_smoke.py         # Action loader & engine integration tests
├── dashboard/                # Encrypted remote companion server & WebSockets
├── launcher/                 # Native C# bootstrap source (LUCY_launcher.cs)
├── main.py                   # Master event loop & session orchestrator
├── ui.py                     # PyQt6 dark HUD, visualizers & settings canvas
├── setup.bat                 # Windows automated deployment bootstrapper
├── setup.py                  # Cross-platform dependency installer
└── build_dist.py             # Production distribution packaging pipeline
```

---

## Core Capabilities

### 1. Production API Protection & Security Layer (`core/api_guard.py`)
* **Sliding-Window Rate Limiting**: Dedicated token and request bucket limiters for Gemini REST, Live WebSockets, web scrapers, browser actions, and tool calls.
* **Concurrency Control**: Semaphore-bounded worker pools preventing resource starvation under rapid query bursts.
* **Exponential Backoff & Jitter**: Full randomized jitter backoff with dynamic parsing of HTTP `429 Retry-After` headers. Never retries indefinitely.
* **Agent Loop Circuit Breaker**: Real-time fingerprinting of tool actions to detect runaway loops, identical repeat thrashing, and alternating cycles.
* **Persistent Quota Tracking**: Daily and monthly request and token quotas persisted to disk (`memory/usage_stats.json`).
* **Emergency Kill Switch**: Instant global kill switch toggleable via configuration or API to halt all outbound network requests.
* **Credential Sanitization**: In-memory regex scrubbing of logs, errors, and tracebacks to ensure API keys, Bearer tokens, and secrets are never leaked.

### 2. Procedural 3D Particle Visualizer (`core/animated_shapes.py`)
* **25 Dynamic Geometric Objects**: Mathematical procedural point-cloud generation for cars, sports cars, hearts, trees, robots, televisions, laptops, fans, chairs, tables, houses, rockets, planets (Earth/Saturn), flowers, birds, animals, and human head silhouettes.
* **Pure-Python 3D OBJ Parser**: Custom mesh loader that samples 3D vertices and polygonal surfaces directly from `core/face_model.obj` without external C-extensions.
* **Dynamic Palette & Camera Mapping**: Pre-calibrated 3D bounding boxes, tilt/pitch angles, and multi-region color palettes (e.g. blue ocean with green land, red sports car with white rims).
* **Fluid Morphing Transitions**: Seamless interpolation between the organic living idle blob and requested physical 3D objects.
* **Adaptive Density**: Particle counts scale dynamically based on host device performance.

### 3. Self-Healing Computer Automation (`core/self_healing_control.py`)
* **7-Point Automated Failure Diagnosis**: Automatically categorizes automation failures into:
  * `STALE_HANDLE`: Stale or closed window handle.
  * `LOST_FOCUS`: Target window minimized, occluded, or backgrounded.
  * `DISCONNECTED_AUTOMATION`: IPC or display worker failure.
  * `FAILED_INPUT_BACKEND`: Display lock, PyAutoGUI failsafe, or clipboard contention.
  * `TEMP_PROCESS_FAILURE`: Process hung or temporarily unresponsive.
  * `PERMISSION_PROBLEM`: Elevated UAC or accessibility permission denial.
  * `APP_SPECIFIC_FAILURE`: Application crashed or missing.
* **Automated Recovery Loop**: Window state recovery using native Win32 `ShowWindow(SW_RESTORE)` + `SetForegroundWindow`, macOS AppleScript frontmost process switching, and Linux `wmctrl` / `xdotool`.
* **Bounded Retries**: Maximum 3 self-healing attempts with exponential retry backoff.
* **Graceful Termination**: Non-destructive `WM_CLOSE` window messaging before escalating to process termination.

### 4. Real-Time Geolocation & Time Engine (`core/geo_time.py`)
* **Host Operating System Clock Sync**: Real-time extraction of host OS time, date, local timezone, and UTC offsets (full support for `Asia/Kolkata` / `UTC+05:30`).
* **Multi-Tier Geolocation**: Configured city override → cached network IP geolocation (1-hour memory cache) → safe fallback.
* **Honest Attribution**: Strictly distinguishes network-based approximate coordinates from GPS and prevents hallucinated precision.

### 5. Multi-Personality Core (`core/personality.py`)
* **GF Mode**: Warm, playful, witty, and engaging companion persona designed for conversational companionship without refusing system actions.
* **JARVIS Mode**: Professional, authoritative, and analytical operator persona inspired by classic desktop AI systems.
* **ASSISTANT Mode**: Minimalist, hyper-concise, and instruction-focused execution mode with zero conversational fluff.

---

## Getting Started

### Windows 1-Click Launch (Recommended)
No manual Python installation required.

1. **Clone the repository**:
   ```cmd
   git clone https://github.com/sorecake12-dotcom/lucy-ai.git
   cd lucy-ai
   ```

2. **Run setup**:
   Double-click `setup.bat`.
   * Automatically configures a portable Python 3.11 runtime.
   * Installs all dependencies.
   * Compiles the native C# launcher `LUCY.exe`.
   * Creates desktop and Start Menu shortcuts.

---

### Cross-Platform Setup (Windows / macOS / Linux)

#### Prerequisites
* Python 3.11, 3.12, or 3.13.
* Google Gemini API Key.

#### Installation
1. **Clone the repository**:
   ```bash
   git clone https://github.com/sorecake12-dotcom/lucy-ai.git
   cd lucy-ai
   ```

2. **Install dependencies**:
   ```bash
   python setup.py
   ```

3. **Launch the assistant**:
   ```bash
   python main.py
   ```
   On first launch, enter your Gemini API key in the configuration dialog.

---

## Running the Test Suite

LUCY includes a comprehensive automated test suite covering all core systems:

```bash
# Run all unit and integration tests
python -m unittest discover tests

# Or run specific subsystem test suites
python -m unittest tests/test_shapes.py
python -m unittest tests/test_api_guard.py
python -m unittest tests/test_self_healing.py
python -m unittest tests/test_geo_time.py
python -m unittest tests/test_platform.py
```

---

## Standalone Distribution Build

To package a standalone, self-contained binary distribution:

```bash
python build_dist.py
```

Outputs:
* `dist/LUCY/`: Standalone application directory with bundled runtime.
* `dist/LUCY.zip`: Production release archive.
* `dist/SHA256SUMS.txt`: Cryptographic SHA-256 verification hashes.

---

## Configuration

Settings are stored in `config/api_keys.json` (auto-generated on initial boot and protected from git):

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "assistant_name": "LUCY",
  "user_name": "Boss",
  "voice_name": "Charon",
  "personality_mode": "GF",
  "ui_color": "#8b5cf6",
  "hud_style": "face",
  "wake_word_enabled": false,
  "location_settings": {
    "mode": "auto",
    "fallback_city": "New Delhi, India",
    "timezone": "Asia/Kolkata"
  },
  "emergency_kill_switch": false
}
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
