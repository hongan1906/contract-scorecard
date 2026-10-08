.PHONY: install test all
install:
	pip install -e ".[dev]"
test:
	pytest -q
all:
	python -m contractscore all
