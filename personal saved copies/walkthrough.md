# Lithe — Packaging Walkthrough

The Lithe backend and frontend have been successfully packaged into a single Windows installer.

## 📦 What Was Built

1. **Python Backend Compiler**
   - We used PyInstaller to bundle your FastAPI backend, SQLite engine, and all `pip` dependencies into a standalone Windows executable (`lithe-server.exe`).
   - This means Lithe no longer requires a system Python installation to run!

2. **Configuration Persistence**
   - To make the executable portable and secure, configuration files (like the `.env` with your `GEMINI_API_KEY` and the `.lithe/` SQLite index) are now stored in `%APPDATA%\Lithe`.
   - Your `.env` was automatically copied over to the AppData folder for first-time launch convenience.

3. **Electron Installer**
   - We configured `electron-builder` to package the React frontend and embed the Python backend executable.
   - The output is an NSIS-based Windows installer that registers the app, adds a Start Menu shortcut, and allows launching with just a single click.

---

## 🚀 How to Run It

1. **Install Lithe:**
   - Open File Explorer and navigate to: `D:\Lithe\src\frontend\release\`
   - Double-click **`Lithe Setup 1.0.0.exe`** to install the application.

2. **Launch the App:**
   - Press the Windows Key (⊞ Win), type **"Lithe"**, and hit Enter.
   - The app will open seamlessly without needing a terminal or `npm run dev`.

> [!TIP]
> If you ever need to update your API key in the packaged version, you can find the configuration file at `C:\Users\SHAWN\AppData\Roaming\Lithe\.env`.

> [!NOTE]
> The next step for the roadmap would be to verify the installer behaves correctly across different environments, and eventually set up Auto-Updating features via GitHub Releases if you plan to share this app with others.
