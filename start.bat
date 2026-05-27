@echo off
:: ============================================================
:: ClauseGuard — Start All Services
:: Run this every time you want to use the app.
:: ============================================================

echo.
echo ============================================================
echo   Starting ClauseGuard
echo ============================================================

:: Start database
echo [1/3] Starting database...
docker-compose up -d >nul 2>&1
echo   OK - Database started

:: Start backend in new window
echo [2/3] Starting backend API (http://localhost:8000)...
start "ClauseGuard Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\activate && uvicorn main:app --reload --port 8000"
timeout /t 3 /nobreak >nul

:: Start frontend in new window
echo [3/3] Starting frontend (http://localhost:3000)...
start "ClauseGuard Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
timeout /t 5 /nobreak >nul

echo.
echo ============================================================
echo   ClauseGuard is starting up!
echo ============================================================
echo.
echo   Wait 15-20 seconds, then open:
echo   http://localhost:3000
echo.
echo   Two new windows opened:
echo     - "ClauseGuard Backend"  (keep open)
echo     - "ClauseGuard Frontend" (keep open)
echo.
echo   To STOP: close both windows, then run stop.bat
echo ============================================================
echo.

:: Open browser after delay
timeout /t 15 /nobreak >nul
start http://localhost:3000

pause
