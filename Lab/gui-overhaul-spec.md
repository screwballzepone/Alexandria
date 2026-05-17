# GUI Overhaul Specification — OpenCode Desktop

**Date**: 2026-05-17  
**Author**: @architect  
**Status**: Specification (pre-implementation)  
**Builds on**: `Lab/qol-needs.md` (UX audit), `Lab/engine-needs.md` (engine audit), `ui/main_window.py` (current codebase)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Design Principles](#2-design-principles)
3. [Layout Architecture](#3-layout-architecture)
4. [Widget Tree](#4-widget-tree)
5. [Sidebar Redesign](#5-sidebar-redesign)
6. [Chat Experience](#6-chat-experience)
7. [Toolbar & Menu Redesign](#7-toolbar--menu-redesign)
8. [Bottom Status Panel](#8-bottom-status-panel)
9. [New Features](#9-new-features)
10. [Theme System](#10-theme-system)
11. [Worker/Streaming Protocol](#11-workerstreaming-protocol)
12. [File Inventory & Change Plan](#12-file-inventory--change-plan)
13. [Phase Plan & Effort Estimates](#13-phase-plan--effort-estimates)
14. [Risks & Mitigations](#14-risks--mitigations)
15. [Wireframe Descriptions](#15-wireframe-descriptions)

---

## 1. Problem Statement

The current GUI (`ui/main_window.py`, 1366 lines) is a functional but unpolished developer debug panel. The pipeline is 100% complete (10/10 phases, 22 agents, entity store, cortex bridge, self-improvement loop) but the GUI has not kept pace. Key problems identified across two audits (`Lab/qol-needs.md`, `Lab/engine-needs.md`):

| # | Problem | Severity | Source |
|---|---------|----------|--------|
| 1 | Toolbar has 11+ elements with no visual hierarchy | HIGH | qol-needs.md H1 |
| 2 | 64% of slash commands are invisible to users | HIGH | qol-needs.md H2 |
| 3 | 7 sidebar tabs overwhelm new users | MEDIUM | qol-needs.md H4 |
| 4 | No streaming feedback during agent execution | MEDIUM | qol-needs.md H5 |
| 5 | Agent execution is a black box (no progress/ETA) | MEDIUM | qol-needs.md Finding 5 |
| 6 | Session loading clears chat without confirmation | MEDIUM | qol-needs.md H3 |
| 7 | Config warnings block startup with no dismissal | MEDIUM | qol-needs.md H6 |
| 8 | Errors are red text in chat wall (no structure) | MEDIUM | qol-needs.md Finding 6 |
| 9 | No onboarding for new users | MEDIUM | qol-needs.md Finding 4 |
| 10 | Chat display is a wall of text (no hierarchy) | LOW | qol-needs.md Finding 8 |
| 11 | No dark/light theme toggle | LOW | qol-needs.md §1.7 |
| 12 | No chat search | LOW | qol-needs.md §3.7 |
| 13 | No keyboard shortcuts | LOW | qol-needs.md §3.7 |
| 14 | Colors hardcoded throughout (not themable) | LOW | qol-needs.md §1.7 |
| 15 | Window layout is rigid (non-resizable panels) | LOW | qol-needs.md §1.1 |
| 16 | Input area is visually flat, attach button oversized | LOW | qol-needs.md §1.1 |

**This specification fixes all 16 problems** through a phased approach that can be built incrementally without breaking the current GUI.

---

## 2. Design Principles

1. **Progressive enhancement** — every phase works standalone. The GUI is usable after each phase.
2. **No worker changes required** — all streaming/state management lives in the MainWindow signal handlers. The `core/worker.py` signal contract is stable.
3. **Windows-first, dark-default** — all new components match the existing dark-theme aesthetic. Light theme is additive.
4. **Extract, don't monolith** — split `main_window.py` (1366 lines) into focused modules under `ui/`. But keep MainWindow as the orchestrator that wires them together.
5. **Keyboard-optional, mouse-friendly** — all features work with both. No single-mode dependencies.
6. **Never regress existing features** — every existing action (undo, redo, fork, attach, mission, stats, providers, sessions, memory, plots, repos) must still work after each phase.

---

## 3. Layout Architecture

### 3.1 Current Layout

```
[Toolbar — 11 elements, no hierarchy]
[Sidebar (250px, fixed) | Chat (850px, fixed)]   ← QSplitter with fixed initial sizes
[Status bar — thin text only]
```

**Problems**: No menu bar, no bottom panel, panels not collapsible, sizes are rigid.

### 3.2 Proposed Layout

```
┌─────────────────────────────────────────────────────────────┐
│ [Menu Bar: File | Edit | View | Help]                       │  ← NEW (~24px)
├─────────────────────────────────────────────────────────────┤
│ [Compact Toolbar — 5 primary elements + overflow ⋮ menu]    │  ← Trimmed (~36px)
├────────────────┬────────────────────────────────┬────────────┤
│                │                                │            │
│ Sidebar        │   Chat Area                    │ Right Panel│ ← NEW
│ (270px,        │   (flex, min 500px)            │ (0–220px,  │
│  collapsible)  │                                │  hidden)   │
│                │  ┌──────────────────────────┐  │            │
│ 4 tabs:        │  │ Chat Search Bar (Ctrl+F) │  │ Activity   │
│ ┌──────────┐   │  ├──────────────────────────┤  │ feed:      │
│ │Sessions  │   │  │ Messages                  │  │ - Tool     │
│ │Files     │   │  │ (QListWidget with         │  │   execs    │
│ │Workspace │   │  │  custom MessageWidgets)   │  │ - Errors   │
│ │Settings  │   │  │                           │  │ - Status   │
│ └──────────┘   │  │                           │  │   changes  │
│                │  │                           │  │            │
│                │  ├──────────────────────────┤  │            │
│                │  │ Input Bar                 │  │            │
│                │  │ [📎] [Model▼] [Agent▼]    │  │            │
│                │  │ [Type message…        ▶ ] │  │            │
│                │  └──────────────────────────┘  │            │
├────────────────┴────────────────────────────────┴────────────┤
│ [Bottom Status Panel — collapsible, ~150px]                   │  ← NEW
│ [🟢 Ready] [Elapsed: 12s] [Errors: 0] [Tokens: 1.2K] [⚙️]  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Activity log: tool execs, errors, mission events        │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Splitter Hierarchy

```
MainWindow.centralWidget
  └── QVBoxLayout
        ├── QSplitter (horizontal) [sidebar | chat_panel]
        │     ├── SidebarWidget (tab widget, min 200px, max 400px)
        │     └── QWidget (chat_panel)
        │           └── QVBoxLayout
        │                 ├── ChatSearchBar (hidden by default)
        │                 ├── QSplitter (vertical) [messages | bottom_panel]
        │                 │     ├── ChatDisplay (QListWidget, stretch=1)
        │                 │     └── StatusPanel (hidden by default, min 80px)
        │                 └── InputBar (fixed height, auto-grow input)
        └── QStatusBar (thin, persistent: model/agent/status text)
```

### 3.4 Resizing Behavior

| Panel | Default | Min | Max | Collapsible | Shortcut |
|-------|---------|-----|-----|-------------|----------|
| Sidebar | 270px | 200px | 400px | Yes (Ctrl+B) | Ctrl+B |
| Right Panel | Hidden | 180px | 400px | Yes (auto) | — |
| Bottom Panel | Hidden | 80px | 300px | Yes (Ctrl+J) | Ctrl+J |
| Chat Area | Flex | 500px | Flex | — | — |
| Input Bar | Auto-height | 36px | 200px | — | — |

### 3.5 Window Size Presets

- **Default**: 1200×800 (sidebar 270px, chat 930px)
- **Compact** (<900px wide): sidebar auto-collapses to icon-only
- **Sessions**: >1400px wide → right panel auto-shows

---

## 4. Widget Tree

### 4.1 Complete Widget Hierarchy

```
MainWindow (QMainWindow)
│
├── QMenuBar
│   ├── File
│   │   ├── New Session (Ctrl+N)
│   │   ├── Load Session...
│   │   ├── Export Chat as Markdown...
│   │   └── Quit (Ctrl+Q)
│   ├── Edit
│   │   ├── Undo Last Changes (Ctrl+Z)
│   │   ├── Redo (Ctrl+Y)
│   │   ├── Clear Chat
│   │   └── Copy Conversation
│   ├── View
│   │   ├── Toggle Sidebar (Ctrl+B)
│   │   ├── Toggle Bottom Panel (Ctrl+J)
│   │   ├── Theme
│   │   │   ├── Dark
│   │   │   ├── Light
│   │   │   └── System
│   │   └── Zoom
│   │       ├── Zoom In (Ctrl++)
│   │       ├── Zoom Out (Ctrl+-)
│   │       └── Reset Zoom (Ctrl+0)
│   └── Help
│       ├── Keyboard Shortcuts (Ctrl+/)
│       ├── About OpenCode
│       └── Check for Updates
│
├── Toolbar (QToolBar, non-movable)
│   ├── ModelButton (QPushButton → QMenu, grouped by provider)
│   ├── AgentCombo (QComboBox, populated from get_agents_from_files())
│   ├── PlanModeCheck (QCheckBox, "Plan")
│   ├── MissionButton (QPushButton, "🚀 Mission")
│   ├── spacer
│   └── MoreButton (QPushButton "⋮" → QMenu)
│       ├── Low Token Mode (QAction, checkable)
│       ├── separator
│       ├── Providers Dialog...
│       ├── Agent Viewer...
│       ├── Stats...
│       ├── MCP Servers...
│       ├── separator
│       ├── New Session
│       ├── Refresh Sessions
│       └── separator
│           └── Keyboard Shortcuts
│
├── Central Widget Layout (QVBoxLayout)
│   ├── QSplitter (horizontal) [SIDEBAR | CHAT]
│   │   │
│   │   ├── SidebarWidget (QWidget)
│   │   │   └── QTabWidget (4 tabs with icons)
│   │   │       ├── Tab 0: "🔄 Sessions"
│   │   │       │   ├── SessionSearch (QLineEdit, placeholder "Search sessions...")
│   │   │       │   ├── SessionList (QListWidget, custom items with title + timestamp)
│   │   │       │   └── SessionActions (QHBoxLayout)
│   │   │       │       ├── ForkButton
│   │   │       │       └── DeleteButton
│   │   │       │
│   │   │       ├── Tab 1: "📁 Files"
│   │   │       │   ├── RepoMapToggle (QCheckBox "Use repo map")
│   │   │       │   └── FileTree (QTreeView + QFileSystemModel)
│   │   │       │
│   │   │       ├── Tab 2: "🧰 Workspace"
│   │   │       │   └── WorkspaceStack (QVBoxLayout of collapsible QGroupBoxes)
│   │   │       │       ├── Memory (search + list + add/delete)
│   │   │       │       ├── Plots (file list + preview)
│   │   │       │       └── Repo Map (QTreeView, hidden when Plots expanded)
│   │   │       │
│   │   │       └── Tab 3: "⚙️ Settings"
│   │   │           ├── ThemeSelector (QComboBox: Dark / Light / System)
│   │   │           ├── FontSizeSlider (QSlider + QLabel "14px")
│   │   │           ├── ShowTimestamps (QCheckBox)
│   │   │           ├── GroupBySession (QCheckBox)
│   │   │           ├── separator
│   │   │           └── KeyboardShortcutsButton → ShortcutsDialog
│   │   │
│   │   └── QWidget (CHAT AREA)
│   │       └── QVBoxLayout (0 margin, spacing=0)
│   │           │
│   │           ├── ChatSearchBar (QWidget, hidden by default, 36px)
│   │           │   ├── QLabel "🔍"
│   │           │   ├── QLineEdit (placeholder "Find in chat...")
│   │           │   ├── QLabel "0/0"
│   │           │   ├── QPushButton "▲" (prev match)
│   │           │   ├── QPushButton "▼" (next match)
│   │           │   └── QPushButton "✕" (close)
│   │           │
│   │           ├── QSplitter (vertical) [messages | status_panel]
│   │           │   │
│   │           │   ├── ChatDisplay (QListWidget)
│   │           │   │   • Custom MessageWidget items
│   │           │   │   • Scroll-to-bottom on new message
│   │           │   │   • Load-more on scroll-to-top
│   │           │   │
│   │           │   └── StatusPanel (QWidget, hidden by default, 120px)
│   │           │       ├── StatusTabs (QTabWidget)
│   │           │       │   ├── "Activity" (QListWidget: recent events)
│   │           │       │   ├── "Errors" (QListWidget: structured errors with retry/copy)
│   │           │       │   └── "Mission" (mini mission view)
│   │           │       └── StatusBar (QHBoxLayout)
│   │           │           ├── ConnectionBadge (QLabel "🟢 Ready" / "🟡 Running" / "🔴 Error")
│   │           │           ├── ElapsedTimer (QLabel "12.3s")
│   │           │           ├── ErrorCount (QLabel "Errors: 0", clickable → Errors tab)
│   │           │           ├── TokenCount (QLabel "Tokens: 1.2K")
│   │           │           └── SettingsButton (QPushButton "⚙️")
│   │           │
│   │           └── InputBar (QWidget, fixed-height bottom)
│   │               ├── AttachButton (QPushButton, "📎", 36×36)
│   │               ├── ModelBadge (QLabel, clickable → model menu)
│   │               ├── AgentBadge (QLabel, clickable → agent menu)
│   │               ├── InputField (QTextEdit, auto-grow 1-8 lines, min-height 36px)
│   │               ├── SendButton (QPushButton, "▶", 70×36)
│   │               └── MoreButton (QPushButton "⋮" → menu: Clear, Format Help)
│   │
│   └── QStatusBar (thin persistent bar)
│       ├── QLabel (context-sensitive status text)
│       └── QProgressBar (hidden, shown during file operations)
```

---

## 5. Sidebar Redesign

### 5.1 Current (7 tabs)
| Index | Tab | Content | Lines | Verdict |
|-------|-----|---------|-------|---------|
| 0 | Files | QTreeView + QFileSystemModel | 144-153 | **KEEP** |
| 1 | Sessions | QListWidget + Fork button | 155-168 | **KEEP** |
| 2 | Memory | Search + List + Buttons | 170-202 | Merge into Workspace |
| 3 | Plots | PNG list + preview + external | 204-248 | Merge into Workspace |
| 4 | Mission | Status table + error budget | 250-254 | **Move to StatusPanel + Right Panel** |
| 5 | Repo Map | File tree with .gitignore | 256-258 | Merge into Workspace |
| — | (unnamed diagnostics) | Placeholder | 1020-1023 | **REMOVE** |

### 5.2 Proposed (4 tabs)

| Index | Tab | Icon | Content | Merged From |
|-------|-----|------|---------|-------------|
| 0 | Sessions | 🔄 | Session search, list, fork/delete buttons | Current Sessions |
| 1 | Files | 📁 | QTreeView + repo map toggle | Current Files |
| 2 | Workspace | 🧰 | Collapsible sections: Memory, Plots, Repo Map | Memory + Plots + Repo Map |
| 3 | Settings | ⚙️ | Theme, font size, timestamps toggle, keyboard shortcuts | **NEW** |

#### 5.2.1 Sessions Tab (Tab 0)

```
┌──────────────────────────┐
│ 🔍 Search sessions...   │  ← QLineEdit, filters list in real-time
├──────────────────────────┤
│ ┌──────────────────────┐ │
│ │ My feature work      │ │  ← QListWidget, custom items
│ │   - 5 min ago        │ │     Each item = 3 lines
│ │                      │ │     Title (bold) + timestamp (gray)
│ │ API integration     │ │     + model/agent badges (small)
│ │   - 2 hours ago     │ │
│ │                      │ │
│ │ Bug fix #42          │ │
│ │   - yesterday        │ │
│ └──────────────────────┘ │
│ [Fork]         [Delete]  │  ← QHBoxLayout
└──────────────────────────┘
```

**Functional changes:**
- Add session search filter (current: none, except in Memory tab)
- Add delete session action (current: none)
- Custom 3-line items with model/agent badges (current: 1-line text)
- Fork button disabled when no session selected (current: just does nothing)

#### 5.2.2 Files Tab (Tab 1)

Minimal changes from current:
- Add "Use repo map" checkbox above the tree (toggles between QFileSystemModel and repomap QStandardItemModel)
- Keep .gitignore filtering from current Repo Map logic but make it opt-in

#### 5.2.3 Workspace Tab (Tab 2)

```
┌──────────────────────────┐
│ ⬇ Memory (12 entries)  │  ← QGroupBox, collapsible
│ │ 🔍 Search memory...  │     Search box + list + buttons
│ │ ┌──────────────────┐ │     Same as current Memory tab
│ │ │ key: value       │ │     but collapsed by default
│ │ │   - 5 min ago    │ │
│ │ └──────────────────┘ │
│ │ [Add] [Delete]       │
│ ⬇ Plots (3 files)      │  ← QGroupBox, collapsible
│ │ ┌──────────────────┐ │     Same as current Plots tab
│ │ │ plot_01.png      │ │     but collapsed by default
│ │ │ plot_02.png      │ │
│ │ └──────────────────┘ │
│ │ [Preview area]       │
│ ⬆ Project Map          │  ← QGroupBox, collapsible
│   ┌──────────────────┐ │     Repo map tree from current
│   │ src/             │ │     collapsed by default
│   │   main.py        │ │
│   │   utils/         │ │
│   └──────────────────┘ │
└──────────────────────────┘
```

**Key design**: `QGroupBox` with `setCollapsible(True)` (via stylesheet or custom event filter — Qt doesn't natively support collapsible group boxes, so we implement a toggle by replacing the group box with a clickable header + a stacked widget underneath).

Implementation note: use `QGroupBox` with a custom title bar click handler that toggles visibility of the content area via `setVisible(not current_visible)`.

#### 5.2.4 Settings Tab (Tab 3)

```
┌──────────────────────────┐
│ Appearance               │
│ ─────────────────────── │
│ Theme: [Dark ▼]         │  ← QComboBox
│ Font size: [====●===] 14│  ← QSlider + label
│                          │
│ Chat                     │
│ ─────────────────────── │
│ ☑ Show timestamps       │  ← QCheckBox
│ ☐ Group by session      │  ← QCheckBox
│ ☑ Collapse thinking     │  ← QCheckBox (default: collapsed)
│                          │
│ Shortcuts                │
│ ─────────────────────── │
│ [View Keyboard Shortcuts]│  → opens ShortcutsDialog
│                          │
│ About                    │
│ ─────────────────────── │
│ OpenCode GUI v0.2       │
│ Engine: opencode.cmd...  │
└──────────────────────────┘
```

### 5.3 Collapse Behavior

- Sidebar collapse button in the toolbar: `Ctrl+B`
- When collapsed: sidebar reduces to 32px wide, shows only tab icons vertically
- Hovering over an icon expands that tab temporarily (flyout)
- Clicking an icon toggles the full sidebar back

Implementation: Use a QSplitter with min/max sizes. On collapse: `splitter.setSizes([32, total-32])`. On expand: restore previous width.

---

## 6. Chat Experience

### 6.1 Message Model (NEW: MessageWidget)

Replace the single `QTextBrowser` with a `QListWidget` where each message is a custom widget.

```python
class MessageWidget(QWidget):
    """A single chat message rendered as a self-contained widget."""

    def __init__(self, role: str, text: str, timestamp: datetime,
                 agent_name: str = "", model_name: str = "",
                 thinking_text: str = "", tool_calls: list = None):
        """
        role: "user" or "assistant"
        text: rendered markdown content
        agent_name: for assistant messages ("orchestrator", "coder", etc.)
        model_name: for assistant messages ("deepseek-v4-flash", etc.)
        thinking_text: collapsible thinking/reasoning block
        tool_calls: list of (tool_name, status, duration) tuples
        """
```

**Widget layout:**

```
User message:
┌────────────────────────────────────────────────┐
│ [You]  [12:34:56]                              │  ← header: avatar+name + timestamp (right)
│                                               │
│ Type your instruction here...                  │  ← body: rich text (QLabel)
└────────────────────────────────────────────────┘

Assistant message:
┌────────────────────────────────────────────────┐
│ [🤖 OpenCode]  via orchestrator · deepseek...  │  ← header: icon + agent + model
│  [12:34:57]                                    │  ← timestamp right-aligned
│                                               │
│ Here's what I found...                         │  ← body: rendered markdown (QLabel)
│                                               │
│ ── Thinking ── [▼]                             │  ← collapsible section (hidden by default)
│ │ I need to check the file structure first...│ │  ← thinking content (light italic)
│ └────────────────────────────────────────────┘ │
│                                               │
│ ⚙️ Tools:                                      │  ← tool call list
│   [✅] read("main.py") — 0.3s                 │  ← completed tool
│   [🔄] grep("function") — running...          │  ← in-progress tool
│   [❌] write("file.py") — failed: perms       │  ← failed tool
└────────────────────────────────────────────────┘
```

### 6.2 Streaming Flow (no worker changes)

The worker emits the same signals. MainWindow manages an `_active_message` state:

```python
class MainWindow:
    def __init__(self):
        self._active_message: Optional[QListWidgetItem] = None
        self._active_message_widget: Optional[MessageWidget] = None
        self._is_streaming = False

    def send_message(self):
        # ... existing logic ...
        # Switch chat display from QTextBrowser to QListWidget
        self._add_user_message(text)
        self._start_assistant_message()  # creates empty active message

    def _start_assistant_message(self):
        """Create a placeholder assistant message for streaming."""
        item = QListWidgetItem(self.chat_display)
        widget = MessageWidget(role="assistant", text="",
                               timestamp=datetime.now(),
                               agent_name=self._selected_agent,
                               model_name=self._selected_model)
        item.setSizeHint(widget.sizeHint())
        self.chat_display.addItem(item)
        self.chat_display.setItemWidget(item, widget)
        self._active_message = item
        self._active_message_widget = widget
        self._is_streaming = True
        self._add_running_indicator()  # animated dots

    @Slot(str)
    def handle_text(self, text):
        if self._is_streaming and self._active_message_widget:
            # Append to active message body
            self._active_message_widget.append_text(text)
            # Invalidate size hint
            self._active_message.setSizeHint(
                self._active_message_widget.sizeHint()
            )
        else:
            # Fallback: create new message
            self._add_assistant_message(text)

    @Slot(str)
    def handle_thinking(self, text):
        if self._is_streaming and self._active_message_widget:
            self._active_message_widget.set_thinking(text)

    @Slot(str, str)
    def handle_tool_start(self, tool_name, details):
        if self._is_streaming and self._active_message_widget:
            self._active_message_widget.add_tool_call(tool_name, "running")

    @Slot(str)
    def handle_tool_finish(self, tool_name):
        if self._is_streaming and self._active_message_widget:
            self._active_message_widget.set_tool_status(tool_name, "completed")

    def _finalize_message(self):
        """Called when worker queue is empty."""
        if self._active_message_widget:
            self._active_message_widget.finalize()
            self._active_message.setSizeHint(
                self._active_message_widget.sizeHint()
            )
        self._active_message = None
        self._active_message_widget = None
        self._is_streaming = False
```

### 6.3 Thinking Display

Current: `<details open>` block (always open by default).

Change: `<details>` block that is **closed by default** (collapsed). The header shows:
- `💭 Thought` with a token/char count
- Click to expand
- Tool calls and final answer are visible without expanding

This matches how ChatGPT, Claude, and VS Code Copilot display thinking.

### 6.4 Tool Execution Display

Current: Inline text "⚙️ Running tool: read..." / "✅ Tool read completed."

Change: Structured tool call list within the assistant message:
- Icons: 🔄 (running), ✅ (completed), ❌ (failed)
- Tool name + abbreviated input
- Duration when completed
- Click to expand full input/output

### 6.5 Error Display

**Inline** (in chat): All errors get a styled error block:
```
┌────────────────────────────────────────────────┐
│ ⚠️ Error running opencode                      │  ← icon + title
│ opencode.cmd returned exit code 1              │  ← message
│ [Copy] [Retry] [Dismiss]                       │  ← action buttons
└────────────────────────────────────────────────┘
```

**Panel** (in bottom StatusPanel "Errors" tab): Structured list of errors with:
- Timestamp
- Error type (from error-log.jsonl)
- Full message
- Copy button
- Retry button (if actionable)

### 6.6 Chat Search (Ctrl+F)

```
┌─────────────────────────────────────────────────────────┐
│ 🔍 Find: [___________________________] [▲] [▼] [2/15] ✕│
└─────────────────────────────────────────────────────────┘
```

- QLineEdit with real-time filtering
- Iterate over QListWidget items, show/hide non-matches OR highlight matches
- Match counter "N/M"
- Up/Down arrows to jump between matches
- Escape to close

### 6.7 Input Bar Redesign

Current:
```
[📎 40×70] [QTextEdit fixed 70px]                                    [Send 90×70]
```

Proposed:
```
[📎 36×36] [Model:v4-f…▼] [Agent:orch▼] [QTextEdit auto-grow 1-8 lines] [▶ 70×36] [⋮]
```

Changes:
- Attach button: 36×36 (down from 40×70 — was oversized)
- Model/Agent badges: clickable, show current selection, allow quick switch via dropdown
- Input field: auto-grows from 36px (1 line) to max 200px (8 lines), scrollbar after that
- Send button: 70×36 (down from 90×70 — was oversized)
- ⋮ button: small menu → Clear Input, Format Help, Toggle Plan Mode

**Agent selector stays as dropdown in the input bar**, not in a separate row above.
**Model selector** appears as a badge (showing short name) that opens the provider-grouped model menu on click.

---

## 7. Toolbar & Menu Redesign

### 7.1 Current Toolbar (11 elements)

```
[Model ▼] | [☐ Low Token] [☐ Plan Mode] | [Providers] [Agents] [Stats] | [New Session] [↻]
```

### 7.2 Proposed Toolbar (5 + menu)

```
[Model ▼] [Agent ▼]  [☐ Plan]  | [🚀 Mission]  | [⋮ More ▼]
```

**⋮ More** menu (secondary actions moved out of toolbar):

```
⋮ More ▼
├── ☐ Low Token Mode              ← checkable
├── ─────────
├── Providers...                  ← opens ProvidersDialog
├── Agents...                     ← opens Agent Viewer
├── Stats...                      ← opens StatsDialog
├── MCP Servers...                ← opens McpDialog
├── ─────────
├── New Session (Ctrl+N)
├── Refresh Sessions
├── ─────────
└── Keyboard Shortcuts (Ctrl+/)  ← opens ShortcutsDialog
```

### 7.3 Rationale

| Element | Current | Proposed | Reason |
|---------|---------|----------|--------|
| Model selector | Toolbar button | Toolbar button (kept) | Used every session |
| Agent selector | Combo below toolbar | Toolbar combo (moved) | More discoverable |
| Low Token Mode | Toolbar checkbox | Overflow menu | Used rarely |
| Plan Mode | Toolbar checkbox | Toolbar checkbox (kept) | Used frequently |
| Providers | Toolbar action | Overflow menu | Config, not daily use |
| Agents | Toolbar action | Overflow menu | Config, not daily use |
| Stats | Toolbar action | Overflow menu | Diagnostic, occasional |
| New Session | Toolbar action | Menu Bar > File + Overflow | Secondary action |
| Refresh | Toolbar button | Overflow menu | Secondary action |
| 🚀 Mission | Below agent combo | Toolbar (promoted) | High-value feature |

### 7.4 Menu Bar (NEW)

**File**
| Action | Shortcut | Source |
|--------|----------|--------|
| New Session | Ctrl+N | `new_session()` |
| Load Session... | — | Sidebar Sessions tab |
| Export Chat as Markdown... | — | New feature |
| Quit | Ctrl+Q | `close()` |

**Edit**
| Action | Shortcut | Source |
|--------|----------|--------|
| Undo Last Changes | Ctrl+Z | `worker.send_input("/undo")` |
| Redo | Ctrl+Y | `worker.send_input("/redo")` |
| Clear Chat | — | `chat_display.clear()` + confirm |
| Copy Conversation | — | New feature (copy all text) |

**View**
| Action | Shortcut | Source |
|--------|----------|--------|
| Toggle Sidebar | Ctrl+B | Sidebar collapse |
| Toggle Bottom Panel | Ctrl+J | Status panel toggle |
| Theme > Dark | — | Load `dark.qss` |
| Theme > Light | — | Load `light.qss` |
| Theme > System | — | Follow OS via `QPalette` |
| Zoom In | Ctrl+= | Font size +1 |
| Zoom Out | Ctrl+- | Font size -1 |
| Reset Zoom | Ctrl+0 | Font size 14px |

**Help**
| Action | Shortcut | Source |
|--------|----------|--------|
| Keyboard Shortcuts | Ctrl+/ | `ShortcutsDialog` |
| About OpenCode | — | About dialog |
| Check for Updates | — | `opencode.cmd --version` check |

---

## 8. Bottom Status Panel

### 8.1 Layout

A splitter-separated panel below the chat display, toggled with `Ctrl+J`.

```
┌─────────────────────────────────────────────────────────────────────┐
│ [Activity ▼] [Errors (3)] [Mission]                                 │  ← QTabBar
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ [12:34:56] ✅ Tool read("main.py") completed in 0.3s          │ │ │ ← Activity log
│ │ [12:34:57] 🔄 Tool grep("function") started                   │ │ │    (QListWidget)
│ │ [12:35:00] ℹ️ Agent switched to coder                         │ │ │
│ │ [12:35:02] ⚠️ Memory DB busy, retried (success)              │ │ │
│ └─────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ 🟢 Ready  |  12.3s  |  Errors: 0  |  Tokens: 1.2K  |  Session: abc123 │ ← Status bar
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 Status Bar Elements (always visible)

| Element | Example | Source |
|---------|---------|--------|
| Connection badge | 🟢 Ready / 🟡 Running / 🔴 Error | Worker state |
| Elapsed timer | 12.3s | QElapsedTimer (current) |
| Error count | Errors: 0 | Clickable → opens Errors tab |
| Token count | Tokens: 1.2K | From opencode stats |
| Session ID | Session: abc12... | worker.session_id (truncated) |
| Settings button | ⚙️ | Opens Settings tab in sidebar |

### 8.3 Activity Tab

A real-time event log (QListWidget):
- Tool starts/completions
- Agent switches
- Mission status changes
- Error events (clickable → Errors tab)
- Message sent/received

Keeps last 200 events, auto-scrolls.

### 8.4 Errors Tab

Structured error list from `error-log.jsonl`:
- Each row: icon + timestamp + error type + abbreviated message
- Click: full error in detail pane below
- Buttons: Copy, Retry (if applicable), Dismiss
- Clear all button

### 8.5 Mission Tab (mini)

Compact version of the current mission table:
- Status badge (same as current)
- Feature count: "5/8 complete"
- Error budget bar (same as current)
- Resume/Clear buttons

Full mission view stays... actually with the right panel and this bottom panel, the Mission tab in the sidebar can be fully removed. The bottom panel's Mission tab handles it.

---

## 9. New Features

### 9.1 Onboarding Welcome (P1)

**Detection**: First launch = no sessions exist OR QSettings key `first_run` flag.

**Implementation**: When no sessions exist and chat is empty, the chat display shows a welcome message (as a MessageWidget):

```
┌────────────────────────────────────────────────────────┐
│ 🎉 Welcome to OpenCode                                 │
│                                                        │
│ OpenCode is an AI development assistant with 22        │
│ specialized agents.                                    │
│                                                        │
│ Here's how to get started:                             │
│                                                        │
│ 1. Type a message below and press Enter to chat        │
│ 2. Use / for commands (undo, redo, lint, review...)   │
│ 3. Select an agent from the toolbar for specific tasks │
│ 4. Click 🚀 Mission for multi-step project work        │
│                                                        │
│ Try: "What can you do?" or "Show me an example"        │
│                                                        │
│ [✕ Dismiss]                                            │
└────────────────────────────────────────────────────────┘
```

**Suppression**: QSetting key `onboarding_dismissed=true`. Also dismisses on first message send.

### 9.2 Chat Search (P1)

See §6.6. Implementation details:
- Ctrl+F toggles search bar visibility
- Use `QListWidget.findItems()` for text matching
- Highlight matches by setting item background
- Navigation: `Ctrl+G` next match, `Ctrl+Shift+G` previous match

### 9.3 Keyboard Shortcuts Dialog (P1)

Triggered by Ctrl+/ or Help > Keyboard Shortcuts (current: implemented but buried).

```
┌────────────────────────────────────────────────────┐
│ Keyboard Shortcuts                          [✕]   │
├────────────────────────────────────────────────────┤
│ General                                            │
│  Ctrl+N     New Session                            │
│  Ctrl+Q     Quit                                   │
│  Ctrl+B     Toggle Sidebar                         │
│  Ctrl+J     Toggle Bottom Panel                    │
│  Ctrl+/     Show this dialog                       │
│                                                    │
│ Chat                                               │
│  Enter       Send message                          │
│  Shift+Enter  Newline                              │
│  Ctrl+F      Search in chat                        │
│  Ctrl+G      Next match                            │
│  Ctrl+Shift+G  Previous match                      │
│                                                    │
│ Editing                                            │
│  Ctrl+Z      Undo last changes                     │
│  Ctrl+Y      Redo                                  │
│  Ctrl+L      Clear chat (with confirm)             │
│                                                    │
│ View                                               │
│  Ctrl+=      Zoom in                               │
│  Ctrl+-      Zoom out                              │
│  Ctrl+0      Reset zoom                            │
└────────────────────────────────────────────────────┘
```

### 9.4 Export Chat (P1)

- Menu: File > Export Chat as Markdown
- Implementation: Iterate over all MessageWidgets in chat_display
- Format: `## You (12:34:56)\n\n{text}\n\n## OpenCode (12:34:57)\n\n{text}\n\n`
- Save to file via QFileDialog.getSaveFileName
- Default filename: `chat-export-{date}.md`

### 9.5 Dark/Light/System Theme (P2)

See §10.

### 9.6 Font Size Adjustment (P2)

- Settings tab slider: 10px - 24px
- Applied via QSS variable or runtime stylesheet reload
- Stored in QSettings

### 9.7 System Tray (P2)

- Minimize to tray icon
- Tray menu: Show/Hide, New Session, Quit
- Notifications on mission complete (optional)

### 9.8 Input Draft Auto-Save (P2)

- On every text change in input, save draft to QSettings or `.opencode/.input-draft.jsonl`
- On app start, restore draft if present
- On send, clear draft

---

## 10. Theme System

### 10.1 Architecture

Current: single `assets/style.qss` loaded in `main.py`.

Proposed: multiple QSS files in `assets/themes/`:

```
assets/
├── style.qss                    # Base (shared) styles — margins, spacings, layout
└── themes/
    ├── dark.qss                 # Dark theme color definitions
    ├── light.qss                # Light theme color definitions
    └── system.qss               # Uses palette-based colors (follows OS)
```

### 10.2 Theme Loading

```python
class ThemeManager:
    def __init__(self, app: QApplication):
        self.app = app
        self.current_theme = QSettings().value("theme", "dark")

    def apply_theme(self, theme_name: str):
        base = Path("assets/style.qss").read_text()
        theme_file = Path(f"assets/themes/{theme_name}.qss")
        if theme_file.exists():
            theme_css = theme_file.read_text()
        else:
            theme_css = ""
        self.app.setStyleSheet(base + "\n" + theme_css)
        QSettings().setValue("theme", theme_name)
        self.current_theme = theme_name
```

### 10.3 Color Token System

Define CSS variables (via QSS class selectors — Qt doesn't support `var()` in QSS):

```css
/* dark.qss */
QMainWindow {
    /* Theme tokens */
    qproperty-bg-primary: #1e1e1e;
    qproperty-bg-secondary: #252526;
    qproperty-bg-tertiary: #2d2d30;
    qproperty-text-primary: #d4d4d4;
    qproperty-text-secondary: #888888;
    qproperty-accent: #569CD6;
    qproperty-user-text: #4CAF50;
    qproperty-error: #F44336;
    qproperty-warning: #f0ad4e;
    qproperty-border: #333333;
}
```

Actually, Qt QSS doesn't support CSS variables. Instead, we define separate complete stylesheets and switch between them. The base `style.qss` handles layout (margins, padding, font families, border radii) and the theme files override colors.

### 10.4 Runtime Switching

- View > Theme > Dark | Light | System submenu
- Settings tab's theme combo box
- Signal: `theme_changed(str)` — components that cache colors can re-read

---

## 11. Worker/Streaming Protocol

### 11.1 Current Contract (unchanged)

The `OpenCodeWorker` signals are the contract. We do NOT modify `core/worker.py`.

| Signal | Signature | Current Handler | New Handler |
|--------|-----------|-----------------|-------------|
| `text_received` | `(str)` | `handle_text`: append block | Append to active message |
| `thinking_received` | `(str)` | `handle_thinking`: append details | Set thinking on active message |
| `tool_started` | `(str, str)` | `handle_tool_start`: append line | Add tool call to active message |
| `tool_finished` | `(str)` | `handle_tool_finish`: append line | Set tool status on active message |
| `error_received` | `(str)` | `handle_error`: append red text | Add to error panel + active message |
| `process_finished` | `(int)` | `handle_finished`: show exit code | Finalize active message |
| `queue_empty` | `()` | `_on_worker_done`: re-enable UI | Same + finalize message |

### 11.2 Active Message State

```python
# State machine for streaming
_streaming_state: Literal["idle", "streaming", "finalizing"] = "idle"
_active_item: Optional[QListWidgetItem] = None
_active_widget: Optional[MessageWidget] = None
```

Transitions:
1. `send_message()` → `_streaming_state = "streaming"`, create empty widget
2. First `text_received` → start populating widget body
3. `queue_empty` emitted → `_streaming_state = "finalizing"`, add final timestamp, stop timer
4. Next `send_message()` or after 2s auto-reset → `_streaming_state = "idle"`

### 11.3 Watchdog (No Worker Changes)

Built into MainWindow:
- When worker starts (`started` signal): start a QTimer with 60s timeout
- On every worker signal (any signal): reset the timer
- If timer fires: show "Agent appears stalled" warning, offer to cancel (call `worker.stop()`) or wait longer

This requires connection to ALL worker signals to reset the watchdog, not just text_received.

---

## 12. File Inventory & Change Plan

### 12.1 Files Modified

| File | Current LOC | Change | New LOC |
|------|-------------|--------|---------|
| `ui/main_window.py` | 1366 | Major restructure: extract sidebar, chat, status panel into modules. Keep as orchestrator/wiring. | ~800 |
| `assets/style.qss` | 120 | Expand with new component styles | ~300 |
| `ui/dialogs.py` | 225 | Refactor: add ShortcutsDialog, AboutDialog, theme picker | ~350 |

### 12.2 Files Created

| File | Est. LOC | Purpose |
|------|----------|---------|
| `ui/sidebar_widget.py` | ~400 | Refactored sidebar with 4 tabs, collapsible groups |
| `ui/chat_widget.py` | ~500 | ChatDisplay (QListWidget + MessageWidget), ChatSearchBar, InputBar |
| `ui/status_panel.py` | ~300 | Bottom status panel with Activity/Errors/Mission tabs |
| `ui/message_widget.py` | ~250 | MessageWidget — single chat message with rich rendering |
| `ui/theme_manager.py` | ~80 | Theme loading/switching logic |
| `ui/shortcuts_dialog.py` | ~80 | Keyboard shortcuts reference dialog (extend existing) |
| `ui/onboarding.py` | ~100 | First-run welcome widget |
| `assets/themes/dark.qss` | ~80 | Dark theme colors (from current style.qss, extracted) |
| `assets/themes/light.qss` | ~80 | Light theme colors |
| `assets/themes/system.qss` | ~60 | System-follows colors |

### 12.3 Total Effort Estimate

| Category | Files | Est. LOC |
|----------|-------|----------|
| Modified | 3 | ~1,100 net |
| Created | 9 | ~1,850 |
| **Total** | **12** | **~2,950** (±500) |

### 12.4 Incremental Buildability

**Yes.** The specification is designed to be built incrementally without breaking the current GUI:

1. Each new widget class is created in its own file with a clean API
2. The old `main_window.py` continues to work alongside new modules (they exist but aren't wired in)
3. A top-level `USE_NEW_UI = True` flag at the top of `main_window.py` switches between old code paths and new module imports
4. Phase-by-phase, the flag covers more:

```python
# main_window.py — top-level feature flag
USE_NEW_MENUBAR = True      # Phase 1
USE_NEW_TOOLBAR = True       # Phase 1
USE_NEW_SIDEBAR = False      # Phase 1 (refactored import)
USE_NEW_CHAT = False         # Phase 2
USE_NEW_STATUS_PANEL = False # Phase 2
USE_NEW_THEMES = False       # Phase 3
```

This way:
- After Phase 1: app still works, menu bar + new toolbar + sidebar refactoring
- After Phase 2: new chat experience + status panel, old one still available
- After Phase 3: themes + polish, everything stable

---

## 13. Phase Plan & Effort Estimates

### Phase 1: Foundation (P0) — Estimated 4-6 hours

**Goal**: Restructure layout, add menu bar, trim toolbar, consolidate sidebar.

| Task | Files | Est. Time | Dependencies |
|------|-------|-----------|--------------|
| 1.1 Add QMenuBar with File/Edit/View/Help | `main_window.py` | 30 min | None |
| 1.2 Trim toolbar to 5 elements + overflow | `main_window.py` | 30 min | 1.1 |
| 1.3 Add sidebar collapse (Ctrl+B) | `main_window.py` | 20 min | None |
| 1.4 Create `SidebarWidget` (4 tabs with icons) | `sidebar_widget.py` | 60 min | None |
| 1.5 Move Memory/Plots/RepoMap into Workspace tab | `sidebar_widget.py`, `main_window.py` | 30 min | 1.4 |
| 1.6 Create Settings tab (theme, font, preferences) | `sidebar_widget.py` | 30 min | 1.4 |
| 1.7 Config warning suppression (QSettings + status bar) | `main_window.py` | 15 min | None |
| 1.8 All existing actions working via menus + overflow | `main_window.py` | 30 min | 1.1, 1.2 |

**Exit criteria**: App launches, menu bar works, toolbar shows 5 elements, sidebar has 4 tabs with all functionality preserved, config warnings don't block startup.

### Phase 2: Experience (P1) — Estimated 6-10 hours

**Goal**: New chat experience, streaming feedback, error panel, onboarding, shortcuts.

| Task | Files | Est. Time | Dependencies |
|------|-------|-----------|--------------|
| 2.1 Create MessageWidget | `message_widget.py` | 60 min | None |
| 2.2 Create ChatWidget (QListWidget-based) | `chat_widget.py` | 90 min | 2.1 |
| 2.3 Wire streaming state machine | `main_window.py` | 45 min | 2.2 |
| 2.4 Chat search bar (Ctrl+F) | `chat_widget.py` | 30 min | 2.2 |
| 2.5 Input bar redesign (badges, auto-grow) | `chat_widget.py` | 30 min | 2.2 |
| 2.6 Create StatusPanel (Activity/Errors/Mission) | `status_panel.py` | 60 min | None |
| 2.7 Wire status panel to worker signals | `main_window.py` | 30 min | 2.6 |
| 2.8 Onboarding welcome widget | `onboarding.py`, `chat_widget.py` | 30 min | 2.2 |
| 2.9 Session load confirmation dialog | `main_window.py` | 15 min | None |
| 2.10 Keyboard shortcuts dialog | `shortcuts_dialog.py` | 30 min | None |
| 2.11 Wire all keyboard shortcuts | `main_window.py` | 20 min | 2.10 |
| 2.12 Export chat as markdown | `chat_widget.py` | 20 min | 2.2 |

**Exit criteria**: Chat streams into MessageWidgets, errors appear in panel, onboarding shows on first launch, Ctrl+F searches chat, keyboard shortcuts work.

### Phase 3: Polish (P2) — Estimated 4-6 hours

**Goal**: Themes, font size, system tray, input draft save, final polish.

| Task | Files | Est. Time | Dependencies |
|------|-------|-----------|--------------|
| 3.1 Extract dark QSS into `themes/dark.qss` | `dark.qss`, `main.py` | 15 min | None |
| 3.2 Create light theme QSS | `light.qss` | 30 min | 3.1 |
| 3.3 Create ThemeManager | `theme_manager.py` | 30 min | 3.1, 3.2 |
| 3.4 Wire theme switching (menu + settings) | `main_window.py` | 15 min | 3.3 |
| 3.5 Font size slider + zoom shortcuts | `main_window.py`, `sidebar_widget.py` | 20 min | None |
| 3.6 System tray icon + menu | `main_window.py` | 30 min | None |
| 3.7 Input draft auto-save/restore | `chat_widget.py`, `main_window.py` | 20 min | None |
| 3.8 Chat timestamp toggle | `message_widget.py` | 10 min | 2.1 |
| 3.9 Final QSS polish (scrollbars, hover states, animations) | `style.qss`, `dark.qss` | 30 min | None |

**Exit criteria**: Theme switching works, font size adjustable, app minimizes to tray, input drafts survive restart.

### Phase Timeline

```
Phase 1 (Foundation):  4-6 hours  →  Day 1-2
Phase 2 (Experience):  6-10 hours →  Day 3-5
Phase 3 (Polish):      4-6 hours  →  Day 5-7
────────────────────────────────────────
Total:                 14-22 hours →  1 week
```

---

## 14. Risks & Mitigations

### 14.1 Migration from QTextBrowser to QListWidget

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Performance**: rendering 100+ MessageWidgets could be slow | MEDIUM | Virtual mode: QListWidget with `setUniformItemSizes(False)`, only visible items are instantiated. Test with 500 messages. |
| **Scroll state loss**: replacing chat display mid-session | HIGH | Keep old chat_display (QTextBrowser) as backup. New chat_init clears it but saves reference. If new chat crashes, fallback to old. |
| **HTML rendering**: QLabel rich text is different from QTextBrowser | MEDIUM | Use same `markdown.markdown()` pipeline. Test edge cases: tables, code blocks, images. |
| **Copy/paste**: QListWidget selection differs from QTextBrowser | LOW | Implement custom context menu with "Copy message" action. |

### 14.2 Monolithic main_window.py Decomposition

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Circular imports**: new ui modules import from each other | MEDIUM | Clear dependency graph: `message_widget` < `chat_widget` < `main_window`. `status_panel` and `sidebar_widget` are independent. `theme_manager` is standalone. |
| **Signal disconnection**: old signals persist alongside new | HIGH | Phase feature flags (USE_NEW_*). Old signal connections stay in place until their phase is active. Remove old handlers in same phase as adding new ones. |
| **Method name collisions**: new modules have same method names as main_window | LOW | Use namespaced imports: `self.sidebar = SidebarWidget(self)`. Methods on the widget, not MainWindow. |

### 14.3 Streaming Edge Cases

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Rapid fire text_received**: signal emitted faster than Qt can layout | MEDIUM | Buffer text in 50ms intervals using QTimer.singleShot debounce. Only update MessageWidget once per frame. |
| **Tool finish before tool start**: race condition in worker | LOW | MessageWidget.add_tool_call() handles "completed" status without prior "running": creates entry as completed immediately. |
| **Multiple messages queued**: user sends second message before first finishes | MEDIUM | Existing queue.Queue handles this. Each message gets its own `_active_message`. When queue empties, `_finalize_message()` runs. |
| **Empty response**: agent returns zero text_received signals | LOW | `_finalize_message()` handles empty body: shows "(no text response)" in italic. |

### 14.4 Theme System Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **QSS incompatibility**: light theme breaks CSS features | MEDIUM | Test all 3 themes before Phase 3 ship. Keep dark.qss as canonical. |
| **Runtime switch causes flicker**: app.setStyleSheet redraws entire UI | LOW | Acceptable. Can optimize by delaying theme apply until next frame with QTimer.singleShot(0). |

### 14.5 Windows-Specific Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **QMenuBar native look**: Windows draws menu bar differently | LOW | Accept default QMenuBar rendering. It's consistent with Windows apps. |
| **System tray**: QSystemTrayIcon may not work on all Windows versions | LOW | Feature-gate with `QSystemTrayIcon.isSystemTrayAvailable()`. |
| **Shortcut conflicts**: Ctrl+B is Windows bookmark shortcut | LOW | Qt event filter consumes shortcuts before OS. Document in settings. |

---

## 15. Wireframe Descriptions

### 15.1 Main Window — Default State (1200×800)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ File  Edit  View  Help                                                   │ ← Menu bar
├──────────────────────────────────────────────────────────────────────────┤
│ [Model▼] [Agent▼]  [☐ Plan]  [🚀 Mission]          [⋮]                │ ← Toolbar
├──────────────┬───────────────────────────────────────────────────────────┤
│ 🔄 Sessions  │ [12:34:56] You                                           │
│ ───────────  │ Type your instruction here...                            │
│ 🔍 Search…   │                                                          │
│ ┌──────────┐ │ [12:34:57] OpenCode  via orchestrator · deepseek-v4-flash│
│ │ My feat  │ │ ┌────────────────────────────────────────────────────────┐│
│ │   - 5m   │ │ │ Here's what I found...                                ││
│ │ API int  │ │ │                                                       ││
│ │   - 2h   │ │ │ The file `main.py` contains...                        ││
│ │ Bug #42  │ │ │                                                       ││
│ │   - 1d   │ │ └────────────────────────────────────────────────────────┘│
│ └──────────┘ │                                                          │
│ [Fork] [Del] │                                                          │
│              │ ──────────────────────────────────────────────────────────│
│ 📁 Files     │ [📎] [M:v4-flash▼] [A:orch▼] [Type message...      ] [▶]│
│ 🧰 Workspace │──────────────────────────────────────────────────────────┤
│ ⚙️ Settings  │ 🟢 Ready  |  0s  |  Errors: 0  |  Tokens: —  |  ⚙️    │
├──────────────┴───────────────────────────────────────────────────────────┤
│ (bottom panel hidden — Ctrl+J to show)                                  │
└──────────────────────────────────────────────────────────────────────────┘

Sizes: Sidebar=270px, Chat=930px, Toolbar=36px, MenuBar=24px, StatusBar=22px
```

### 15.2 Main Window — Running State (Agent Working, Error Present)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ File  Edit  View  Help                                                   │
├──────────────────────────────────────────────────────────────────────────┤
│ [Model▼] [Agent▼]  [☐ Plan]  [🚀 Mission]          [⋮]                │
├──────────────┬───────────────────────────────────────────────────────────┤
│ ...sidebar   │ [You]                                                     │
│   (active)   │ Show me the architecture                                    │
│              │                                                           │
│              │ [OpenCode]  via coder · deepseek-v4-flash                 │
│              │   [12:35:00]                                              │
│              │ ┌────────────────────────────────────────────────────────┐│
│              │ │ I'll read the architecture docs first...               ││
│              │ │                                                        ││
│              │ │ ── 💭 Thought (140 chars) [▼] ──                      ││
│              │ │ │ The user wants architecture overview.               ││
│              │ │ │ Let me check the project files.                     ││
│              │ │ └────────────────────────────────────────────────────┘││
│              │ │                                                        ││
│              │ │ ⚙️ Tools:                                              ││
│              │ │   [🔄] read(".opencode/context/project-overview.md")   ││
│              │ │   [⏳] grep("class.*QMainWindow")                      ││
│              │ └────────────────────────────────────────────────────────┘│
│              │                                                           │
│              │ ── [12:35:05] ⚠️ Error loading session list ──           │
│              │ │ [Copy]  [Retry]  [Dismiss]                             │
│              │ ─────────────────────────────────────────────────────────│
│              │ [📎] [M:v4-flash▼] [A:coder▼] [Type message...      ] [▶]│
├──────────────┴───────────────────────────────────────────────────────────┤
│ [Activity] [Errors(1)] [Mission]  [Ctrl+J to collapse]                  │
│ ┌──────────────────────────────────────────────────────────────────────┐│
│ │ 12:35:02  🔄 Tool read started                                    ││
│ │ 12:35:03  ✅ Tool read completed in 0.4s                           ││
│ │ 12:35:04  🔄 Tool grep started                                     ││
│ │ 12:34:58  ⚠️ Error loading session list                            ││
│ └──────────────────────────────────────────────────────────────────────┘│
│ 🟡 Running  |  5.2s  |  Errors: 1  |  Tokens: ~340  |  Session: abc123│
└──────────────────────────────────────────────────────────────────────────┘
```

### 15.3 Bottom Panel — Errors Tab (expanded)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Activity] [Errors(3)] [Mission]                                         │
├──────────────────────────────────────────────────────────────────────────┤
│ ☐ [12:34:58] db_error  Memory DB busy - retry succeeded (2 attempts)    │
│ ☐ [12:35:10] config_error  opencode.json: unknown key 'compaction_v1'   │
│ ☐ [12:35:15] tool_error  write("test.txt") failed: permission denied    │
│                                                                          │
│ Selected error detail:                                                   │
│ ┌──────────────────────────────────────────────────────────────────────┐│
│ │ Type:    config_error                                               ││
│ │ Time:    12:35:10                                                   ││
│ │ Context: opencode.json:5  unknown key 'compaction_v1'               ││
│ │ File:    .opencode/opencode.json                                    ││
│ │ Fix:     Rename 'compaction_v1' to 'compaction'                     ││
│ └──────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│ [Copy Selected]  [Dismiss Selected]  [Clear All]                         │
└──────────────────────────────────────────────────────────────────────────┘
```

### 15.4 Compact Window (<900px wide)

```
┌──────────────────────────────────────────────────────────────┐
│ [☰] [Model ▼] [Agent ▼] [☐ Plan] [🚀] [⋮]                 │ ← Sidebar icon-only
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   [Chat fills entire width — no sidebar]                     │
│                                                              │
│                                                              │
│                                                              │
│ [📎] [M:v4▼] [A:orch▼] [Type message...              ] [▶] │
├──────────────────────────────────────────────────────────────┤
│ 🟢 Ready  |  0s  |  Errors: 0  |  ⚙️                       │
└──────────────────────────────────────────────────────────────┘

Sidebar collapses to icon strip on left. ☰ button expands flyout.
```

---

## Appendix A: Dependency Graph for New Modules

```
┌────────────────┐
│  theme_manager  │ ← standalone
└────────────────┘
       │ loads
       ▼
┌──────────────┐    ┌─────────────┐
│   style.qss   │    │ shortcuts   │ ← standalone
│  themes/*.qss │    │ _dialog.py  │
└──────────────┘    └─────────────┘

┌────────────────┐
│ message_widget  │ ← standalone (depends on markdown library)
└────────┬───────┘
         │ used by
         ▼
┌──────────────┐    ┌────────────┐
│  chat_widget  │    │ onboarding │
│ (chat display │    │ .py        │
│  + search     │    └────────────┘
│  + input bar) │
└────────┬──────┘
         │ wired by
         ▼
┌────────────────┐    ┌──────────────┐    ┌──────────────┐
│  main_window    │◄───│ sidebar_      │    │ status_panel  │
│  (orchestrator) │    │ widget.py    │    │ .py          │
│  (receives      │    └──────────────┘    └──────────────┘
│   worker sgnls) │
└────────────────┘
```

No circular dependencies. `main_window.py` is the only module that imports from all others. Each sub-module is self-contained.

---

## Appendix B: QSS Component Inventory (for theme system)

The following QSS selectors must be themed in both dark.qss and light.qss:

| Selector | Purpose | Dark Value | Light Value |
|----------|---------|------------|-------------|
| `QMainWindow` | Background | `#1e1e1e` | `#f5f5f5` |
| `QTextBrowser` | Chat bg | `#1e1e1e` | `#ffffff` |
| `QTextEdit` | Input bg | `#2d2d30` | `#f0f0f0` |
| `QPushButton` | Default button | `#0e639c` | `#0078d4` |
| `QToolBar` | Toolbar bg | `#252526` | `#e8e8e8` |
| `QTreeView` | File tree bg | `#252526` | `#ffffff` |
| `QListWidget` | List bg | `#1e1e1e` | `#ffffff` |
| `QSplitter::handle` | Divider | `#333333` | `#cccccc` |
| `QMenuBar` | Menu bg | `#252526` | `#f0f0f0` |
| `QStatusBar` | Status bg | `#007acc` | `#e0e0e0` |
| `QTabWidget::pane` | Tab bg | `#252526` | `#ffffff` |
| `.MessageWidget-user` | User msg bg | `#1a3a1a` | `#e8f5e9` |
| `.MessageWidget-assistant` | Assistant bg | `#252526` | `#f5f5f5` |
| `.MessageWidget-error` | Error bg | `#3a1a1a` | `#ffebee` |
| `.StatusPanel` | Panel bg | `#1e1e1e` | `#fafafa` |
| `QScrollBar` | Scrollbar | `#3c3c3c` | `#c0c0c0` |

---

*End of GUI Overhaul Specification. Ready for orchestrator review and Phase 1 implementation.*
