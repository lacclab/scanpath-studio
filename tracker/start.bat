@echo off
rem Windows twin of start.command. Double-click to run the tracker.
rem
rem `python3` on Windows is normally the Microsoft Store alias, which prints
rem "Python was not found" and exits 9009 rather than running anything -- so
rem the documented `python3 tracker/server.py` fails here. Try the launcher
rem (`py`) first, then `python`, and never `python3`.
setlocal
set "TRACKER_DIR=%~dp0"

where py >nul 2>&1 && (
  py "%TRACKER_DIR%server.py" %*
  goto :done
)

where python >nul 2>&1 && (
  python "%TRACKER_DIR%server.py" %*
  goto :done
)

echo Could not find Python. Install it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH", then run this file again.
pause
exit /b 1

:done
rem Double-clicked windows close on exit and take the error with them; a server
rem that failed to start is exactly when the message matters most.
if errorlevel 1 pause
