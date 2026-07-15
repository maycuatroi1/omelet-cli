$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Installing omelet-cli (editable, with dev deps)"
python -m pip install -e ".[dev]"

Write-Host "==> Smoke test: omelet --help"
omelet --help | Select-Object -First 6

Write-Host ""
Write-Host "Ready. Run tests with:  pytest -q   (or: make test)"
Write-Host "This package OWNS the cluster seams. After changing a command name, an MDX"
Write-Host "component (NAME= in omelet/mdx/components), or an env var, verify consumers still agree:"
Write-Host "  python ..\blog-harness\scripts\verify_all.py"
