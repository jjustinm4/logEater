from PySide6.QtWidgets import QWidget, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QStackedWidget
from PySide6.QtCore import Qt
from .search_panel import SearchPanel
from .extract_panel import ExtractPanel
from .class_registration_dialog import ClassRegistrationDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LogBuster")
        self.setMinimumWidth(1100)
        self.setMinimumHeight(700)

        # Top Buttons
        self.search_btn = QPushButton("Search Mode")
        self.extract_btn = QPushButton("Extract Mode")
        self.register_btn = QPushButton("+ Class")

        self.search_btn.clicked.connect(self.show_search_panel)
        self.extract_btn.clicked.connect(self.show_extract_panel)
        self.register_btn.clicked.connect(self.show_class_dialog)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.search_btn)
        top_layout.addWidget(self.extract_btn)
        top_layout.addStretch()
        top_layout.addWidget(self.register_btn)

        # Stacked Panels
        self.stack = QStackedWidget()
        self.search_panel = SearchPanel()
        self.extract_panel = ExtractPanel()
        self.stack.addWidget(self.search_panel)
        self.stack.addWidget(self.extract_panel)

        # Main Layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.stack)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Default View
        self.show_search_panel()

    def show_search_panel(self):
        self.stack.setCurrentWidget(self.search_panel)

    def show_extract_panel(self):
        self.stack.setCurrentWidget(self.extract_panel)

    def show_class_dialog(self):
        dialog = ClassRegistrationDialog(self)
        dialog.exec()
