import json
import subprocess
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


def get_auth_json_path():
    # Typically ~/.local/share/opencode/auth.json on Windows/Linux
    home = Path.home()
    return home / ".local" / "share" / "opencode" / "auth.json"


class ProvidersDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Providers (auth.json)")
        self.resize(500, 300)
        self.auth_path = get_auth_json_path()
        self.auth_data = self.load_auth()

        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        # Supported providers
        self.providers = [
            "google",
            "anthropic",
            "openai",
            "perplexity",
            "deepseek",
            "openrouter",
        ]
        self.inputs = {}

        for provider in self.providers:
            line_edit = QLineEdit()
            line_edit.setEchoMode(QLineEdit.Password)

            # Populate if exists
            if provider in self.auth_data and "key" in self.auth_data[provider]:
                line_edit.setText(self.auth_data[provider]["key"])

            self.inputs[provider] = line_edit
            self.form_layout.addRow(QLabel(f"{provider.capitalize()} API Key:"), line_edit)

        self.layout.addLayout(self.form_layout)

        # Buttons
        self.btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_auth)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.save_btn)
        self.btn_layout.addWidget(self.cancel_btn)

        self.layout.addLayout(self.btn_layout)

    def load_auth(self):
        try:
            if self.auth_path.exists():
                with open(self.auth_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading auth.json: {e}")
        return {}

    def save_auth(self):
        # Update auth_data
        for provider in self.providers:
            key = self.inputs[provider].text().strip()
            if key:
                if provider not in self.auth_data:
                    self.auth_data[provider] = {"type": "api"}
                self.auth_data[provider]["key"] = key
            else:
                # Remove if empty
                if provider in self.auth_data:
                    del self.auth_data[provider]

        try:
            # Ensure dir exists
            self.auth_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.auth_path, "w", encoding="utf-8") as f:
                json.dump(self.auth_data, f, indent=2)
            QMessageBox.information(self, "Success", "Providers updated successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save auth.json:\n{e}")


class StatsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Token Usage & Statistics")
        self.resize(600, 400)
        layout = QVBoxLayout(self)

        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setStyleSheet(
            "font-family: monospace; background-color: #1e1e1e; color: #d4d4d4;"
        )
        layout.addWidget(self.text_display)

        self.text_display.setText("Loading stats…")
        QTimer.singleShot(0, self._load_async)

    @staticmethod
    def _fetch_stats():
        import re

        process = subprocess.Popen(
            "opencode.cmd stats",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout, _ = process.communicate(timeout=30)
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", stdout)

    def _load_async(self):
        from core.service_worker import ServiceWorker

        self._worker = ServiceWorker(self._fetch_stats)
        self._worker.result_ready.connect(self.text_display.setText)
        self._worker.error_occurred.connect(
            lambda e: self.text_display.setText(f"Error loading stats:\n{e}")
        )
        self._worker.start()


class McpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MCP Servers Manager")
        self.resize(600, 400)
        layout = QVBoxLayout(self)

        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setStyleSheet(
            "font-family: monospace; background-color: #1e1e1e; color: #d4d4d4;"
        )
        layout.addWidget(self.text_display)

        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_mcp)
        self.add_btn = QPushButton("Add MCP Server")
        self.add_btn.clicked.connect(self.add_mcp)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.add_btn)
        layout.addLayout(btn_layout)

        self.text_display.setText("Loading MCP servers…")
        QTimer.singleShot(0, self.load_mcp)

    @staticmethod
    def _fetch_mcp():
        import re

        process = subprocess.Popen(
            "opencode.cmd mcp list",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout, _ = process.communicate(timeout=30)
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", stdout)

    def load_mcp(self):
        self.text_display.setText("Loading MCP servers…")
        from core.service_worker import ServiceWorker

        self._worker = ServiceWorker(self._fetch_mcp)
        self._worker.result_ready.connect(self.text_display.setText)
        self._worker.error_occurred.connect(
            lambda e: self.text_display.setText(f"Error loading MCP servers:\n{e}")
        )
        self._worker.start()

    def add_mcp(self):
        url, ok = QInputDialog.getText(
            self,
            "Add MCP Server",
            "Enter the exact start command or url for the MCP server:",
        )
        if ok and url:
            try:
                # Sanitize URL: only allow safe URL characters to prevent command injection
                import re
                safe_url = re.sub(r'[^a-zA-Z0-9:/._\-?=&%+#]', '', url)
                subprocess.Popen(f'start cmd /c "opencode.cmd mcp add {safe_url} & pause"', shell=True)
                QMessageBox.information(
                    self,
                    "Success",
                    "MCP add command launched. Refresh this view once completed.",
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to launch command:\n{e}")
