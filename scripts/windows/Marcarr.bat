@echo off
rem Marcarr, portable: everything it needs is in this folder.
rem Settings and data live in the "config" folder next to this file.
setlocal
set "HERE=%~dp0"
set "PATH=%HERE%ffmpeg;%PATH%"
set "MARCARR_CONFIG=%HERE%config\config.yaml"
set "MARCARR_DATA_DIR=%HERE%config\data"
if not exist "%HERE%config" mkdir "%HERE%config"
echo Marcarr is starting on http://127.0.0.1:7470 (close this window to stop it).
start "" /b cmd /c "timeout /t 5 /nobreak >nul & start http://127.0.0.1:7470"
"%HERE%python\python.exe" -m marcarr %*
echo.
echo Marcarr stopped.
pause
