---
description: Build the package for distribution
allowed-tools: Bash, Read
---

Build the omelet-cli package:

1. Clean previous builds:
   ```bash
   rm -rf build/ dist/ *.egg-info
   ```

2. Build the package:
   ```bash
   python -m build
   ```

3. Verify the build:
   ```bash
   ls -la dist/
   ```

4. Check the package:
   ```bash
   twine check dist/*
   ```

Report the build status and output files.
