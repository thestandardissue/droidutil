@echo off
cd /d "%~dp0"
where py >nul 2>nul && (start "" pyw droidutil.py & exit /b)
where python >nul 2>nul && (start "" pythonw droidutil.py & exit /b)
echo Python is not installed. Install it with:  winget install Python.Python.3.12
echo (or from https://www.python.org/downloads/ ) and run this again.
pause
