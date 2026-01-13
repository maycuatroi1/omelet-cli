---
description: Run all linting and formatting checks
allowed-tools: Bash, Read, Edit
---

Run code quality checks on the omelet package:

1. **Black** (formatting):
   ```bash
   black --check omelet/
   ```

2. **Flake8** (linting):
   ```bash
   flake8 omelet/
   ```

3. **MyPy** (type checking):
   ```bash
   mypy omelet/
   ```

4. **isort** (import sorting):
   ```bash
   isort --check-only omelet/
   ```

Report any issues found. If `$ARGUMENTS` contains "fix", automatically fix issues:
- `black omelet/`
- `isort omelet/`
