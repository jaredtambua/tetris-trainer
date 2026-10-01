.PHONY: check format lint test typecheck

check: lint typecheck test

format:
	ruff format .

lint:
	ruff format --check .
	ruff check .

typecheck:
	mypy src tests

test:
	pytest
