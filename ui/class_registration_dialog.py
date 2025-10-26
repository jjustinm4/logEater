# ui/class_registration_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout,
    QFileDialog, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer
from pathlib import Path
import json
import re

from core.llm.schema_extractor import SchemaExtractor
import textwrap



# ----------------------------
# Worker Thread
# ----------------------------
class SchemaWorker(QObject):
    finished = Signal(dict, dict)      # base_schema, refined_schema
    error = Signal(str)

    def __init__(self, extractor: SchemaExtractor, sample: str):
        super().__init__()
        self.extractor = extractor
        self.sample = sample

    def run(self):
        try:
            # Step 1 — deterministic skeleton
            base_schema = self.extractor.extract_schema(self.sample, use_ai_refine=False)

            # Step 2 — AI refinement (safe fallback)
            try:
                refined = self.extractor.extract_schema(self.sample, use_ai_refine=True)
            except Exception:
                refined = None

            self.finished.emit(base_schema, refined)

        except Exception as e:
            self.error.emit(str(e))


# ----------------------------
# Dialog
# ----------------------------
class ClassRegistrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register New Log Class")
        self.setMinimumWidth(700)
        self.extractor = SchemaExtractor(model="llama3:latest")
        self.thread = None
        self.worker = None
        self._dot_timer = None
        self._dot_state = 0

        layout = QVBoxLayout(self)

        # Class name
        self.class_name_input = QLineEdit()
        self.class_name_input.setPlaceholderText("Enter class name (e.g., ChatPipelineLog_V1)")
        layout.addWidget(QLabel("Class Name"))
        layout.addWidget(self.class_name_input)

        # Sample log
        row = QHBoxLayout()
        load_btn = QPushButton("Load Sample File")
        load_btn.clicked.connect(self.load_sample_file)
        row.addWidget(QLabel("Sample Log"))
        row.addStretch()
        row.addWidget(load_btn)
        layout.addLayout(row)

        self.sample_text = QTextEdit()
        self.sample_text.setPlaceholderText("Paste a representative sample log here...")
        self.sample_text.setAcceptRichText(False)
        layout.addWidget(self.sample_text)

        # Progress label
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)

        # Buttons
        btn_row = QHBoxLayout()
        self.gen_btn = QPushButton("Generate Schema via AI")
        self.gen_btn.clicked.connect(self.generate_schema)
        self.save_btn = QPushButton("Save Schema")
        self.save_btn.clicked.connect(self.save_schema)
        self.save_btn.setEnabled(False)
        btn_row.addWidget(self.gen_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        # Schema preview
        layout.addWidget(QLabel("Schema Preview"))
        self.schema_preview = QTextEdit()
        self.schema_preview.setReadOnly(True)
        layout.addWidget(self.schema_preview)

        # Close
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        self.generated_schema_text: str | None = None


    # ---------------- Spinner (dot animation) ----------------
    def _start_spinner(self, text):
        self.progress_label.setVisible(True)
        self.progress_label.setText(text)
        self._dot_state = 0

        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(lambda: self._animate_dots(text))
        self._dot_timer.start(400)

    def _animate_dots(self, base):
        self._dot_state = (self._dot_state + 1) % 4
        self.progress_label.setText(base + "." * self._dot_state)

    def _stop_spinner(self):
        if self._dot_timer:
            self._dot_timer.stop()
        self.progress_label.setVisible(False)


    # ---------------- Actions ----------------
    def load_sample_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Sample Log", "", "All Files (*.*)")
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8", errors="ignore")
            self.sample_text.setPlainText(content)
        except Exception as e:
            QMessageBox.critical(self, "Read Error", f"Could not read file:\n{e}")

    def generate_schema(self):
        class_name = self.class_name_input.text().strip()
        if not class_name:
            QMessageBox.warning(self, "Class Name", "Please provide a class name.")
            return
        sample = self.sample_text.toPlainText().strip()
        if not sample:
            QMessageBox.warning(self, "Sample Log", "Please paste or load a sample log.")
            return

        self.gen_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.schema_preview.setPlainText("")

        self._start_spinner("Building skeleton... Then refining with AI")

        self.thread = QThread()
        self.worker = SchemaWorker(self.extractor, sample)
        self.worker.moveToThread(self.thread)

        # When the thread starts, run the worker. Keep a reference to the
        # worker on self so it isn't garbage-collected which can drop
        # signal connections in some PySide/PyQt builds.
        self.thread.started.connect(self.worker.run)

        # Connect result handlers
        self.worker.finished.connect(self._on_schema_finished)
        self.worker.error.connect(self._on_schema_error)

        # Ensure the worker is deleted when done and the thread is asked to quit
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        # Quit the thread when work finishes or errors so the thread's
        # event loop can stop and resources are cleaned up.
        self.worker.finished.connect(lambda *_: self.thread.quit())
        self.worker.error.connect(lambda *_: self.thread.quit())

        # Clean up references when the thread finishes
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: setattr(self, 'worker', None))
        self.thread.finished.connect(lambda: setattr(self, 'thread', None))

        self.thread.start()

    def _on_schema_error(self, message: str):
        self._stop_spinner()
        QMessageBox.critical(self, "Schema Error", message)
        self.gen_btn.setEnabled(True)
        self.save_btn.setEnabled(False)

    def _on_schema_finished(self, base_schema: dict, refined_schema: dict | None):
        self._stop_spinner()

        schema = refined_schema or base_schema
        pretty = json.dumps(schema, indent=2, ensure_ascii=False)
        self.generated_schema_text = pretty
        self.schema_preview.setPlainText(pretty)

        self.gen_btn.setEnabled(True)
        self.save_btn.setEnabled(True)


    # -------- Parser Autogen (PROTECT_MANUAL_EDITS) --------
    def _safe_module_name(self, name: str) -> str:
        s = name.strip().lower()
        s = re.sub(r"[^a-z0-9]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return f"{s}_parser"

    def _class_name_from_schema(self, name: str) -> str:
        core = re.sub(r"[^a-zA-Z0-9]+", " ", name).title().replace(" ", "")
        return core + "Parser" if not core.endswith("Parser") else core

    def _write_parser_file(self, class_name: str, project_root: Path) -> Path:
        print(f"[INFO] Starting _write_parser_file for class: {class_name}, project_root: {project_root}")

        parsers_dir = project_root / "core" / "schema" / "parsers"
        print(f"[DEBUG] Ensuring directory exists: {parsers_dir}")
        parsers_dir.mkdir(parents=True, exist_ok=True)

        module_stem = self._safe_module_name(class_name)
        print(f"[DEBUG] Generated module_stem: {module_stem}")

        class_title = self._class_name_from_schema(class_name)
        print(f"[DEBUG] Generated class_title: {class_title}")

        out_path = parsers_dir / f"{module_stem}.py"
        print(f"[DEBUG] Output path resolved to: {out_path}")

        if out_path.exists():  # PROTECT_MANUAL_EDITS
            print(f"[INFO] File already exists, skipping generation: {out_path}")
            return out_path

        print(f"[INFO] Writing new parser file to: {out_path}")
        content = textwrap.dedent(f'''\
# Auto-generated parser for schema: {class_name}
from __future__ import annotations
from typing import Dict, Any
from .base_parser import BaseParser
from core.utils.dot_walker import get_dot_value


class {class_title}(BaseParser):
    """
    Auto-generated parser. Override extract_field() for custom logic.
    """

    def extract_field(self, data: Dict[str, Any], field: str):
        return None

    def _fallback_get(self, data: Dict[str, Any], field: str):
        return get_dot_value(data, field)
''')

        out_path.write_text(content, encoding="utf-8")
        print(f"[SUCCESS] Parser file written: {out_path}")
        return out_path



    # ---------------- Save Schema ----------------
    def save_schema(self):
        if not self.generated_schema_text:
            QMessageBox.information(self, "No Schema", "Generate a schema first.")
            return

        class_name = self.class_name_input.text().strip()
        if not class_name:
            QMessageBox.warning(self, "Class Name", "Please provide a class name.")
            return

        try:
            schema_dict = json.loads(self.generated_schema_text)
        except Exception as e:
            QMessageBox.critical(self, "Schema Error", f"Preview is not valid JSON:\n{e}")
            return

        try:
            out_path = self.extractor.save_schema(class_name, schema_dict)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save schema:\n{e}")
            return

        project_root = Path(__file__).resolve().parents[1]
        parser_path = self._write_parser_file(class_name, project_root)

        QMessageBox.information(
            self,
            "Saved",
            f"Schema saved to:\n{out_path}\n\nParser generated at:\n{parser_path}"
        )
        self.save_btn.setEnabled(False)
