import os
import json
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QLabel, QScrollArea, QFileDialog, QGridLayout, QListWidget, QListWidgetItem,
    QLineEdit, QFrame, QSizePolicy, QSpacerItem
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

# Импортируем оверлей поиска
from app.modules.ui.search_overlay import SearchOverlay
from app.modules.module_logic.game_scanner import scan_games

# Импорт пути игровых данных
from core import get_users_subpath

# Добавляем логгер
logger = logging.getLogger('ArcadeDeck')

class GameTile(QFrame):
    """Tile widget for a single game"""
    clicked = pyqtSignal()

    def __init__(self, game_data: dict, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self._init_ui()

    def _init_ui(self):
        """Initialize UI components"""
        self.setMinimumSize(200, 420)
        self.setMaximumSize(260, 550)
        self.setObjectName("GameTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Контейнер для обложки игры - занимает большую часть плитки
        self.cover_container = QFrame()
        self.cover_container.setObjectName("CoverContainer")
        cover_layout = QVBoxLayout(self.cover_container)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        cover_layout.setSpacing(0)

        # Game cover - занимает большую часть плитки
        self.cover_label = QLabel()
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Устанавливаем пропорциональные размеры для обложки
        self.cover_label.setMinimumSize(200, 350)
        self.cover_label.setMaximumSize(260, 370)

        # Загружаем обложку
        self.update_cover_image()

        cover_layout.addWidget(self.cover_label)
        layout.addWidget(self.cover_container, 5)  # 5/6 частей для обложки

        # Контейнер для названия игры - меньшая часть
        title_container = QFrame()
        title_container.setMinimumHeight(35)
        title_container.setMaximumHeight(60)
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(8, 4, 8, 8)
        title_layout.setSpacing(0)

        # Game title - одна строка с троеточием
        self.title_label = QLabel(self.game_data.get("title", "Без названия"))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Настройки для обрезания текста
        self.title_label.setWordWrap(False)
        self.title_label.setMinimumHeight(18)
        self.title_label.setMaximumHeight(24)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        title_layout.addWidget(self.title_label)
        layout.addWidget(title_container, 1)  # 1/6 часть для названия

    def resizeEvent(self, event):
        """Обработчик изменения размера"""
        super().resizeEvent(event)
        # Обновляем обложку при изменении размера
        self.update_cover_image()

    def update_cover_image(self):
        """Обновить изображение обложки с учетом пользовательских обложек"""
        # Сначала пытаемся найти пользовательскую обложку
        custom_cover_path = self.get_custom_cover_path()

        if custom_cover_path and os.path.exists(custom_cover_path):
            try:
                pixmap = QPixmap(custom_cover_path)
                if not pixmap.isNull():
                    self.set_cover_pixmap(pixmap)
                    return
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки пользовательской обложки: {e}")

        # Используем стандартную обложку из данных игры
        image_path = self.game_data.get("image_path")
        if image_path and os.path.exists(image_path):
            try:
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    self.set_cover_pixmap(pixmap)
                    return
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки стандартной обложки: {e}")

        # Fallback - серая плитка
        self.set_fallback_cover()

    def set_cover_pixmap(self, pixmap):
        """Установить обложку с правильным масштабированием - СОХРАНЯЕМ ПРОПОРЦИИ"""
        if hasattr(self, 'cover_label') and self.cover_label:
            # Получаем текущий размер label'а
            label_size = self.cover_label.size()
            if label_size.width() > 0 and label_size.height() > 0:
                # Масштабируем обложку с сохранением пропорций и обрезанием
                scaled_pixmap = pixmap.scaled(
                    label_size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.cover_label.setPixmap(scaled_pixmap)

    def set_fallback_cover(self):
        """Установить fallback обложку"""
        if hasattr(self, 'cover_label') and self.cover_label:
            label_size = self.cover_label.size()
            if label_size.width() > 0 and label_size.height() > 0:
                pixmap = QPixmap(label_size)
                pixmap.fill(Qt.GlobalColor.darkGray)
                self.cover_label.setPixmap(pixmap)
    def get_custom_cover_path(self):
        """Получить путь к пользовательской обложке игры"""
        if not self.game_data:
            return None

        game_id = self.game_data.get('id')
        platform = self.game_data.get('platform')

        if not all([game_id, platform]):
            return None

        # Получаем project_root из родительского окна
        try:
            project_root = self.window().project_root
        except AttributeError:
            project_root = Path(".")

        # Формируем путь к пользовательской обложке
        images_dir = Path(get_users_subpath("images")) / platform / game_id

        # Ищем файлы изображений
        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.webp']
        for ext in image_extensions:
            cover_path = images_dir / f"cover{ext}"
            if cover_path.exists():
                return str(cover_path)

        return None

    def refresh_cover(self):
        """Обновить обложку (вызывается при изменении пользовательской обложки)"""
        self.update_cover_image()

    def mousePressEvent(self, event):
        """Обработчик клика по плитке"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class AddGameButton(QPushButton):
    """Кнопка добавления новой игры с иконкой и текстом"""
    def __init__(self, text: str, library_page, parent=None, is_large=False):
        super().__init__(parent)
        self.library_page = library_page
        self.is_large = is_large
        self.setAcceptDrops(True)

        # Устанавливаем размеры в зависимости от типа кнопки
        if is_large:
            # Занимает 2/4 экрана - будет установлено динамически
            self.setMinimumSize(600, 400)
            self.setObjectName("LargeAddGameArea")
        else:
            self.setFixedHeight(40)
            self.setObjectName("AddGameButton")

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Создаем QHBoxLayout для контента
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Текст кнопки
        text_label = QLabel(text)
        text_label.setObjectName("AddGameButtonLabel")
        layout.addWidget(text_label)

        # Добавляем иконку "+"
        plus_label = QLabel("+")
        layout.addWidget(plus_label)

    def dragEnterEvent(self, event):
        """Accept drag events with URLs"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle dropped files"""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            self.library_page.handle_file_drop(path)

class SearchTrigger(QLineEdit):
    searchActivated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Поиск игры")
        self.setFixedSize(450, 65)
        self.setObjectName("SearchInput")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Убираем фокус

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.searchActivated.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

class GameLibrary(QWidget):
    """Main game library widget"""
    coverUpdated = pyqtSignal(str)  # Сигнал обновления обложки для игры

    def __init__(self, games_dir: str, parent=None):
        super().__init__(parent)
        self.games_dir = games_dir
        self.base_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.all_games = []
        self.game_tiles = {}  # Словарь для хранения плиток игр по ID
        self._init_ui()

    def _init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Создаем оверлей поиска
        self.search_overlay = SearchOverlay(self)
        self.search_overlay.hide()
        self.search_overlay.resultSelected.connect(self.show_game_info)
        self.search_overlay.searchClosed.connect(self.on_search_closed)

        # Стек экранов
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self._init_empty_state()  # Инициализируем экран пустой библиотеки
        self._init_grid_view()

        # Загружаем игры
        self.load_games()

        # Убираем фокус с элементов интерфейса
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    def _init_empty_state(self):
        """Экран для пустой библиотеки с поиском по центру и большой кнопкой-областью"""
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.setSpacing(0)

        # Хедер с поиском (только поиск по центру, кнопка скрыта)
        header_widget = QWidget()
        header_widget.setFixedHeight(100)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 10, 20, 10)

        header_layout.addStretch()

        # Поле поиска для пустого состояния
        self.search_input_empty = SearchTrigger()
        self.search_input_empty.searchActivated.connect(self.show_search_overlay)
        header_layout.addWidget(self.search_input_empty)

        # Пустое место вместо кнопки (для сохранения баланса)
        spacer = QWidget()
        spacer.setFixedSize(150, 40)
        header_layout.addWidget(spacer)

        header_layout.addStretch()
        empty_layout.addWidget(header_widget)

        # Центральный контейнер с большой кнопкой-областью
        center_container = QWidget()
        center_container.setObjectName("EmptyLibraryContainer")
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(30)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Большая кнопка-область добавления игры
        self.large_add_button = AddGameButton("Добавить игру", self, is_large=True)
        self.large_add_button.clicked.connect(self.open_file_dialog)
        self.large_add_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        center_layout.addWidget(self.large_add_button)

        # Добавляем растяжку сверху и снизу для центрирования
        empty_layout.addStretch(1)
        empty_layout.addWidget(center_container, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch(1)

        self.stack.addWidget(empty_widget)

    def _init_grid_view(self):
        """Экран с плитками игр"""
        grid_widget = QWidget()
        grid_layout = QVBoxLayout(grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)

        # Горизонтальный хедер с поиском и кнопкой добавления
        header_widget = QWidget()
        header_widget.setFixedHeight(100)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 10, 20, 10)

        header_layout.addStretch()

        self.search_input_grid = SearchTrigger()
        self.search_input_grid.searchActivated.connect(self.show_search_overlay)
        header_layout.addWidget(self.search_input_grid)

        # Кнопка добавления игры
        self.add_game_button = AddGameButton("Добавить игру", self)
        self.add_game_button.clicked.connect(self.open_file_dialog)
        self.add_game_button.setFixedSize(150, 40)
        self.add_game_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        header_layout.addWidget(self.add_game_button)

        header_layout.addStretch()
        grid_layout.addWidget(header_widget)

        # Контейнер для плиток игр
        self.games_container = QFrame()
        self.games_container.setObjectName("GamesContainer")
        self.games_container.setStyleSheet("""
            #GamesContainer {
                background: transparent;
                border: none;
            }
        """)

        games_layout = QVBoxLayout(self.games_container)
        games_layout.setContentsMargins(20, 140, 20, 20)
        games_layout.setSpacing(0)

        # Создаем контейнер для сетки плиток
        self.grid_container = QWidget()
        self.grid_container.setObjectName("GridContainer")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setHorizontalSpacing(25)  # Увеличили отступы
        self.grid_layout.setVerticalSpacing(25)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)

        # Оборачиваем сетку в QScrollArea
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("GamesScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.grid_container)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        games_layout.addWidget(self.scroll_area)
        grid_layout.addWidget(self.games_container, 1)

        self.stack.addWidget(grid_widget)

    def resizeEvent(self, event):
        """Обновление размера при изменении окна"""
        super().resizeEvent(event)
        # Устанавливаем размер оверлея равным размеру GameLibrary
        self.search_overlay.setGeometry(self.rect())

        # Размер кнопки-области для пустого состояния
        if hasattr(self, 'large_add_button') and self.large_add_button:
            # Занимаем 3/4 ширины и 1/2 высоты экрана
            parent_size = self.size()
            button_width = int(parent_size.width() * 0.75)  # 3/4 ширины
            button_height = parent_size.height() // 2       # 1/2 высоты
            self.large_add_button.setFixedSize(button_width, button_height)

        # Принудительно перестраиваем сетку при изменении размера
        if self.all_games and len(self.all_games) > 0:
            QTimer.singleShot(50, lambda: self.show_game_grid(self.all_games))

    def update_tiles_size(self):
        """Обновить размеры всех плиток"""
        for tile in self.game_tiles.values():
            if hasattr(tile, 'update_tile_size'):
                tile.update_tile_size()

    def show_search_overlay(self):
        """Показать оверлей поиска"""
        # Устанавливаем размер оверлея равным размеру GameLibrary
        self.search_overlay.setGeometry(self.rect())
        self.search_overlay.set_game_list(self.all_games)
        self.search_overlay.show_overlay()

    def on_search_closed(self):
        """Обработчик закрытия поиска"""
        # Сбрасываем текст в SearchBar
        if hasattr(self, 'search_input_ph'):
            self.search_input_ph.clear()
        self.search_input_grid.clear()
        self.search_input_empty.clear()
        self.setFocus()

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
            # ПЕРЕДАЕМ project_root как второй аргумент
            game_data = import_game(path, Path(self.base_dir))
            QMessageBox.information(
                self,
                "Готово",
                f"Игра добавлена: {game_data.get('title', 'Без названия')}"
            )
            self.load_games()
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def open_file_dialog(self):
        """Открытие диалога выбора файла с фильтрами из импортера"""
        try:
            from app.modules.module_logic.game_importer import create_importer

            project_root = Path(__file__).parent.parent.parent.parent
            importer = create_importer(project_root)
            file_filter = importer.get_file_dialog_filters()

            path, selected_filter = QFileDialog.getOpenFileName(
                self,
                "Выберите файл игры",
                "",
                file_filter
            )

            if path:
                self.handle_file_drop(path)

        except Exception as e:
            logger.error(f"❌ Ошибка открытия диалога выбора файла: {e}")
            # Fallback
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Выберите файл игры",
                "",
                "Все файлы (*.*)"
            )
            if path:
                self.handle_file_drop(path)

    def load_games(self):
        """Загрузка и отображение игр через централизованный менеджер"""
        try:
            from app.modules.module_logic.game_data_manager import get_game_data_manager
            manager = get_game_data_manager(Path(self.base_dir))

            if manager:
                all_games = manager.get_all_games()
            else:
                all_games = self._fallback_load_games()

            self.all_games = all_games
            self.search_overlay.set_game_list(all_games)

            # Переключаем вид в зависимости от наличия игр
            if not all_games:
                self.stack.setCurrentIndex(0)  # Экран пустой библиотеки
            else:
                self.stack.setCurrentIndex(1)  # Экран с играми
                self.show_game_grid(all_games)

        except Exception as e:
            logger.error(f"Error loading games: {e}")
            self.stack.setCurrentIndex(0)

    def _fallback_load_games(self):
        """Резервный метод загрузки игр"""
        try:
            user_games = scan_games(self.games_dir)
            registry_path = self.base_dir / "app" / "registry" / "registry_games.json"
            registry_games = []
            if registry_path.exists():
                with open(registry_path, 'r', encoding='utf-8') as f:
                    registry_games = json.load(f)

            return user_games + [
                g for g in registry_games
                if not any(ug.get('id') == g.get('id') for ug in user_games)
            ]

        except Exception as e:
            logger.error(f"Error in fallback loading: {e}")
            return []

    def show_game_grid(self, games):
        """Отображение плиток игр"""
        # Очищаем старый layout
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.game_tiles.clear()

        # Рассчитываем количество колонок в зависимости от ширины контейнера
        container_width = self.grid_container.width()
        # УВЕЛИЧИЛИ МИНИМАЛЬНУЮ ШИРИНУ ПЛИТКИ
        min_tile_width = 200
        horizontal_spacing = 20

        # Вычисляем максимальное количество колонок
        max_cols = max(1, (container_width - 40) // (min_tile_width + horizontal_spacing))

        # Если колонок больше чем игр - центрируем
        if len(games) < max_cols:
            max_cols = len(games)

        row, col = 0, 0

        for game in games:
            tile = GameTile(game, parent=self.grid_container)
            game_id = game.get('id')
            if game_id:
                self.game_tiles[game_id] = tile

            # Подключаем клик по плитке
            tile.clicked.connect(lambda checked=False, g=game: self.show_game_info(g))

            self.grid_layout.addWidget(tile, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Настраиваем растяжение колонок
        for i in range(max_cols):
            self.grid_layout.setColumnStretch(i, 1)
            self.grid_layout.setColumnMinimumWidth(i, min_tile_width)

        # Добавляем растяжку снизу
        if row > 0 or col > 0:
            self.grid_layout.addItem(
                QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding),
                row + 1, 0, 1, max_cols
            )

        # Принудительно обновляем layout
        self.grid_container.update()
        self.grid_container.repaint()

    def show_game_info(self, game_data):
        """Показать информацию об игре"""
        if not game_data:
            return

        main_window = self.window()
        if hasattr(main_window, "show_game_info"):
            # Скрываем оверлей поиска перед переходом
            self.search_overlay.hide_overlay()
            # Вызываем метод главного окна
            main_window.show_game_info(game_data)

    def update_game_cover(self, game_id):
        """Обновить обложку для конкретной игры"""
        if game_id in self.game_tiles:
            tile = self.game_tiles[game_id]
            tile.refresh_cover()

    def filter_games(self, results):
        """Фильтрация игр по результатам поиска"""
        pass
