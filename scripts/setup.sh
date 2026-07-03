#!/usr/bin/env bash

# ARGUS Project Bootstrap Setup Script
# Automatically creates virtual env, installs dependencies, and configures tooling.

set -e

echo "=== ARGUS Project Setup started ==="

# 1. Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed. Please install Python 3.11 first." >&2
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Detected Python version: ${PYTHON_VERSION}"

# 2. Create Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv..."
    python3 -m venv .venv
else
    echo "Virtual environment already exists in .venv."
fi

# 3. Activate Virtual Environment and Install Dependencies
echo "Activating virtual environment..."
source .venv/bin/activate

echo "Upgrading pip and setuptools..."
pip install --upgrade pip setuptools wheel

echo "Installing project dependencies from requirements.txt..."
pip install -r requirements.txt

# 4. Initialize DVC
if [ ! -d ".dvc" ]; then
    echo "Initializing DVC (Data Version Control)..."
    dvc init
else
    echo "DVC already initialized."
fi

echo "=== ARGUS Project Setup successfully completed! ==="
echo "To activate the environment, run: source .venv/bin/activate"
