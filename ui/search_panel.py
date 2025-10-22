from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog,
    QHBoxLayout, QCheckBox, QTextEdit, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt
from core.search.search_service import SearchService, SearchResult, FileMatch

class SearchPanel(QWidget):
    def __init__(self):
        super().__init__()

        self.service = SearchService(include_exts=[".log", ".txt", ".json"])
        self.last_results: SearchResult | None = None

        # Folder input
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select log directory...")

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_folder)

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(browse_btn)

        # Search text input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Enter keyword or regex pattern... (For AND/OR use comma-separated terms)"
        )

        # Case and regex checkboxes
        self.case_checkbox = QCheckBox("Case Sensitive")
        self.regex_checkbox = QCheckBox("Use Regex")

        # AND / OR selector
        self.logic_selector = QComboBox()
        self.logic_selector.addItems(["Single Pattern", "AND", "OR"])

        logic_layout = QHBoxLayout()
        logic_layout.addWidget(self.case_checkbox)
        logic_layout.addWidget(self.regex_checkbox)
        logic_layout.addStretch()
        logic_layout.addWidget(QLabel("Mode:"))
        logic_layout.addWidget(self.logic_selector)

        # Search + Export buttons
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.run_search)

        export_btn = QPushButton("Export Results")
        export_btn.clicked.connect(self.export_results)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(search_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(export_btn)

        # Result area
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setPlaceholderText("Search results will appear here...")

        # Layout assembly
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Search Panel"))
        layout.addLayout(folder_layout)
        layout.addWidget(self.search_input)
        layout.addLayout(logic_layout)
        layout.addLayout(buttons_layout)
        layout.addWidget(self.result_area)
        self.setLayout(layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Log Directory")
        if folder:
            self.folder_input.setText(folder)

    def run_search(self):
        folder = self.folder_input.text().strip()
        pattern = self.search_input.text().strip()
        if not folder:
            QMessageBox.warning(self, "Missing folder", "Please select a log directory.")
            return
        if not pattern:
            QMessageBox.warning(self, "Missing pattern", "Please enter a search pattern or keyword.")
            return

        use_regex = self.regex_checkbox.isChecked()
        case_sensitive = self.case_checkbox.isChecked()
        logic_mode = self.logic_selector.currentText()

        try:
            self.result_area.setText("Running search...\n")
            results = self.service.search(
                folder=folder,
                pattern_input=pattern,
                logic_mode=logic_mode,
                use_regex=use_regex,
                case_sensitive=case_sensitive
            )
            self.last_results = results
            self._render_results(results)
        except ValueError as ve:
            QMessageBox.critical(self, "Invalid Pattern", str(ve))
        except Exception as e:
            QMessageBox.critical(self, "Search Error", str(e))

    def _render_results(self, results: SearchResult):
        lines: list[str] = []
        lines.append("=== SEARCH RESULTS ===\n")

        # Matched
        lines.append(f"MATCHED FILES ({len(results.matched)}):")
        for fm in results.matched:
            lines.append(f"  - {fm.file}")
        lines.append("")

        # Not matched
        lines.append(f"NON-MATCHED FILES ({len(results.not_matched)}):")
        for nf in results.not_matched:
            lines.append(f"  - {nf}")
        lines.append("")

        # Preview
        lines.append("MATCH PREVIEW:")
        for fm in results.matched:
            lines.append(f"\n{fm.file}:")
            for m in fm.matches:
                # Clip very long lines for readability
                snippet = m.text if len(m.text) <= 300 else (m.text[:300] + " ...")
                lines.append(f"  (line {m.line}) {snippet}")

        self.result_area.setPlainText("\n".join(lines))

    def export_results(self):
        if not self.last_results:
            QMessageBox.information(self, "No Results", "Run a search before exporting.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export Results", "search_results.txt", "Text Files (*.txt)")
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8", errors="ignore") as f:
                # Reuse the current rendered view
                f.write(self.result_area.toPlainText())
            QMessageBox.information(self, "Exported", f"Results saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))
