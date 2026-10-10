# KeyFlow Changelog

## [1.1.0] - 2026-10-10

### 🚀 Major Features & QoL Updates
- **Complete Rebranding:** Renamed the entire project from "Autotyper" to **KeyFlow**.
- **Project Packaging:** Added standard Python project structure (`pyproject.toml`, `README.md`).
- **Persistent PIN:** Implemented persistent PIN logic saving to `~/.keyflow_pin`. Phone browser sessions no longer expire on PC script restart.
- **Auto-Port Fallback:** KeyFlow now automatically detects if default port `8765` is busy and sequentially searches for a free port, preventing startup crashes.
- **Web UI Focus Improvement:** The mobile web UI now auto-focuses the text area immediately after the "Clear" or "Undo" buttons are pressed, keeping the virtual keyboard open for faster pasting.
- **Modern Desktop UI:** Replaced the terminal CMD black screen with a beautiful, dark-themed **CustomTkinter** desktop window displaying the QR code, link, and PIN.
- **Standalone Installer (`KeyFlowSetup.exe`):** Bundled the Python script, Flask server, dependencies, and UI into a single `.exe` using PyInstaller. Created an official Windows Setup Wizard using Inno Setup 6, complete with a professional End User License Agreement (EULA).
- **System Tray Integration:** App window now safely minimizes to the Windows System Tray rather than completely exiting, keeping the typing server alive in the background. (Right-click to Show/Quit).
- **Premium Activation Security:** Added a built-in Activation Key system requiring a randomly-generated secure key before the server can start. Keys are securely stored and verified using `SHA-256` hashing.
- **Code Obfuscation:** The source code and embedded hashed activation keys are completely obfuscated using `PyArmor` for maximum anti-reverse-engineering security.

### 🐛 Bug Fixes
- **Code Mode Auto-Indent Bug:** Fixed a race condition in `code` typing mode where empty lines combined with IDE auto-indentation would result in deleted characters or missing lines. The script now aggressively drops back to "Column 0" explicitly before typing any new line.
