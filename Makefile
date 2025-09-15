.PHONY: setup run migrate seed validate test test-cov lint format

setup:
	uv sync

run:
	uv run python app/manage.py runserver

migrate:
	uv run python app/manage.py migrate

seed:
	uv run python manage.py create_dev_data --from seeds/demo_briefs.json

validate:
	uv run --with jsonschema python scripts/validate_fixtures.py

test:
	uv run pytest app/ -v

test-cov:
	uv run pytest app/ --cov=app/campaign_generator --cov-report=term-missing --cov-report=html -v

lint:
	uv run ruff check app/

format:
	uv run ruff format app/
	
