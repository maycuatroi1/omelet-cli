---
description: Run pytest tests for the project
allowed-tools: Bash, Read
argument-hint: [test-pattern]
---

Run tests for this project.

If arguments are provided, use them as the test pattern:
```
pytest $ARGUMENTS -v
```

If no arguments, run all tests:
```
pytest tests/ -v
```

After running:
1. Report the results (passed/failed/skipped)
2. If any tests fail, analyze the failures and suggest fixes
