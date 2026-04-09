PYTHON := python3
PIP := $(PYTHON) -m pip

.PHONY: install build test runtimelib benchmark graph help

install:
	@echo "Installing Numerobis from source..."
	$(PIP) install -e .

build:
	@echo "Building Numerobis..."
	./scripts/build.sh

test:
	@echo "Running tests..."
	$(PYTHON) run.py $(filter-out $@,$(MAKECMDGOALS))

runtimelib:
	@echo "Building static runtime library..."
	$(PYTHON) runtime/build_lib.py

benchmark:
	$(PYTHON) tests/benchmarking/benchmark.py

graph:
	pyreverse -ASmy -o png -d assets src/numerobis

highlight:
	cd highlighting/numerobis-vscode && npx @vscode/vsce package
	code --install-extension highlighting/numerobis-vscode/numerobis-0.1.0.vsix

clean:
	echo "Removing .o, .a, and __pycache__ files..."
	find . -type f -name "*.o" -delete
	find . -type f -name "*.a" -delete
	find . -type d -name "__pycache__" -exec rm -r {} +

update:
	git pull
	make runtimelib

report: # SCC report
	scc --exclude-dir runtime/numerobis/libs --sort code --no-duplicates

help: # Show this help
	@grep -E '^[a-zA-Z_-]+:.*?#' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?# "}; {printf "  make %-12s %s\n", $$1, $$2}'

%:
	@:
