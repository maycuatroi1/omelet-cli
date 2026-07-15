.PHONY: install test lint format seams

install:
	python -m pip install -e ".[dev]"

test:
	pytest -q

lint:
	flake8 omelet && mypy omelet

format:
	black omelet && isort omelet

seams:
	python ../blog-harness/scripts/verify_all.py
