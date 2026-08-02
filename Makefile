.PHONY: run test test-fast test-integration lint format typecheck build clean

run:
	uv run feathers

test:
	uv run pytest

# Everything that needs neither a generated-service boot nor a Docker daemon.
test-fast:
	uv run pytest -m "not slow and not integration"

# Generated service against a real Postgres (Testcontainers); skips without Docker.
test-integration:
	uv run pytest -m integration

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src/

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy src/

build:
	uv build

clean:
	rm -rf dist build *.egg-info .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
