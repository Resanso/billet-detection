@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM build.bat — Build BilletDetection.exe on Windows
REM Usage: double-click build.bat OR run from Command Prompt
REM ─────────────────────────────────────────────────────────────────────────────

echo =^> Checking virtual environment ...
IF NOT EXIST venv (
    python -m venv venv
)
CALL venv\Scripts\activate.bat

echo =^> Installing / upgrading dependencies ...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo =^> Cleaning previous build ...
IF EXIST build  RMDIR /S /Q build
IF EXIST dist   RMDIR /S /Q dist

echo =^> Running PyInstaller ...
pyinstaller app.spec

echo.
echo [OK] Build complete!
echo      Output: dist\BilletDetection\BilletDetection.exe
pause
