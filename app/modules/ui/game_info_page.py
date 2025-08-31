import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt
from pathlib import Path


class GameInfoPage(QWidget):
    """Page for displaying game information"""
    def __init__(self, game_data=None, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self._init_ui()

        # Initialize with game data if provided
        if game_data:
            self.set_game(game_data, is_installed=False)

    def _init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Game title
        self.title_label = QLabel("Название игры")
        self.title_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        layout.addWidget(self.title_label)

        # Game cover
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(400, 225)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cover_label)

        # Game description
        self.description_label = QLabel("Описание игры...")
        self.description_label.setWordWrap(True)
        self.description_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.description_label)

        # Action buttons
        button_layout = QHBoxLayout()
        self.action_button = QPushButton("Играть")
        self.delete_button = QPushButton("Удалить")
        self.back_button = QPushButton("Назад")
        button_layout.addWidget(self.action_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.back_button)
        layout.addLayout(button_layout)

        # Connect signals
        self.back_button.clicked.connect(self.on_back)
        self.action_button.clicked.connect(self.on_action)
        self.delete_button.clicked.connect(self.on_delete)  # Подключаем удаление

        # Изначально скрываем кнопку удаления
        self.delete_button.setVisible(False)

    def update_installation_status(self, is_installed):
        """Update button based on installation status"""
        self.is_installed = is_installed
        self.action_button.setText("Играть" if self.is_installed else "Установить")
        self.delete_button.setVisible(self.is_installed)

    def set_game(self, game_data, is_installed=False):
        """Set game data to display"""
        self.game_data = game_data or {}
        self.is_installed = bool(is_installed)

        # Update title
        self.title_label.setText(
            self.game_data.get("title", "Без названия")
        )

        # Update description
        self.description_label.setText(
            self.game_data.get("description", "Нет описания")
        )

        # Update cover image
        image_path = self.game_data.get("image_path")
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            self.cover_label.setPixmap(pixmap.scaled(
                self.cover_label.size(), 
                Qt.AspectRatioMode.KeepAspectRatio
            ))
        else:
            self.cover_label.clear()

        # Update buttons
        self.action_button.setText("Играть" if self.is_installed else "Установить")
        self.delete_button.setVisible(self.is_installed)

    def on_back(self):
        """Handle back button click"""
        if self.back_callback:
            self.back_callback()

    def on_action(self):
        """Handle action button click"""
        if self.action_callback:
            self.action_callback(self.game_data, self.is_installed)

    def on_delete(self):
        """Handle delete button click"""
        if self.delete_callback:
            self.delete_callback(self.game_data)

    # Properties for callbacks
    @property
    def back_callback(self):
        return self._back_callback

    @back_callback.setter
    def back_callback(self, callback):
        self._back_callback = callback

    @property
    def action_callback(self):
        return self._action_callback

    @action_callback.setter
    def action_callback(self, callback):
        self._action_callback = callback

    @property
    def delete_callback(self):
        return self._delete_callback

    @delete_callback.setter
    def delete_callback(self, callback):
        self._delete_callback = callback
