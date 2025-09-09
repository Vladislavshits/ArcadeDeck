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
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(40)

        # Левая часть - обложка игры (увеличиваем размер)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Game cover - увеличенная плитка как в библиотеке
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(500, 600)  # Увеличиваем размер
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("""
            border: 3px solid #444;
            border-radius: 15px;
            background-color: #2a2a2a;
        """)
        left_layout.addWidget(self.cover_label)
        left_layout.addStretch()

        # Правая часть - информация и кнопки
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_layout.setSpacing(25)

        # Game title
        self.title_label = QLabel("Название игры")
        self.title_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #ffffff; margin-bottom: 10px;")
        right_layout.addWidget(self.title_label)

        # Game description
        self.description_label = QLabel("Описание игры...")
        self.description_label.setWordWrap(True)
        self.description_label.setFont(QFont("Arial", 14))
        self.description_label.setStyleSheet("color: #cccccc;")
        self.description_label.setMinimumWidth(400)
        right_layout.addWidget(self.description_label)

        # Кнопки действий (располагаем снизу вверх)
        right_layout.addStretch()

        # Action buttons - вертикальное расположение
        self.action_button = QPushButton("Играть")
        self.action_button.setFixedHeight(60)
        self.action_button.setFont(QFont("Arial", 16, QFont.Weight.Bold))

        self.delete_button = QPushButton("Удалить")
        self.delete_button.setFixedHeight(50)
        self.delete_button.setFont(QFont("Arial", 14))

        self.back_button = QPushButton("Назад в библиотеку")
        self.back_button.setFixedHeight(50)
        self.back_button.setFont(QFont("Arial", 14))

        # Добавляем кнопки в обратном порядке (снизу вверх)
        right_layout.addWidget(self.action_button)
        right_layout.addWidget(self.delete_button)
        right_layout.addWidget(self.back_button)

        # Добавляем левую и правую части в основной layout
        main_layout.addWidget(left_widget, 45)  # 45% ширины для обложки
        main_layout.addWidget(right_widget, 55)  # 55% ширины для информации

        # Connect signals
        self.back_button.clicked.connect(self.on_back)
        self.action_button.clicked.connect(self.on_action)
        self.delete_button.clicked.connect(self.on_delete)

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

    def load_game(self, game_data):
        """
        Загружает данные игры и отображает их на странице.
        Использует централизованный менеджер для актуальных данных.
        """
        if not game_data:
            return

        try:
            # Получаем актуальные данные из централизованного менеджера
            game_id = game_data.get('id')
            if game_id:
                from app.modules.module_logic.game_data_manager import get_game_data_manager
                manager = get_game_data_manager()

                if manager:
                    actual_game_data = manager.get_game_by_id(game_id)
                    if actual_game_data:
                        game_data = actual_game_data

            # Устанавливаем данные игры
            is_installed_status = game_data.get('is_installed', False)
            self.set_game(game_data, is_installed_status)

        except Exception as e:
            logger.error(f"Ошибка загрузки данных игры: {e}")
            # Используем переданные данные как fallback
            is_installed_status = game_data.get('is_installed', False)
            self.set_game(game_data, is_installed_status)

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
