# /lint command
# Invoke: /lint (or /lint <path>)

Run ruff linter on the codebase (or specified path):

```bash
ruff check .
```

If errors found, report them. If `--fix` is added to the command:
```bash
ruff check --fix .
```

Then report what was fixed.
