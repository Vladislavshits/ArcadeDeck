# app/modules/ui/search_bar.py

from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtCore import pyqtSignal, Qt

class SearchBar(QLineEdit):
    searchUpdated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Игры, гайды, настройки...")
        self.setClearButtonEnabled(True)
        self.setObjectName("SearchInput")
        self.setFixedWidth(500)
        self.setMaximumWidth(500)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.textChanged.connect(self.searchUpdated.emit)
