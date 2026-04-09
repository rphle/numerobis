#!/bin/bash
set -euo pipefail

pip install -e .

./scripts/gc.sh
python3 runtime/build_lib.py

pip install -e .

pip wheel . -w wheels

echo "Build complete. Wheel(s) are in wheels/"
