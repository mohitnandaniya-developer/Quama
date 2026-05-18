#!/bin/bash
set -euo pipefail

echo "Frontend quality checks..."
echo "Step 1: Installing dependencies..."
cd frontend
pnpm install --frozen-lockfile || { echo "  Dependency installation failed."; exit 1; }

echo "Step 2: Checking code style and formatting..."
pnpm lint || { echo "  Linting failed. Run 'pnpm lint --fix' to auto-fix."; exit 1; }
pnpm format:check || { echo "  Format check failed. Run 'pnpm format' to auto-format."; exit 1; }

echo "Step 3: Type checking..."
pnpm typecheck || { echo "  Type check failed. See errors above."; exit 1; }

echo "Step 4: Building..."
pnpm build || { echo "  Build failed. Check output above."; exit 1; }

echo "Frontend checks passed"
