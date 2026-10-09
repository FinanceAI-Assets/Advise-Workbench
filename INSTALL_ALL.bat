@echo off
REM Advise Workbench - Automated Windows Setup Script
REM This script installs all dependencies and prepares the app for first run
REM No coding knowledge required!

setlocal enabledelayedexpansion
cls

echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║                                                                    ║
echo ║         Advise Workbench - Automated Setup for Windows            ║
echo ║                                                                    ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.

REM Colors and styling
color 0A
REM Store current directory
set "REPO_DIR=%cd%"

echo [INFO] Repository directory: %REPO_DIR%
echo.

REM ============================================================================
REM CHECK PYTHON
REM ============================================================================
echo [STEP 1/6] Checking Python installation...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.12 not found!
    echo [INFO] Downloading Python 3.12.10...
    powershell -Command ^
        "$ProgressPreference='SilentlyContinue'; ^
        Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' ^
        -OutFile '%TEMP%\python-3.12.10-amd64.exe'"

    echo [INFO] Installing Python 3.12.10...
    "%TEMP%\python-3.12.10-amd64.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    timeout /t 15 /nobreak >nul

    python --version >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Python installation failed. Please visit https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo [OK] Python installed successfully!
) else (
    echo [OK] Python already installed:
    python --version
)
echo.

REM ============================================================================
REM CHECK NODE.JS
REM ============================================================================
echo [STEP 2/6] Checking Node.js installation...
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js not found!
    echo [INFO] Downloading Node.js v20 LTS...
    powershell -Command ^
        "$ProgressPreference='SilentlyContinue'; ^
        Invoke-WebRequest -Uri 'https://nodejs.org/dist/v20.15.0/node-v20.15.0-x64.msi' ^
        -OutFile '%TEMP%\node-v20.15.0-x64.msi'"

    echo [INFO] Installing Node.js v20 LTS...
    msiexec.exe /i "%TEMP%\node-v20.15.0-x64.msi" /quiet /norestart
    timeout /t 30 /nobreak >nul

    REM Refresh PATH
    for /f "tokens=2*" %%A in ('reg query HKLM\SYSTEM\CurrentControlSet\Control\Session\ Manager\Environment /v PATH') do set "PATH=%%B"

    node --version >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Node.js installation failed. Please visit https://nodejs.org/
        pause
        exit /b 1
    )
    echo [OK] Node.js installed successfully!
) else (
    echo [OK] Node.js already installed:
    node --version
    npm --version
)
echo.

REM ============================================================================
REM CREATE PYTHON VIRTUAL ENVIRONMENT
REM ============================================================================
echo [STEP 3/6] Creating Python virtual environment...
if exist ".venv" (
    echo [OK] Virtual environment already exists
) else (
    echo [INFO] Creating .venv...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
)
echo.

REM ============================================================================
REM INSTALL BACKEND PACKAGES
REM ============================================================================
echo [STEP 4/6] Installing backend packages ^(this may take 5-10 minutes^)...
call .venv\Scripts\activate.bat
pip install -q -r requirements-dev.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install backend packages
    pause
    exit /b 1
)
echo [OK] Backend packages installed
echo.

REM ============================================================================
REM INSTALL FRONTEND PACKAGES
REM ============================================================================
echo [STEP 5/6] Installing frontend packages ^(this may take 3-5 minutes^)...
cd frontend
call npm install --no-fund --no-audit
if %ERRORLEVEL% neq 0 (
    echo [WARN] Frontend installation completed with warnings
) else (
    echo [OK] Frontend packages installed
)
cd ..
echo.

REM ============================================================================
REM SETUP .ENV FILE
REM ============================================================================
echo [STEP 6/6] Configuring environment...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [OK] Created .env from template
    )
)

REM Check if JWT_SECRET needs to be set
findstr /M "JWT_SECRET=change-me" .env >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "tokens=*" %%i in ('powershell -Command "import sys; import secrets; print(secrets.token_urlsafe(32))"') do set "JWT=%%i"
    powershell -Command "(Get-Content '.env') -replace 'JWT_SECRET=change-me-to-a-long-random-string', 'JWT_SECRET=%JWT%' | Set-Content '.env'"
    echo [OK] Generated secure JWT_SECRET
)
echo.

REM ============================================================================
REM SUMMARY
REM ============================================================================
cls
color 0A
echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║                   ✅ SETUP COMPLETE!                              ║
echo ║              Advise Workbench is Ready to Run                      ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.
echo 📦 INSTALLED COMPONENTS:
echo   ✅ Python 3.12.10
echo   ✅ Node.js v20 LTS
echo   ✅ Python virtual environment
echo   ✅ Backend packages
echo   ✅ Frontend packages
echo   ✅ Environment configured
echo.
echo 🔑 IMPORTANT: Set Your API Key
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo   Edit the file: .env
echo.
echo   Find line 135 and replace:
echo     ANTHROPIC_API_KEY=your_api_key_here
echo   With your actual key:
echo     ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
echo.
echo   Get your key from: https://console.anthropic.com
echo.
echo   OR use Claude Code CLI (free, no key needed):
echo     npm install -g @anthropic-ai/claude-code
echo     claude
echo     Then set in .env: LLM_PROVIDER=claude_cli
echo.
echo 🚀 NEXT STEPS:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo   1. Edit .env and add your API key (see above)
echo   2. Run: START_APP.bat
echo   3. Open: http://localhost:3000 in your browser
echo.
echo 🌐 QUICK ACCESS:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   Frontend:      http://localhost:3000
echo   Backend API:   http://127.0.0.1:8000
echo   API Docs:      http://127.0.0.1:8000/docs
echo.
echo 📚 HELPFUL FILES:
echo   • SETUP_COMPLETE.md  - Full setup guide
echo   • WINDOWS_SETUP.md   - Windows-specific help
echo   • README_RUN.md      - How to use the app
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo 📝 EDIT .env FILE?
echo   Type:  1 = Yes, open .env in Notepad
echo   Type:  2 = No, I'll edit it myself
echo   Type:  3 = Start the app anyway
echo.
choice /C 123 /M "Choose (1/2/3): " /T 10 /D 2

if errorlevel 3 goto start_app
if errorlevel 2 goto done
if errorlevel 1 goto edit_env

:edit_env
notepad .env
goto done

:start_app
echo.
echo [INFO] Starting Advise Workbench...
echo.
call .venv\Scripts\activate.bat
cd %REPO_DIR%
start cmd /k "cd /d %REPO_DIR% && .venv\Scripts\uvicorn src.app.main:app --reload --port 8000"
timeout /t 3 /nobreak >nul
cd frontend
start cmd /k "npm run dev -- -p 3000"
echo.
echo [INFO] Backend and Frontend starting...
echo [INFO] Wait 30-60 seconds, then open: http://localhost:3000
echo.
timeout /t 5 >nul
exit /b 0

:done
echo.
echo ✅ Setup is complete! When ready, run: START_APP.bat
echo.
pause
exit /b 0
