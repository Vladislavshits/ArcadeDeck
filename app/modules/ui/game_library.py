import os
import json
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QLabel, QScrollArea, QFileDialog, QGridLayout, QListWidget, QListWidgetItem
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from app.modules.ui.search_bar import SearchBar
from app.modules.module_logic.game_scanner import scan_games

# Добавляем логгер
logger = logging.getLogger('ArcadeDeck')

class GameTile(QPushButton):
    """Tile widget for a single game"""
    def __init__(self, game_data: dict, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self._init_ui()

    def _init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(5)

        # Game icon
        icon_label = QLabel()
        image_path = self.game_data.get("image_path")
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                icon_label.setPixmap(
                    pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio)
                )
        else:
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

        self.setFixedSize(330, 410)
        self.setObjectName("GameTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

class AddGameButton(QPushButton):
    """Кнопка добавления новой игры"""
    def __init__(self, text: str, library_page, parent=None):
        super().__init__(parent)
        self.library_page = library_page
        self.setAcceptDrops(True)
        self.setFixedSize(240, 190)
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
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._init_ui()

    def _init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Поисковая строка
        self.search_input = SearchBar(
            open_game_info_callback=self.show_game_info
        )
        # Поисковик теперь работает независимо от библиотеки
        # self.search_input.searchUpdated.connect(self.filter_games)  # Убрано!
        self.search_input.setFixedWidth(500)
        self.search_input.setMaximumWidth(500)

        search_layout = QHBoxLayout()
        search_layout.addStretch()
        search_layout.addWidget(self.search_input)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # Стек экранов
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        # Placeholder view
        self._init_placeholder_view()

        # Grid view
        self._init_grid_view()

        # Загружаем игры
        self.load_games()

    def _init_placeholder_view(self):
        """Экран для пустой библиотеки"""
        placeholder = QWidget()
        placeholder.setAcceptDrops(True)
        ph_layout = QVBoxLayout(placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.setSpacing(30)

        self.search_input_ph = self.search_input

        self.placeholder_label = QLabel("Перетащите игру сюда")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(self.placeholder_label)

        self.add_btn_ph = AddGameButton("Добавить игру", self)
        self.add_btn_ph.clicked.connect(self.open_file_dialog)
        self.add_btn_ph.setFixedWidth(500)
        self.add_btn_ph.setMaximumWidth(500)
        ph_layout.addWidget(self.add_btn_ph)

        self.stack.addWidget(placeholder)

    def _init_grid_view(self):
        """Экран с плитками игр"""
        grid_widget = QWidget()
        grid_layout = QVBoxLayout(grid_widget)

        self.search_input_grid = self.search_input

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        grid_layout.addWidget(self.scroll_area)

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
            self.load_games()
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
        """Загрузка и отображение игр через централизованный менеджер"""
        try:
            logger.info(f"[LIBRARY] Loading games using centralized manager")

            # Используем централизованный менеджер
            from app.modules.module_logic.game_data_manager import get_game_data_manager
            from pathlib import Path
            manager = get_game_data_manager(Path(self.base_dir))

            if manager:
                all_games = manager.get_all_games()
                logger.info(f"[LIBRARY] Loaded {len(all_games)} games from centralized manager")
            else:
                # Fallback для обратной совместимости
                logger.warning("[LIBRARY] Using fallback game loading")
                all_games = self._fallback_load_games()

            # Обновляем список игр в поисковике (ВСЕ игры из реестра)
            self.search_input.set_game_list(all_games)
            self.search_input_ph.set_game_list(all_games)
            self.search_input_grid.set_game_list(all_games)

            # Переключаем экран
            if not all_games:
                logger.info("[LIBRARY] No games found, showing placeholder")
                self.stack.setCurrentIndex(0)
            else:
                logger.info("[LIBRARY] Games found, showing grid")
                self.stack.setCurrentIndex(1)
                self.show_game_grid(all_games)

        except Exception as e:
            logger.error(f"Error loading games: {e}")
            import traceback
            traceback.print_exc()
            self.stack.setCurrentIndex(0)

    def _fallback_load_games(self):
        """Резервный метод загрузки игр"""
        try:
            logger.info(f"[LIBRARY] Scanning games from: {self.games_dir}")

            user_games = scan_games(self.games_dir)
            logger.info(f"[LIBRARY] Found {len(user_games)} user games")

            registry_path = os.path.join(self.base_dir, "app", "registry", "registry_games.json")
            registry_games = []
            if os.path.exists(registry_path):
                with open(registry_path, 'r', encoding='utf-8') as f:
                    registry_games = json.load(f)
                    logger.info(f"[LIBRARY] Loaded {len(registry_games)} registry games")

            all_games = user_games + [
                g for g in registry_games
                if not any(ug.get('id') == g.get('id') for ug in user_games)
            ]

            return all_games

        except Exception as e:
            logger.error(f"Error in fallback loading: {e}")
            return []

    def show_game_grid(self, games):
        """Отображение плиток игр"""
        if self.scroll_area.widget():
            self.scroll_area.widget().deleteLater()

        container = QWidget()
        layout = QGridLayout(container)
        layout.setHorizontalSpacing(15)
        layout.setVerticalSpacing(20)
        layout.setContentsMargins(15, 15, 15, 15)

        row, col, max_cols = 0, 0, 4
        for game in games:
            tile = GameTile(game)
            tile.clicked.connect(lambda _, g=game: self.show_game_info(g))
            layout.addWidget(tile, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Добавляем кнопку добавления игры в конец
        add_button = AddGameButton("Добавить игру", self)
        add_button.clicked.connect(self.open_file_dialog)
        layout.addWidget(add_button, row, col)

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
        """Фильтрация игр по результатам поиска - теперь игнорируем результаты поиска"""
        # Библиотека больше не реагирует на результаты поиска
        # Поисковик работает независимо и показывает результаты в своем выпадающем списке
        pass
