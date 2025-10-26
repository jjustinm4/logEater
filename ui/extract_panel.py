from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog,
    QHBoxLayout, QTextEdit, QComboBox, QMessageBox, QScrollArea, QFrame,
    QToolButton, QGroupBox, QCheckBox, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer
from pathlib import Path
import json
from typing import Dict, Any, List, DefaultDict
from collections import defaultdict

from core.extract.extract_service import ExtractService
from core.ai.insight_service import InsightService


# ---------------- AI Worker ----------------
class AIWorker(QObject):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, insight_service: InsightService, text: str):
        super().__init__()
        self.svc = insight_service
        self.text = text

    def run(self):
        try:
            out = self.svc.summarize_text(self.text)
            self.finished.emit(out)
        except Exception as e:
            self.error.emit(str(e))


# ---------------- Collapsible Group (unchanged) ----------------
class CollapsibleGroup(QGroupBox):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setTitle("")
        self._main = QVBoxLayout(self)
        self._main.setContentsMargins(0, 0, 0, 0)

        self._header = QToolButton()
        self._header.setStyleSheet("QToolButton { border: none; font-weight: 600; }")
        self._header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._header.setArrowType(Qt.RightArrow)
        self._header.setText(title)
        self._header.setCheckable(True)
        self._header.setChecked(False)
        self._header.toggled.connect(self._on_toggled)

        self._content = QWidget()
        self._content.setVisible(False)
        self._content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.content_layout = QVBoxLayout(self._content)
        self.content_layout.setContentsMargins(12, 4, 4, 8)
        self.content_layout.setSpacing(4)

        self._main.addWidget(self._header)
        self._main.addWidget(self._content)
        self.extract_service = ExtractService()

    def _on_toggled(self, checked: bool):
        self._header.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self._content.setVisible(checked)


