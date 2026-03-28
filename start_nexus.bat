@echo off
setlocal EnableExtensions

for %%I in ("%~dp0.") do set "ROOT=%%~fI"
set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"
set "VENV_ACT=%ROOT%\.venv\Scripts\activate.bat"
set "UI_DIR=%ROOT%\nexus-ui"

title Nexus Intelligence Launcher
echo ==================================================
echo Starting Nexus Intelligence Stack
echo - Backend API (FastAPI)
echo - Frontend UI (React/Vite)
echo - Streamlit App
echo ==================================================

if not exist "%VENV_PY%" (
	echo [ERROR] Python virtual environment not found at:
	echo         %VENV_PY%
	echo Create it first:
	echo   python -m venv .venv
	echo   .venv\Scripts\pip install -r requirements.txt
	pause
	exit /b 1
)

if not exist "%UI_DIR%\package.json" (
	echo [ERROR] Frontend folder missing package.json:
	echo         %UI_DIR%
	pause
	exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
	echo [ERROR] npm is not available on PATH.
	echo Install Node.js and reopen terminal.
	pause
	exit /b 1
)

echo [1/3] Starting Backend API on http://127.0.0.1:8000 ...
start "Nexus Backend API" /D "%ROOT%" cmd /k "call .venv\Scripts\activate.bat && python api.py"

echo [2/3] Starting Frontend React UI on http://localhost:5173 ...
start "Nexus Frontend UI" /D "%UI_DIR%" cmd /k "if not exist node_modules (echo Installing frontend dependencies... && npm install) && npm run dev -- --host 0.0.0.0 --port 5173"

echo [3/3] Starting Streamlit on http://localhost:8501 ...
start "Nexus Streamlit" /D "%ROOT%" cmd /k "call .venv\Scripts\activate.bat && python -m streamlit run app.py"

echo.
echo ==================================================
echo All launch commands were sent.
echo Three terminal windows should now be open.
echo ==================================================
echo To stop services later, close those windows.
echo.
pause
exit /b 0
