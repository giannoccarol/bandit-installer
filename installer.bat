@echo off
rem Android installer for the Nokia Lumia 1520 (bandit), Windows launcher.
rem Options are passed through, for example: installer.bat --lang it
rem The release package carries its own Python in python\; a source checkout uses the system one.
setlocal
cd /d "%~dp0"
if exist "%~dp0python\python.exe" ("%~dp0python\python.exe" -B installer.py %* & goto :end)
where py >nul 2>nul && (py -3 -B installer.py %* & goto :end)
where python >nul 2>nul && (python -B installer.py %* & goto :end)
echo Python 3 is needed: https://www.python.org/downloads/windows/
echo or: winget install Python.Python.3.14
pause
:end
endlocal
