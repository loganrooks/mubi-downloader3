#!/bin/bash

# Setup colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check Python version
check_python_version() {
    local python_cmd=$1
    if ! command -v $python_cmd &> /dev/null; then
        return 1
    fi
    local version=$($python_cmd -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
    local major=$(echo $version | cut -d. -f1)
    local minor=$(echo $version | cut -d. -f2)
    if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 7 ]); then
        return 1
    fi
    return 0
}

# Check Python installation
echo -e "${BLUE}Checking Python installation...${NC}"
if check_python_version "python3"; then
    PYTHON_CMD="python3"
elif check_python_version "python"; then
    PYTHON_CMD="python"
else
    echo -e "${RED}Error: Python 3.7 or higher is required${NC}"
    exit 1
fi

# Environment checks
echo -e "${BLUE}Performing environment checks...${NC}"

# Check if running in WSL
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo -e "${YELLOW}WSL environment detected${NC}"
    
    # Check if DISPLAY is set for GUI capabilities
    if [ -z "$DISPLAY" ]; then
        echo -e "${YELLOW}No DISPLAY environment variable set. GUI authentication may not be available.${NC}"
    fi
    
    # Check Windows browser paths
    WINDOWS_USERNAME=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
    if [ ! -z "$WINDOWS_USERNAME" ]; then
        CHROME_PATH="/mnt/c/Users/$WINDOWS_USERNAME/AppData/Local/Google/Chrome/User Data/Default/Cookies"
        FIREFOX_PATH="/mnt/c/Users/$WINDOWS_USERNAME/AppData/Roaming/Mozilla/Firefox/Profiles"
        EDGE_PATH="/mnt/c/Users/$WINDOWS_USERNAME/AppData/Local/Microsoft/Edge/User Data/Default/Cookies"
        
        BROWSER_FOUND=false
        if [ -f "$CHROME_PATH" ]; then
            echo -e "${GREEN}Found Chrome installation${NC}"
            BROWSER_FOUND=true
        fi
        if [ -d "$FIREFOX_PATH" ]; then
            echo -e "${GREEN}Found Firefox installation${NC}"
            BROWSER_FOUND=true
        fi
        if [ -f "$EDGE_PATH" ]; then
            echo -e "${GREEN}Found Edge installation${NC}"
            BROWSER_FOUND=true
        fi
        
        if [ "$BROWSER_FOUND" = false ]; then
            echo -e "${YELLOW}No supported browsers detected in Windows. You may need to enter authentication manually.${NC}"
        fi
    fi
else
    # Check native Linux browser paths
    CHROME_PATH="$HOME/.config/google-chrome/Default/Cookies"
    FIREFOX_PATH="$HOME/.mozilla/firefox"
    EDGE_PATH="$HOME/.config/microsoft-edge/Default/Cookies"
    
    BROWSER_FOUND=false
    if [ -f "$CHROME_PATH" ]; then
        echo -e "${GREEN}Found Chrome installation${NC}"
        BROWSER_FOUND=true
    fi
    if [ -d "$FIREFOX_PATH" ]; then
        echo -e "${GREEN}Found Firefox installation${NC}"
        BROWSER_FOUND=true
    fi
    if [ -f "$EDGE_PATH" ]; then
        echo -e "${GREEN}Found Edge installation${NC}"
        BROWSER_FOUND=true
    fi
    
    if [ "$BROWSER_FOUND" = false ]; then
        echo -e "${YELLOW}No supported browsers detected. You may need to enter authentication manually.${NC}"
    fi
fi

# Check if Python virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${BLUE}Creating virtual environment...${NC}"
    $PYTHON_CMD -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install requirements if needed
if [ ! -f ".venv/requirements_installed" ]; then
    echo -e "${BLUE}Installing requirements...${NC}"
    pip install -r requirements.txt
    touch .venv/requirements_installed
fi

# Find the actual path to the module
MODULE_PATH="src/mubi_downloader"
if [ ! -d "$MODULE_PATH" ]; then
    echo -e "${RED}Error: Could not find mubi_downloader module${NC}"
    exit 1
fi

# Add the src directory to PYTHONPATH
export PYTHONPATH="$PYTHONPATH:$(pwd)"

# Run the mubi downloader
echo -e "${GREEN}Starting Mubi Downloader...${NC}"
python3 -m mubi_downloader "$@"

# Deactivate virtual environment
deactivate