@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "RUNNER=%SCRIPT_DIR%start-session.py"
if not defined PYTHONIOENCODING set "PYTHONIOENCODING=utf-8"
if not defined PYTHONUTF8 set "PYTHONUTF8=1"

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

for %%T in (conda mamba micromamba) do (
  for /f "usebackq delims=" %%B in (`%%T info --base 2^>nul`) do (
    if exist "%%B\python.exe" (
      "%%B\python.exe" "%RUNNER%" %*
      exit /b %ERRORLEVEL%
    )
    if exist "%%B\bin\python.exe" (
      "%%B\bin\python.exe" "%RUNNER%" %*
      exit /b %ERRORLEVEL%
    )
  )
)

echo No Python launcher was found. Install Python 3 or make sure Conda's Python is on PATH.
exit /b 1
