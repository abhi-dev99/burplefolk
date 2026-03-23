@echo off
title Nexus Intelligence Launcher
echo ==================================================
echo Starting Nexus Intelligence System
echo ==================================================

echo [1/2] Booting Python AI Backend (FastAPI)...
start /b "" .venv\Scripts\python.exe api.py > backend.log 2>&1

timeout /t 2 /nobreak > nul

echo [2/2] Booting Ethereal React Interface (Vite)...
cd /d "%~dp0\nexus-ui"
start /b "" npm run dev > frontend.log 2>&1

echo.
echo ==================================================
echo System successfully initiated IN BACKGROUND!
echo --------------------------------------------------
echo Logs are saved to backend.log and frontend.log
echo To cleanly stop all background processes:
echo Stop-Process -Name node, python (via PowerShell)
echo ==================================================
pause
