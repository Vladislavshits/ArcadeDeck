# game_library.py
import os
import json
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QLabel, QScrollArea, QFileDialog, QGridLayout, QListWidget, QListWidgetItem,
    QLineEdit, QFrame, QSizePolicy, QSpacerItem, QButtonGroup
)
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QPen
from PyQt6.QtCore import Qt, QRunnable, QThreadPool, QObject, pyqtSignal, QTimer, QRect, QPoint, QRectF

from app.modules.ui.search_overlay import SearchOverlay
from app.modules.module_logic.game_scanner import scan_games
from core import get_users_subpath, BASE_DIR

# Импорт модуля навигации
from navigation import NavigationLayer

logger = logging.getLogger('Модуль библиотеки игр')

# Глобальный кэш масштабированных обложек: {game_id: {size_tuple: QPixmap}}
from collections import defaultdict
COVER_CACHE = defaultdict(dict)

# Ограничим количество потоков для загрузки обложек
QThreadPool.globalInstance().setMaxThreadCount(4)


class FocusButton(QPushButton):
    """Кнопка с внешностью карточки и предсказуемым фокусом"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)      # ← КЛЮЧЕВОЕ ИЗМЕНЕНИЕ
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("focused", False)

    def focusInEvent(self, event):
        self.setProperty("focused", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.setProperty("focused", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().focusOutEvent(event)


class TileMetrics:
    """Единые размеры карточки игры (4 в ряд на экране Deck)."""
    COLS = 4
    TILE_W = 240
    TILE_H = 0
    LAYOUT_MARGIN = 10
    LAYOUT_SPACING = 15
    INNER_W = TILE_W - 2 * LAYOUT_MARGIN
    COVER_H = 340
    TITLE_H = 10
    COVER_RADIUS = 12
    COVER_ZOOM_RELAX = 1.08
    PLACEHOLDER = QColor("#2a2a2e")
    # Обводка обложки (QSS на QLabel#GameCover не работает — рисуем в paintEvent)
    COVER_BORDER_WIDTH = 3       # обычная серая рамка
    FOCUS_BORDER_WIDTH = 4       # синяя рамка при фокусе (толщина — меняй здесь)
    COVER_BORDER_COLOR = QColor("#45454b")
    FOCUS_COLOR = QColor(100, 181, 246)


class CoverImageLabel(QLabel):
    """Обложка со скруглением и умеренным cover-crop (QSS не режет pixmap)."""
    RADIUS = TileMetrics.COVER_RADIUS

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GameCover")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)
        self._source: QPixmap | None = None

    def set_source_pixmap(self, pixmap: QPixmap | None):
        self._source = pixmap if pixmap and not pixmap.isNull() else None
        self.update()

    def clear_cover(self):
        self._source = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, self.RADIUS, self.RADIUS)
        painter.setClipPath(path)
        painter.fillRect(self.rect(), TileMetrics.PLACEHOLDER)

        if self._source and not self._source.isNull():
            iw, ih = self.width(), self.height()
            if iw > 0 and ih > 0:
                relax = TileMetrics.COVER_ZOOM_RELAX
                scaled = self._source.scaled(
                    max(1, int(iw * relax)),
                    max(1, int(ih * relax)),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                sx = max(0, (scaled.width() - iw) // 2)
                sy = max(0, (scaled.height() - ih) // 2)
                painter.drawPixmap(0, 0, iw, ih, scaled, sx, sy, iw, ih)

        self._paint_cover_border(painter, rect)
        painter.end()

    def _paint_cover_border(self, painter: QPainter, rect: QRectF):
        """Обводка всегда в коде: и для заглушки, и для обложки, и при фокусе."""
        painter.setClipping(False)
        if self._tile_is_focused():
            width = TileMetrics.FOCUS_BORDER_WIDTH
            color = TileMetrics.FOCUS_COLOR
        else:
            width = TileMetrics.COVER_BORDER_WIDTH
            color = TileMetrics.COVER_BORDER_COLOR

        pen = QPen(color, width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inset = width / 2.0 + 0.5
        painter.drawRoundedRect(
            rect.adjusted(inset, inset, -inset, -inset),
            self.RADIUS, self.RADIUS,
        )

    def _tile_is_focused(self) -> bool:
        w = self.parent()
        while w:
            if w.objectName() == "GameTile":
                return bool(w.property("focused"))
            w = w.parent()
        return False


class PlatformTag(QPushButton):
    """Плашка-тег платформы для фильтрации"""

    def __init__(self, platform_name: str, parent=None):
        super().__init__(parent)
        self.platform_name = platform_name
        self._init_ui()

    def _init_ui(self):
        """Инициализация UI плашки"""
        self.setText(self.platform_name)
        self.setFixedHeight(45)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("PlatformTag")
        self.setCheckable(True)


class GameTile(FocusButton):
    """Карточка игры: обложка + название (FocusButton для навигации)."""
    def __init__(self, game_data, parent=None):
        super().__init__("", parent)
        self.game_data = game_data
        self.cover_loaded = False
        self._current_pixmap = None
        self._init_ui()
        self.apply_tile_metrics()
        self.set_fallback_cover()

    def _init_ui(self):
        self.setObjectName("GameTile")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        m = TileMetrics
        layout = QVBoxLayout(self)
        layout.setContentsMargins(m.LAYOUT_MARGIN, m.LAYOUT_MARGIN, m.LAYOUT_MARGIN, m.LAYOUT_MARGIN)
        layout.setSpacing(m.LAYOUT_SPACING)

        cover_row = QHBoxLayout()
        cover_row.setContentsMargins(0, 0, 0, 0)
        cover_row.setSpacing(0)
        self.cover_label = CoverImageLabel(self)
        cover_row.addStretch(1)
        cover_row.addWidget(self.cover_label)
        cover_row.addStretch(1)
        layout.addLayout(cover_row)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(0)
        self.title_label = QLabel(self.game_data.get("title", "Без названия"), self)
        self.title_label.setObjectName("GameTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        title_row.addWidget(self.title_label)
        layout.addLayout(title_row)

    def apply_tile_metrics(self):
        m = TileMetrics
        self.setFixedSize(m.TILE_W, m.TILE_H)
        self.cover_label.setFixedSize(m.INNER_W, m.COVER_H)
        self.title_label.setFixedWidth(m.INNER_W)
        self.title_label.setFixedHeight(m.TITLE_H)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.cover_label.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.cover_label.update()

    def load_cover_if_needed(self):
        if not self.cover_loaded:
            self.cover_loaded = True
            worker = CoverLoadWorker(self.game_data)
            worker.signals.finished.connect(self._on_cover_loaded)
            QThreadPool.globalInstance().start(worker)

    def _start_cover_loading(self):
        """Запуск загрузки обложки в фоновом потоке"""
        worker = CoverLoadWorker(self.game_data)
        worker.signals.finished.connect(self._on_cover_loaded)
        QThreadPool.globalInstance().start(worker)

    def _on_cover_loaded(self, game_id: str, pixmap):
        """Обработчик завершения загрузки обложки"""
        if pixmap is not None:
            self._current_pixmap = pixmap  # сохраняем оригинальное фото
            self.set_cover_pixmap(pixmap)
        # Если None — оставляем fallback (серую)

    def set_cover_pixmap(self, pixmap):
        """Передаёт исходник в CoverImageLabel (масштаб и crop — в paintEvent)."""
        if not hasattr(self, 'cover_label') or not self.cover_label:
            return
        if not pixmap or pixmap.isNull():
            return

        label_size = self.cover_label.size()
        if not label_size.isValid() or label_size.width() <= 0 or label_size.height() <= 0:
            QTimer.singleShot(0, lambda: self.set_cover_pixmap(pixmap))
            return

        game_id = self.game_data.get('id', 'unknown')
        COVER_CACHE[game_id]['source'] = pixmap
        self.cover_label.set_source_pixmap(pixmap)

    def set_fallback_cover(self):
        """Placeholder до загрузки обложки"""
        if hasattr(self, 'cover_label') and self.cover_label:
            self.cover_label.clear_cover()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Если обложка уже загружена — обновим её под новый размер
        if hasattr(self, '_current_pixmap') and self._current_pixmap:
            self.set_cover_pixmap(self._current_pixmap)


class CoverLoadWorker(QRunnable):
    """Фоновый загрузчик обложки"""

    class Signals(QObject):
        finished = pyqtSignal(str, object)  # game_id, QPixmap или None

    def __init__(self, game_data):
        super().__init__()
        self.game_data = game_data
        self.signals = self.Signals()

    def run(self):
        from app.modules.module_logic.game_art_manager import GameArtManager
        import os
        from pathlib import Path

        game_id = self.game_data.get('id')
        platform = self.game_data.get('platform')
        title = self.game_data.get('title')
        pixmap = None

        try:
            project_root = Path(__file__).parent.parent.parent.parent

            # 1. Пользовательская обложка
            if game_id and platform:
                images_dir = Path(get_users_subpath("images")) / platform / game_id
                for ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']:
                    cover_path = images_dir / f"cover{ext}"
                    if cover_path.exists():
                        pixmap = QPixmap(str(cover_path))
                        if not pixmap.isNull():
                            break

            # 2. Через GameArtManager
            if (not pixmap or pixmap.isNull()) and platform and title:
                manager = GameArtManager(project_root)
                cover_path = manager.get_cover_path(platform, title)
                if cover_path and os.path.exists(cover_path):
                    pixmap = QPixmap(cover_path)

            # 3. Fallback image_path
            if (not pixmap or pixmap.isNull()):
                image_path = self.game_data.get("image_path")
                if image_path and os.path.exists(image_path):
                    pixmap = QPixmap(image_path)

        except Exception as e:
            logger.error(f"Ошибка загрузки обложки: {e}")
            pixmap = None

        # Отправляем результат (даже если None)
        self.signals.finished.emit(game_id or "unknown", pixmap if (pixmap and not pixmap.isNull()) else None)


class AddGameButton(QPushButton):
    """Кнопка добавления новой игры"""
    def __init__(self, text: str, library_page, parent=None, is_large=False):
        super().__init__(parent)
        self.library_page = library_page
        self.is_large = is_large
        self.setAcceptDrops(True)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_label = QLabel(text)
        text_label.setObjectName("AddGameButtonLabel")
        layout.addWidget(text_label)

        plus_label = QLabel("+")
        layout.addWidget(plus_label)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            self.library_page.handle_file_drop(path)


class SearchTrigger(QPushButton):
    searchActivated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setText("🔍")
        self.clicked.connect(self.searchActivated.emit)


class PlatformFilterManager:
    """Менеджер фильтрации по платформам"""

    def __init__(self, library_widget):
        self.library = library_widget
        self.current_platform_filter = "Все"
        self.platform_tags = {}
        self.tag_button_group = QButtonGroup()
        self.tag_button_group.setExclusive(True)

    def create_platform_tags(self, games_list):
        """Создает теги платформ на основе списка игр"""
        logger.info("🎯 СОЗДАНИЕ ТЕГОВ ПЛАТФОРМ")

        # Определяем контейнер для тегов в зависимости от состояния
        if self.library.stack.currentIndex() == 1:  # Есть установленные игры
            tags_container = self.library.tags_container
            tags_layout = self.library.tags_layout
        else:  # Нет установленных - используем доступные
            tags_container = self.library.tags_container_empty
            tags_layout = self.library.tags_layout_empty

        # Очищаем старые теги
        self._clear_tags_container(tags_layout)
        self.platform_tags.clear()

        # Собираем уникальные платформы
        unique_platforms = self._get_unique_platforms(games_list)
        logger.info(f"🏷️ Найдены платформы: {sorted(unique_platforms)}")

        # Создаем теги
        self._create_tag_elements(unique_platforms, tags_layout)

        tags_container.update()

    def _clear_tags_container(self, tags_layout):
        """Очищает контейнер тегов"""
        while tags_layout.count():
            child = tags_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _get_unique_platforms(self, games_list):
        """Получает уникальные платформы из списка игр"""
        unique_platforms = set()
        for game in games_list:
            platform = game.get('platform')
            if platform:
                unique_platforms.add(platform)
        return sorted(unique_platforms)

    def _create_tag_elements(self, platforms, tags_layout):
        """Создает элементы тегов"""
        # Добавляем тег "Все"
        all_tag = PlatformTag("Все")
        all_tag.setChecked(True)
        all_tag.clicked.connect(lambda: self._on_tag_clicked("Все"))
        self.tag_button_group.addButton(all_tag)
        self.platform_tags["Все"] = all_tag
        tags_layout.addWidget(all_tag)

        # Добавляем теги для каждой платформы
        for platform in platforms:
            tag = PlatformTag(platform)
            tag.clicked.connect(self._make_click_handler(platform))
            self.tag_button_group.addButton(tag)
            self.platform_tags[platform] = tag
            tags_layout.addWidget(tag)

        tags_layout.addStretch()

        # Собираем список тегов для навигации (sorted по порядку)
        self.tag_widgets = [self.platform_tags["Все"]] + [self.platform_tags[p] for p in platforms]

    def _make_click_handler(self, platform):
        return lambda checked=False: self._on_tag_clicked(platform)

    def _on_tag_clicked(self, platform_name):
        """Обработчик клика по тегу"""
        logger.info(f"🎯 ФИЛЬТРАЦИЯ: выбрана платформа '{platform_name}'")
        self.current_platform_filter = platform_name
        self.library.apply_platform_filter(platform_name)

    def get_current_filter(self):
        """Возвращает текущий активный фильтр"""
        return self.current_platform_filter


class GameLibrary(QWidget):
    """Страница библиотеки игр"""
    coverUpdated = pyqtSignal(str)
    focusChanged = pyqtSignal(QWidget)
    cover_updated_signal = pyqtSignal(str)

    def __init__(self, games_dir: str, parent=None):
        super().__init__(parent)
        self.games_dir = games_dir
        self.base_dir = Path(BASE_DIR).parent
        self.all_games = []
        self.available_games = []
        self.filtered_games = []
        self.game_tiles = {}
        self.cover_updated_signal.connect(self.update_game_cover)

        # Таймер для отложенной загрузки обложек видимых плиток
        self.visibility_timer = QTimer(self)
        self.visibility_timer.setInterval(100)  # Проверять раз в 100ms после прокрутки
        self.visibility_timer.setSingleShot(True)  # Debounce: запускать один раз
        self.visibility_timer.timeout.connect(self._load_visible_covers)
        
        # Флаг для отслеживания переключения вида
        self._just_switched_view = False

        # Новая система фильтрации
        self.filter_manager = PlatformFilterManager(self)

        # Параметры сетки (cols = TileMetrics.COLS для навигации main_grid_cols)
        self.tiles_per_row = TileMetrics.COLS
        self.tile_spacing = 40
        self.scroll_to_focused = True   # Будет использовано в навигации

        self._init_ui()

    def _init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Стек экранов
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self._init_empty_state()
        self._init_grid_view()

        # Загружаем игры
        self.load_games()

        self.setFocus()

    def _init_empty_state(self):
        """Экран для пустой библиотеки"""
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.setSpacing(0)

        # Хедер с центрированными кнопками
        header_widget = QWidget()
        header_widget.setFixedHeight(100)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 10, 20, 10)

        # Центральный контейнер с тремя кнопками
        center_container = QWidget()
        center_layout = QHBoxLayout(center_container)
        center_layout.setSpacing(25)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # Кнопка переключения
        self.switch_view_button_empty = QPushButton("📚 Мои игры")
        self.switch_view_button_empty.setObjectName("SwitchViewButton")
        self.switch_view_button_empty.clicked.connect(self.switch_to_installed_view)
        center_layout.addWidget(self.switch_view_button_empty)

        # Кнопка поиска
        self.search_button_empty = SearchTrigger()
        self.search_button_empty.searchActivated.connect(self.show_search_overlay)
        center_layout.addWidget(self.search_button_empty)

        # Кнопка добавления игры
        self.add_game_button_empty = AddGameButton("Добавить игру", self, is_large=False)
        self.add_game_button_empty.clicked.connect(self.open_file_dialog)
        center_layout.addWidget(self.add_game_button_empty)

        # Растягиваем слева и справа от центрального контейнера
        header_layout.addStretch(1)
        header_layout.addWidget(center_container)
        header_layout.addStretch(1)

        empty_layout.addWidget(header_widget)

        # Контейнер для тегов платформ
        self.tags_container_empty = QWidget()
        self.tags_container_empty.setObjectName("TagsContainer")
        self.tags_container_empty.setFixedHeight(80)
        self.tags_layout_empty = QHBoxLayout(self.tags_container_empty)
        self.tags_layout_empty.setContentsMargins(20, 20, 20, 20)
        self.tags_layout_empty.setSpacing(10)
        self.tags_layout_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.tags_container_empty)

        # Контейнер для плиток игр
        self.games_container_empty = QFrame()
        self.games_container_empty.setObjectName("GamesContainer")
        self.games_container_empty.setStyleSheet("#GamesContainer { background: transparent; border: none; }")

        games_layout_empty = QVBoxLayout(self.games_container_empty)
        games_layout_empty.setContentsMargins(20, 20, 20, 20)
        games_layout_empty.setSpacing(0)

        # Сетка плиток
        self.grid_container_empty = QWidget()
        self.grid_container_empty.setObjectName("GridContainer")
        self.grid_layout_empty = QGridLayout(self.grid_container_empty)
        self.grid_layout_empty.setHorizontalSpacing(25)
        self.grid_layout_empty.setVerticalSpacing(25)
        self.grid_layout_empty.setContentsMargins(0, 0, 0, 0)
        self.grid_layout_empty.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)

        # Scroll area
        self.scroll_area_empty = QScrollArea()
        self.scroll_area_empty.setObjectName("GamesScrollArea")
        self.scroll_area_empty.setWidgetResizable(True)
        self.scroll_area_empty.setWidget(self.grid_container_empty)
        self.scroll_area_empty.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area_empty.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area_empty.setFrameShape(QFrame.Shape.NoFrame)
        
        # Подключаем прокрутку для ленивой загрузки
        self.scroll_area_empty.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        self.scroll_area_empty.horizontalScrollBar().valueChanged.connect(self._on_scroll_changed)

        games_layout_empty.addWidget(self.scroll_area_empty)
        empty_layout.addWidget(self.games_container_empty, 1)

        self.stack.addWidget(empty_widget)

    def _init_grid_view(self):
        """Экран с плитками игр"""
        grid_widget = QWidget()
        grid_layout = QVBoxLayout(grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)

        # Хедер с центрированными кнопками
        header_widget = QWidget()
        header_widget.setFixedHeight(100)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 10, 20, 10)

        # Центральный контейнер с тремя кнопками
        center_container = QWidget()
        center_layout = QHBoxLayout(center_container)
        center_layout.setSpacing(25)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # Кнопка переключения
        self.switch_view_button = QPushButton("📂 Каталог игр")
        self.switch_view_button.setObjectName("SwitchViewButton")
        self.switch_view_button.clicked.connect(self.switch_to_available_view)
        center_layout.addWidget(self.switch_view_button)

        # Кнопка поиска
        self.search_button_grid = SearchTrigger()
        self.search_button_grid.searchActivated.connect(self.show_search_overlay)
        center_layout.addWidget(self.search_button_grid)

        # Кнопка добавления игры
        self.add_game_button = AddGameButton("Добавить игру", self)
        self.add_game_button.clicked.connect(self.open_file_dialog)
        center_layout.addWidget(self.add_game_button)

        # Растягиваем слева и справа от центрального контейнера
        header_layout.addStretch(1)
        header_layout.addWidget(center_container)
        header_layout.addStretch(1)

        grid_layout.addWidget(header_widget)

        # Контейнер для тегов платформ
        self.tags_container = QWidget()
        self.tags_container.setObjectName("TagsContainer")
        self.tags_container.setFixedHeight(80)
        self.tags_layout = QHBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(20, 20, 20, 20)
        self.tags_layout.setSpacing(10)
        self.tags_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(self.tags_container)

        # Контейнер для плиток игр
        self.games_container = QFrame()
        self.games_container.setObjectName("GamesContainer")
        self.games_container.setStyleSheet("#GamesContainer { background: transparent; border: none; }")

        games_layout = QVBoxLayout(self.games_container)
        games_layout.setContentsMargins(20, 0, 20, 0)
        games_layout.setSpacing(0)

        # Сетка плиток
        self.grid_container = QWidget()
        self.grid_container.setObjectName("GridContainer")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setHorizontalSpacing(80)
        self.grid_layout.setVerticalSpacing(80)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("GamesScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.grid_container)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # Подключаем прокрутку для ленивой загрузки
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self._on_scroll_changed)

        games_layout.addWidget(self.scroll_area)
        grid_layout.addWidget(self.games_container, 1)

        self.stack.addWidget(grid_widget)

    def _on_scroll_changed(self, value):
        """Обработчик прокрутки — debounce проверку видимости"""
        self.visibility_timer.start()

    def _load_visible_covers(self):
        """Загружает обложки для видимых плиток + предзагружает следующие 4"""
        # Определяем, какой scroll_area активен
        if self.stack.currentIndex() == 0:  # Пустое состояние
            scroll = self.scroll_area_empty
            grid_layout = self.grid_layout_empty
        else:  # Состояние с играми
            scroll = self.scroll_area
            grid_layout = self.grid_layout

        if not scroll or not grid_layout:
            return

        # Собираем все плитки
        grid_widgets = []
        for i in range(grid_layout.count()):
            item = grid_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), GameTile):
                grid_widgets.append(item.widget())

        if not grid_widgets:
            return

        viewport = scroll.viewport()
        viewport_rect = viewport.rect()

        visible_indices = []
        for idx, tile in enumerate(grid_widgets):
            if not tile or not hasattr(tile, 'load_cover_if_needed'):
                continue

            # Преобразуем координаты плитки относительно viewport
            tile_rect_global = tile.mapToGlobal(tile.rect().topLeft())
            viewport_global = viewport.mapToGlobal(QPoint(0, 0))
            tile_rect_rel = QRect(
                tile_rect_global.x() - viewport_global.x(),
                tile_rect_global.y() - viewport_global.y(),
                tile.width(), tile.height()
            )

            # Проверяем пересечение с видимой областью
            intersection = tile_rect_rel.intersected(viewport_rect)
            intersection_area = intersection.width() * intersection.height()
            tile_area = tile_rect_rel.width() * tile_rect_rel.height()

            if tile_area > 0 and intersection_area >= 0.3 * tile_area:  # 30% плитки должно быть видно
                tile.load_cover_if_needed()
                visible_indices.append(idx)

        # Предзагрузка следующих 4 плиток (для плавной прокрутки)
        if visible_indices:
            last_visible_idx = max(visible_indices)
            preload_start = last_visible_idx + 1
            preload_end = min(preload_start + 4, len(grid_widgets))
            for i in range(preload_start, preload_end):
                if i < len(grid_widgets):
                    grid_widgets[i].load_cover_if_needed()

    def _update_switch_button_text(self):
        """Метод для обновления текста кнопок переключения"""
        if self.stack.currentIndex() == 0:  # Каталог игр (Экран по умолчанию)
            self.switch_view_button_empty.setText("📚 Мои игры")
            self.switch_view_button.setText("📚 Мои игры")
        else:  # Мои игры (Игры, установленные пользователем)
            self.switch_view_button_empty.setText("📂 Каталог игр")
            self.switch_view_button.setText("📂 Каталог игр")

    def apply_platform_filter(self, platform_name):
        """Применяет фильтр по платформе"""
        logger.info(f"🎯 Выбрана платформа: {platform_name}")

        # Определяем исходный список игр для фильтрации
        if self.stack.currentIndex() == 1:  # Есть установленные игры
            source_games = self.all_games
        else:  # Нет установленных
            source_games = self.available_games

        # Применяем фильтр
        if platform_name == "Все":
            self.filtered_games = source_games
        else:
            self.filtered_games = [
                game for game in source_games
                if game.get('platform', '').lower() == platform_name.lower()
            ]

        # Обновляем отображение
        self.refresh_game_grid()

    def switch_to_installed_view(self):
        """Переключиться на экран установленных игр"""
        if not self.all_games:
            return

        # Устанавливаем флаг переключения вида
        self._just_switched_view = True
        
        self.filtered_games = self.all_games
        self.stack.setCurrentIndex(1)
        self.filter_manager.create_platform_tags(self.all_games)
        self.refresh_game_grid()

        self._update_switch_button_text()

        # Принудительно ставим фокус на первую плитку после переключения
        QTimer.singleShot(100, self._focus_first_tile_after_switch)

    def switch_to_available_view(self):
        """Переключиться на экран доступных игр"""
        if not self.available_games:
            return

        # Устанавливаем флаг переключения вида
        self._just_switched_view = True

        self.filtered_games = self.available_games
        self.stack.setCurrentIndex(0)
        self.filter_manager.create_platform_tags(self.available_games)
        self.refresh_game_grid()

        self._update_switch_button_text()

        # Принудительно ставим фокус на первую плитку после переключения
        QTimer.singleShot(100, self._focus_first_tile_after_switch)

    def _focus_first_tile_after_switch(self):
        """Универсальный метод — ставит фокус на первую плитку после смены вида"""
        if not hasattr(self.window(), 'navigation_controller'):
            return

        nav = self.window().navigation_controller

        header_len = nav.focus_manager.main_header_len
        tags_len = nav.focus_manager.main_tags_len
        target_index = header_len + tags_len
        widgets = nav.focus_manager.get_widgets(NavigationLayer.MAIN)
        if target_index < len(widgets):
            nav.set_focus(NavigationLayer.MAIN, target_index)
        else:
            if tags_len > 0:
                nav.set_focus(NavigationLayer.MAIN, header_len)

    def refresh_game_grid(self):
        """Обновляет сетку игр"""
        if self.stack.currentIndex() == 0:  # Пустое состояние
            self.show_game_grid(self.filtered_games, self.grid_layout_empty, self.grid_container_empty)
        else:  # Состояние с играми
            self.show_game_grid(self.filtered_games, self.grid_layout, self.grid_container)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Больше не пересоздаём плитки при ресайзе!
        # Обложки сами обновляются через кэш + set_cover_pixmap вызывается при paintEvent
        pass

    def show_search_overlay(self):
        """Показать оверлей поиска - единый метод"""
        # Создаем или получаем экземпляр SearchOverlay
        if not hasattr(self, '_search_overlay'):
            self._search_overlay = SearchOverlay(self)
            self._search_overlay.resultSelected.connect(self.show_game_info)
            self._search_overlay.searchClosed.connect(self.on_search_closed)
        
        # Всегда используем единый метод показа
        self._search_overlay.show_overlay()
        
        # Переключаем навигацию
        if hasattr(self.window(), 'navigation_controller'):
            nav = self.window().navigation_controller
            nav.switch_layer(NavigationLayer.SEARCH)

    def on_search_closed(self):
        """Обработчик закрытия поиска"""
        # Очищаем фокус с кнопок поиска
        if hasattr(self, 'search_button_empty'):
            self.search_button_empty.clearFocus()
        if hasattr(self, 'search_button_grid'):
            self.search_button_grid.clearFocus()
        
        # Возвращаем фокус библиотеке
        self.setFocus()
        
        # Обновляем навигацию
        if hasattr(self.window(), 'navigation_controller'):
            nav = self.window().navigation_controller
            nav.switch_layer(NavigationLayer.MAIN)

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
        from app.modules.ui.add_game_dialog import AddGameDialog
        dialog = AddGameDialog(Path(self.base_dir), self, parent=self.window())
        dialog.show()

    def load_games(self):
        """Загрузка и отображение игр"""
        try:
            from app.modules.module_logic.game_data_manager import get_game_data_manager
            manager = get_game_data_manager(Path(self.base_dir))

            if manager:
                installed_games = manager.get_all_games()
                available_games = manager.get_all_available_games()

                self.all_games = installed_games
                self.available_games = available_games

                if installed_games:
                    self.filtered_games = installed_games
                    target_stack = 1
                else:
                    self.filtered_games = available_games
                    target_stack = 0
            else:
                current_games = self._fallback_load_games()
                self.all_games = current_games
                self.available_games = current_games
                self.filtered_games = current_games
                target_stack = 1 if current_games else 0

            self.stack.setCurrentIndex(target_stack)

            # Обновляем текст кнопок при загрузке
            self._update_switch_button_text()

            # СОЗДАЕМ ТЕГИ ПЛАТФОРМ
            games_for_tags = self.all_games if installed_games else self.available_games
            self.filter_manager.create_platform_tags(games_for_tags)

            # Отображаем игры
            self.refresh_game_grid()

            logger.info(f"✅ Загружено игр: установленные={len(self.all_games)}, доступные={len(self.available_games)}")

        except Exception as e:
            logger.error(f"Error loading games: {e}")
            self.stack.setCurrentIndex(0)

    def _fallback_load_games(self):
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

    def show_game_grid(self, games, grid_layout, grid_container):
        """Отображение плиток игр в указанном layout."""
        # 1. Очистка старого layout
        while grid_layout.count():
            item = grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.game_tiles.clear()

        m = TileMetrics

        # 2. Параметры сетки
        cols = self.tiles_per_row
        spacing = self.tile_spacing
        grid_layout.setHorizontalSpacing(spacing)
        grid_layout.setVerticalSpacing(spacing)
        grid_layout.setContentsMargins(spacing, spacing, spacing, spacing)

        # 3. Создаём плитки
        grid_widgets = []                     # только плитки (для навигации)
        for idx, game in enumerate(games):
            tile = GameTile(game, parent=grid_container)
            tile.apply_tile_metrics()

            game_id = game.get('id')
            if game_id:
                self.game_tiles[game_id] = tile

            tile.clicked.connect(lambda _=False, g=game: self.show_game_info(g))
            tile.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

            row = idx // cols
            col = idx % cols
            grid_layout.addWidget(tile, row, col, Qt.AlignmentFlag.AlignCenter)
            grid_widgets.append(tile)

        # 4. Растягиваем колонки, чтобы центрировать ряды
        for c in range(cols):
            grid_layout.setColumnStretch(c, 1)

        # 5. Цетрирование с помощью spacer
        if games:
            last_row = (len(games) - 1) // cols
            spacer = QSpacerItem(
                20, 20,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding
            )
            grid_layout.addItem(spacer, last_row + 1, 0, 1, cols)

        # 6. Регистрация в NavigationController
        # Динамически определяем header_widgets в зависимости от текущего стека
        if self.stack.currentIndex() == 0:  # Каталог (empty state)
            header_widgets = [
                self.switch_view_button_empty,   # Кнопка переключения
                self.search_button_empty,        # Поиск
                self.add_game_button_empty       # Добавление игры
            ]
        else:  # Установленные игры (grid view)
            header_widgets = [
                self.switch_view_button,         # Кнопка переключения
                self.search_button_grid,         # Поиск
                self.add_game_button             # Добавление игры
            ]

        tag_widgets = getattr(self.filter_manager, 'tag_widgets', [])  # Теги платформ

        all_widgets = header_widgets + tag_widgets + grid_widgets  # Полный список: хедер + теги + плитки

        if hasattr(self.window(), 'navigation_controller'):
            nav = self.window().navigation_controller
            nav.register_widgets(NavigationLayer.MAIN, all_widgets)

            # Передаём параметры 2-D-навигации
            nav.focus_manager.main_header_len = len(header_widgets)
            nav.focus_manager.main_tags_len = len(tag_widgets)
            nav.focus_manager.main_grid_cols = cols
            focus_idx = nav.focus_manager.main_header_len + nav.focus_manager.main_tags_len  # Индекс первой плитки
            if focus_idx >= len(all_widgets):
                # Если плиток нет — фокус на первый тег, или на первую кнопку хедера
                if nav.focus_manager.main_tags_len > 0:
                    focus_idx = nav.focus_manager.main_header_len  # Первый тег
                else:
                    focus_idx = 0  # Первая кнопка хедера

            # ВАЖНОЕ ИСПРАВЛЕНИЕ: Убедимся, что фокус не ставится на кнопку переключения
            # если мы только что переключили вид
            if hasattr(self, '_just_switched_view') and self._just_switched_view:
                # После переключения вида фокусируемся на первой плитке, а не на кнопке
                focus_idx = nav.focus_manager.main_header_len + nav.focus_manager.main_tags_len
                if focus_idx >= len(all_widgets) and nav.focus_manager.main_tags_len > 0:
                    focus_idx = nav.focus_manager.main_header_len  # Или на первый тег
                self._just_switched_view = False

            nav.set_focus(NavigationLayer.MAIN, focus_idx)

            # Добавь этот лог для теста — увидишь, что регистрируется
            logger.info(
                f"Зарегистрировано {len(all_widgets)} виджетов: "
                f"header={nav.focus_manager.main_header_len} ({[w.text() for w in header_widgets if hasattr(w, 'text')]}), "
                f"tags={nav.focus_manager.main_tags_len}, grid={len(grid_widgets)}, cols={cols}"
            )

        # 7. Запускаем проверку видимых обложек после небольшой задержки
        QTimer.singleShot(50, self._load_visible_covers)

        grid_container.update()
        grid_container.repaint()

    # Метод для перемещения по фокусу
    def _ensure_visible_focused(self, grid_container):
        """Прокрутить scroll-area так, чтобы текущая плитка была видна."""
        nav = getattr(self.window(), 'navigation_controller', None)
        if not nav:
            return

        idx = nav.focus_manager.get_focus_index(NavigationLayer.MAIN)
        widgets = nav.focus_manager.get_widgets(NavigationLayer.MAIN)
        if idx < 0 or idx >= len(widgets):
            return

        widget = widgets[idx]
        if not isinstance(widget, GameTile):
            return

        # находим QScrollArea, в которой находится grid_container
        scroll = grid_container.parent()
        while scroll and not isinstance(scroll, QScrollArea):
            scroll = scroll.parent()
        if not scroll:
            return

        # координаты плитки относительно grid_container
        pos = widget.mapTo(grid_container, widget.rect().topLeft())
        # гарантируем, что верхняя часть плитки видна
        scroll.ensureVisible(
            pos.x() + widget.width() // 2,
            pos.y() + widget.height() // 2,
            widget.width() // 2,
            widget.height() // 2
        )

    def show_game_info(self, game_data):
        if not game_data:
            return
        main_window = self.window()
        if hasattr(main_window, "show_game_info"):
            main_window.show_game_info(game_data)

    def update_game_cover(self, game_id: str):
        if game_id in self.game_tiles:
            tile = self.game_tiles[game_id]
            # Очищаем кэш для этой игры
            COVER_CACHE.pop(game_id, None)
            # Перезапускаем загрузку
            tile._start_cover_loading()

    def filter_games(self, results):
        pass
