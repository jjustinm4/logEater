from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog,
    QHBoxLayout, QTextEdit, QComboBox, QMessageBox, QScrollArea, QFrame,
    QToolButton, QGroupBox, QCheckBox, QSizePolicy
)
from PySide6.QtCore import Qt
from pathlib import Path
import json
from typing import Dict, Any, List, Tuple, Iterable, DefaultDict
from collections import defaultdict
from core.extract.extract_service import ExtractService
from core.extract.extract_service import ExtractService



class CollapsibleGroup(QGroupBox):
    """A simple collapsible group using a toggle toolbutton."""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setTitle("")  # we render our own header
        self._main = QVBoxLayout(self)
        self._main.setContentsMargins(0, 0, 0, 0)

        # Header
        self._header = QToolButton()
        self._header.setStyleSheet("QToolButton { border: none; font-weight: 600; }")
        self._header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._header.setArrowType(Qt.RightArrow)
        self._header.setText(title)
        self._header.setCheckable(True)
        self._header.setChecked(False)
        self._header.toggled.connect(self._on_toggled)

        # Content area
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


class ExtractPanel(QWidget):
    def __init__(self):
        super().__init__()

        # Folder input
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select folder for extraction...")

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_folder)

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(browse_btn)

        # Schema selector
        self.schema_selector = QComboBox()
        self.schema_selector.addItem("Select schema...")  # populated by refresh

        refresh_btn = QPushButton("Refresh Schemas")
        refresh_btn.clicked.connect(self.refresh_schemas)

        load_fields_btn = QPushButton("Load Fields")
        load_fields_btn.clicked.connect(self.load_fields_from_schema)

        schema_layout = QHBoxLayout()
        schema_layout.addWidget(QLabel("Schema:"))
        schema_layout.addWidget(self.schema_selector)
        schema_layout.addWidget(refresh_btn)
        schema_layout.addWidget(load_fields_btn)

        # Field selection area (scrollable)
        self.fields_scroll = QScrollArea()
        self.fields_scroll.setWidgetResizable(True)
        self.fields_container = QWidget()
        self.fields_layout = QVBoxLayout(self.fields_container)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.setSpacing(8)
        self.fields_scroll.setWidget(self.fields_container)

        # Output format
        self.format_selector = QComboBox()
        self.format_selector.addItems(["TXT", "JSON"])

        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Output Format:"))
        format_layout.addWidget(self.format_selector)
        format_layout.addStretch()

        # Extract button
        extract_btn = QPushButton("Extract")
        extract_btn.clicked.connect(self.extract_data)  # backend wires later

        # Output area
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setPlaceholderText("Extraction summary will be shown here...")

        # Assemble
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Extract Panel"))
        layout.addLayout(folder_layout)
        layout.addLayout(schema_layout)
        layout.addWidget(QLabel("Schema Fields"))
        layout.addWidget(self.fields_scroll)
        layout.addLayout(format_layout)
        layout.addWidget(extract_btn)
        layout.addWidget(self.result_area)
        self.setLayout(layout)

        # Internal state
        self.checkbox_map: Dict[str, QCheckBox] = {}  # dot_path -> checkbox
        self.extract_service = ExtractService()


    # ---------- UI Actions ----------

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_input.setText(folder)

    def refresh_schemas(self):
        """Load list of schema files from /registry/schemas/*.json"""
        try:
            root = Path(__file__).resolve().parents[1]  # project root
            schemas_dir = root / "registry" / "schemas"
            self.schema_selector.clear()
            found_any = False
            if schemas_dir.exists():
                for f in sorted(schemas_dir.glob("*.json")):
                    self.schema_selector.addItem(f.stem, userData=str(f))
                    found_any = True
            if not found_any:
                self.schema_selector.addItem("No schemas found")
            QMessageBox.information(self, "Schemas", "Schema list refreshed.")
        except Exception as e:
            QMessageBox.critical(self, "Schema Error", f"Failed to refresh schemas:\n{e}")

    def load_fields_from_schema(self):
        """Read selected schema JSON and build grouped checkbox UI (collapsible)."""
        data_path = self.schema_selector.currentData()
        if not data_path or not isinstance(data_path, str):
            QMessageBox.warning(self, "Schema", "Please select a valid schema (use Refresh Schemas).")
            return
        try:
            schema = json.loads(Path(data_path).read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.critical(self, "Schema Load Error", f"Could not load schema:\n{e}")
            return

        # Build flattened dot-paths grouped by top-level key
        grouped = self._flatten_to_groups(schema)

        # Clear previous
        self._clear_fields_ui()
        self.checkbox_map.clear()

        # Build collapsible groups
        for group_name, fields in grouped.items():
            grp = CollapsibleGroup(group_name, self)
            for dot_path in fields:
                cb = QCheckBox(dot_path)
                grp.content_layout.addWidget(cb)
                self.checkbox_map[dot_path] = cb
            # small spacer for breath
            spacer = QFrame()
            spacer.setFrameShape(QFrame.NoFrame)
            grp.content_layout.addWidget(spacer)
            self.fields_layout.addWidget(grp)

        self.fields_layout.addStretch(1)
        self.result_area.setPlainText("Fields loaded. Select what you need, choose output format, then click Extract.")

    def extract_data(self):
        folder = self.folder_input.text().strip()
        if not folder:
            QMessageBox.warning(self, "Folder", "Please select a folder to extract from.")
            return

        schema_name = self.schema_selector.currentText().strip()
        if not schema_name or schema_name.lower().startswith("select"):
            QMessageBox.warning(self, "Schema", "Please choose a schema (Refresh if needed).")
            return

        selected = self._selected_fields()
        if not selected:
            QMessageBox.warning(self, "Fields", "Please select at least one field to extract.")
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
            f"- Failed to parse: {summary.parsed_failed}\n"
            f"- Output: {summary.written_path}\n"
        )



    # ---------- Helpers ----------

    def _clear_fields_ui(self):
        while self.fields_layout.count():
            item = self.fields_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _selected_fields(self) -> List[str]:
        return [path for path, cb in self.checkbox_map.items() if cb.isChecked()]

    def _flatten_to_groups(self, schema: Any) -> DefaultDict[str, List[str]]:
        """
        Convert nested schema to grouped dot-paths.
        Group key = top-level field name.
        Arrays: show children of object elements (no [0] indexes).
        Primitive arrays: just the array key.
        """
        grouped: DefaultDict[str, List[str]] = defaultdict(list)

        def add(group: str, path: str):
            grouped[group].append(path)

        def walk(node: Any, prefix: str = "", group: str = ""):
            # Determine group from top-level
            if prefix and "." not in prefix:
                group = prefix.split(".")[0]
            elif not prefix and isinstance(node, dict):
                # top-level dict: each key becomes its own group in recursion
                pass

            if isinstance(node, dict):
                if prefix == "":
                    # top-level object: recurse each key separately to create groups
                    for k, v in node.items():
                        walk(v, k, k)
                else:
                    # inside object
                    for k, v in node.items():
                        new_prefix = f"{prefix}.{k}"
                        walk(v, new_prefix, group or prefix.split(".")[0])
            elif isinstance(node, list):
                if not node:
                    # empty array: include the array itself
                    add(group or prefix.split(".")[0], prefix)
                else:
                    first = node[0]
                    if isinstance(first, dict):
                        # show children fields of objects (no index)
                        for k, v in first.items():
                            child_path = f"{prefix}.{k}"
                            walk(v, child_path, group or prefix.split(".")[0])
                    else:
                        # primitive array: include the array field itself
                        add(group or prefix.split(".")[0], prefix)
            else:
                # primitive value -> add the path
                if prefix:
                    add(group or prefix.split(".")[0], prefix)

        walk(schema, "", "")
        # Sort fields within each group for a stable UI
        for k in list(grouped.keys()):
            grouped[k] = sorted(set(grouped[k]))
        return grouped
