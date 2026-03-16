PYTHON := python3
PIP := $(PYTHON) -m pip
NPM := npm
CC := "gcc"

.PHONY: install build test docs docs-serve clean help

install:
	@echo "Installing Numerobis from source..."
	pip install -e .

build:
	@echo "Building Numerobis..."
	./scripts/build.sh

test:
	@echo "Running tests..."
	python3 run.py $(filter-out $@,$(MAKECMDGOALS)) --cc "$(CC)"

runtimelib:
	@echo "Building static runtime library..."
	python3 runtime/build_lib.py

benchmark:
	python3 tests/benchmarking/benchmark.py


graph:
	pyreverse -ASmy -o png -d assets src/numerobis


help: # Show this help
	@grep -E '^[a-zA-Z_-]+:.*?#' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?# "}; {printf "  make %-12s %s\n", $$1, $$2}'

%:
	@:
