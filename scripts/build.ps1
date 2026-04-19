$ErrorActionPreference = "Stop"

$PythonCmd = if ($env:NBIS_PYTHON) { $env:NBIS_PYTHON } else { "python" }

& $PythonCmd -m pip install -e .

./scripts/gc.ps1

& $PythonCmd runtime/build_lib.py

& $PythonCmd -m pip install -e .

& $PythonCmd -m pip wheel . -w wheels

Write-Host "Build complete. Wheel(s) are in wheels/"
