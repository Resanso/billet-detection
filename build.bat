@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM build.bat — Build BilletDetection.exe on Windows
REM Usage: double-click build.bat OR run from Command Prompt
REM ─────────────────────────────────────────────────────────────────────────────

echo =^> Checking virtual environment ...
IF NOT EXIST venv (
    echo =^> Trying to use Windows AppData Python 3.11 ...
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" -m venv venv 2>NUL || py -3.11 -m venv venv 2>NUL || python -m venv venv
)
CALL venv\Scripts\activate.bat

echo =^> Installing / upgrading dependencies ...
python -m pip install --upgrade pip || exit /B 1
pip install -r requirements.txt || exit /B 1
pip install pyinstaller || exit /B 1

echo =^> Cleaning previous build ...
IF EXIST build  RMDIR /S /Q build
IF EXIST dist   RMDIR /S /Q dist

echo =^> Running PyInstaller ...
pyinstaller app.spec

echo.
echo [OK] Build complete!
echo      Output: dist\BilletDetection\BilletDetection.exe
pause
