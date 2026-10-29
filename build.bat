@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo       Building EasyAnswer Windows Executable (.exe)
echo ========================================================

cd /d "%~dp0"

:: Check if virtual environment exists
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    set "PYINSTALLER_EXE=.venv\Scripts\pyinstaller.exe"
) else (
    set "PYTHON_EXE=python"
    set "PYINSTALLER_EXE=pyinstaller"
)

echo [1/3] Generating application icon (app.ico)...
"%PYTHON_EXE%" tools\build_icon.py
if errorlevel 1 (
    echo [ERROR] Failed to generate icon.
    exit /b 1
)

echo [2/3] Running PyInstaller packaging...
"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm EasyAnswer.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed!
    exit /b 1
)


echo [3/3] Preparing distribution folder...
if not exist "dist\" mkdir dist
copy /y "screenshot_ai\.env.example" "dist\.env.example" >nul

echo ========================================================
echo [SUCCESS] Build completed successfully!
echo Executable is ready at: dist\EasyAnswer.exe
echo.
echo NOTE: Make sure to create a .env file next to EasyAnswer.exe
echo       with your GEMINI_API_KEY before running.
echo ========================================================
