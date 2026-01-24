#!/bin/bash
set -euo pipefail

pip install -e .

pip wheel . -w wheels

echo "Build complete. Wheel(s) are in wheels/"
