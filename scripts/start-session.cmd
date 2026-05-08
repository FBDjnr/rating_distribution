@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "RUNNER=%SCRIPT_DIR%start-session.py"

python --version >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python "%RUNNER%" %*
  exit /b %ERRORLEVEL%
)

python3 --version >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python3 "%RUNNER%" %*
  exit /b %ERRORLEVEL%
)

py -3 --version >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 "%RUNNER%" %*
  exit /b %ERRORLEVEL%
)

conda run -n base python --version >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  conda run -n base python "%RUNNER%" %*
  exit /b %ERRORLEVEL%
)

mamba run -n base python --version >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  mamba run -n base python "%RUNNER%" %*
  exit /b %ERRORLEVEL%
)

micromamba run -n base python --version >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  micromamba run -n base python "%RUNNER%" %*
  exit /b %ERRORLEVEL%
)

echo No Python launcher was found. Install Python 3 or make sure Conda's Python is on PATH.
exit /b 1
