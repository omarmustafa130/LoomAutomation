#!/bin/bash
cd "$(dirname "$0")"
set -e

echo "Cleaning previous builds..."
rm -rf ./venv ./dist ./build ./browsers *.spec

echo "Creating virtual environment..."
python3 -m venv venv

echo "Activating environment and installing dependencies..."
source venv/bin/activate
pip install --upgrade pip==23.3.1
pip install \
    playwright==1.44.0 \
    openpyxl==3.1.2 \
    google-auth==2.29.0 \
    google-api-python-client==2.122.0 \
    pyinstaller==6.3.0

export PLAYWRIGHT_BROWSERS_PATH="$(pwd)/browsers"

echo "Installing Playwright browsers..."
python -m playwright install chromium

echo "Building executable..."
pyinstaller \
    --onefile \
    --noconfirm \
    --noconsole \
    --name "LoomAutomation" \
    --add-data "venv/lib/python*/site-packages/playwright/driver:playwright/driver" \
    --add-data "browsers:browsers" \
    --hidden-import "google.auth.transport.requests" \
    --hidden-import "openpyxl.xml" \
    --clean \
    automate_loom.py

echo "Moving executable to main folder..."
mv ./dist/LoomAutomation .

echo "Cleaning up build directories..."
rm -rf ./build ./dist *.spec

echo "----------------------------------------"
echo "BUILD SUCCESSFUL!"
echo "Executable: $(pwd)/LoomAutomation"
echo "----------------------------------------"

read -p "Press Enter to close..."
