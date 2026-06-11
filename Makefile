# OpenBioOps Makefile
# Common commands for development, testing, and deployment

PYTHON = uv run python
UV = uv
PIP = uv pip

.PHONY: help install install-dev install-snowflake lint format test test-cov api dashboard docker-build docker-up docker-down migrate clean generate-model generate-test-model mlflow-ui

# Default target
help:
	@echo "OpenBioOps Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install            Install production dependencies"
	@echo "  make install-dev        Install development dependencies"
	@echo "  make install-snowflake  Install Snowflake connector (optional)"
	@echo ""
	@echo "Quality:"
	@echo "  make lint          Run linters (ruff, mypy)"
	@echo "  make format        Format code with ruff"
	@echo "  make test          Run all tests"
	@echo "  make test-cov      Run tests with coverage report"
	@echo ""
	@echo "Development:"
	@echo "  make api              Start API server with hot reload"
	@echo "  make dashboard        Start React dashboard"
	@echo "  make migrate          Run database migrations"
	@echo ""
	@echo "ML Models:"
	@echo "  make generate-model	    Generate initial ml/model.pt from PBMC data"
	@echo "  make generate-test-model   Generate test fixture for integration tests"
	@echo "  make mlflow-ui        		Start MLflow UI for model tracking"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build  Build all Docker images"
	@echo "  make docker-up     Start all services"
	@echo "  make docker-down   Stop all services"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         Remove build artifacts and cache"

# --- Setup ---------------------------------------------------------------------

install:
	$(UV) sync

install-dev:
	$(UV) sync --all-extras
	cd services/dashboard && npm install

install-snowflake:
	$(UV) install snowflake-connector-python>=3.0.0

# --- Quality -------------------------------------------------------------------

lint:
	$(UV) run ruff check services/api/app services/api/tests lib/openbioops
	$(UV) run mypy services/api/app --ignore-missing-imports

format:
	$(UV) run ruff check --fix services/api/app services/api/tests lib/openbioops
	$(UV) run ruff format services/api/app services/api/tests lib/openbioops

test:
	$(UV) run pytest -v

test-cov:
	$(UV) run pytest --cov=app --cov=lib/openbioops --cov=ml --cov-report=term-missing --cov-report=html

test-ml:
	$(UV) run pytest -v tests/ml ml/

# --- Development ---------------------------------------------------------------

api:
	$(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dashboard:
	cd services/dashboard && npm start

migrate:
	$(UV) run --directory services/api alembic upgrade head

migrate-new:
	@read -p "Migration message: " msg; /
	$(UV) run --directory services/api alembic revision --autogenerate -m "$$msg"

# --- ML Models -----------------------------------------------------------------

generate-model:
	@echo "Generating ml/model.pt from PBMC 3k data..."
	$(PYTHON) ml/generate_model.py

generate-test-model:
	@echo "Generating test fixture ml/model.pt..."
	$(PYTHON) ml/generate_test_model.py

mlflow-ui:
	@echo "Starting MLflow UI at http://localhost:5000"
	$(UV) run mlflow ui --backend-store-uri sqlite:///artifacts/mlflow/mlflow.db --default-artifact-root ./artifacts/mlflow/artifacts

# --- Docker --------------------------------------------------------------------

docker-build:
	docker compose build 2>/dev/null || docker-compose build

docker-up:
	docker compose up -d 2>/dev/null || docker-compose up -d

docker-down:
	docker compose down 2>/dev/null || docker-compose down

docker-logs:
	docker compose logs -f 2>/dev/null || docker-compose logs -f

# --- Cleanup -------------------------------------------------------------------

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
