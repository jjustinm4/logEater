from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit

class ClassRegistrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register New Log Class")
        self.setMinimumWidth(500)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Upload a sample log for schema learning:"))
        layout.addWidget(QTextEdit("Paste or load log here... (LLM will process)"))

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        self.setLayout(layout)
