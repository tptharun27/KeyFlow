# KeyFlow

KeyFlow is an innovative application that allows you to control your PC's typing remotely from your smartphone browser via Wi-Fi. It is perfect for securely pasting long text snippets, auto-typing code, or securely entering passwords without manual retyping.

## 🌟 Features
- **Remote Typing**: Type or paste on your phone, and your PC will type it exactly.
- **Code Mode Engine**: Perfectly overwrites your IDE's auto-indentation, preventing line-break mangling.
- **App Activation**: Secure SHA-256 hashed activation token system.
- **Background Mode**: Minimizes directly to the System Tray for uninterrupted background functioning.
- **Smart UI**: Dark mode web UI with typing speed slider, pause/resume, and saved snippets.

## 🔧 Installation
1. Run `KeyFlowSetup.exe` to install the desktop application.
2. Provide a valid Product Activation Key (refer to `activation_keys.txt`).
3. Click **Start Server** and scan the QR code using your phone's camera.

## 💻 How It Works
- The application launches a lightweight background HTTP server on a dynamically assigned port (default 8765).
- It creates a local access tunnel requiring a 6-digit PIN.
- Upon receiving text from the web UI, it simulates keystrokes natively using `pynput`, seamlessly navigating different editor environments (like VS Code, Notepad, Slack, etc.) using specific Line Break modes.

## 🛠️ Modes
1. **Code**: Presses Enter, waits for the IDE to auto-indent, then selects and clears the indent so your original pasted whitespace remains identical.
2. **Shift+Enter**: For chat apps (like Slack/Discord) to prevent early sending.
3. **Enter**: Standard line break typing.
4. **One Line**: Strips out all newlines and types continuously as a single line.

## 🛡️ Security
- **End-to-end Local**: Works entirely on your Local Area Network (LAN). No data is sent over the open internet.
- **Obfuscation**: The source codebase is heavily obfuscated using PyArmor to protect core logic and the hashed activation keys.

## 📄 License
This project is licensed under the custom KeyFlow EULA. Refer to `eula.txt` for details.
