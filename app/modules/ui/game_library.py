import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QLabel, QScrollArea, QFileDialog, QGridLayout, QListWidget, QListWidgetItem
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from app.modules.ui.search_bar import SearchBar
from app.modules.module_logic.game_scanner import scan_games

import json


class GameTile(QPushButton):
    """Tile widget for a single game"""
    def __init__(self, game_data: dict, parent=None):
        super().__init__(parent)
        self.game_data = game_data  # Сохраняем данные игры
        self._init_ui()  # Вызываем инициализацию UI

    def _init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(5)

        # Game icon
        icon_label = QLabel()
        # Попробуем использовать изображение из данных игры если есть
        image_path = self.game_data.get("image_path")
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                icon_label.setPixmap(
                    pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio)
                )
        else:
            # Заглушка если нет изображения
            pixmap = QPixmap(120, 120)
            pixmap.fill(Qt.GlobalColor.gray)
            icon_label.setPixmap(pixmap)
        
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Game title
        title_label = QLabel(self.game_data.get("title", "Без названия"))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setMaximumWidth(120)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        
        # Стилизация
        self.setFixedSize(150, 180)
        self.setObjectName("GameTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class AddGameButton(QPushButton):
    """Button for adding new games"""
    def __init__(self, text: str, library_page, parent=None):
        super().__init__(parent)
        self.library_page = library_page
        self.setAcceptDrops(True)
        self.setFixedSize(220, 180)
        self.setObjectName("TileButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_label = QLabel(text)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(text_label)
        layout.addStretch()

        self.setFixedSize(220, 220)

    def dragEnterEvent(self, event):
        """Accept drag events with URLs"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle dropped files"""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            self.library_page.handle_file_drop(path)


class GameLibrary(QWidget):
    """Main game library widget"""
    def __init__(self, games_dir: str, parent=None):
        super().__init__(parent)
        self.games_dir = games_dir
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Добавляем base_dir
        self._init_ui()

    def _init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # ===== ЕДИНЫЙ ПОИСКОВЫЙ ВИДЖЕТ ДЛЯ ОБОИХ ЭКРАНОВ =====
        self.search_input = SearchBar(
            open_game_info_callback=self.show_game_info
        )
        self.search_input.searchUpdated.connect(self.filter_games)
        self.search_input.setFixedWidth(500)
        self.search_input.setMaximumWidth(500)

        # Центрируем поисковую строку
        search_layout = QHBoxLayout()
        search_layout.addStretch()
        search_layout.addWidget(self.search_input)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # ===== СТЕК ЭКРАНОВ =====
        # Stacked widget для разных состояний библиотеки
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)  # Растягиваем на оставшееся пространство

        # Placeholder view (пустая библиотека)
        self._init_placeholder_view()

        # Grid view (библиотека с играми)
        self._init_grid_view()

        # Загружаем игры при инициализации
        self.load_games()

    def _init_placeholder_view(self):
        """Экран для пустой библиотеки"""
        placeholder = QWidget()
        placeholder.setAcceptDrops(True)
        ph_layout = QVBoxLayout(placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.setSpacing(30)

        # СОХРАНЯЕМ search_input_ph для обратной совместимости
        # но он будет просто перенаправлять на основной поисковик
        self.search_input_ph = self.search_input

        # Текст пустого состояния
        self.placeholder_label = QLabel("Перетащите игру сюда")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(self.placeholder_label)

        # Кнопка добавления игры
        self.add_btn_ph = AddGameButton("Добавить игру", self)
        self.add_btn_ph.clicked.connect(self.open_file_dialog)
        self.add_btn_ph.setFixedWidth(500)
        self.add_btn_ph.setMaximumWidth(500)
        ph_layout.addWidget(self.add_btn_ph)

        # Добавляем в стек
        self.stack.addWidget(placeholder)

    def _init_grid_view(self):
        """Экран с плитками игр"""
        grid_widget = QWidget()
        grid_layout = QVBoxLayout(grid_widget)

        # СОХРАНЯЕМ search_input_grid для обратной совместимости
        self.search_input_grid = self.search_input

        # Область с прокруткой для плиток игр
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        grid_layout.addWidget(self.scroll_area)

        # Добавляем в стек
        self.stack.addWidget(grid_widget)

    def dragEnterEvent(self, event):
        """Обработчик перетаскивания файлов"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Обработчик отпускания файлов"""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            self.handle_file_drop(path)

    def handle_file_drop(self, path):
        """Импорт перетащенного файла игры"""
        from app.modules.module_logic.game_importer import import_game
        from PyQt6.QtWidgets import QMessageBox

        try:
            game_data = import_game(path)
            QMessageBox.information(
                self, 
                "Готово", 
                f"Игра добавлена: {game_data.get('title', 'Без названия')}"
            )
            self.load_games()  # Перезагружаем библиотеку
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def open_file_dialog(self):
        """Открытие диалога выбора файла"""
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "Выберите файл игры", 
            "", 
            "PSP образы (*.iso *.cso *.cho)"
        )
        if path:
            self.handle_file_drop(path)

    def load_games(self):
        """Загрузка и отображение игр"""
        try:
            print(f"[LIBRARY] Scanning games from: {self.games_dir}")
            
            # Сканируем игры из папки
            user_games = scan_games(self.games_dir)
            print(f"[LIBRARY] Found {len(user_games)} user games")

            # Загружаем игры из реестра
            registry_path = os.path.join(self.base_dir, "app", "registry", "registry_games.json")
            registry_games = []
            if os.path.exists(registry_path):
                with open(registry_path, 'r', encoding='utf-8') as f:
                    registry_games = json.load(f)
                    print(f"[LIBRARY] Loaded {len(registry_games)} registry games")

            # Объединяем игры (установленные + из реестра)
            all_games = user_games + [
                g for g in registry_games 
                if not any(ug.get('id') == g.get('id') for ug in user_games)
            ]

            # Обновляем список игр в поисковике (оба варианта для совместимости)
            self.search_input.set_game_list(all_games)
            self.search_input_ph.set_game_list(all_games)
            self.search_input_grid.set_game_list(all_games)

            # Переключаем экран в зависимости от наличия игр
            if not all_games:
                print("[LIBRARY] No games found, showing placeholder")
                self.stack.setCurrentIndex(0)  # Пустой экран
            else:
                print("[LIBRARY] Games found, showing grid")
                self.stack.setCurrentIndex(1)  # Экран с играми
                self.show_game_grid(all_games)
                
        except Exception as e:
            print(f"Error loading games: {e}")
            import traceback
            traceback.print_exc()
            # В случае ошибки показываем пустой экран
            self.stack.setCurrentIndex(0)

    def show_game_grid(self, games):
        """Отображение плиток игр"""
        # Очищаем предыдущий контент
        if self.scroll_area.widget():
            self.scroll_area.widget().deleteLater()

        # Создаем контейнер для плиток
        container = QWidget()
        layout = QGridLayout(container)
        layout.setSpacing(20)
        layout.setContentsMargins(10, 10, 10, 10)

        # Добавляем игры в сетку
        row, col, max_cols = 0, 0, 4
        for game in games:
            tile = GameTile(game)
            tile.clicked.connect(lambda _, g=game: self.show_game_info(g))
            layout.addWidget(tile, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Обновляем область прокрутки
        self.scroll_area.setWidget(container)
        self.scroll_area.show()

    def show_game_info(self, game_data):
        """Показать информацию об игре"""
        if not game_data:
            return

        main_window = self.window()
        if hasattr(main_window, "show_game_info"):
            main_window.show_game_info(game_data)

    def filter_games(self, results):
        """
        Фильтрация игр по результатам поиска
        Args: results: List of game dicts or None
        """
        if results is None:
            return

        # Управляем видимостью плиток в зависимости от результатов поиска
        if self.stack.currentIndex() == 1:  # Если это экран с играми
            if not results:
                # Пустой поиск - показываем плитки
                self.scroll_area.show()
            else:
                # Есть результаты - скрываем плитки
                self.scroll_area.hide()
