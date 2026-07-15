#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Installing omelet-cli (editable, with dev deps)"
python -m pip install -e ".[dev]"

echo "==> Smoke test: omelet --help"
omelet --help | head -6

echo ""
echo "Ready. Run tests with:  pytest -q   (or: make test)"
echo "This package OWNS the cluster seams. After changing a command name, an MDX"
echo "component (NAME= in omelet/mdx/components), or an env var, verify consumers still agree:"
echo "  python ../blog-harness/scripts/verify_all.py"
