@echo off
echo ============================================================
echo   ClauseGuard - Running Tests
echo ============================================================
echo.
echo Tests use mocks - no API keys needed, no cost.
echo.
cd /d %~dp0backend
call venv\Scripts\activate
pytest tests/ -v
call venv\Scripts\deactivate
echo.
echo Tests complete.
pause
