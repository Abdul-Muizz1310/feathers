.PHONY: run test lint format typecheck build clean

run:
	uv run feathers

test:
	uv run pytest

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
