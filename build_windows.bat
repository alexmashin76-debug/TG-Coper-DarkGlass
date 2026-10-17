@echo off
setlocal
cd /d "%~dp0"
echo === TG_Coper Windows build ===
py -3 -m pip install --upgrade pip
if errorlevel 1 goto fail
py -3 -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail
py -3 -m PyInstaller --noconfirm --clean --windowed --onedir --name TG_Coper --icon "TG_Coper.ico" --add-data "ui_background.png;." --add-data "tg_coper_splash.png;." tg_coper_panel.py
if errorlevel 1 goto fail
echo.
echo === Build installer (requires Inno Setup 6) ===
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
  "%ISCC%" "TG_Coper_Setup.iss"
  if errorlevel 1 goto fail
  echo Installer: %CD%\installer_output\TG_Coper_Setup.exe
) else (
  echo Inno Setup 6 not found. Portable build created; installer step skipped.
)
echo.
echo Build complete: %CD%\dist\TG_Coper\TG_Coper.exe
echo Keep all files in the TG_Coper folder together.
pause
exit /b 0
:fail
echo.
echo BUILD FAILED. Copy the error text and send it for troubleshooting.
pause
exit /b 1
