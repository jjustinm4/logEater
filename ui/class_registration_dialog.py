# ui/class_registration_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout,
    QFileDialog, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt
from pathlib import Path
import json

from core.llm.schema_extractor import SchemaExtractor, SchemaExtractionError


class ClassRegistrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register New Log Class")
        self.setMinimumWidth(700)

        self.extractor = SchemaExtractor(model="llama3:latest")

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

        # Actions
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

    # ---------- actions ----------

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

        # UI state
        self.gen_btn.setEnabled(False)
        self.schema_preview.setPlainText("Building deterministic skeleton...\n")

        # Step 1: Deterministic skeleton (rule-based)
        try:
            # use_ai_refine=False here to separately show skeleton then refined
            base_schema = self.extractor.extract_schema(sample, use_ai_refine=False)
        except Exception as e:
            QMessageBox.critical(self, "Schema Error", f"Could not build skeleton:\n{e}")
            self.gen_btn.setEnabled(True)
            self.save_btn.setEnabled(False)
            self.schema_preview.setPlainText("")
            return

        base_pretty = json.dumps(base_schema, indent=2, ensure_ascii=False)
        self.schema_preview.setPlainText(
            "Deterministic skeleton generated.\n\n"
            "Attempting AI refinement (non-destructive)...\n\n"
            f"--- SKELETON ---\n{base_pretty}\n"
        )

        # Step 2: AI refinement (safe fallback if it fails)
        try:
            refined = self.extractor.extract_schema(sample, use_ai_refine=True)
            pretty = json.dumps(refined, indent=2, ensure_ascii=False)
            self.generated_schema_text = pretty
            self.schema_preview.setPlainText(pretty)
            self.save_btn.setEnabled(True)
        except Exception as e:
            # fall back to skeleton
            self.generated_schema_text = base_pretty
            self.schema_preview.setPlainText(
                f"{base_pretty}\n\n(Shown is deterministic skeleton; AI refinement failed: {e})"
            )
            self.save_btn.setEnabled(True)

        self.gen_btn.setEnabled(True)

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

        QMessageBox.information(self, "Saved", f"Schema saved to:\n{out_path}")
        self.save_btn.setEnabled(False)
