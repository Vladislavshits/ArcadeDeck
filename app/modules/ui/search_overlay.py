from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
)
from PyQt6.QtGui import QKeyEvent
import logging

logger = logging.getLogger('ArcadeDeck')


class SearchOverlay(QWidget):
    """Оверлей поиска поверх библиотеки игр"""
    resultSelected = pyqtSignal(dict)  # Сигнал с данными выбранной игры
    searchClosed = pyqtSignal()  # Сигнал закрытия поиска

    def __init__(self, parent=None):
        super().__init__(parent)
        self.games_data = []
        self._init_ui()

    def _init_ui(self):
        """Инициализация UI"""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0, 30, 0, 0)
        layout.setSpacing(10)

        # Поле поиска
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск игр...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.setFixedWidth(500)
        self.search_input.setObjectName("SearchOverlayInput")

        # Список результатов
        self.results_list = QListWidget()
        self.results_list.setFixedWidth(500)
        self.results_list.setMaximumHeight(400)
        self.results_list.itemClicked.connect(self._on_result_clicked)
        self.results_list.setObjectName("SearchOverlayResults")
        # Автоматическая высота элементов
        self.results_list.setUniformItemSizes(False)

        layout.addWidget(self.search_input)
        layout.addWidget(self.results_list)

        # Скрываем по умолчанию
        self.hide()

    def set_game_list(self, games):
        """Установить список игр для поиска через централизованный менеджер"""
        try:
            from app.modules.module_logic.game_data_manager import get_game_data_manager
            manager = get_game_data_manager()
            if manager:
                # Получаем ВСЕ доступные игры через менеджер
                all_available_games = manager.get_all_available_games()
                self.games_data = all_available_games
                logger.info(f"[SearchOverlay] Загружено {len(all_available_games)} игр")
            else:
                # Fallback: используем переданные игры
                self.games_data = [g for g in (games or []) if isinstance(g, dict)]
                logger.info(f"[SearchOverlay] Загружено {len(self.games_data)} игр (fallback)")
        except Exception as e:
            logger.error(f"[SearchOverlay] Ошибка при set_game_list: {e}")
            self.games_data = [g for g in (games or []) if isinstance(g, dict)]

    def show_overlay(self):
        """Показать оверлей поиска"""
        self.search_input.clear()
        self.results_list.clear()
        self.results_list.hide()
        self.raise_()
        self.show()
        self.search_input.setFocus()

    def hide_overlay(self):
        """Скрыть оверлей поиска"""
        self.hide()
        self.search_input.clear()
        self.results_list.clear()
        self.searchClosed.emit()

    def mousePressEvent(self, event):
        """Закрытие оверлея при клике вне области поиска"""
        # Проверяем, был ли клик вне области поискового виджета
        if not self.search_input.geometry().contains(event.pos()) and not self.results_list.geometry().contains(event.pos()):
            self.hide_overlay()
        else:
            super().mousePressEvent(event)

    def _on_search_text_changed(self, text):
        """Обновление результатов поиска"""
        self.results_list.clear()

        text = (text or "").strip().lower()
        if not text:
            # Скрываем подложку при пустом поле ввода
            self.results_list.hide()
            return

        # Показываем подложку только когда есть текст для поиска
        self.results_list.show()

        # Поиск начинается с текста
        results = [
            game for game in self.games_data
            if (game.get("title") or "").lower().startswith(text)
        ]

        # Ограничиваем количество результатов
        displayed_results = results[:6]
        for game in displayed_results:
            title = game.get("title", "Без названия")
            title = f"✅ {title}" if game.get("is_installed") else f"⬇️ {title}"
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, game)
            # Включаем перенос текста для автоматической высоты
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsAutoTristate)
            self.results_list.addItem(item)

        if len(results) > 6:
            hidden_count = len(results) - 6
            item = QListWidgetItem(f"... и ещё {hidden_count} результатов")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.results_list.addItem(item)

        # Автоматически подстраиваем высоту списка
        self._adjust_results_height()

    def _adjust_results_height(self):
        """Автоматическая подстройка высоты списка результатов"""
        total_height = 0
        for i in range(self.results_list.count()):
            item = self.results_list.item(i)
            self.results_list.setItemWidget(item, None)  # Обеспечиваем правильный расчет размера
            size_hint = self.results_list.sizeHintForRow(i)
            total_height += size_hint if size_hint > 0 else 30  # Минимальная высота 30px

        # Ограничиваем максимальную высоту
        total_height = min(total_height, 400)
        self.results_list.setFixedHeight(total_height)

    def _on_result_clicked(self, item):
        """Обработка клика по результату"""
        game_data = item.data(Qt.ItemDataRole.UserRole)
        if game_data:
            self.resultSelected.emit(game_data)
            self.hide_overlay()

    def keyPressEvent(self, event: QKeyEvent):
        """Обработка клавиш"""
        if event.key() == Qt.Key.Key_Escape:
            self.hide_overlay()
            event.accept()
        elif event.key() == Qt.Key.Key_Return and self.results_list.count() > 0:
            # Enter выбирает первый результат
            first_item = self.results_list.item(0)
            if first_item and first_item.flags() & Qt.ItemFlag.ItemIsEnabled:
                self._on_result_clicked(first_item)
            event.accept()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        """Обновление размера при изменении родительского окна"""
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)
