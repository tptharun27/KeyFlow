# KeyFlow

KeyFlow is a desktop + mobile web application that lets you control your PC's keyboard remotely from your smartphone browser over Wi-Fi. It is built for auto-typing code into IDEs with automatic indentation, pasting long text snippets, or entering text across devices.

## 🌟 Key Features
- **Code-Aware Auto-Indent Engine (v2.0)**: Engineered specifically for modern IDEs (VS Code, PyCharm, Sublime, Monaco). Dismisses IntelliSense popups, cleans auto-closed trailing brackets, clears auto-indent to Column 0, and paces leading indentation spaces so indentation is preserved even at high typing speeds.
- **3 Dedicated Typing Modes**:
  1. **Code**: Smart auto-indent reset (`Enter` + Column 0 reset + paced indentation).
  2. **Shift+Enter**: Inserts line breaks without sending messages in chat apps (WhatsApp, Discord, Slack, Teams).
  3. **Enter**: Standard plain `Enter` keystroke at every line break.
- **Full Desktop Dashboard**:
  - Resizable two-column desktop UI with top menu bar (**File**, **View**, **Settings**, **Build Info**).
  - Live telemetry monitor (progress bar, active mode, CPS/WPM readout, PC Pause/Stop controls, and activity log).
  - Instant QR Code pairing with embedded PIN and one-click URL/PIN copy.
  - Minimizes cleanly to the Windows System Tray for background operation.
- **Global Hotkeys**:
  - `F8` — Emergency Stop
  - `F9` — Pause / Resume Typing

## 🔧 Installation & Usage
1. Run `Output\KeyFlowSetup.exe` to install **KeyFlow** on your PC (or run `dist\KeyFlow.exe` directly).
2. Enter your Product Activation Key on first launch.
3. Scan the QR code shown on the PC dashboard using your phone camera (on the same Wi-Fi network).
4. Paste your code or text on your phone, choose **Code**, **Shift+Enter**, or **Enter**, and tap **Start typing**.

## 📄 License
Licensed under the KeyFlow EULA (`eula.txt`).
