#!/bin/bash
# BioTechDemo Setup Script
# Installs uv if needed, creates virtual environment, and installs all dependencies

set -e  # Exit on error

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BioTechDemo Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo ""
    echo "uv installed successfully"
    echo ""
    echo "Please restart your shell or run:"
    echo "    source \$HOME/.cargo/env"
    echo ""
    echo "Then run this script again."
    exit 0
fi

echo "uv is installed"
echo ""

# Check Python version
echo "Checking Python..."
PYTHON_VERSION=$(uv python list | grep "3.11" | head -n1 || echo "")
if [ -z "$PYTHON_VERSION" ]; then
    echo "Installing Python 3.11..."
    uv python install 3.11
fi
echo "Python 3.11 available"
echo ""

# Check Docker (required for containerized deployment)
echo "Checking Dcoker..."
if ! command -v docker &> /dev/null; then
    echo "   Docker not found"
    echo "   Required for: make docker-up, make docker-build"
    echo "   Install: https://docs.docker.com/get-docker"
    echo ""
else
    echo "Docker is installed"
    if ! docker ps &> /dev/null 2>&1; then
        echo "   Docker daemon not running or requires permissions"
        echo "   Start: sudo systemctl start docker"
        echo "   Fix permissions: sudo usermod -aG docker \$USER (requires logout)"
        echo ""
    else
        echo "Docker daemon is running"
    fi
fi
echo ""

# Sync dependencies
echo "Installing dependencies..."
uv sync --all-extras
echo "Python dependencies installed"
echo ""

# Install Node dependencies for dashboard
if [ -d "services/dashboard" ]; then
    echo "Installing dashboard dependencies..."
    cd services/dashboard && npm install && cd ../..
    echo "Dashboard dependencies installed"
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To activate the virtual environment:"
echo "  source .venv/bin/activate"
echo ""
echo "Then run:"
echo "  make generate-model    # Generate ML model"
echo "  make test              # Run tests"
echo "  make api               # Start API server"
echo ""