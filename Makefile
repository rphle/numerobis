PYTHON := python3
PIP := $(PYTHON) -m pip
NPM := npm

.PHONY: install build test docs docs-serve clean help

install:
	@echo "Installing Numerobis from source..."
	pip install -e .

build:
	@echo "Building Numerobis..."
	./scripts/build.sh

test:
	@echo "Running tests..."
	python3 run.py $(filter-out $@,$(MAKECMDGOALS))

help: # Show this help
	@grep -E '^[a-zA-Z_-]+:.*?#' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?# "}; {printf "  make %-12s %s\n", $$1, $$2}'

%:
	@:
