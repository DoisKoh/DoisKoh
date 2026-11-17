.PHONY: lint typecheck format-check test check refresh

lint:
	uv run --locked ruff check scripts tests
	actionlint

typecheck:
	uv run --locked mypy scripts tests

format-check:
	uv run --locked ruff format --check scripts tests

test:
	uv run --locked python -m unittest discover -s tests -v

check: lint typecheck format-check test

refresh:
	python3 scripts/refresh_chart.py
