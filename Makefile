.PHONY: install check test lint typecheck run docker-up docker-down

install:
	uv sync --group dev

check: lint typecheck test

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

run:
	uv run knowledge-agent

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
