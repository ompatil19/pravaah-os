# Pravaah OS v2 — Makefile
# Usage: make <target>
# Uses tabs for recipe indentation (required by make).

PYTHON := python3
PIP    := $(PYTHON) -m pip
NPM    := npm
VENV   := .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP    := $(VENV)/bin/pip


.PHONY: setup dev worker test test-pipeline lint clean create-admin help

##@ Help

help: ## Show this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup

setup: ## Create venv, pip install, npm install, and check Redis
	@echo "==> Checking Redis..."
	@if ! command -v redis-server >/dev/null 2>&1; then \
		echo ""; \
		echo "  ERROR: redis-server not found."; \
		echo "  macOS (Homebrew):  brew install redis"; \
		echo "  Ubuntu/Debian:     sudo apt-get install -y redis-server"; \
		echo ""; \
		exit 1; \
	fi
	@echo "  Redis OK: $$(redis-server --version | awk '{print $$3}')"
	@echo "==> Creating Python virtual environment in $(VENV)..."
	$(PYTHON) -m venv $(VENV)
	@echo "==> Upgrading pip..."
	$(VENV_PIP) install --upgrade pip -q
	@echo "==> Installing Python dependencies..."
	$(VENV_PIP) install -r backend/requirements.txt
	$(VENV_PIP) install pytest pytest-flask -q
	@echo "==> Installing frontend Node dependencies..."
	cd frontend && $(NPM) install
	@echo "==> Checking for .env file..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ""; \
		echo "  .env created from .env.example."; \
		echo "  IMPORTANT: Open .env and set your API keys before running."; \
		echo ""; \
	else \
		echo "  .env already exists — skipping."; \
	fi
	@echo ""
	@echo "Setup complete. Run 'make dev' to start the app."

##@ Development

dev: ## Start Redis, RQ worker, Flask backend, and Vite frontend
	@bash start.sh

worker: ## Start RQ worker only (queue: pravaah)
	@echo "==> Starting RQ worker for queue: pravaah..."
	@if [ ! -d $(VENV) ]; then \
		echo "ERROR: venv not found. Run 'make setup' first."; \
		exit 1; \
	fi
	PYTHONPATH=. $(VENV_PYTHON) -m rq worker pravaah

##@ Testing

test: ## Run all pytest tests (backend API + pipeline + socket)
	@echo "==> Running all tests..."
	@if [ ! -d $(VENV) ]; then \
		echo "ERROR: venv not found. Run 'make setup' first."; \
		exit 1; \
	fi
	$(VENV_PYTHON) -m pytest backend/tests/ tests/ -v --tb=short 2>&1 || true

test-pipeline: ## Run pipeline-specific tests only
	@echo "==> Running pipeline tests..."
	@if [ ! -d $(VENV) ]; then \
		echo "ERROR: venv not found. Run 'make setup' first."; \
		exit 1; \
	fi
	$(VENV_PYTHON) -m pytest tests/test_pipeline.py -v --tb=short

##@ Code Quality

lint: ## Run flake8 on backend + pipeline Python code (max line length: 120)
	@echo "==> Linting Python code..."
	@if [ ! -d $(VENV) ]; then \
		echo "ERROR: venv not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@$(VENV_PIP) show flake8 > /dev/null 2>&1 || $(VENV_PIP) install flake8 -q
	$(VENV)/bin/flake8 backend/ pipeline/ --max-line-length=120 --extend-ignore=E203,W503

##@ Admin

create-admin: ## Create the first admin user (interactive)
	@echo "==> Creating admin user..."
	@if [ ! -d $(VENV) ]; then \
		echo "ERROR: venv not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@if [ ! -f .env ]; then \
		echo "ERROR: .env not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo ""
	@echo "  To create an admin user, run the following command:"
	@echo ""
	@echo "    source .env && PYTHONPATH=. $(VENV_PYTHON) -c \\"
	@echo "      \"from backend.database import create_user; from backend.auth import hash_password; import uuid; \\"
	@echo "       uid = create_user(username='admin', password_hash=hash_password('changeme'), role='admin', api_key=str(uuid.uuid4())); \\"
	@echo "       print(f'Admin user created with id={uid}. Change the password immediately.')\""
	@echo ""
	@echo "  Then update the password via POST /api/auth/login and the /api/auth/users endpoint."

##@ Cleanup

clean: ## Remove venv, node_modules, *.pyc, pravaah.db, chroma_store/, redis.log, *.log
	@echo "==> Removing Python virtual environment..."
	rm -rf $(VENV)
	@echo "==> Removing frontend node_modules and dist..."
	rm -rf frontend/node_modules frontend/dist
	@echo "==> Removing Python cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.pyo" -delete 2>/dev/null || true
	@echo "==> Removing SQLite database..."
	rm -f pravaah.db
	@echo "==> Removing ChromaDB vector store..."
	rm -rf chroma_store/
	@echo "==> Removing uploaded files..."
	rm -rf uploads/*
	@echo "==> Removing log files..."
	rm -f flask.log vite.log rq-worker.log redis.log
	@echo "Clean complete."
