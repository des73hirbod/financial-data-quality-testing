@echo off
setlocal
cd /d "%~dp0"
title Financial Data Quality - Run All Tests

echo =======================================================
echo Financial Data Quality - Automated Test Runner
echo =======================================================
echo.
echo This runner needs Python 3.10 or newer. No pip install needed.
echo.

REM Prefer the Windows Python launcher when available.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 --version >nul 2>nul
    if not errorlevel 1 goto run_py
)
where python >nul 2>nul
if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 goto run_python
)

echo ERROR: Python was not found.
echo Install Python 3.10+ from https://www.python.org/downloads/
echo During installation, enable "Add Python to PATH".
echo Then double-click this file again.
pause
exit /b 2

:run_py
py -3 "%~dp0run_all_tests.py"
goto finish

:run_python
python "%~dp0run_all_tests.py"
goto finish

:finish
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
    echo Test execution completed. Open results\LATEST_RESULT.txt
) else (
    echo There were test or execution failures. Open results\LATEST_RESULT.txt
)
echo.
echo Press any key to close this window.
pause >nul
exit /b %RESULT%
