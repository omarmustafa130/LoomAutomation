@echo off
cd /d %~dp0
setlocal enabledelayedexpansion

:: ONE-CLICK BUILDER WITH SYSTEM PYTHON
:: Save as 'build.bat' in the same folder as automate_loom.py

:: Clear previous installations
echo Cleaning previous builds...
rmdir /s /q .\venv 2>nul
rmdir /s /q .\dist 2>nul
rmdir /s /q .\build 2>nul
del *.spec 2>nul
rmdir /s /q .\browsers 2>nul

:: Create virtual environment
echo Creating virtual environment...
python -m venv venv

:: Activate environment and install requirements
echo Installing dependencies...
call .\venv\Scripts\activate.bat
python -m pip install --upgrade pip==23.3.1
python -m pip install ^
    playwright==1.44.0 ^
    openpyxl==3.1.2 ^
    google-auth==2.29.0 ^
    google-api-python-client==2.122.0 ^
    pyinstaller==6.3.0

:: Set environment variable so Playwright downloads browsers locally
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0browsers"

echo Installing Playwright browsers...
python -m playwright install chromium

:: Build executable with proper paths
echo Building executable...
python -m PyInstaller ^
    --onefile ^
    --noconfirm ^
    --noconsole ^
    --name "LoomAutomation" ^
    --add-data "venv\Lib\site-packages\playwright\driver;playwright\driver" ^
    --add-data "browsers;.\browsers" ^
    --hidden-import "google.auth.transport.requests" ^
    --hidden-import "openpyxl.xml" ^
    --clean ^
    automate_loom.py

:: Move the executable from the dist folder to the main folder
echo Moving executable to main folder...
move /Y "%~dp0dist\LoomAutomation.exe" "%~dp0LoomAutomation.exe"

:: Delete build and dist folders
echo Cleaning up build directories...
rmdir /s /q "%~dp0build" 2>nul
rmdir /s /q "%~dp0dist" 2>nul

:: Delete all .spec files
echo Deleting .spec files...
del /q *.spec 2>nul

echo ----------------------------------------
echo BUILD SUCCESSFUL!
echo Executable: %~dp0LoomAutomation.exe
echo ----------------------------------------
pause
