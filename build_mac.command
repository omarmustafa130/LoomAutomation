#!/bin/bash
# Change directory to the folder where the script resides.
cd "$(dirname "$0")"

echo "Cleaning previous builds..."
rm -rf ./venv
rm -rf ./dist
rm -rf ./build
rm -f *.spec
rm -rf ./browsers

echo "Creating virtual environment..."
python3 -m venv venv

echo "Activating virtual environment and installing dependencies..."
source venv/bin/activate
pip install --upgrade "pip==23.3.1"
pip install \
    "playwright" \
    "openpyxl" \
    "google-auth" \
    "google-api-python-client" \
    "pyinstaller"

echo "Setting PLAYWRIGHT_BROWSERS_PATH and installing Playwright browsers..."
export PLAYWRIGHT_BROWSERS_PATH="$(pwd)/browsers"
python -m playwright install chromium

echo "Building executable..."
python -m PyInstaller \
    --onefile \
    --noconfirm \
    --noconsole \
    --name "LoomAutomation" \
    --add-data "venv/lib/python3.11/site-packages/playwright/driver:playwright/driver" \
    --add-data "browsers:./browsers" \
    --hidden-import "google.auth.transport.requests" \
    --hidden-import "openpyxl.xml" \
    --clean \
    automate_loom.py

echo "Moving executable to main folder..."
mv -f "./dist/LoomAutomation" "./LoomAutomation"

echo "Cleaning up build directories..."
rm -rf "./build"
rm -rf "./dist"
rm -f *.spec

echo "----------------------------------------"
echo "BUILD SUCCESSFUL!"
echo "Executable: $(pwd)/LoomAutomation"
echo "----------------------------------------"

deactivate
