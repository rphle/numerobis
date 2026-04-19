#!/bin/bash
set -euo pipefail

PYTHON_CMD="${NBIS_PYTHON:-python3}"

$PYTHON_CMD -m pip install -e .

./scripts/gc.sh
$PYTHON_CMD runtime/build_lib.py

$PYTHON_CMD -m pip install -e .

$PYTHON_CMD -m pip wheel . -w wheels

echo "Build complete. Wheel(s) are in wheels/"
