#!/bin/bash
# Start script for Helix Backend

if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Run ./setup.sh first"
    exit 1
fi

echo "🚀 Starting Helix Backend..."
source .venv/bin/activate
python run.py
