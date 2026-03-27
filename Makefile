.PHONY: dev-api dev-worker test test-integration lint format type-check \
        migrate docker-up docker-down clean flower

dev-api:
	uv run uvicorn src.api.main:app --reload --port 8000

dev-worker:
	uv run celery -A src.tasks.celery_app worker --concurrency=2 --loglevel=info

test:
	uv run pytest tests/unit -v --cov=src --cov-report=term-missing

test-integration:
	uv run pytest tests/ -m integration -v

test-e2e:
	uv run pytest tests/e2e -v

lint:
	uv run ruff check src tests

format:
	uv run ruff format src tests

type-check:
	uv run mypy src

migrate:
	uv run alembic upgrade head

docker-up:
	docker compose -f docker/docker-compose.yml up -d --build

docker-down:
	docker compose -f docker/docker-compose.yml down -v

flower:
	uv run celery -A src.tasks.celery_app flower --port=5555

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name .mypy_cache  -exec rm -rf {} + 2>/dev/null; \
	rm -rf .coverage htmlcov/