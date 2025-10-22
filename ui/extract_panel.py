from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog, QHBoxLayout

class ExtractPanel(QWidget):
    def __init__(self):
        super().__init__()

        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select folder for extraction...")

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_folder)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Extract Panel"))

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(browse_btn)

        layout.addLayout(folder_layout)
        self.setLayout(layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_input.setText(folder)
