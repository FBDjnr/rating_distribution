@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python "%SCRIPT_DIR%save_session.py" %*
    exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 "%SCRIPT_DIR%save_session.py" %*
    exit /b %ERRORLEVEL%
)

echo Could not find Python. Install Miniforge/Miniconda or Python, then try again.
exit /b 1
