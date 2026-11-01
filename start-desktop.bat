@echo off
setlocal
cd /d "%~dp0apps\desktop"
where node >nul 2>nul
if errorlevel 1 (
  echo [DAWLoop] Node.js is missing. Install Node.js 22.12 or newer, then retry.
  pause
  exit /b 1
)
where npm.cmd >nul 2>nul
if errorlevel 1 (
  echo [DAWLoop] npm is missing. Repair your Node.js installation, then retry.
  pause
  exit /b 1
)
node scripts\dev-launcher.mjs %*
if errorlevel 1 (
  echo [DAWLoop] Startup failed. Read the error above; this is the developer entry.
  pause
  exit /b 1
)
endlocal
