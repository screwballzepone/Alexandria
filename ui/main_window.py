import os

from PySide6.QtCore import QSize, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QColor, QStandardItem, QStandardItemModel, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileSystemModel,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from core.opencode_service import OpenCodeService
from core.service_worker import ServiceWorker
from core.worker import OpenCodeWorker
from ui.dialogs import McpDialog, ProvidersDialog, StatsDialog

# Phase 1 feature flags — set False to fall back to legacy layout
USE_NEW_MENUBAR = True
USE_NEW_TOOLBAR = True
USE_NEW_SIDEBAR = True


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenCode")
        self.resize(1100, 750)
        self._attached_file = None
        self._pending_title = None

        # Main splitter layout to divide sidebar and chat
        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)

        # 0. Setup Menu Bar
        if USE_NEW_MENUBAR:
            self.setup_menu_bar()

        # 1. Setup Toolbar
        self.setup_toolbar()

        # 1. Setup Left Sidebar (File Explorer)
        self.setup_sidebar()

        # 2. Setup Right Area (Chat & Input)
        self.setup_chat_area()

        # Set the initial splitter proportions (Sidebar: 250px, Chat: 850px)
        self.splitter.setSizes([250, 850])

        # 3. Setup Backend Worker (OpenCode process)
        self.worker = OpenCodeWorker()
        self.worker.text_received.connect(self.handle_text)
        self.worker.tool_started.connect(self.handle_tool_start)
        self.worker.tool_finished.connect(self.handle_tool_finish)
        self.worker.error_received.connect(self.handle_error)
        self.worker.process_finished.connect(self.handle_finished)
        self.worker.started.connect(self._on_worker_started)
        self.worker.queue_empty.connect(self._on_worker_done)

        # Drift guard - validate config on startup
        from core.drift_guard import check_config

        config_warnings = check_config(os.getcwd())
        if config_warnings:
            from PySide6.QtCore import QSettings

            settings = QSettings("OpenCode", "OpenCodeGUI")
            dont_show = settings.value("config/ignore_warnings", False, type=bool)
            if not dont_show:
                msg = QMessageBox(self)
                msg.setWindowTitle("Config Warnings")
                msg.setIcon(QMessageBox.Warning)
                msg.setText(
                    "OpenCode config issues detected:\n\n" + "\n".join(config_warnings)
                )
                cb = QCheckBox("Don't show again")
                msg.setCheckBox(cb)
                msg.exec()
                if cb.isChecked():
                    settings.setValue("config/ignore_warnings", True)

        # Mission tab state tracking
        self._prev_mission_status = None
        self._all_memories = []

        # Defer slow CLI calls until event loop is running - keeps startup instant
        QTimer.singleShot(0, self._load_models_async)
        QTimer.singleShot(0, self._load_agents_async)

    # -----------------------------------------------------------------------
    # Menu Bar
    # -----------------------------------------------------------------------

    def setup_menu_bar(self):
        """Build the application menu bar (File / Edit / View / Help)."""
        mb = self.menuBar()

        # ── File ──────────────────────────────────────────────────────
        file_menu = mb.addMenu("&File")
        file_menu.addAction("New Session", self.new_session, "Ctrl+N")
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close, "Alt+F4")

        # ── Edit ──────────────────────────────────────────────────────
        edit_menu = mb.addMenu("&Edit")
        edit_menu.addAction("Undo", self.run_undo, "Ctrl+Z")
        edit_menu.addAction("Redo", self.run_redo, "Ctrl+Y")
        edit_menu.addSeparator()
        edit_menu.addAction("&Preferences...", self._show_preferences)

        # ── View ──────────────────────────────────────────────────────
        view_menu = mb.addMenu("&View")
        self._act_toggle_sidebar = view_menu.addAction(
            "Toggle Sidebar", self._toggle_sidebar_visibility, "Ctrl+B"
        )
        self._act_toggle_sidebar.setCheckable(True)
        self._act_toggle_sidebar.setChecked(True)
        self._act_toggle_status = view_menu.addAction(
            "Toggle Status Panel", self._toggle_status_panel, "Ctrl+J"
        )
        self._act_toggle_status.setCheckable(True)
        self._act_toggle_status.setChecked(False)
        if not USE_NEW_SIDEBAR:
            self._act_toggle_sidebar.setVisible(False)
        view_menu.addSeparator()
        self._act_view_mission = view_menu.addAction("&Mission Status", self._show_mission_dialog)
        if not USE_NEW_SIDEBAR:
            self._act_view_mission.setVisible(False)
        view_menu.addSeparator()
        view_menu.addAction("&Refresh", self.refresh_sessions, "F5")

        # ── Help ──────────────────────────────────────────────────────
        help_menu = mb.addMenu("&Help")
        help_menu.addAction("Keyboard Shortcuts", self._show_shortcuts, "Ctrl+/")
        help_menu.addSeparator()
        help_menu.addAction("&About", self._show_about)

    # -----------------------------------------------------------------------
    # Toolbar
    # -----------------------------------------------------------------------

    def setup_toolbar(self):
        if USE_NEW_TOOLBAR:
            self._setup_toolbar_new()
            return
        # --- legacy toolbar (Phase 0) ---
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        self.model_btn = QPushButton("Model")
        self.model_btn.setToolTip("Select model - grouped by provider")
        self.model_btn.setStyleSheet(
            "QPushButton { text-align: left; padding: 3px 6px; min-width: 70px; }"
        )
        self.model_btn.clicked.connect(self._show_model_menu)
        self._selected_model = "Default Model (Auto)"
        self._model_list = []
        self.toolbar.addWidget(self.model_btn)

        self.toolbar.addSeparator()

        # Low Token + Plan Mode checkboxes (side by side)
        self.low_token_check = QCheckBox("Low Token")
        self.low_token_check.setToolTip("Uses nano-coder and gemini-2.5-flash to save tokens")
        self.low_token_check.stateChanged.connect(self.toggle_low_token)
        self.toolbar.addWidget(self.low_token_check)

        self.plan_mode_check = QCheckBox("Plan Mode")
        self.plan_mode_check.setToolTip("Agent describes changes without modifying any files")
        self.toolbar.addWidget(self.plan_mode_check)

        self.toolbar.addSeparator()

        # Core action buttons
        actions = [
            ("Providers", "Manage AI providers", self.run_providers),
            ("Agents", "Manage agents", self.run_agents),
            ("Stats", "Show token usage", self.run_stats),
        ]
        for text, tooltip, slot in actions:
            action = QAction(text, self)
            action.setToolTip(tooltip)
            action.triggered.connect(slot)
            self.toolbar.addAction(action)

        self.toolbar.addSeparator()
        self.toolbar.addAction(QAction("New Session", self, triggered=self.new_session))
        self.toolbar.addAction(QAction("↻", self, triggered=self.refresh_sessions, toolTip="Refresh"))

    def _setup_toolbar_new(self):
        """Phase 1 compact toolbar: Model | Agent | Plan | New Session | ⋮ More."""
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        # 1. Model selector (compact button)
        self.model_btn = QPushButton("Model")
        self.model_btn.setToolTip("Select model - grouped by provider")
        self.model_btn.setStyleSheet(
            "QPushButton { text-align: left; padding: 3px 6px; min-width: 70px; }"
        )
        self.model_btn.clicked.connect(self._show_model_menu)
        self._selected_model = "Default Model (Auto)"
        self._model_list = []
        self.toolbar.addWidget(self.model_btn)

        self.toolbar.addSeparator()

        # 2. Agent selector (moved from chat area)
        self.agent_combo = QComboBox()
        self.agent_combo.setMinimumWidth(140)
        self.agent_combo.setStyleSheet(
            "QComboBox { padding: 2px 6px; font-size: 11px; }"
        )
        from core.opencode_service import OpenCodeService
        pills_agents = OpenCodeService.get_agents_from_files()
        if not pills_agents:
            pills_agents = ["orchestrator"]
        for a in pills_agents:
            self.agent_combo.addItem(a)
        self.agent_combo.setCurrentText("orchestrator")
        self.agent_combo.currentTextChanged.connect(self._select_agent_pill)
        self._selected_agent = "orchestrator"
        self.toolbar.addWidget(self.agent_combo)

        self.toolbar.addSeparator()

        # 3. Plan Mode checkbox
        self.plan_mode_check = QCheckBox("Plan")
        self.plan_mode_check.setToolTip("Agent describes changes without modifying any files")
        self.toolbar.addWidget(self.plan_mode_check)

        self.toolbar.addSeparator()

        # 4. New Session button
        new_session_btn = QPushButton("New Session")
        new_session_btn.setToolTip("Start a new chat session")
        new_session_btn.clicked.connect(self.new_session)
        self.toolbar.addWidget(new_session_btn)

        self.toolbar.addSeparator()

        # Mission status indicator
        self.mission_indicator = QLabel("Mission: —")
        self.mission_indicator.setStyleSheet("color: #888; font-size: 11px; padding: 0 6px;")
        self.mission_indicator.setToolTip("Click to view mission status")
        self.mission_indicator.mousePressEvent = lambda e: self._show_mission_dialog()
        self.toolbar.addWidget(self.mission_indicator)

        # 5. ⋮ More overflow menu button
        self.more_btn = QPushButton("⋮ More")
        self.more_btn.setToolTip("Additional actions")
        self.more_btn.setStyleSheet(
            "QPushButton { padding: 3px 10px; font-weight: bold; }"
        )
        self.more_menu = QMenu(self)
        self._build_more_menu()
        self.more_btn.setMenu(self.more_menu)
        self.toolbar.addWidget(self.more_btn)

    def _build_more_menu(self):
        """Populate the ⋮ More overflow menu."""
        self.more_menu.clear()

        # Low Token Mode (checkable — hidden checkbox acts as state holder)
        self.low_token_check = QCheckBox("Low Token Mode", self)
        self.low_token_check.setVisible(False)
        self.low_token_check.setToolTip("Uses nano-coder and gemini-2.5-flash to save tokens")
        self.low_token_check.stateChanged.connect(self.toggle_low_token)
        act_low = self.more_menu.addAction("Low Token Mode")
        act_low.setCheckable(True)
        act_low.setChecked(False)
        act_low.triggered.connect(self._toggle_low_token_from_menu)
        self._more_low_token_action = act_low

        self.more_menu.addSeparator()

        self.more_menu.addAction("Providers...", self.run_providers)
        self.more_menu.addAction("Agents...", self.run_agents)
        self.more_menu.addAction("Stats...", self.run_stats)
        self.more_menu.addAction("MCP Servers...", self.run_mcp)

        self.more_menu.addSeparator()

        self.more_menu.addAction("Undo", self.run_undo, "Ctrl+Z")
        self.more_menu.addAction("Redo", self.run_redo, "Ctrl+Y")

        self.more_menu.addSeparator()

        self.more_menu.addAction("Refresh Sessions", self.refresh_sessions)

    def _toggle_low_token_from_menu(self, checked):
        """Sync the hidden low_token_checkbox state from the menu action."""
        self.low_token_check.setChecked(checked)

    # -----------------------------------------------------------------------
    # Sidebar
    # -----------------------------------------------------------------------

    def setup_sidebar(self):
        if USE_NEW_SIDEBAR:
            self._setup_sidebar_new()
            return
        # --- legacy sidebar (Phase 0) ---
        self.sidebar_tabs = QTabWidget()

        # Files Tab
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(os.getcwd())

        self.tree = QTreeView()
        self.tree.setModel(self.file_model)
        self.tree.setRootIndex(self.file_model.index(os.getcwd()))
        for i in range(1, 4):
            self.tree.hideColumn(i)
        self.sidebar_tabs.addTab(self.tree, "Files")

        # Sessions Tab - wrapped in widget with Fork button below list
        self.session_list = QListWidget()
        self.refresh_sessions()
        self.session_list.itemClicked.connect(self.load_session)

        session_widget = QWidget()
        session_layout = QVBoxLayout(session_widget)
        session_layout.setContentsMargins(0, 0, 0, 0)
        session_layout.addWidget(self.session_list)
        self.fork_btn = QPushButton("Fork Session")
        self.fork_btn.setToolTip("Branch the selected session into a new one")
        self.fork_btn.clicked.connect(self.fork_session)
        session_layout.addWidget(self.fork_btn)
        self.sidebar_tabs.addTab(session_widget, "Sessions")

        # Memory Tab
        self.memory_widget = QWidget()
        self.memory_layout = QVBoxLayout(self.memory_widget)

        # Search box for filtering memory entries by key
        self.memory_search = QLineEdit()
        self.memory_search.setPlaceholderText("Search memory by key…")
        self.memory_search.textChanged.connect(self._filter_memory)
        self.memory_search.setStyleSheet(
            "QLineEdit { background: #3c3c3c; color: #d4d4d4; border: 1px solid #555; "
            "border-radius: 3px; padding: 4px 8px; font-size: 12px; }"
        )
        self.memory_layout.addWidget(self.memory_search)

        self.memory_list = QListWidget()
        self.memory_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.memory_list.customContextMenuRequested.connect(self._show_memory_context_menu)
        self.memory_layout.addWidget(self.memory_list)

        self.mem_btn_layout = QHBoxLayout()
        self.refresh_mem_btn = QPushButton("Refresh")
        self.refresh_mem_btn.clicked.connect(self.refresh_memory)
        self.add_mem_btn = QPushButton("Add Fact")
        self.add_mem_btn.clicked.connect(self.add_manual_memory)
        self.del_mem_btn = QPushButton("Delete")
        self.del_mem_btn.clicked.connect(self.delete_selected_memory)
        self.mem_btn_layout.addWidget(self.refresh_mem_btn)
        self.mem_btn_layout.addWidget(self.add_mem_btn)
        self.mem_btn_layout.addWidget(self.del_mem_btn)
        self.memory_layout.addLayout(self.mem_btn_layout)

        self.refresh_memory()
        self.sidebar_tabs.addTab(self.memory_widget, "Memory")

        # Plots Tab - image viewer for LCN figures
        self.plots_widget = QWidget()
        self.plots_layout = QVBoxLayout(self.plots_widget)
        self.plots_layout.setContentsMargins(4, 4, 4, 4)

        # Top: file list + refresh
        plots_header = QHBoxLayout()
        plots_label = QLabel("📊 Plots")
        plots_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.plots_refresh_btn = QPushButton("🔄")
        self.plots_refresh_btn.setFixedWidth(32)
        self.plots_refresh_btn.setToolTip("Rescan for plot files")
        self.plots_refresh_btn.clicked.connect(self._refresh_plots_list)
        plots_header.addWidget(plots_label)
        plots_header.addStretch()
        plots_header.addWidget(self.plots_refresh_btn)
        self.plots_layout.addLayout(plots_header)

        self.plots_list = QListWidget()
        self.plots_list.setMinimumHeight(80)
        self.plots_list.itemClicked.connect(self._show_plot_preview)
        self.plots_layout.addWidget(self.plots_list)

        # Image preview area
        self.plot_preview = QLabel("Click a plot file to preview")
        self.plot_preview.setAlignment(Qt.AlignCenter)
        self.plot_preview.setStyleSheet(
            "QLabel { background-color: #1e1e1e; border: 1px solid #3c3c3c; "
            "border-radius: 4px; padding: 8px; color: #888; font-size: 11px; }"
        )
        self.plot_preview.setMinimumHeight(200)
        self.plot_preview.setScaledContents(False)
        self.plots_layout.addWidget(self.plot_preview, stretch=1)

        # Open in external viewer button
        plots_btn_row = QHBoxLayout()
        self.plots_open_btn = QPushButton("Open in external viewer")
        self.plots_open_btn.clicked.connect(self._open_plot_external)
        self.plots_open_btn.setEnabled(False)
        plots_btn_row.addStretch()
        plots_btn_row.addWidget(self.plots_open_btn)
        self.plots_layout.addLayout(plots_btn_row)

        self.sidebar_tabs.addTab(self.plots_widget, "Plots")
        self._refresh_plots_list()

        # Mission Tab
        self.mission_tab = QWidget()
        self.mission_layout = QVBoxLayout(self.mission_tab)
        self.sidebar_tabs.addTab(self.mission_tab, "Mission")
        self._setup_mission_tab()

        # Repo Map Tab
        self._setup_repomap_tab()

        self.splitter.addWidget(self.sidebar_tabs)

    def _setup_sidebar_new(self):
        """Phase 1 sidebar: Sessions | Files | Workspace | Settings."""
        self.sidebar_tabs = QTabWidget()

        # ── Tab 0: Sessions ──────────────────────────────────────────
        self._build_sidebar_sessions()

        # ── Tab 1: Files ─────────────────────────────────────────────
        self._build_sidebar_files()

        # ── Tab 2: Workspace (collapsible sections) ──────────────────
        self._build_sidebar_workspace()

        # ── Tab 3: Settings ──────────────────────────────────────────
        self._build_sidebar_settings()

        self.splitter.addWidget(self.sidebar_tabs)

        # Mission tab — kept as standalone widget (accessed via View menu)
        self.mission_tab = QWidget()
        self.mission_layout = QVBoxLayout(self.mission_tab)
        self._setup_mission_tab()

    def _build_sidebar_sessions(self):
        """Sessions tab — list + fork button."""
        self.session_list = QListWidget()
        self.refresh_sessions()
        self.session_list.itemClicked.connect(self.load_session)

        session_widget = QWidget()
        session_layout = QVBoxLayout(session_widget)
        session_layout.setContentsMargins(0, 0, 0, 0)
        session_layout.addWidget(self.session_list)
        self.fork_btn = QPushButton("Fork Session")
        self.fork_btn.setToolTip("Branch the selected session into a new one")
        self.fork_btn.clicked.connect(self.fork_session)
        session_layout.addWidget(self.fork_btn)
        self.sidebar_tabs.addTab(session_widget, "Sessions")

    def _build_sidebar_files(self):
        """Files tab — QTreeView with QFileSystemModel."""
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(os.getcwd())

        self.tree = QTreeView()
        self.tree.setModel(self.file_model)
        self.tree.setRootIndex(self.file_model.index(os.getcwd()))
        for i in range(1, 4):
            self.tree.hideColumn(i)
        self.sidebar_tabs.addTab(self.tree, "Files")

    def _build_sidebar_workspace(self):
        """Workspace tab — collapsible QGroupBox sections for Memory, Plots, Repo Map."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        workspace_root = QWidget()
        workspace_layout = QVBoxLayout(workspace_root)
        workspace_layout.setContentsMargins(4, 4, 4, 4)
        workspace_layout.setSpacing(4)

        # ── Memory section ───────────────────────────────────────────
        mem_box = QGroupBox("Memory")
        mem_box.setCheckable(True)
        mem_box.setChecked(True)
        mem_layout = QVBoxLayout(mem_box)

        self.memory_search = QLineEdit()
        self.memory_search.setPlaceholderText("Search memory by key…")
        self.memory_search.textChanged.connect(self._filter_memory)
        self.memory_search.setStyleSheet(
            "QLineEdit { background: #3c3c3c; color: #d4d4d4; border: 1px solid #555; "
            "border-radius: 3px; padding: 4px 8px; font-size: 12px; }"
        )
        mem_layout.addWidget(self.memory_search)

        self.memory_list = QListWidget()
        self.memory_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.memory_list.customContextMenuRequested.connect(self._show_memory_context_menu)
        mem_layout.addWidget(self.memory_list)

        mem_btn_row = QHBoxLayout()
        self.refresh_mem_btn = QPushButton("Refresh")
        self.refresh_mem_btn.clicked.connect(self.refresh_memory)
        self.add_mem_btn = QPushButton("Add Fact")
        self.add_mem_btn.clicked.connect(self.add_manual_memory)
        self.del_mem_btn = QPushButton("Delete")
        self.del_mem_btn.clicked.connect(self.delete_selected_memory)
        mem_btn_row.addWidget(self.refresh_mem_btn)
        mem_btn_row.addWidget(self.add_mem_btn)
        mem_btn_row.addWidget(self.del_mem_btn)
        mem_layout.addLayout(mem_btn_row)

        self.refresh_memory()
        workspace_layout.addWidget(mem_box)

        # ── Plots section ────────────────────────────────────────────
        plots_box = QGroupBox("Plots")
        plots_box.setCheckable(True)
        plots_box.setChecked(False)
        plots_inner = QVBoxLayout(plots_box)
        plots_inner.setContentsMargins(4, 4, 4, 4)

        plots_header = QHBoxLayout()
        self.plots_refresh_btn = QPushButton("🔄")
        self.plots_refresh_btn.setFixedWidth(32)
        self.plots_refresh_btn.setToolTip("Rescan for plot files")
        self.plots_refresh_btn.clicked.connect(self._refresh_plots_list)
        plots_header.addStretch()
        plots_header.addWidget(self.plots_refresh_btn)
        plots_inner.addLayout(plots_header)

        self.plots_list = QListWidget()
        self.plots_list.setMinimumHeight(80)
        self.plots_list.itemClicked.connect(self._show_plot_preview)
        plots_inner.addWidget(self.plots_list)

        self.plot_preview = QLabel("Click a plot file to preview")
        self.plot_preview.setAlignment(Qt.AlignCenter)
        self.plot_preview.setStyleSheet(
            "QLabel { background-color: #1e1e1e; border: 1px solid #3c3c3c; "
            "border-radius: 4px; padding: 8px; color: #888; font-size: 11px; }"
        )
        self.plot_preview.setMinimumHeight(160)
        self.plot_preview.setScaledContents(False)
        plots_inner.addWidget(self.plot_preview, stretch=1)

        plots_btn_row = QHBoxLayout()
        self.plots_open_btn = QPushButton("Open in external viewer")
        self.plots_open_btn.clicked.connect(self._open_plot_external)
        self.plots_open_btn.setEnabled(False)
        plots_btn_row.addStretch()
        plots_btn_row.addWidget(self.plots_open_btn)
        plots_inner.addLayout(plots_btn_row)

        self._refresh_plots_list()
        workspace_layout.addWidget(plots_box)

        # ── Repo Map section ─────────────────────────────────────────
        repomap_box = QGroupBox("Project Map")
        repomap_box.setCheckable(True)
        repomap_box.setChecked(False)
        repomap_inner = QVBoxLayout(repomap_box)

        repomap_header = QHBoxLayout()
        self.repomap_refresh_btn = QPushButton("🔄")
        self.repomap_refresh_btn.setFixedWidth(32)
        self.repomap_refresh_btn.setToolTip("Rescan file structure")
        self.repomap_refresh_btn.clicked.connect(self._refresh_repomap)
        repomap_header.addStretch()
        repomap_header.addWidget(self.repomap_refresh_btn)
        repomap_inner.addLayout(repomap_header)

        self.repomap_tree = QTreeView()
        self.repomap_tree.setHeaderHidden(True)
        self.repomap_tree.setAnimated(True)
        self.repomap_tree.setIndentation(16)
        repomap_inner.addWidget(self.repomap_tree)

        self._refresh_repomap()
        workspace_layout.addWidget(repomap_box)

        workspace_layout.addStretch()
        scroll.setWidget(workspace_root)
        self.sidebar_tabs.addTab(scroll, "Workspace")

    def _build_sidebar_settings(self):
        """Settings tab — theme, font size, keyboard shortcuts."""
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        settings_layout.setSpacing(8)

        # Appearance
        appearance_label = QLabel("Appearance")
        appearance_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #888;")
        settings_layout.addWidget(appearance_label)

        sep1 = QLabel("─" * 30)
        sep1.setStyleSheet("color: #3c3c3c;")
        settings_layout.addWidget(sep1)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.setCurrentText("Dark")
        self.theme_combo.currentTextChanged.connect(self._apply_theme)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        settings_layout.addLayout(theme_row)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font size:"))
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(10, 24)
        self.font_slider.setValue(14)
        self.font_slider.setFixedWidth(120)
        self.font_label = QLabel("14px")
        self.font_slider.valueChanged.connect(self._on_font_changed)
        font_row.addWidget(self.font_slider)
        font_row.addWidget(self.font_label)
        font_row.addStretch()
        settings_layout.addLayout(font_row)

        # Chat
        chat_label = QLabel("Chat")
        chat_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #888; margin-top: 8px;")
        settings_layout.addWidget(chat_label)

        sep2 = QLabel("─" * 30)
        sep2.setStyleSheet("color: #3c3c3c;")
        settings_layout.addWidget(sep2)

        self.show_timestamps_check = QCheckBox("Show timestamps")
        self.show_timestamps_check.setChecked(True)
        settings_layout.addWidget(self.show_timestamps_check)

        self.collapse_thinking_check = QCheckBox("Collapse thinking by default")
        self.collapse_thinking_check.setChecked(True)
        settings_layout.addWidget(self.collapse_thinking_check)

        # Shortcuts
        shortcuts_label = QLabel("Shortcuts")
        shortcuts_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #888; margin-top: 8px;")
        settings_layout.addWidget(shortcuts_label)

        sep3 = QLabel("─" * 30)
        sep3.setStyleSheet("color: #3c3c3c;")
        settings_layout.addWidget(sep3)

        shortcuts_btn = QPushButton("View Keyboard Shortcuts")
        shortcuts_btn.clicked.connect(self._show_shortcuts)
        settings_layout.addWidget(shortcuts_btn)

        # About
        about_label = QLabel("About")
        about_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #888; margin-top: 8px;")
        settings_layout.addWidget(about_label)

        sep4 = QLabel("─" * 30)
        sep4.setStyleSheet("color: #3c3c3c;")
        settings_layout.addWidget(sep4)

        about_text = QLabel("OpenCode GUI v0.2")
        about_text.setStyleSheet("color: #aaa; font-size: 11px;")
        settings_layout.addWidget(about_text)

        engine_text = QLabel("Engine: opencode.cmd")
        engine_text.setStyleSheet("color: #888; font-size: 10px;")
        settings_layout.addWidget(engine_text)

        settings_layout.addStretch()
        self.sidebar_tabs.addTab(settings_widget, "Settings")

    def _apply_theme(self, theme):
        from pathlib import Path

        from PySide6.QtWidgets import QApplication

        if theme == "Light":
            QApplication.instance().setStyleSheet(
                "QMainWindow{background:#f0f0f0;color:#1a1a1a}"
                "QTextEdit,QTextBrowser,QListWidget,QTreeView{background:#fff;color:#1a1a1a;border:1px solid #ccc}"
                "QToolBar{background:#e8e8e8;border-bottom:1px solid #ccc}"
                "QPushButton{background:#e0e0e0;color:#1a1a1a;border:1px solid #bbb;padding:3px 8px}"
                "QPushButton:hover{background:#d0d0d0}"
                "QTabBar::tab{background:#e0e0e0;color:#1a1a1a;padding:4px 12px}"
                "QTabBar::tab:selected{background:#fff}"
                "QLabel{color:#1a1a1a}"
                "QComboBox{background:#fff;color:#1a1a1a}"
                "QMenuBar{background:#e8e8e8;color:#1a1a1a}"
            )
        else:
            qss = Path(__file__).parent.parent / "assets" / "style.qss"
            if qss.exists():
                QApplication.instance().setStyleSheet(qss.read_text())

    def _on_font_changed(self, size):
        self.font_label.setText(f"{size}px")
        self.setStyleSheet(f"* {{ font-size: {size}px; }}")

    def add_manual_memory(self):
        from PySide6.QtWidgets import QInputDialog

        key, ok1 = QInputDialog.getText(self, "Add Memory", "Key (e.g. API Endpoint):")
        if ok1 and key:
            value, ok2 = QInputDialog.getText(self, "Add Memory", f"Value for {key}:")
            if ok2 and value:
                from core.memory import AgentMemory

                mem = AgentMemory()
                mem.store(os.getcwd(), key, value)
                self.refresh_memory()

    def delete_selected_memory(self):
        item = self.memory_list.currentItem()
        if not item:
            return
        key = item.data(Qt.UserRole)
        from core.memory import AgentMemory

        mem = AgentMemory()
        mem.delete(os.getcwd(), key)
        self.refresh_memory()

    def refresh_memory(self):
        self.refresh_mem_btn.setText("Loading...")
        from core.memory import AgentMemory

        mem = AgentMemory()
        self._all_memories = mem.retrieve_with_timestamps(os.getcwd())
        filter_text = self.memory_search.text().strip().lower() if hasattr(self, "memory_search") else ""
        self._render_memory_list(filter_text)
        self.refresh_mem_btn.setText("Refresh")

    def _render_memory_list(self, filter_text=""):
        """Populate the memory list from self._all_memories with optional filter."""
        self.memory_list.clear()
        from datetime import datetime

        from utils.helpers import format_timestamp

        for key, value, tags, time_updated in self._all_memories:
            if filter_text and filter_text not in key.lower():
                continue

            dt = datetime.fromtimestamp(time_updated) if time_updated else None
            time_str = format_timestamp(dt) if dt else ""

            # Two-line display: key:value on top, timestamp below in smaller font
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(4, 2, 4, 2)
            layout.setSpacing(1)

            main_label = QLabel(f"{key}: {value}")
            main_label.setStyleSheet("color: #d4d4d4; font-size: 12px;")
            main_label.setWordWrap(True)

            time_label = QLabel(time_str)
            time_label.setStyleSheet("color: #888; font-size: 10px;")

            layout.addWidget(main_label)
            layout.addWidget(time_label)

            item = QListWidgetItem()
            item.setData(Qt.UserRole, key)
            item.setSizeHint(QSize(0, 38))
            self.memory_list.addItem(item)
            self.memory_list.setItemWidget(item, widget)

    def _filter_memory(self, text):
        """Real-time search filter on memory entries by key substring."""
        self._render_memory_list(text.strip().lower())

    def _show_memory_context_menu(self, pos):
        """Right-click context menu for memory list items."""
        item = self.memory_list.itemAt(pos)
        if not item:
            return
        self.memory_list.setCurrentItem(item)
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_memory)
        menu.exec(self.memory_list.mapToGlobal(pos))

    def refresh_sessions(self):
        self.session_list.clear()
        self.session_list.addItem("Loading sessions…")
        self._sessions_worker = ServiceWorker(OpenCodeService.get_sessions)
        self._sessions_worker.result_ready.connect(self._on_sessions_loaded)
        self._sessions_worker.error_occurred.connect(
            lambda e: (self.session_list.clear(), self.session_list.addItem(f"Error: {e}"))
        )
        self._sessions_worker.start()

    def _on_sessions_loaded(self, sessions):
        from datetime import datetime

        from utils.helpers import format_timestamp

        self.session_list.clear()
        for session in sessions:
            title = session.get("title", "Untitled")
            updated_at = session.get("updated_at")
            dt = datetime.fromtimestamp(updated_at / 1000) if updated_at else None
            display_title = f"{title}  -  {format_timestamp(dt)}" if dt is not None else title
            item = QListWidgetItem(display_title)
            item.setData(Qt.UserRole, session.get("id"))
            self.session_list.addItem(item)

    def load_session(self, item):
        session_id = item.data(Qt.UserRole)
        session_title = item.text()

        self.chat_display.clear()
        self.chat_display.append(f"<hr><h2>{session_title} - history</h2><hr>")

        if not session_id:
            self.chat_display.append("<i>Error: No session ID found for this item.</i>")
            self.worker.session_id = None
            self.chat_display.append("<hr><i>[Ready - no session selected]</i><hr>")
            return

        self.worker.session_id = session_id
        self.chat_display.append("<i>Loading session history...</i>")
        full_text = OpenCodeService.get_session_messages(session_id, limit=100)
        self._on_session_messages_loaded(full_text)

    def _on_session_messages_loaded(self, full_text):
        import markdown

        if not full_text or not full_text.strip():
            self.chat_display.append("<i>No history found for this session.</i>")
            self.chat_display.append("<hr><i>[Ready - continuing session]</i><hr>")
            return

        parts = [p.strip() for p in full_text.split("\n\n") if p.strip()]
        for part in parts:
            is_user = part.startswith("You:")
            color = "#4CAF50" if is_user else "#569CD6"
            label = "You:" if is_user else "OpenCode:"
            content = part[4:].lstrip() if part.startswith("You:") else part[9:].lstrip()
            html_content = markdown.markdown(content, extensions=["fenced_code", "codehilite"])
            self.chat_display.append(
                f'<div style="margin-top:10px;margin-bottom:10px;background:#252526;'
                f'padding:10px;border-radius:5px;">'
                f'<span style="color:{color};font-weight:bold;">{label}</span><br>'
                f"{html_content}</div>"
            )
        self.chat_display.append("<hr><i>[Ready - continuing session]</i><hr>")

    def _on_session_load_error(self, error_msg):
        self.chat_display.append(
            f'<div style="color:#F44336;">&#9888; Failed to load session: {error_msg}</div>'
        )
        self.chat_display.append("<hr><i>[Ready]</i><hr>")

    # -----------------------------------------------------------------------
    # Chat area
    # -----------------------------------------------------------------------

    def setup_chat_area(self):
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(15, 15, 15, 15)
        self.right_layout.setSpacing(10)

        # Chat Display Window
        self.chat_display = QTextBrowser()
        self.chat_display.setOpenExternalLinks(True)
        self.right_layout.addWidget(self.chat_display)

        # Agent selector — in toolbar when USE_NEW_TOOLBAR, otherwise inline here
        agent_bar = QHBoxLayout()
        if not USE_NEW_TOOLBAR:
            self._selected_agent = "orchestrator"
            from PySide6.QtWidgets import QLabel as _QL
            agent_bar.addWidget(_QL("Agent:"))
            self.agent_combo = QComboBox()
            self.agent_combo.setMinimumWidth(140)
            self.agent_combo.setStyleSheet(
                "QComboBox { padding: 2px 6px; font-size: 11px; }"
            )
            pills_agents = OpenCodeService.get_agents_from_files()
            if not pills_agents:
                pills_agents = ["orchestrator"]
            for a in pills_agents:
                self.agent_combo.addItem(a)
            self.agent_combo.setCurrentText("orchestrator")
            self.agent_combo.currentTextChanged.connect(self._select_agent_pill)
            agent_bar.addWidget(self.agent_combo)

        # Mission button — right-aligned in agent bar
        self.mission_btn = QPushButton("🚀 Mission")
        self.mission_btn.setToolTip(
            "Start a PROJECT-tier autonomous mission.\n"
            "The orchestrator will create mission.json, decompose into features,\n"
            "and manage execution across sessions."
        )
        self.mission_btn.setStyleSheet(
            "QPushButton { background: #2d4a2d; color: #7dbb7d; border: 1px solid #4a7a4a; "
            "border-radius: 4px; padding: 2px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #3a5e3a; }"
            "QPushButton:disabled { background: #1a2a1a; color: #445544; }"
        )
        self.mission_btn.clicked.connect(self._send_mission_task)
        agent_bar.addWidget(self.mission_btn)

        self.right_layout.addLayout(agent_bar)

        # Input Section
        self.input_layout = QHBoxLayout()

        # Attach button - leftmost
        self.attach_button = QPushButton("📎")
        self.attach_button.setFixedSize(40, 70)
        self.attach_button.setToolTip("Attach a file to the next message")
        self.attach_button.clicked.connect(self.pick_attachment)
        self.input_layout.addWidget(self.attach_button)

        self.input_field = QTextEdit()
        self.input_field.setFixedHeight(70)
        self.input_field.setPlaceholderText(
            "Type your instruction here...\n(Shift+Enter for newline, Enter to send)"
        )
        self.input_field.installEventFilter(self)
        self.input_layout.addWidget(self.input_field)

        # Send - full height, sole button on the right
        self.send_button = QPushButton("Send")
        self.send_button.setFixedSize(90, 70)
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.clicked.connect(self.send_message)
        self.input_layout.addWidget(self.send_button)

        self.right_layout.addLayout(self.input_layout)
        self.splitter.addWidget(self.right_widget)

    def pick_attachment(self):
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(self, "Attach File")
        if path:
            self._attached_file = path
            self.attach_button.setToolTip(f"Attached: {os.path.basename(path)}")
            self.attach_button.setText("📎✓")
        else:
            self._attached_file = None
            self.attach_button.setToolTip("Attach a file to the next message")
            self.attach_button.setText("📎")

    def eventFilter(self, obj, event):
        if obj == self.input_field and event.type() == event.Type.KeyPress:
            # Enter (without Shift) → send
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self.send_message()
                return True
            # "/" typed into an empty field → show slash command palette
            if event.key() == Qt.Key_Slash and self.input_field.toPlainText().strip() == "":
                self._show_slash_menu()
                return False  # still insert the "/"
        return super().eventFilter(obj, event)

    def _show_slash_menu(self):
        from pathlib import Path

        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        builtins = {"/plan", "/status", "/undo", "/redo", "/share", "/init"}
        cmd_dir = Path(".opencode/commands")
        if cmd_dir.exists():
            for f in sorted(cmd_dir.glob("*.md")):
                builtins.add(f"/{f.stem}")
        for cmd in sorted(builtins):
            action = menu.addAction(cmd)
            action.triggered.connect(lambda checked=False, c=cmd: self._insert_slash_command(c))
        point = self.input_field.mapToGlobal(self.input_field.rect().bottomLeft())
        point.setY(point.y() - menu.sizeHint().height() - 5)
        menu.popup(point)

    def _insert_slash_command(self, cmd):
        self.input_field.setPlainText(cmd)
        self.input_field.moveCursor(QTextCursor.End)

    def toggle_low_token(self, state):
        if state == Qt.Checked.value:
            # Switch model to gemini flash if available
            flash = next(
                (m for m in self._model_list if "gemini-2.5-flash" in m and "google" in m),
                None,
            )
            if flash:
                self._selected_model = flash
                self.model_btn.setText(flash.split("/")[-1])
            # Switch agent to nano-coder
            self.agent_combo.setCurrentText("nano-coder")
            self._selected_agent = "nano-coder"
            self.statusBar().showMessage("Low Token Mode Enabled", 3000)

    @Slot()
    def send_message(self):
        text = self.input_field.toPlainText().strip()
        if text:
            # Append visually so the user sees what they sent
            self.chat_display.moveCursor(QTextCursor.End)
            html = f"""
            <div style="margin-top: 10px; margin-bottom: 10px;">
                <span style="color: #4CAF50; font-weight: bold;">You:</span><br>
                {text.replace(chr(10), "<br>")}
            </div>
            """
            self.chat_display.append(html)
            self.input_field.clear()

            selected_model = self._selected_model
            selected_agent = self._selected_agent
            self.worker.send_input(
                text,
                model=None if selected_model == "Default Model (Auto)" else selected_model,
                agent=None if selected_agent == "orchestrator" else selected_agent,
                plan_mode=self.plan_mode_check.isChecked(),
                file=self._attached_file,
                title=self._pending_title,
            )
            self._pending_title = None
            self._attached_file = None
            self.attach_button.setText("📎")
            self.attach_button.setToolTip("Attach a file to the next message")

    def _send_mission_task(self):
        """Frame the current input as a PROJECT-tier mission and send it."""
        text = self.input_field.toPlainText().strip()
        if not text:
            QMessageBox.information(
                self,
                "Mission",
                "Describe the mission in the input field first.\n\n"
                "Example: 'Build a REST API with JWT auth, rate limiting, and PostgreSQL'",
            )
            return

        mission_prompt = (
            f"This is a PROJECT-tier task.\n\n"
            f"Follow .opencode/protocols/mission-protocol.md exactly:\n"
            f"1. Read .opencode/mission.json (if exists → resume; if not → create new mission)\n"
            f"2. Read .opencode/blackboard.json\n"
            f"3. Read .opencode/protocols/healing-protocol.md\n"
            f"4. Decompose into features with a dependency DAG\n"
            f"5. Execute features one by one (parallel where possible)\n\n"
            f"Mission description:\n{text}"
        )

        self.input_field.setPlainText(mission_prompt)
        self.send_message()

        # Show mission status (dialog in new sidebar, tab in legacy)
        if USE_NEW_SIDEBAR:
            self._show_mission_dialog()
        else:
            for i in range(self.sidebar_tabs.count()):
                if self.sidebar_tabs.tabText(i) == "Mission":
                    self.sidebar_tabs.setCurrentIndex(i)
                    break

    # -----------------------------------------------------------------------
    # Worker signal handlers
    # -----------------------------------------------------------------------

    @Slot(str)
    def handle_text(self, text):
        import markdown

        self.chat_display.moveCursor(QTextCursor.End)
        html = markdown.markdown(text, extensions=["fenced_code", "codehilite"])
        formatted = (
            '<div style="margin-top:10px;margin-bottom:10px;background:#252526;'
            'padding:10px;border-radius:5px;">'
            '<span style="color:#569CD6;font-weight:bold;">OpenCode:</span><br>'
            f"{html}</div>"
        )
        self.chat_display.append(formatted)
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    @Slot(str)
    @Slot(str, str)
    def handle_tool_start(self, tool_name, details):
        self.chat_display.moveCursor(QTextCursor.End)
        self.chat_display.append(
            f'<div style="color:#9cdcfe;margin-left:20px;font-style:italic;font-size:12px;">'
            f"&#9881; Running tool: <b>{tool_name}</b>...</div>"
        )

    @Slot(str)
    def handle_tool_finish(self, tool_name):
        self.chat_display.moveCursor(QTextCursor.End)
        self.chat_display.append(
            f'<div style="color:#4CAF50;margin-left:20px;font-size:12px;">'
            f"&#10003; Tool <b>{tool_name}</b> completed.</div>"
        )

    @Slot(str)
    def handle_error(self, error_msg):
        self.chat_display.moveCursor(QTextCursor.End)
        self.chat_display.append(
            f'<div style="color:#F44336;margin-top:5px;">&#9888; Error: {error_msg}</div>'
        )

    @Slot(int)
    def handle_finished(self, returncode):
        if returncode != 0:
            self.chat_display.append(
                f"<br><b style='color:#F44336;'>[Process exited with code {returncode}]</b>"
            )

    def _on_worker_started(self):
        self.send_button.setEnabled(False)
        self.send_button.setText("…")
        self.input_field.setEnabled(False)
        self.mission_btn.setEnabled(False)
        from PySide6.QtCore import QElapsedTimer

        self._exec_timer = QElapsedTimer()
        self._exec_timer.start()
        self._exec_tick = QTimer(self)
        self._exec_tick.timeout.connect(self._update_exec_timer)
        self._exec_tick.start(1000)

    def _update_exec_timer(self):
        elapsed = self._exec_timer.elapsed() / 1000
        self.statusBar().showMessage(f"Running… {elapsed:.0f}s")

    def _on_worker_done(self):
        self.send_button.setEnabled(True)
        self.send_button.setText("Send")
        self.input_field.setEnabled(True)
        self.input_field.setFocus()
        self.mission_btn.setEnabled(True)
        self.refresh_mission()
        if hasattr(self, "_exec_tick") and self._exec_tick:
            self._exec_tick.stop()
        elapsed = self._exec_timer.elapsed() / 1000 if hasattr(self, "_exec_timer") else 0
        self.statusBar().showMessage(f"Done in {elapsed:.1f}s")

    # -----------------------------------------------------------------------
    # Toolbar actions
    # -----------------------------------------------------------------------

    def open_external_terminal(self, command):
        import subprocess

        try:
            subprocess.Popen(f'start cmd /c "opencode.cmd {command} & pause"', shell=True)
        except Exception as e:
            self.handle_error(f"Failed to launch external terminal: {e}")

    def run_providers(self):
        dialog = ProvidersDialog(self)
        dialog.exec()

    def run_agents(self):
        from pathlib import Path

        from PySide6.QtWidgets import QDialog, QTabWidget, QTextEdit, QVBoxLayout

        agent_dir = Path(os.getcwd()) / ".opencode" / "agent"
        dialog = QDialog(self)
        dialog.setWindowTitle("Agents")
        dialog.resize(700, 500)
        dlg_layout = QVBoxLayout(dialog)
        tabs = QTabWidget()
        if agent_dir.exists():
            for md_file in sorted(agent_dir.glob("*.md")):
                try:
                    content = md_file.read_text(encoding="utf-8")
                except Exception as exc:
                    content = f"Error reading {md_file.name}: {exc}"
                text_edit = QTextEdit()
                text_edit.setReadOnly(True)
                text_edit.setPlainText(content)
                text_edit.setStyleSheet(
                    "font-family: monospace; background: #1e1e1e; color: #d4d4d4;"
                )
                tabs.addTab(text_edit, md_file.stem)
        else:
            placeholder = QTextEdit()
            placeholder.setReadOnly(True)
            placeholder.setPlainText("No .opencode/agent/ directory found.")
            dlg_layout.addWidget(placeholder)
        dlg_layout.addWidget(tabs)
        dialog.exec()

    def run_sessions(self):
        for i in range(self.sidebar_tabs.count()):
            if self.sidebar_tabs.tabText(i) == "Sessions":
                self.sidebar_tabs.setCurrentIndex(i)
                break

    def run_mcp(self):
        dialog = McpDialog(self)
        dialog.exec()

    def run_github(self):
        QMessageBox.information(
            self,
            "GitHub Integration",
            "GitHub integration is managed via the OpenCode CLI.\n\n"
            "To authenticate, run in a terminal:\n"
            "  opencode.cmd auth github\n\n"
            "Or configure your GitHub token in the Providers dialog.",
        )

    def run_stats(self):
        dialog = StatsDialog(self)
        dialog.exec()

    def run_undo(self):
        self.worker.send_input("/undo", slash_command=True)

    def run_redo(self):
        self.worker.send_input("/redo", slash_command=True)

    # -----------------------------------------------------------------------
    # Model menu + agent pill helpers
    # -----------------------------------------------------------------------

    def _show_model_menu(self):
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)

        # Default option
        default_action = menu.addAction("Default Model (Auto)")
        default_action.triggered.connect(lambda: self._select_model("Default Model (Auto)"))
        menu.addSeparator()

        # Group models by provider prefix
        groups: dict = {}
        for m in self._model_list:
            provider = m.split("/")[0] if "/" in m else "other"
            groups.setdefault(provider, []).append(m)

        for provider in sorted(groups):
            submenu = menu.addMenu(provider.capitalize())
            for model in groups[provider]:
                label = model.split("/", 1)[1] if "/" in model else model
                action = submenu.addAction(label)
                action.triggered.connect(lambda checked=False, mod=model: self._select_model(mod))

        menu.exec(self.model_btn.mapToGlobal(self.model_btn.rect().bottomLeft()))

    def _select_model(self, model_str):
        self._selected_model = model_str
        if model_str == "Default Model (Auto)":
            self.model_btn.setText("Default Model (Auto)")
        else:
            label = model_str.split("/", 1)[1] if "/" in model_str else model_str
            self.model_btn.setText(label[:30] + "…" if len(label) > 30 else label)

    def _select_agent_pill(self, agent_name):
        self._selected_agent = agent_name

    # -----------------------------------------------------------------------
    # Async load helpers for models / agents
    # -----------------------------------------------------------------------

    def refresh_models(self):
        self._refresh_model_current = self._selected_model
        self.model_btn.setText("Refreshing…")
        self._models_worker = ServiceWorker(OpenCodeService.get_models)
        self._models_worker.result_ready.connect(self._on_models_loaded)
        self._models_worker.error_occurred.connect(
            lambda e: self.statusBar().showMessage(f"Models load error: {e}", 3000)
        )
        self._models_worker.start()

    def _load_models_async(self):
        self._models_worker = ServiceWorker(OpenCodeService.get_models)
        self._models_worker.result_ready.connect(self._on_models_loaded)
        self._models_worker.error_occurred.connect(
            lambda e: self.statusBar().showMessage(f"Models load error: {e}", 3000)
        )
        self._models_worker.start()

    def _on_models_loaded(self, models):
        self._model_list = models
        # Restore preferred selection if refresh_models() saved one
        preferred = getattr(self, "_refresh_model_current", None)
        if preferred and preferred != "Default Model (Auto)" and preferred in models:
            self._select_model(preferred)
        self._refresh_model_current = None

    def _load_agents_async(self):
        # Agents are loaded synchronously from files in setup_chat_area() -
        # this async path is no longer needed but kept for the QTimer trigger
        pass

    def _on_agents_loaded(self, agents):
        # Pills are already built in setup_chat_area(); nothing to do here
        pass

    # ── Plots Tab ───────────────────────────────────────────────────────

    def _refresh_plots_list(self):
        """Scan project for .png files and populate the plots list."""
        self.plots_list.clear()
        scan_dirs = [
            (os.getcwd(), ""),
            (os.path.join(os.getcwd(), "logs"), "logs/"),
        ]
        from pathlib import Path

        found = []
        for base_dir, prefix in scan_dirs:
            if not os.path.isdir(base_dir):
                continue
            for f in sorted(Path(base_dir).glob("*.png"), key=os.path.getmtime, reverse=True):
                display = prefix + f.name
                found.append((str(f), display))

        if not found:
            self.plots_list.addItem("(no plots found)")
            self.plot_preview.setText("No plot files found.\nRun LCN tests to generate plots.")
            self.plots_open_btn.setEnabled(False)
            return

        for full_path, display in found:
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, full_path)
            self.plots_list.addItem(item)

        # Auto-select first
        self.plots_list.setCurrentRow(0)
        if found:
            self._show_plot_preview(self.plots_list.item(0))
            self.plots_open_btn.setEnabled(True)

    def _show_plot_preview(self, item):
        """Load and display the selected image in the preview label."""
        from PySide6.QtGui import QPixmap

        full_path = item.data(Qt.UserRole)
        if not full_path or not os.path.exists(full_path):
            self.plot_preview.setText("(file not found)")
            self.plots_open_btn.setEnabled(False)
            return

        pixmap = QPixmap(full_path)
        if pixmap.isNull():
            self.plot_preview.setText(f"(cannot load: {item.text()})")
            self.plots_open_btn.setEnabled(False)
            return

        # Scale to fit preview area while maintaining aspect ratio
        max_w = self.plot_preview.width() - 16
        max_h = self.plot_preview.height() - 16
        scaled = pixmap.scaled(
            max(max_w, 50), max(max_h, 50),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.plot_preview.setPixmap(scaled)
        self.plot_preview.setText("")  # clear placeholder text
        self.plots_open_btn.setEnabled(True)

    def _open_plot_external(self):
        """Open the currently selected plot in the default image viewer."""
        item = self.plots_list.currentItem()
        if not item:
            return
        full_path = item.data(Qt.UserRole)
        if full_path and os.path.exists(full_path):
            os.startfile(full_path)

    def new_session(self):
        from PySide6.QtWidgets import QInputDialog

        title, ok = QInputDialog.getText(self, "New Session", "Session title (optional):")
        self.worker.session_id = None
        self.chat_display.clear()
        display_title = title.strip() if ok and title.strip() else "New session"
        self.chat_display.append(f"<hr><i>{display_title} started.</i><hr>")
        self._pending_title = title.strip() if ok and title.strip() else None

    def fork_session(self):
        item = self.session_list.currentItem()
        if not item:
            return
        from PySide6.QtWidgets import QInputDialog

        title, ok = QInputDialog.getText(self, "Fork Session", "New session title (optional):")
        self.worker.session_id = item.data(Qt.UserRole)
        self.chat_display.clear()
        self.chat_display.append("<hr><i>Forking session...</i><hr>")
        self.worker.send_input(
            "Continue from here.",
            fork=True,
            title=title.strip() if ok and title.strip() else None,
        )
        QTimer.singleShot(500, self.refresh_sessions)

    # -----------------------------------------------------------------------
    # Mission tab
    # -----------------------------------------------------------------------

    def _setup_mission_tab(self):
        from PySide6.QtWidgets import (
            QHeaderView,
            QLabel,
            QProgressBar,
            QPushButton,
            QTableWidget,
        )

        # Status row
        status_row = QHBoxLayout()
        self.mission_title_label = QLabel("No active mission")
        self.mission_title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.mission_status_badge = QLabel("")
        status_row.addWidget(self.mission_title_label)
        status_row.addStretch()
        status_row.addWidget(self.mission_status_badge)
        self.mission_layout.addLayout(status_row)

        # Feature table
        self.mission_table = QTableWidget(0, 3)
        self.mission_table.setHorizontalHeaderLabels(["Feature", "Status", ""])
        self.mission_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.mission_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.mission_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.mission_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.mission_layout.addWidget(self.mission_table)

        # Error budget bar
        budget_row = QHBoxLayout()
        budget_label = QLabel("Error budget:")
        self.mission_budget_bar = QProgressBar()
        self.mission_budget_bar.setRange(0, 100)
        self.mission_budget_bar.setTextVisible(True)
        budget_row.addWidget(budget_label)
        budget_row.addWidget(self.mission_budget_bar)
        self.mission_layout.addLayout(budget_row)

        # Buttons
        btn_row = QHBoxLayout()
        self.mission_resume_btn = QPushButton("Resume Mission")
        self.mission_resume_btn.clicked.connect(self._resume_mission)
        self.mission_clear_btn = QPushButton("Clear Mission")
        self.mission_clear_btn.clicked.connect(self._clear_mission)
        btn_row.addWidget(self.mission_resume_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.mission_clear_btn)
        self.mission_layout.addLayout(btn_row)

        # ── Diagnostics section (removed — LCN module was archived) ──
        diag_placeholder = QLabel("📊 Diagnostics removed — LCN module was archived")
        diag_placeholder.setStyleSheet("font-size: 11px; color: #888; margin-top: 6px;")
        self.mission_layout.addWidget(diag_placeholder)

        # ── Error log display ──
        error_label = QLabel("Recent errors:")
        error_label.setStyleSheet("font-size: 11px; color: #888; margin-top: 4px;")
        self.mission_error_log = QTextEdit()
        self.mission_error_log.setReadOnly(True)
        self.mission_error_log.setMaximumHeight(100)
        self.mission_error_log.setStyleSheet(
            "QTextEdit { background: #1e1e1e; color: #F44336; border: 1px solid #3c3c3c; "
            "border-radius: 3px; padding: 4px; font-size: 10px; font-family: monospace; }"
        )
        self.mission_layout.addWidget(error_label)
        self.mission_layout.addWidget(self.mission_error_log)

        self.mission_layout.addStretch()
        self._prev_mission_status = None
        self.refresh_mission()

        # Auto-refresh timer: fires every 2s but only refreshes when tab is visible
        self.mission_timer = QTimer(self)
        self.mission_timer.timeout.connect(self._refresh_mission_if_visible)
        self.mission_timer.start(2000)

    def refresh_mission(self):
        import json
        from pathlib import Path

        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QTableWidgetItem

        mission_path = Path(os.getcwd()) / ".opencode" / "mission.json"
        if not mission_path.exists():
            self.mission_title_label.setText("No active mission")
            self.mission_status_badge.setText("")
            self.mission_table.setRowCount(0)
            self.mission_budget_bar.setValue(0)
            self.mission_budget_bar.setFormat("No mission")
            self.mission_resume_btn.setEnabled(False)
            self.mission_clear_btn.setEnabled(False)
            return

        try:
            mission = json.loads(mission_path.read_text(encoding="utf-8"))
        except Exception:
            self.mission_title_label.setText("mission.json unreadable")
            return

        # Status badge
        status = mission.get("status", "unknown")
        # Flash tab if mission status changed
        if self._prev_mission_status is not None and self._prev_mission_status != status:
            self._flash_mission_tab()
        self._prev_mission_status = status

        status_colors = {
            "planning": "#f0ad4e",
            "in_progress": "#5bc0de",
            "degraded": "#d9534f",
            "complete": "#5cb85c",
        }
        color = status_colors.get(status, "#999")
        self.mission_title_label.setText(mission.get("title", "Untitled Mission"))
        self.mission_status_badge.setText(f"  {status.upper()}  ")
        self.mission_status_badge.setStyleSheet(
            f"background: {color}; color: white; padding: 2px 6px; border-radius: 3px;"
        )

        # Feature table
        features = mission.get("features", [])
        self.mission_table.setRowCount(len(features))
        status_icons = {
            "pending": "⏳",
            "in_progress": "🔄",
            "done": "✅",
            "failed": "❌",
            "skipped": "⏭",
        }
        for row, feat in enumerate(features):
            self.mission_table.setItem(
                row, 0, QTableWidgetItem(feat.get("title", feat.get("id", "")))
            )
            feat_status = feat.get("status", "pending")
            self.mission_table.setItem(row, 1, QTableWidgetItem(feat_status))
            self.mission_table.setItem(row, 2, QTableWidgetItem(status_icons.get(feat_status, "?")))
            if feat_status == "done":
                for col in range(3):
                    it = self.mission_table.item(row, col)
                    if it:
                        it.setForeground(QColor("#5cb85c"))
            elif feat_status == "failed":
                for col in range(3):
                    it = self.mission_table.item(row, col)
                    if it:
                        it.setForeground(QColor("#d9534f"))

        # Error budget bar
        budget = mission.get("error_budget", {})
        used = budget.get("failures_used", 0)
        max_f = budget.get("max_feature_failures", 3)
        pct = int((used / max(max_f, 1)) * 100)
        self.mission_budget_bar.setValue(pct)
        self.mission_budget_bar.setFormat(f"{used}/{max_f} failures used")
        if pct >= 75:
            self.mission_budget_bar.setStyleSheet("QProgressBar::chunk { background: #d9534f; }")
        elif pct >= 50:
            self.mission_budget_bar.setStyleSheet("QProgressBar::chunk { background: #f0ad4e; }")
        else:
            self.mission_budget_bar.setStyleSheet("")

        self.mission_resume_btn.setEnabled(status == "in_progress")
        self.mission_clear_btn.setEnabled(True)

        # Update toolbar indicator
        mission_title = mission.get("title", "No mission")[:30]
        self.mission_indicator.setText(f"Mission: {status}")
        self.mission_indicator.setStyleSheet(
            f"color: {color}; font-size: 11px; padding: 0 6px;"
        )
        self.mission_indicator.setToolTip(f"{mission_title}\nStatus: {status}")

    def _refresh_mission_if_visible(self):
        """Refresh mission data (always in new sidebar, only when visible in legacy)."""
        if USE_NEW_SIDEBAR:
            self.refresh_mission()
            self._update_error_log()
        elif self.sidebar_tabs.currentWidget() == self.mission_tab:
            self.refresh_mission()
            self._update_error_log()

    def _update_error_log(self):
        """Read the last 5 lines from error-log.jsonl and display them."""
        import json
        from pathlib import Path

        log_path = Path(os.getcwd()) / ".opencode" / "error-log.jsonl"
        if not log_path.exists():
            self.mission_error_log.setText("(no error log)")
            return

        try:
            lines = log_path.read_text(encoding="utf-8").strip().splitlines()
            last = lines[-5:] if len(lines) >= 5 else lines
            parts = []
            for line in last:
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp", "?")[:19]
                    etype = entry.get("error_type", "?")
                    ctx = entry.get("context", "?")
                    parts.append(f"[{ts}] {etype}: {ctx[:80]}")
                except json.JSONDecodeError:
                    parts.append(line.strip()[:100])
            self.mission_error_log.setText("\n".join(parts) if parts else "(no errors)")
        except Exception as e:
            self.mission_error_log.setText(f"(read error: {e})")

    def _flash_mission_tab(self):
        """Briefly change the Mission tab label color to indicate status change."""
        if USE_NEW_SIDEBAR:
            return  # No tab to flash in new sidebar
        for i in range(self.sidebar_tabs.count()):
            if self.sidebar_tabs.tabText(i) == "Mission":
                tab_bar = self.sidebar_tabs.tabBar()
                tab_bar.setTabTextColor(i, QColor("#FFA500"))
                QTimer.singleShot(1000, lambda idx=i: self._revert_tab_color(idx))
                break

    def _revert_tab_color(self, index):
        """Revert Mission tab label color back to default."""
        if USE_NEW_SIDEBAR:
            return
        self.sidebar_tabs.tabBar().setTabTextColor(index, QColor("#d4d4d4"))

    # -----------------------------------------------------------------------
    # Repo Map tab
    # -----------------------------------------------------------------------

    def _setup_repomap_tab(self):
        """Set up the Repo Map sidebar tab with a project file tree view."""
        self.repomap_widget = QWidget()
        repomap_layout = QVBoxLayout(self.repomap_widget)
        repomap_layout.setContentsMargins(0, 0, 0, 0)

        # Header row with refresh button
        header_row = QHBoxLayout()
        repomap_title = QLabel("Project File Map")
        repomap_title.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px;")
        self.repomap_refresh_btn = QPushButton("🔄")
        self.repomap_refresh_btn.setFixedWidth(32)
        self.repomap_refresh_btn.setToolTip("Rescan file structure")
        self.repomap_refresh_btn.clicked.connect(self._refresh_repomap)
        header_row.addWidget(repomap_title)
        header_row.addStretch()
        header_row.addWidget(self.repomap_refresh_btn)
        repomap_layout.addLayout(header_row)

        # Tree view
        self.repomap_tree = QTreeView()
        self.repomap_tree.setHeaderHidden(True)
        self.repomap_tree.setAnimated(True)
        self.repomap_tree.setIndentation(16)
        repomap_layout.addWidget(self.repomap_tree)

        self._refresh_repomap()
        self.sidebar_tabs.addTab(self.repomap_widget, "Repo Map")

    def _refresh_repomap(self):
        """Rebuild the repo map tree model from the filesystem."""
        model = self._build_repomap_model(os.getcwd())
        self.repomap_tree.setModel(model)
        self.repomap_tree.expandToDepth(0)

    def _build_repomap_model(self, root_path):
        """Build a QStandardItemModel from the directory tree, respecting .gitignore."""
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Name"])
        root_item = model.invisibleRootItem()
        gitignore_patterns = self._parse_gitignore(root_path)
        self._add_dir_to_model(root_item, root_path, root_path, gitignore_patterns)
        return model

    def _add_dir_to_model(self, parent_item, base_path, dir_path, gitignore_patterns):
        """Recursively add directory entries to the tree model."""
        import fnmatch

        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return

        for entry in entries:
            full_path = os.path.join(dir_path, entry)
            rel_path = os.path.relpath(full_path, base_path).replace("\\", "/")
            is_dir = os.path.isdir(full_path)

            # Check against gitignore patterns
            ignored = False
            for pattern in gitignore_patterns:
                stripped = pattern.rstrip("/")
                if fnmatch.fnmatch(entry, stripped) or fnmatch.fnmatch(rel_path, stripped):
                    ignored = True
                    break

            item = QStandardItem(entry)
            item.setEditable(False)

            if ignored:
                item.setForeground(QColor("#555555"))
                item.setToolTip("Ignored by .gitignore")
            elif is_dir:
                item.setForeground(QColor("#569CD6"))
            else:
                item.setForeground(QColor("#cccccc"))

            if is_dir:
                self._add_dir_to_model(item, base_path, full_path, gitignore_patterns)

            parent_item.appendRow(item)

    @staticmethod
    def _parse_gitignore(root_path):
        """Parse .gitignore file and return a list of patterns."""
        patterns = []
        gitignore_path = os.path.join(root_path, ".gitignore")
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            if line.startswith("/"):
                                line = line[1:]
                            patterns.append(line)
            except Exception:
                pass
        return patterns

    def _resume_mission(self):
        """Inject resume.json content as the next message to send."""
        import json
        from pathlib import Path

        resume_path = Path(os.getcwd()) / ".opencode" / "resume.json"
        mission_path = Path(os.getcwd()) / ".opencode" / "mission.json"

        if resume_path.exists():
            try:
                resume = json.loads(resume_path.read_text(encoding="utf-8"))
                summary = resume.get("context_summary", "")
                resume_from = resume.get("resume_from", "")
                msg = f"Resume mission. Resume from: {resume_from}. Context: {summary}"
                self.input_field.setPlainText(msg)
                self.input_field.setFocus()
            except Exception:
                self.input_field.setPlainText(
                    "Resume mission from where we left off. Read .opencode/mission.json first."
                )
        elif mission_path.exists():
            self.input_field.setPlainText(
                "Resume mission from where we left off. Read .opencode/mission.json first."
            )

    def _clear_mission(self):
        """Delete mission.json and resume.json after confirmation."""
        from pathlib import Path

        reply = QMessageBox.question(
            self,
            "Clear Mission",
            "Delete mission.json and resume.json? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            for fname in ["mission.json", "resume.json"]:
                p = Path(os.getcwd()) / ".opencode" / fname
                if p.exists():
                    p.unlink()
            self.refresh_mission()

    # -----------------------------------------------------------------------
    # Phase 1 helpers: menus, dialogs, toggles
    # -----------------------------------------------------------------------

    def _show_preferences(self):
        """Placeholder Preferences dialog."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Preferences")
        dlg.resize(400, 250)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Preferences will be available in a future update."))
        layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)
        dlg.exec()

    def _show_about(self):
        """About OpenCode dialog."""
        QMessageBox.about(
            self,
            "About OpenCode",
            "<h3>OpenCode GUI</h3>"
            "<p>Version 0.2</p>"
            "<p>A PySide6 desktop interface for OpenCode CLI.</p>"
            "<p>22-agent multi-agent system for AI-assisted development.</p>"
        )

    def _show_shortcuts(self):
        """Keyboard Shortcuts reference dialog."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Keyboard Shortcuts")
        dlg.resize(450, 400)
        layout = QVBoxLayout(dlg)

        text = (
            "<h3>General</h3>"
            "<pre>"
            "Ctrl+N      New Session\n"
            "Ctrl+Q      Quit\n"
            "Ctrl+B      Toggle Sidebar\n"
            "Ctrl+J      Toggle Status Panel\n"
            "Ctrl+/      Show this dialog\n"
            "F5          Refresh\n"
            "</pre>"
            "<h3>Chat</h3>"
            "<pre>"
            "Enter       Send message\n"
            "Shift+Enter Newline\n"
            "</pre>"
            "<h3>Editing</h3>"
            "<pre>"
            "Ctrl+Z      Undo last changes\n"
            "Ctrl+Y      Redo\n"
            "</pre>"
        )
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)
        dlg.exec()

    def _toggle_sidebar_visibility(self):
        """Toggle sidebar visibility (Ctrl+B)."""
        if not USE_NEW_SIDEBAR:
            return
        visible = self.sidebar_tabs.isVisible()
        self.sidebar_tabs.setVisible(not visible)
        if hasattr(self, "_act_toggle_sidebar"):
            self._act_toggle_sidebar.setChecked(not visible)

    def _toggle_status_panel(self):
        """Toggle bottom status panel (Ctrl+B shortcut, placeholder for Phase 2)."""
        if hasattr(self, "_act_toggle_status"):
            self._act_toggle_status.setChecked(
                not self._act_toggle_status.isChecked()
            )

    def _show_mission_dialog(self):
        """Open mission status in a standalone dialog (new sidebar has no Mission tab)."""
        import json
        from pathlib import Path

        dlg = QDialog(self)
        dlg.setWindowTitle("Mission Status")
        dlg.resize(550, 450)
        layout = QVBoxLayout(dlg)

        mission_path = Path(os.getcwd()) / ".opencode" / "mission.json"
        if not mission_path.exists():
            layout.addWidget(QLabel("No active mission."))
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dlg.accept)
            layout.addWidget(close_btn)
            dlg.exec()
            return

        try:
            mission = json.loads(mission_path.read_text(encoding="utf-8"))
            title = mission.get("title", "Untitled Mission")
            status = mission.get("status", "unknown")
            features = mission.get("features", [])

            title_label = QLabel(f"<b>{title}</b>  <i>({status})</i>")
            layout.addWidget(title_label)

            feat_text = QLabel()
            feat_html = "<ul>"
            for feat in features:
                fstatus = feat.get("status", "pending")
                fname = feat.get("title", feat.get("id", "?"))
                icon = {"done": "✅", "failed": "❌", "in_progress": "🔄",
                        "pending": "⏳", "skipped": "⏭"}.get(fstatus, "❓")
                feat_html += f"<li>{icon} {fname} — <i>{fstatus}</i></li>"
            feat_html += "</ul>"
            feat_text.setText(feat_html)
            layout.addWidget(feat_text)

            btn_row = QHBoxLayout()
            resume_btn = QPushButton("Resume Mission")
            resume_btn.clicked.connect(lambda: (self._resume_mission(), dlg.accept()))
            clear_btn = QPushButton("Clear Mission")
            clear_btn.clicked.connect(self._clear_mission)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dlg.accept)
            btn_row.addWidget(resume_btn)
            btn_row.addStretch()
            btn_row.addWidget(clear_btn)
            btn_row.addWidget(close_btn)
            layout.addLayout(btn_row)
        except Exception as e:
            layout.addWidget(QLabel(f"Error reading mission: {e}"))
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dlg.accept)
            layout.addWidget(close_btn)

        dlg.exec()

    # -----------------------------------------------------------------------
    # Close
    # -----------------------------------------------------------------------

    def closeEvent(self, event):
        # Stop all background ServiceWorker threads gracefully
        for attr in (
            "_models_worker",
            "_agents_worker",
            "_sessions_worker",
            "_session_load_worker",
        ):
            w = getattr(self, attr, None)
            if w and w.isRunning():
                w.quit()
                w.wait(2000)

        self.worker.stop()
        self.worker.wait()
        super().closeEvent(event)

