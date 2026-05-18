#!/bin/bash
set -euo pipefail

echo "Backend quality checks..."
echo "Step 1: Checking code style..."
cd backend
uv run ruff check . || { echo "  Ruff check failed. Run 'uv run ruff check . --fix' to auto-fix."; exit 1; }

echo "Step 2: Verifying formatting..."
uv run ruff format --check . || { echo "  Format check failed. Run 'uv run ruff format .' to auto-format."; exit 1; }

echo "Step 3: Running unit tests..."
uv run pytest tests/ -v --tb=short || { echo "  Tests failed. Check output above."; exit 1; }

echo "Backend checks passed"
