@echo off
:: ============================================================
:: ClauseGuard — Windows One-Click Setup
:: ============================================================
:: Run this ONCE after extracting the project.
:: After setup, use start.bat to run the app daily.
:: ============================================================

echo.
echo ============================================================
echo   ClauseGuard Setup for Windows
echo ============================================================
echo.

:: ── Check prerequisites ──────────────────────────────────────
echo [1/6] Checking prerequisites...

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Please install Python 3.11 from https://python.org
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo   OK - Python found

node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found.
    echo Please install Node.js LTS from https://nodejs.org
    pause
    exit /b 1
)
echo   OK - Node.js found

docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker not found.
    echo Please install Docker Desktop from https://docker.com
    pause
    exit /b 1
)
echo   OK - Docker found

:: ── Create .env if it doesn't exist ─────────────────────────
echo.
echo [2/6] Setting up environment...

if not exist ".env" (
    copy ".env.example" ".env"
    echo.
    echo   IMPORTANT: .env file created from template.
    echo   You MUST edit .env and add your API keys before the app will work.
    echo.
    echo   Required keys:
    echo     ANTHROPIC_API_KEY  - from console.anthropic.com
    echo     OPENAI_API_KEY     - from platform.openai.com
    echo     PINECONE_API_KEY   - from app.pinecone.io
    echo.
    echo   Press any key to open .env in Notepad, then save and close it.
    pause
    notepad .env
) else (
    echo   OK - .env already exists
)

:: Copy .env to backend directory
copy ".env" "backend\.env" >nul 2>&1
echo   OK - .env copied to backend/

:: Create frontend .env.local
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > "frontend\.env.local"
echo BACKEND_URL=http://localhost:8000 >> "frontend\.env.local"
echo   OK - frontend/.env.local created

:: ── Start database ───────────────────────────────────────────
echo.
echo [3/6] Starting database (PostgreSQL)...
docker-compose up -d
if errorlevel 1 (
    echo ERROR: Docker failed to start. Is Docker Desktop running?
    echo Please start Docker Desktop and run setup.bat again.
    pause
    exit /b 1
)
echo   OK - Database starting (may take 10-15 seconds to be ready)
timeout /t 10 /nobreak >nul

:: ── Backend Python setup ─────────────────────────────────────
echo.
echo [4/6] Setting up Python backend...
cd backend

python -m venv venv
call venv\Scripts\activate.bat

echo   Installing Python packages (this takes 3-10 minutes)...
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: pip install failed.
    echo Try running: pip install -r requirements.txt
    echo in the backend folder with the venv activated.
    cd ..
    pause
    exit /b 1
)
echo   OK - Python packages installed

call venv\Scripts\deactivate.bat
cd ..

:: ── Frontend Node setup ──────────────────────────────────────
echo.
echo [5/6] Setting up frontend (Node.js)...
cd frontend
echo   Installing Node packages (this takes 2-5 minutes)...
npm install --silent
if errorlevel 1 (
    echo ERROR: npm install failed.
    echo Try running: npm install
    echo in the frontend folder manually.
    cd ..
    pause
    exit /b 1
)
echo   OK - Node packages installed
cd ..

:: ── Done ────────────────────────────────────────────────────
echo.
echo [6/6] Setup complete!
echo.
echo ============================================================
echo   SETUP SUCCESSFUL
echo ============================================================
echo.
echo   To START the app, run:  start.bat
echo.
echo   The app will open at:   http://localhost:3000
echo   The API runs at:        http://localhost:8000
echo.
echo   REMINDER: Make sure .env has your real API keys or
echo   the AI analysis will not work.
echo ============================================================
echo.
pause
