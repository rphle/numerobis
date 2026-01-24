#!/bin/bash
set -euo pipefail

pip install -e .

pip wheel . -w wheels
python -m build

echo "Build complete. Wheel(s) are in wheels/"
