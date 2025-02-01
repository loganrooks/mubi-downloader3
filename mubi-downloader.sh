#!/bin/bash

# Setup colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Python virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${BLUE}Creating virtual environment...${NC}"
    python3 -m venv .venv
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
    echo "Error: Could not find mubi_downloader module"
    exit 1
fi

# Add the src directory to PYTHONPATH
export PYTHONPATH="$PYTHONPATH:$(pwd)"

# Run the mubi downloader
echo -e "${GREEN}Starting Mubi Downloader...${NC}"
python3 -m mubi_downloader "$@"

# Deactivate virtual environment
deactivate