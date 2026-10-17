# TG_Coper v4.8.1 — Windows startup and installer

- Added a branded Dark Glass splash screen.
- Added a dedicated application icon.
- Added Inno Setup installer with Start Menu shortcut, optional Desktop shortcut, and Windows uninstaller.
- Moved frozen-build writable state, logs, and Telegram session to `%LOCALAPPDATA%\TG_Coper` so installation under the user's Programs directory remains writable.
- Updated GitHub Actions workflow to build the portable directory and installer.
- Validation: Python syntax compilation passed; 12 engine/network tests passed. GUI tests require a graphical display and were not runnable in the headless environment. Windows installer compilation still needs to be confirmed by GitHub Actions.
