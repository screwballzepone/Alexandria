# Glob: ui/**/*.py — PySide6 GUI Rules

## Threading
- Never touch UI widgets from the worker thread
- Always use signals/slots for cross-thread communication
- Heavy imports inside methods (e.g., `markdown`)

## Styling
- Dark theme: background #252526, accent #569CD6, user text #4CAF50, error #F44336
- Chat output formatted as inline HTML appended to QTextBrowser
- Stylesheet in assets/style.qss, VS Code-inspired

## Widget Patterns
- Sidebar tab widget is `self.sidebar_tabs` (NOT `self.tab_widget`)
- File model root is `os.getcwd()` (NOT `QDir.rootPath()`)
- Memory list items store key in `Qt.UserRole` (values can contain colons)

## Existing worker params (unwired)
- `send_input(plan_mode=True)` — Plan/Act toggle
- `send_input(file=path)` — File attachment
- `send_input(slash_command=True)` — Slash commands
- `send_input(fork=True)` — Session fork
- `send_input(title=...)` — Session title
