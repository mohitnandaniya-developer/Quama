# Development Scripts

Local quality check scripts for Quama development.

## Available Scripts

- `backend-check.sh` - Local backend quality checks (lint, format, tests)
- `frontend-check.sh` - Local frontend quality checks (lint, format, typecheck, build)
- `quality-gate.sh` - Combined backend + frontend checks

## Usage

Run all checks locally before committing:

```bash
make ci-local
```

Or run individual scripts:

```bash
bash scripts/backend-check.sh
bash scripts/frontend-check.sh
bash scripts/quality-gate.sh
```

## GitHub Actions

GitHub Actions workflows are in `.github/workflows/`:
- `backend-ci.yml` - Runs on backend changes (push/PR to main, develop)
- `frontend-ci.yml` - Runs on frontend changes (push/PR to main, develop)

These workflows are automatically triggered by GitHub and mirror the local scripts.
