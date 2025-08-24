import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QLabel, QScrollArea, QFileDialog, QGridLayout, QListWidget, QListWidgetItem
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from app.modules.ui.search_bar import SearchBar
from app.modules.module_logic.game_scanner import scan_games


class GameTile(QPushButton):
    """Tile widget for a single game"""
    def __init__(self, game_data: dict, parent=None):  # Принимаем данные игры
        super().__init__(parent)
        self.game_data = game_data  # Сохраняем данные игры
        self._init_ui()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Game icon
        icon_label = QLabel()
        pixmap = QPixmap(":/icons/game_placeholder.png")
        if pixmap.isNull():
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.gray)
        icon_label.setPixmap(
            pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio)
        )
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Game title
        title_label = QLabel(self.game_data.get("title", "Без названия"))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)


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

        # Stacked widget for different views
        self.stack = QStackedWidget()

        # Placeholder view (empty library)
        self._init_placeholder_view()

        # Grid view (with games)
        self._init_grid_view()

        layout.addWidget(self.stack)
        self.load_games()

    def _init_placeholder_view(self):
        """Initialize view for empty library"""
        placeholder = QWidget()
        placeholder.setAcceptDrops(True)
        ph_layout = QVBoxLayout(placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.setSpacing(30)

        # Search bar
        self.search_input_ph = SearchBar(
            open_game_info_callback=self.show_game_info
        )
        self.search_input_ph.setFixedWidth(500)
        self.search_input_ph.setMaximumWidth(500)
        ph_layout.addWidget(self.search_input_ph)

        # Empty state label
        self.placeholder_label = QLabel("Перетащите игру сюда")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(self.placeholder_label)

        # Add game button
        self.add_btn_ph = AddGameButton("Добавить игру", self)
        self.add_btn_ph.clicked.connect(self.open_file_dialog)
        self.add_btn_ph.setFixedWidth(500)
        self.add_btn_ph.setMaximumWidth(500)
        ph_layout.addWidget(self.add_btn_ph)

        self.stack.addWidget(placeholder)

    def _init_grid_view(self):
        """Initialize grid view with games"""
        grid_widget = QWidget()
        grid_layout = QVBoxLayout(grid_widget)

        # Search bar
        self.search_input_grid = SearchBar(
            open_game_info_callback=self.show_game_info
        )
        self.search_input_grid.searchUpdated.connect(self.filter_games)
        self.search_input_grid.setFixedWidth(500)
        self.search_input_grid.setMaximumWidth(500)

        search_layout = QHBoxLayout()
        search_layout.addStretch()
        search_layout.addWidget(self.search_input_grid)
        search_layout.addStretch()
        grid_layout.addLayout(search_layout)

        # Search results list
        self.results_list_widget = QListWidget()
        self.results_list_widget.itemClicked.connect(
            self._on_search_item_clicked
        )
        self.results_list_widget.hide()
        grid_layout.addWidget(self.results_list_widget)

        # Game tiles scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        grid_layout.addWidget(self.scroll_area)

        self.stack.addWidget(grid_widget)

    def _on_search_item_clicked(self, item):
        """Handle click on search result item"""
        game = item.data(1000)
        if game:
            self.show_game_info(game)

    def dragEnterEvent(self, event):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle drop event"""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            self.handle_file_drop(path)

    def handle_file_drop(self, path):
        """Import dropped game file"""
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
        """Open file dialog to select game"""
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
        # Сканируем игры из users/games
        user_games = scan_games(self.games_dir)

        # Загружаем игры из реестра
        registry_path = os.path.join(self.base_dir, "app", "registry", "registry_games.json")
        registry_games = []
        if os.path.exists(registry_path):
            with open(registry_path, 'r') as f:
                registry_games = json.load(f)

        # Объединяем игры (установленные + из реестра)
        all_games = user_games + [
            g for g in registry_games 
            if not any(ug['id'] == g['id'] for ug in user_games)
        ]

        try:
            self.search_input_ph.set_game_list(all_games)
            self.search_input_grid.set_game_list(all_games)
        except Exception as e:
            print(f"Error setting game list: {e}")

        if not all_games:
            self.stack.setCurrentIndex(0)
        else:
            self.stack.setCurrentIndex(1)
            self.show_game_grid(all_games)

    def show_game_grid(self, games):
        # Очистка предыдущего контента
        if self.scroll_area.widget():
            self.scroll_area.widget().deleteLater()

        # Создание контейнера
        container = QWidget()
        layout = QGridLayout(container)
        layout.setSpacing(20)

        # Добавление игр
        row, col, max_cols = 0, 0, 4
        for game in games:
            tile = GameTile(game)
            tile.clicked.connect(lambda _, g=game: self.show_game_info(g))
            layout.addWidget(tile, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Обновление ScrollArea
        self.scroll_area.setWidget(container)
        self.scroll_area.show()
        self.results_list_widget.hide()

    def show_game_info(self, game_data):
        """Show game info page"""
        if not game_data:
            return

        main_window = self.window()
        if hasattr(main_window, "show_game_info"):
            main_window.show_game_info(game_data)

    def filter_games(self, results):
        """
        Filter games based on search results
        Args: results: List of game dicts or None
        """
        if results is None:
            return

        if not results:
            # Empty search - show full library
            self.results_list_widget.hide()
            self.load_games()
            return

        # Show search results
        self.results_list_widget.clear()
        for game in results:
            item = QListWidgetItem(game.get("title", "Без названия"))
            item.setData(1000, game)
            self.results_list_widget.addItem(item)

        # Show results and hide tiles
        self.scroll_area.hide()
        self.results_list_widget.show()
