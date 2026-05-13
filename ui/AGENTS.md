# ui/ — AGENTS.md

## Architecture
- `main_window.py`: MainWindow (QMainWindow). Toolbar, sidebar (self.sidebar_tabs), chat area.
- `dialogs.py`: ProvidersDialog, StatsDialog, McpDialog.

## Key patterns
- QTextBrowser for chat output — all content is inline HTML
- Dark theme colors: bg `#252526`, accent `#569CD6`, user text `#4CAF50`, error `#F44336`
- Sidebar is 250px, chat area 850px (minimum sizes from style.qss)
- Enter to send, Shift+Enter for newline
- Worker signals connected in `__init__` — never touch UI from worker thread
- `self.sidebar_tabs` is the tab widget (NOT `self.tab_widget`)
- Model/agent dropdowns populate from `OpenCodeService.get_models()` and `get_agents()`

## Unwired worker params (exist in worker.signals but no UI)
- `plan_mode` → needs toolbar checkbox
- `file=` → needs attach button + QFileDialog
- `slash_command` → needs `/` key popup palette
- `fork` → needs button in sessions tab
- `title` → needs QInputDialog on new session

## What NOT to do
- Never use `QDir.rootPath()` as file model root — use `os.getcwd()`
- Never call `process.terminate()` alone — use `taskkill /F /T /PID`
- Never split memory display text on `:` to extract keys — use `Qt.UserRole`
- Never rename `self.sidebar_tabs` — it's the tab widget throughout the codebase
