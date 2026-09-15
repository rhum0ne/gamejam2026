@echo off
REM Lanceur Windows : trouve un Python utilisable et delegue a play.py,
REM qui se charge de creer .venv et d'installer les dependances si besoin.

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" play.py %*
    exit /b %errorlevel%
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 play.py %*
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python play.py %*
    exit /b %errorlevel%
)

echo Aucun Python trouve sur cette machine.
echo Installe Python 3.10 ou plus recent : https://www.python.org/downloads/
exit /b 1
