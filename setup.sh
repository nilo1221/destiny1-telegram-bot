#!/bin/bash
# Setup script for Helix Backend

echo "🔧 Setting up Helix Backend..."

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install fastapi uvicorn httpx tenacity redis pydantic pydantic-settings python-dotenv structlog

echo "✅ Setup complete!"
echo ""
echo "To run the server:"
echo "  source .venv/bin/activate && python run.py"
