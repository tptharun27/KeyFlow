# KeyFlow Changelog

## [1.2.0] - 2026-10-11

### 🚀 Major Features & Complete Revamp
- **Code-Aware Auto-Indent Engine v2.0:**
  - Dismisses IDE autocomplete/IntelliSense popups and cleans up auto-closed trailing brackets/parens (`Shift+End` -> `Space` -> `Backspace`) before pressing `Enter`, preventing `Enter` from being consumed by autocomplete suggestions.
  - Resets `next_t` timing budget after every newline so the engine never sprints or drops characters at the start of a new line.
  - Paces leading indentation spaces (`>=12ms` per space) independently of high typing speeds so IDEs like VS Code never drop indentation even at Turbo speeds.
  - Streamlined to strictly **3 modes**: `Code`, `Shift+Enter`, and `Enter`.
- **Full-Featured Resizable Desktop App:**
  - Replaced the small static window with a resizable (`960x650`, min `800x560`) two-column desktop dashboard.
  - Added a top Menu Bar (`File`, `View`, `Settings`, `Build Info`) with dropdown menus, Always-on-Top toggle, PIN regeneration, URL/PIN clipboard copy, and a detailed **Build & System Information** dialog.
  - Added a live **Typing Monitor** card showing real-time progress, active mode, speed (CPS/WPM), PC-side Pause/Stop controls, and a timestamped **Activity & Telemetry Log**.
  - Bulletproof System Tray (`pystray`) integration with fallback icon generation so minimizing to tray works in all environments.
- **Mobile Web UI Revamp:**
  - Fixed segmented mode control CSS for 3 modes (`repeat(3, 1fr)`), fixed `localStorage` mode validation crash, added an indent/tab cleaner tool (`Clean`), and added live host state display.

---

## [1.1.0] - 2026-10-10

### 🚀 Major Features & QoL Updates
- **Complete Rebranding:** Renamed the entire project from "Autotyper" to **KeyFlow**.
- **Project Packaging:** Added standard Python project structure (`pyproject.toml`, `README.md`).
- **Persistent PIN:** Implemented persistent PIN logic saving to `~/.keyflow_pin`. Phone browser sessions no longer expire on PC script restart.
- **Auto-Port Fallback:** KeyFlow now automatically detects if default port `8765` is busy and sequentially searches for a free port, preventing startup crashes.
- **Web UI Focus Improvement:** The mobile web UI now auto-focuses the text area immediately after the "Clear" or "Undo" buttons are pressed, keeping the virtual keyboard open for faster pasting.
- **Modern Desktop UI:** Replaced the terminal CMD black screen with a dark-themed **CustomTkinter** desktop window displaying the QR code, link, and PIN.
- **Standalone Installer (`KeyFlowSetup.exe`):** Bundled the Python script, Flask server, dependencies, and UI into a single `.exe` using PyInstaller and Inno Setup 6.
- **System Tray Integration:** App window safely minimizes to the Windows System Tray rather than exiting.
- **Activation Security:** Added a built-in Activation Key system verified using `SHA-256` hashing.
