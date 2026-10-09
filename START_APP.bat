@echo off
REM Advise Workbench - Quick Start Script
REM Simply run this to start the application!

setlocal enabledelayedexpansion
cls

echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║                                                                    ║
echo ║              🚀 Starting Advise Workbench                         ║
echo ║                                                                    ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.

REM Store repo directory
set "REPO_DIR=%cd%"

REM Check if .env exists
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo [INFO] Please run INSTALL_ALL.bat first
    pause
    exit /b 1
)

REM Check if .venv exists
if not exist ".venv" (
    echo [ERROR] Virtual environment not found!
    echo [INFO] Please run INSTALL_ALL.bat first
    pause
    exit /b 1
)

REM Check API key is set
findstr /M "ANTHROPIC_API_KEY=your_api_key_here" .env >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [WARNING] API key is not configured!
    echo.
    echo Please edit .env and set:
    echo   ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
    echo.
    echo Get your key from: https://console.anthropic.com
    echo.
    choice /C YN /M "Continue anyway (Y/N)? " /T 10 /D N
    if errorlevel 2 exit /b 1
)

echo [INFO] Activating Python virtual environment...
call .venv\Scripts\activate.bat

echo [INFO] Checking ports...
netstat -ano | findstr ":8000" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [WARNING] Port 8000 is already in use!
    echo [INFO] Using alternative port instead...
    set "BACKEND_PORT=8001"
) else (
    set "BACKEND_PORT=8000"
)

netstat -ano | findstr ":3000" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [WARNING] Port 3000 is already in use!
    echo [INFO] Using alternative port instead...
    set "FRONTEND_PORT=3001"
) else (
    set "FRONTEND_PORT=3000"
)

echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║                   STARTING SERVICES                               ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.
echo 🔧 Backend: Starting on port %BACKEND_PORT%...
echo 🎨 Frontend: Starting on port %FRONTEND_PORT%...
echo.
echo ⏳ Please wait 30-60 seconds for services to start...
echo.

REM Start backend in new window
start "Advise Workbench Backend" cmd /k "cd /d "%REPO_DIR%" && .venv\Scripts\uvicorn src.app.main:app --reload --port %BACKEND_PORT%"

REM Wait for backend to start
timeout /t 5 /nobreak >nul

REM Start frontend in new window
cd frontend
start "Advise Workbench Frontend" cmd /k "npm run dev -- -p %FRONTEND_PORT%"
cd ..

REM Wait for frontend to start
timeout /t 10 /nobreak >nul

echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║                   ✅ SERVICES STARTED!                            ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.
echo 🌐 ACCESS YOUR APPLICATION:
echo.
echo   Frontend:    http://localhost:%FRONTEND_PORT%
echo   Backend API: http://127.0.0.1:%BACKEND_PORT%
echo   API Docs:    http://127.0.0.1:%BACKEND_PORT%/docs
echo.
echo 📋 FIRST TIME?
echo.
echo   1. Open http://localhost:%FRONTEND_PORT% in your browser
echo   2. Sign up with any email and password
echo   3. Create a new project
echo   4. Upload sample files from: data/examples/northwind-p2p/source-documents/
echo   5. Chat with Sheldon to request a deck or document
echo.
echo 🛑 TO STOP:
echo.
echo   Close these two windows:
echo   • Advise Workbench Backend
echo   • Advise Workbench Frontend
echo.
echo 📚 NEED HELP?
echo.
echo   Read:
echo   • SETUP_COMPLETE.md  - Setup guide
echo   • WINDOWS_SETUP.md   - Windows troubleshooting
echo   • README_RUN.md      - How to use
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
pause
