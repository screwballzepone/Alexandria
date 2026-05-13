# Always: Code Style

## Python
- Use 4-space indentation, no tabs
- Max line length: 100 characters
- Docstrings for all public functions (Google style)
- Type hints on all function signatures
- Lazy imports inside methods when importing heavy modules

## Commit Messages
- Conventional commits: `fix:`, `feat:`, `chore:`, `docs:`
- Keep first line under 72 characters

## No-Go
- Never commit secrets, API keys, or tokens
- Never use `shell=True` without explicit justification
- Never block the main Qt thread