# ---------------- Extract Panel (Main UI) ----------------
class ExtractPanel(QWidget):
    def __init__(self):
        super().__init__()

        self.extract_service = ExtractService()
        self.insight_service = InsightService(model="llama3:latest")

        self.thread = None
        self.ai_worker = None
        self._dot_timer = None
        self._dot_state = 0
        self.checkbox_map: Dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Extract Panel"))

        # Folder picker
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select folder for extraction...")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_folder)
        fl = QHBoxLayout()
        fl.addWidget(self.folder_input)
        fl.addWidget(browse_btn)
        layout.addLayout(fl)

        # Schema selector
        self.schema_selector = QComboBox()
        self.schema_selector.addItem("Select schema...")
        refresh_btn = QPushButton("Refresh Schemas")
        refresh_btn.clicked.connect(self.refresh_schemas)
        load_fields_btn = QPushButton("Load Fields")
        load_fields_btn.clicked.connect(self.load_fields_from_schema)
        sl = QHBoxLayout()
        sl.addWidget(QLabel("Schema:"))
        sl.addWidget(self.schema_selector)
        sl.addWidget(refresh_btn)
        sl.addWidget(load_fields_btn)
        layout.addLayout(sl)

        # Field selection scroll
        self.fields_scroll = QScrollArea()
        self.fields_scroll.setWidgetResizable(True)
        self.fields_container = QWidget()
        self.fields_layout = QVBoxLayout(self.fields_container)
        self.fields_scroll.setWidget(self.fields_container)
        layout.addWidget(QLabel("Schema Fields"))
        layout.addWidget(self.fields_scroll)

        # Format selector
        self.format_selector = QComboBox()
        self.format_selector.addItems(["TXT", "JSON"])
        fmtrow = QHBoxLayout()
        fmtrow.addWidget(QLabel("Output Format:"))
        fmtrow.addWidget(self.format_selector)
        fmtrow.addStretch()
        layout.addLayout(fmtrow)

        # Buttons row
        btn_row = QHBoxLayout()
        extract_btn = QPushButton("Extract")
        extract_btn.clicked.connect(self.extract_data)

        self.ai_btn = QPushButton("Generate AI Insight")
        self.ai_btn.clicked.connect(self.generate_ai_insight)
        self.ai_btn.setEnabled(False)

        self.export_ai_btn = QPushButton("Export Insight")
        self.export_ai_btn.clicked.connect(self.export_ai_insight)
        self.export_ai_btn.setEnabled(False)

        btn_row.addWidget(extract_btn)
        btn_row.addWidget(self.ai_btn)
        btn_row.addWidget(self.export_ai_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)


        # Extraction output
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setPlaceholderText("Extraction summary will be shown here...")
        layout.addWidget(self.result_area)

        # AI progress + AI output box (at bottom)
        self.ai_progress = QLabel("")
        self.ai_progress.setAlignment(Qt.AlignCenter)
        self.ai_progress.setVisible(False)
        layout.addWidget(self.ai_progress)

        self.ai_output = QTextEdit()
        self.ai_output.setReadOnly(True)
        self.ai_output.setPlaceholderText("AI Insight will appear here...")
        layout.addWidget(self.ai_output)

    # ---------------- Extraction unchanged ----------------
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_input.setText(folder)

    def refresh_schemas(self):
        try:
            root = Path(__file__).resolve().parents[1]
            schemas_dir = root / "registry" / "schemas"
            self.schema_selector.clear()
            found = False
            if schemas_dir.exists():
                for f in sorted(schemas_dir.glob("*.json")):
                    self.schema_selector.addItem(f.stem, userData=str(f))
                    found = True
            if not found:
                self.schema_selector.addItem("No schemas found")
        except Exception as e:
            QMessageBox.critical(self, "Schema Error", str(e))

    def load_fields_from_schema(self):
        data_path = self.schema_selector.currentData()
        if not data_path or not isinstance(data_path, str):
            QMessageBox.warning(self, "Schema", "Please select a valid schema first.")
            return
        try:
            schema = json.loads(Path(data_path).read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.critical(self, "Schema Load Error", str(e))
            return

        grouped = self._flatten_to_groups(schema)
        self._clear_fields_ui()
        self.checkbox_map.clear()

        for group_name, fields in grouped.items():
            grp = CollapsibleGroup(group_name, self)
            for dot_path in fields:
                cb = QCheckBox(dot_path)
                grp.content_layout.addWidget(cb)
                self.checkbox_map[dot_path] = cb
            spacer = QFrame()
            grp.content_layout.addWidget(spacer)
            self.fields_layout.addWidget(grp)
        self.fields_layout.addStretch(1)

    def extract_data(self):
        folder = self.folder_input.text().strip()
        if not folder:
            QMessageBox.warning(self, "Folder", "Please select a folder.")
            return

        schema_name = self.schema_selector.currentText().strip()
        if not schema_name or schema_name.lower().startswith("select"):
            QMessageBox.warning(self, "Schema", "Please choose a schema.")
            return

        selected = self._selected_fields()
        if not selected:
            QMessageBox.warning(self, "Fields", "Please select at least one field.")
            return

        fmt = self.format_selector.currentText().upper()
        default_name = "extracted.json" if fmt == "JSON" else "extracted.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Extraction Output", default_name,
            "JSON (*.json);;Text (*.txt);;All Files (*.*)"
        )
        if not path:
            return

        try:
            if fmt == "JSON" or path.lower().endswith(".json"):
                summary = self.extract_service.extract_to_json(folder, schema_name, selected, path)
            else:
                summary = self.extract_service.extract_to_txt(folder, schema_name, selected, path)
        except Exception as e:
            QMessageBox.critical(self, "Extraction Error", str(e))
            return

        self.result_area.setPlainText(
            "Extraction complete.\n"
            f"- Files scanned: {summary.scanned}\n"
            f"- Parsed OK: {summary.parsed_ok}\n"
            f"- Failed: {summary.parsed_failed}\n"
            f"- Output: {summary.written_path}\n"
        )
        self.ai_btn.setEnabled(True)

    # ---------------- AI Flow (NEW) ----------------
    def generate_ai_insight(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Extracted Output", "", "Text or JSON Files (*.txt *.json)"
        )
        if not file_path:
            return

        try:
            extracted_text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            QMessageBox.critical(self, "File Error", str(e))
            return

        self.ai_btn.setEnabled(False)
        self.ai_output.clear()
        self._start_spinner("Analyzing with AI...")

        self.thread = QThread()
        self.ai_worker = AIWorker(self.insight_service, extracted_text)
        self.ai_worker.moveToThread(self.thread)

        self.thread.started.connect(self.ai_worker.run)
        self.ai_worker.finished.connect(self._ai_done)
        self.ai_worker.error.connect(self._ai_error)

        self.ai_worker.finished.connect(self.ai_worker.deleteLater)
        self.ai_worker.error.connect(self.ai_worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def _ai_done(self, out: str):
        self._stop_spinner()
        self.ai_output.setPlainText(out or "(No AI output)")
        self.ai_btn.setEnabled(True)
        self.export_ai_btn.setEnabled(True)


    def _ai_error(self, msg: str):
        self._stop_spinner()
        QMessageBox.critical(self, "AI Error", msg)
        self.ai_btn.setEnabled(True)

    # ---------------- Spinner ----------------
    def _start_spinner(self, base_text: str):
        self.ai_progress.setVisible(True)
        self.ai_progress.setText(base_text)
        self._dot_state = 0
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(lambda: self._animate_dots(base_text))
        self._dot_timer.start(350)

    def _animate_dots(self, base):
        self._dot_state = (self._dot_state + 1) % 4
        self.ai_progress.setText(base + "." * self._dot_state)

    def _stop_spinner(self):
        if self._dot_timer:
            self._dot_timer.stop()
        self.ai_progress.setVisible(False)

    # ---------------- Helpers ----------------
    def _clear_fields_ui(self):
        while self.fields_layout.count():
            item = self.fields_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _selected_fields(self) -> List[str]:
        return [path for path, cb in self.checkbox_map.items() if cb.isChecked()]

    def _flatten_to_groups(self, schema: Any) -> DefaultDict[str, List[str]]:
        grouped: DefaultDict[str, List[str]] = defaultdict(list)

        def add(g, p): grouped[g].append(p)

        def walk(node, prefix="", group=""):
            if prefix and "." not in prefix:
                group = prefix.split(".")[0]

            if isinstance(node, dict):
                if prefix == "":
                    for k, v in node.items():
                        walk(v, k, k)
                else:
                    for k, v in node.items():
                        walk(v, f"{prefix}.{k}", group or prefix.split(".")[0])
            elif isinstance(node, list):
                if not node:
                    add(group or prefix.split(".")[0], prefix)
                else:
                    first = node[0]
                    if isinstance(first, dict):
                        for k, v in first.items():
                            walk(v, f"{prefix}.{k}", group or prefix.split(".")[0])
                    else:
                        add(group or prefix.split(".")[0], prefix)
            else:
                add(group or prefix.split(".")[0], prefix)

        walk(schema, "", "")
        for k in list(grouped.keys()):
            grouped[k] = sorted(set(grouped[k]))
        return grouped
    
    def export_ai_insight(self):
        text = self.ai_output.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "No Data", "No AI insight available to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Insight Output",
            "insight.txt",
            "Text (*.txt);;Markdown (*.md);;All Files (*.*)"
        )
        if not path:
            return

        try:
            Path(path).write_text(text, encoding="utf-8")
            QMessageBox.information(self, "Saved", f"Insight exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

