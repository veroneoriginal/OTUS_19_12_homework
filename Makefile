.PHONY: help test test-unit test-integration test-functional test-all lint

PYTHON := python3
PYTEST := pytest

help:
	@echo "Available commands:"
	@echo "  make test              - run all tests"
	@echo "  make test-unit         - run unit tests"
	@echo "  make test-integration  - run integration tests"
	@echo "  make test-functional   - run functional tests"
	@echo "  make lint              - run flake8 (if installed)"

test: test_all

test_all:
	$(PYTEST) -v

test-unit:
	$(PYTEST) -v tests/unit

test-integration:
	$(PYTEST) -v tests/integration

test-functional:
	$(PYTEST) -v tests/functional
