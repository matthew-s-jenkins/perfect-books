#!/bin/bash
cd "$(dirname "$0")"

echo ""
echo "============================================================"
echo "Perfect Books - Starting..."
echo "============================================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed."
    echo ""
    echo "Please install Python 3.8+ from https://www.python.org/downloads/"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Run the launcher
python3 start.py

# Keep terminal open on error
if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] An error occurred. See messages above."
    echo ""
    read -p "Press Enter to exit..."
fi
