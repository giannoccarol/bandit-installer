@echo off
rem Android installer for the Nokia Lumia 1520 (bandit), Windows launcher.
rem Options are passed through, for example: installer.bat --lang it
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (py -3 -B installer.py %* & goto :end)
where python >nul 2>nul && (python -B installer.py %* & goto :end)
echo Python 3 is needed: https://www.python.org/downloads/windows/
echo or: winget install Python.Python.3.12
pause
:end
endlocal
