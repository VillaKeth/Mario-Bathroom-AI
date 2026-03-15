# =============================================================
#  Mario AI — Bathroom Party Bot 🍄
#  Makefile for development and deployment
# =============================================================

SHELL := /bin/bash
PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PIP := $(VENV_BIN)/pip
SERVER_HOST := 0.0.0.0
SERVER_PORT := 8765
CLIENT_SERVER_URL := ws://localhost:$(SERVER_PORT)/ws

# =============================================================
#  Default target — full application startup
# =============================================================

.PHONY: all
all: install start ## Install deps and start the full application

# =============================================================
#  Virtual Environment
# =============================================================

.PHONY: venv
venv: $(VENV)/bin/activate ## Create Python virtual environment

$(VENV)/bin/activate:
	@echo "==================================="
	@echo "  Creating virtual environment..."
	@echo "==================================="
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip
	@echo "✅ Virtual environment created at $(VENV)/"

# =============================================================
#  Install
# =============================================================

.PHONY: install
install: venv ## Install all dependencies into venv
	@echo "==================================="
	@echo "  Installing all dependencies..."
	@echo "==================================="
	$(VENV_PIP) install -r requirements.txt
	@echo "✅ All dependencies installed"

.PHONY: install-server
install-server: venv ## Install server dependencies only
	@echo "Installing server dependencies..."
	$(VENV_PIP) install -r server/requirements.txt
	@echo "✅ Server dependencies installed"

.PHONY: install-client
install-client: venv ## Install client dependencies only
	@echo "Installing client dependencies..."
	$(VENV_PIP) install -r client/requirements.txt
	@echo "✅ Client dependencies installed"

# =============================================================
#  Start — Full Application (Server + Client)
# =============================================================

.PHONY: start
start: install ## Start server (background) + client (foreground)
	@echo "==================================="
	@echo "  Mario AI — Starting Full App"
	@echo "==================================="
	@echo "Starting server in background..."
	@cd server && ../$(VENV_PYTHON) main.py &
	@echo "Waiting for server to be ready..."
	@sleep 3
	@echo "Starting client..."
	@cd client && ../$(VENV_PYTHON) main.py --server $(CLIENT_SERVER_URL)

# =============================================================
#  Individual Components
# =============================================================

.PHONY: server
server: install ## Start the server only
	@echo "==================================="
	@echo "  Mario AI Server"
	@echo "  Listening on $(SERVER_HOST):$(SERVER_PORT)"
	@echo "==================================="
	cd server && ../$(VENV_PYTHON) main.py

.PHONY: client
client: install ## Start the client only (connects to localhost)
	@echo "==================================="
	@echo "  Mario AI Client"
	@echo "  Connecting to $(CLIENT_SERVER_URL)"
	@echo "==================================="
	cd client && ../$(VENV_PYTHON) main.py --server $(CLIENT_SERVER_URL)

.PHONY: client-remote
client-remote: install ## Start client connecting to remote server (usage: make client-remote SERVER=192.168.1.100)
ifndef SERVER
	$(error SERVER is required. Usage: make client-remote SERVER=192.168.1.100)
endif
	@echo "==================================="
	@echo "  Mario AI Client"
	@echo "  Connecting to ws://$(SERVER):$(SERVER_PORT)/ws"
	@echo "==================================="
	cd client && ../$(VENV_PYTHON) main.py --server ws://$(SERVER):$(SERVER_PORT)/ws

# =============================================================
#  Ollama (LLM Backend)
# =============================================================

.PHONY: ollama-setup
ollama-setup: ## Pull the required Ollama model
	@echo "Checking Ollama..."
	@command -v ollama >/dev/null 2>&1 || { echo "❌ Ollama not found. Install from https://ollama.ai"; exit 1; }
	@echo "Pulling qwen2:1.5b model..."
	ollama pull qwen2:1.5b
	@echo "✅ Ollama model ready"

# =============================================================
#  Testing
# =============================================================

.PHONY: test
test: install ## Run integration tests
	$(VENV_PYTHON) test_integration.py

# =============================================================
#  Cleanup
# =============================================================

.PHONY: clean
clean: ## Remove virtual environment and caches
	@echo "Cleaning up..."
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleaned"

# =============================================================
#  Help
# =============================================================

.PHONY: help
help: ## Show this help message
	@echo "Mario AI — Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make                              # Install + start full app"
	@echo "  make server                       # Start server only"
	@echo "  make client                       # Start client (localhost)"
	@echo "  make client-remote SERVER=1.2.3.4 # Connect to remote server"
