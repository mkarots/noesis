#!/bin/bash
# Test runner script for Noesis Agent Framework

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🧪 Running Noesis Agent Framework Tests..."
echo ""

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo -e "${RED}Error: Virtual environment not found. Run: python3 -m venv .venv && pip install -e \".[dev]\"${NC}"
    exit 1
fi

# Run pytest with verbose output
python -m pytest tests/ -v --tb=line

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"
else
    echo ""
    echo -e "${RED}❌ Some tests failed.${NC}"
    exit 1
fi

