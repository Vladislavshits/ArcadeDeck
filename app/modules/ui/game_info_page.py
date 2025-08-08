# modules/ui/game_info_page.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt
import os

class GameInfoPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.game_data = None
        self.is_installed = False

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        self.title_label = QLabel("Название игры")
        self.title_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        layout.addWidget(self.title_label)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(400, 225)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cover_label)

        self.description_label = QLabel("Описание игры...")
        self.description_label.setWordWrap(True)
        self.description_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.description_label)

        button_layout = QHBoxLayout()
        self.action_button = QPushButton("Играть")
        self.back_button = QPushButton("Назад")

        button_layout.addWidget(self.action_button)
        button_layout.addWidget(self.back_button)
        layout.addLayout(button_layout)

        self.back_callback = None
        self.action_callback = None

        self.back_button.clicked.connect(self.on_back)
        self.action_button.clicked.connect(self.on_action)

    def set_game(self, game_data, is_installed=False):
        self.game_data = game_data
        self.is_installed = is_installed

        self.title_label.setText(game_data.get("title", "Без названия"))
        self.description_label.setText(game_data.get("description", "Нет описания"))

        image_path = game_data.get("image_path")
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            self.cover_label.setPixmap(pixmap.scaled(
                self.cover_label.size(), Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.cover_label.clear()

        self.action_button.setText("Играть" if is_installed else "Установить")

    def on_back(self):
        if self.back_callback:
            self.back_callback()

    def on_action(self):
        if self.action_callback:
            self.action_callback(self.game_data, self.is_installed)