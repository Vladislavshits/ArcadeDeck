# app/modules/ui/game_library.py

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QLabel, QScrollArea, QFrame, QFileDialog
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from modules.ui.search_bar import SearchBar
from app.modules.module_logic.game_scanner import scan_games

class GameTile(QPushButton):
    def __init__(self, game_data: dict, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.setObjectName("TileButton")
        self.setFixedSize(220, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Иконка-заглушка (пока без обложки)
        icon_label = QLabel()
        pixmap = QPixmap(":/icons/game_placeholder.png").scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio)
        icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(game_data["title"])
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)


class AddGameButton(QPushButton):
    def __init__(self, icon_path: str, text: str, library_page, parent=None):
        super().__init__(parent)
        self.library_page = library_page
        self.setAcceptDrops(True)
        self.setFixedSize(220, 180)
        self.setObjectName("TileButton")  # Стиль такой же, как в настройках
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_label = QLabel(text)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(text_label)
        layout.addStretch()

        # Новый размер кнопки
        self.setFixedSize(220, 220)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            self.library_page.handle_file_drop(path)  # вызываем у GameLibraryPage

class GameLibraryPage(QWidget):
    def __init__(self, games_dir: str, parent=None):
        super().__init__(parent)
        self.games_dir = games_dir
        self.supported_exts = {"cso", "iso", "cho"}  # для PSP
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Контейнер с двумя экранами
        self.stack = QStackedWidget()

        # 1. Placeholder
        self.placeholder = QWidget()
        self.placeholder.setAcceptDrops(True)  # drag-n-drop
        ph_layout = QVBoxLayout(self.placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.setSpacing(30)

        # Поисковая строка
        self.search_input_ph = SearchBar()
        self.search_input_ph.searchUpdated.connect(self.filter_games)
        self.search_input_ph.setFixedWidth(500)
        self.search_input_ph.setMaximumWidth(500)
        self.search_input_ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(self.search_input_ph)

        # Сообщение плейсхолдер
        self.placeholder_label = QLabel("Перетащите игру сюда")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(self.placeholder_label)

        # Кнопка добавить игру
        self.add_btn_ph = AddGameButton(":/icons/add_game.png", "Добавить игру", self)
        self.add_btn_ph.clicked.connect(self.open_file_dialog)
        self.add_btn_ph.setFixedWidth(500)
        self.add_btn_ph.setMaximumWidth(500)
        ph_layout.addWidget(self.add_btn_ph)

        self.stack.addWidget(self.placeholder)

        # 2. Сетка игр (в разработке)
        self.grid = QWidget()
        grid_layout = QVBoxLayout(self.grid)

        # Поисковик на экране с играми
        self.search_input_grid = SearchBar()
        self.search_input_grid.searchUpdated.connect(self.filter_games)
        self.search_input_grid.setFixedWidth(500)
        self.search_input_grid.setMaximumWidth(500)
        self.search_input_grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Выравнивание по центру
        search_layout = QHBoxLayout()
        search_layout.addStretch()
        search_layout.addWidget(self.search_input_grid)
        search_layout.addStretch()
        grid_layout.addLayout(search_layout)


        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        grid_layout.addWidget(self.scroll_area)
        self.stack.addWidget(self.grid)

        layout.addWidget(self.stack)
        self.load_games()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            self.handle_file_drop(path)

    def handle_file_drop(self, path):
        from app.modules.module_logic.game_importer import import_game
        from PyQt6.QtWidgets import QMessageBox

        try:
            game_data = import_game(path)
            # TODO: после импорта — отрисовать игру
            QMessageBox.information(self, "Готово", f"Игра добавлена: {game_data['title']}")
            self.load_games()  # Обновить экран
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл игры", "", "PSP образы (*.iso *.cso *.cho)")
        if path:
            self.handle_file_drop(path)

    def load_games(self):
        games = scan_games()
        if not games:
            self.stack.setCurrentIndex(0)  # Показать placeholder
        else:
            self.stack.setCurrentIndex(1)  # Показать грид
            self.show_game_grid(games)
    
    def show_game_grid(self, games):
        from PyQt6.QtWidgets import QGridLayout
        layout = QGridLayout()
        layout.setSpacing(20)

        row, col = 0, 0
        max_cols = 4

        for game in games:
            tile = GameTile(game)
            tile.clicked.connect(lambda _, g=game: self.show_game_info(g))
            layout.addWidget(tile, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        container = QWidget()
        container.setLayout(layout)
        self.scroll_area.setWidget(container)

    def show_game_info(self, game_data):
        main_window = self.window()
        if hasattr(main_window, "show_game_info"):
            main_window.show_game_info(game_data)

    def filter_games(self, text):
        # TODO: Обработка фильтрации игр по тексту
        print(f"[Search] Фильтрация по: {text}")
