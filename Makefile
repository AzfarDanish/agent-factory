.PHONY: install test lint clean run

# Install dependencies
install:
	pip install -r requirements.txt

# Run all tests
test:
	python -m pytest

# Run unit tests only
test-unit:
	python -m pytest -m unit

# Run integration tests
test-integration:
	python -m pytest -m integration

# Check syntax and formatting
lint:
	python -m py_compile src/contracts/*.py
	python -m py_compile tests/conftest.py

# Clean artifacts
clean:
	rm -rf .queues output .pytest_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Run the full factory
run:
	./scripts/run.sh

# Seed demo requests
demo:
	python -m src.entrypoints.cli submit --prompt "a friendly dragon" --age-group child
