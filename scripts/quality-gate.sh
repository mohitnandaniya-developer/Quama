#!/bin/bash
set -euo pipefail

trap 'echo "Quality gate failed" >&2; exit 1' ERR

echo "Full quality gate..."
echo ""

echo "-----------------------------------------------"
echo "Backend Checks"
echo "-----------------------------------------------"
bash scripts/backend-check.sh || exit 1
echo ""

echo "-----------------------------------------------"
echo "Frontend Checks"
echo "-----------------------------------------------"
bash scripts/frontend-check.sh || exit 1
echo ""

echo "-----------------------------------------------"
echo "All checks passed"
echo "-----------------------------------------------"
