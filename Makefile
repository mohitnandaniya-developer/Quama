.PHONY: help setup check-deps \
	backend-install backend-env backend-dev backend-test backend-lint backend-format \
	backend-clean backend-db-reset \
	frontend-install frontend-env frontend-dev frontend-build frontend-lint \
	frontend-format frontend-typecheck frontend-clean \
	worker migrate \
	install-all dev lint lint-all clean \
	db-setup db-reset db-status \
	ci-backend ci-frontend ci-local quality-check

help:
	@echo "QUAMA DEVELOPER COMMANDS"
	@echo ""
	@echo "INITIAL SETUP"
	@echo "  make setup              Initialize project (envs + migrations)"
	@echo "  make check-deps         Check if all prerequisites are installed"
	@echo ""
	@echo "BACKEND TARGETS"
	@echo "  make backend-install    Install Python dependencies"
	@echo "  make backend-env        Setup .env.local and .env placeholders from .env.sample"
	@echo "  make backend-dev        Start backend server (port 8000)"
	@echo "  make backend-test       Run pytest test suite"
	@echo "  make backend-lint       Run ruff linter"
	@echo "  make backend-format     Auto-format code with ruff"
	@echo "  make backend-clean      Remove .venv and cache files"
	@echo ""
	@echo "FRONTEND TARGETS"
	@echo "  make frontend-install   Install Node dependencies"
	@echo "  make frontend-env       Setup .env.local and .env placeholders from .env.sample"
	@echo "  make frontend-dev       Start dev server"
	@echo "  make frontend-build     Build for production"
	@echo "  make frontend-lint      Run linter"
	@echo "  make frontend-format    Auto-format code with prettier"
	@echo "  make frontend-typecheck Run TypeScript type checking"
	@echo "  make frontend-clean     Remove node_modules and build"
	@echo ""
	@echo "DATABASE & WORKER"
	@echo "  make db-setup           Run migrations (alias: make migrate)"
	@echo "  make db-reset           Reset database and re-run migrations"
	@echo "  make db-status          Show migration status"
	@echo "  make worker             Start market data worker"
	@echo ""
	@echo "COMBINED COMMANDS"
	@echo "  make install-all        Install both backend + frontend deps"
	@echo "  make dev                Start backend + frontend (separate terminals)"
	@echo "  make lint               Run backend linting (ruff)"
	@echo "  make lint-all           Run all linters (backend + frontend)"
	@echo "  make clean              Clean all generated files"
	@echo "  make ci-backend         Run backend quality checks"
	@echo "  make ci-frontend        Run frontend quality checks"
	@echo "  make ci-local           Run backend + frontend quality checks"
	@echo ""

check-deps:
	@echo "Checking prerequisites..."
	@command -v python3 >/dev/null 2>&1 && echo "OK Python3" || (echo "ERROR Python3 not found"; exit 1)
	@command -v uv >/dev/null 2>&1 && echo "OK uv" || (echo "ERROR uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1)
	@command -v node >/dev/null 2>&1 && echo "OK Node.js" || (echo "ERROR Node.js not found"; exit 1)
	@command -v pnpm >/dev/null 2>&1 && echo "OK pnpm" || (echo "ERROR pnpm not found. Install: npm install -g pnpm"; exit 1)
	@echo ""
	@python3 --version | grep -q "3.11\|3.12\|3.13" && echo "OK Python 3.11+" || echo "WARN Python 3.11+ recommended"
	@node --version && pnpm --version

setup: check-deps backend-env frontend-env backend-install frontend-install db-setup
	@echo ""
	@echo "Project setup complete"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Review backend/.env.local and frontend/.env.local"
	@echo "  2. If deploying, review backend/.env and frontend/.env"
	@echo "  3. Run: make dev"

backend-install:
	cd backend && uv sync --all-groups

backend-env:
	@if [ ! -f backend/.env.local ]; then \
		echo "Creating backend/.env.local..."; \
		cp backend/.env.sample backend/.env.local; \
		echo "Created backend/.env.local. Please review and update it for local development"; \
	else \
		echo "backend/.env.local already exists"; \
	fi; \
	if [ ! -f backend/.env ]; then \
		echo "Creating backend/.env (production placeholder)..."; \
		cp backend/.env.sample backend/.env; \
		echo "Created backend/.env (edit for production)."; \
	else \
		echo "backend/.env already exists"; \
	fi

backend-dev:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-test:
	cd backend && uv run pytest tests/ -v --tb=short

backend-lint:
	cd backend && uv run ruff check .

backend-format:
	cd backend && uv run ruff format .

backend-clean:
	cd backend && rm -rf .venv __pycache__ .pytest_cache .ruff_cache *.egg-info dist build
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

frontend-install:
	cd frontend && pnpm install

frontend-env:
	@if [ ! -f frontend/.env.local ]; then \
		echo "Creating frontend/.env.local..."; \
		cp frontend/.env.sample frontend/.env.local; \
		echo "Created frontend/.env.local. Please review and update it for local development"; \
	else \
		echo "frontend/.env.local already exists"; \
	fi; \
	if [ ! -f frontend/.env ]; then \
		echo "Creating frontend/.env (production placeholder)..."; \
		cp frontend/.env.sample frontend/.env; \
		echo "Created frontend/.env (edit for production)."; \
	else \
		echo "frontend/.env already exists"; \
	fi

frontend-dev:
	cd frontend && pnpm dev

frontend-build:
	cd frontend && pnpm build

frontend-lint:
	cd frontend && pnpm lint

frontend-format:
	cd frontend && pnpm format

frontend-typecheck:
	cd frontend && pnpm typecheck

frontend-clean:
	cd frontend && rm -rf node_modules .turbo dist build
	rm -rf frontend/apps/*/dist frontend/apps/*/.turbo
	rm -rf frontend/packages/*/dist frontend/packages/*/.turbo

migrate: db-setup

db-setup:
	cd backend && uv run alembic upgrade head
	@echo "Migrations complete"

db-reset:
	@read -p "WARN This will reset your database. Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		cd backend && uv run alembic downgrade base && uv run alembic upgrade head; \
		echo "Database reset complete"; \
	else \
		echo "Cancelled"; \
	fi

db-status:
	cd backend && uv run alembic current

worker:
	cd backend && uv run python -m workers.market_data

install-all: backend-install frontend-install
	@echo "All dependencies installed"

dev:
	@echo "Starting Quama development environment..."
	@echo "Backend on http://localhost:8000, Frontend on http://localhost:3000"
	@echo ""
	@echo "To start both, run in separate terminals:"
	@echo "  Terminal 1: make backend-dev"
	@echo "  Terminal 2: make frontend-dev"
	@echo "  Terminal 3: make worker (optional, for live market data)"
	@echo ""
	@echo "Or use your terminal multiplexer (tmux/screen) for a single command."

lint: backend-lint
	@echo "Linting complete"

lint-all: backend-lint frontend-lint
	@echo "All linting complete"

clean: backend-clean frontend-clean
	@echo "Clean complete"

ci-backend:
	bash scripts/backend-check.sh

ci-frontend:
	bash scripts/frontend-check.sh

ci-local: ci-backend ci-frontend
	@echo "All quality checks passed"

quality-check: ci-local
