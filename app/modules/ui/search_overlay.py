# search_overlay.py
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QFrame, QApplication, QHBoxLayout, QScrollArea, QPushButton
)
from PyQt6.QtGui import QKeyEvent, QFont, QPalette, QColor, QPixmap
from pathlib import Path
import logging

# Импорт модуля базовых путей
from core import STYLES_DIR

# Импорт модуля навигации
from navigation import NavigationLayer

logger = logging.getLogger('Модуль поиска')


class FocusButton(QPushButton):
    """
    Класс фокуса для кнопок
    Автоматически ставит свойство фокус кнопкам и виджетам
    """
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(False)
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


class SearchResultWidget(FocusButton):
    """Виджет результата поиска — без чёрных квадратов и с увеличенной высотой"""
    def __init__(self, game_data, parent=None):
        super().__init__("", parent)
        self.game_data = game_data
        self.setObjectName("SearchResultItem")
        self._init_ui()

    def _init_ui(self):
            layout = QHBoxLayout(self)
            layout.setContentsMargins(22, 18, 22, 18)   # больше воздуха сверху/снизу
            layout.setSpacing(16)

            title = self.game_data.get("title", "Без названия")
            platform = self.game_data.get("platform", "Unknown")

            # Иконка
            status_label = QLabel()
            status_label.setFixedSize(34, 34)
            status_label.setStyleSheet("background: transparent;")
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_label.setScaledContents(True)

            icon_path = Path(STYLES_DIR) / "icon"
            if self.game_data.get("is_installed"):
                icon_file = icon_path / "installed.svg"
            else:
                icon_file = icon_path / "download.svg"

            if icon_file.exists():
                status_label.setPixmap(QPixmap(str(icon_file)))
            else:
                status_label.setText("✓" if self.game_data.get("is_installed") else "↓")

            # Контент
            content_layout = QVBoxLayout()
            content_layout.setSpacing(5)

            self.title_label = QLabel(title)
            self.title_label.setObjectName("SearchResultTitle")
            self.title_label.setStyleSheet("background: transparent;")
            self.title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))

            platform_badge = QLabel(platform)
            platform_badge.setObjectName("PlatformBadge")
            platform_badge.setStyleSheet("background: transparent;")

            content_layout.addWidget(self.title_label)
            content_layout.addWidget(platform_badge)

            layout.addWidget(status_label)
            layout.addLayout(content_layout, 1)

    def activate(self):
        """Активация по кнопке A"""
        logger.info(f"🎮 Активация результата поиска: {self.game_data.get('title')}")
        
        # Находим родительский SearchOverlay
        parent = self.parent()
        while parent and not isinstance(parent, SearchOverlay):
            parent = parent.parent()

        if parent:
            logger.info(f"✅ Найден SearchOverlay, передача данных игры")
            parent._on_result_clicked(self.game_data)
        else:
            logger.error("❌ Не удалось найти SearchOverlay для активации результата")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            parent = self.parent()
            while parent and not isinstance(parent, SearchOverlay):
                parent = parent.parent()

            if parent and hasattr(parent, '_on_result_clicked'):
                parent._on_result_clicked(self.game_data)
        super().mousePressEvent(event)


class SearchOverlay(QWidget):
    """Оверлей поиска"""
    resultSelected = pyqtSignal(dict)
    searchClosed = pyqtSignal()
    searchActivated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.games_data = []
        self.result_widgets = []
        self._init_ui()
        self.search_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        QTimer.singleShot(0, self._load_games_list)

    def _init_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(100, 50, 100, 120)   # уменьшил нижний отступ, т.к. подсказки убрали
        layout.setSpacing(30)

        self.setObjectName("SearchOverlay")

        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("Введите название игры...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.setFixedHeight(80)
        self.search_input.textEdited.connect(self._on_text_edited)
        
        layout.addWidget(self.search_input)

        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFixedHeight(480)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(10)
        self.results_scroll.setWidget(self.results_container)
        layout.addWidget(self.results_scroll)

        self.hide()

    def _on_text_edited(self, text):
        """Обработчик для предотвращения автоматического выделения текста"""
        QTimer.singleShot(0, lambda: self.search_input.deselect())

    def toggle_overlay(self):
        """Переключение состояния оверлея"""
        if self.isVisible():
            self.hide_overlay()
        else:
            self.show_overlay()

    def show_overlay(self):
        """Показать оверлей поиска"""
        if self.parent_widget:
            self.setGeometry(self.parent_widget.rect())
            self.raise_()
            self.activateWindow()

        # Загружаем актуальный список игр
        self._load_games_list()
        
        self.search_input.clear()
        self._clear_results()
        
        # Показываем список игр сразу при открытии
        self._on_search_text_changed("")  # Показываем первые 20 игр
        
        self.show()
        self.raise_()
        self.activateWindow()

        # Активируем ввод и навигацию
        QTimer.singleShot(0, self.activate_input)
        self.searchActivated.emit()

    def hide_overlay(self):
        """Скрыть оверлей поиска - публичный метод"""
        self.hide()
        self.searchClosed.emit()
        self.hide_virtual_keyboard()

        # Очистка навигации
        if self.parent_widget and hasattr(self.parent_widget.window(), 'navigation_controller'):
            nav = self.parent_widget.window().navigation_controller
            nav.search_active = False
            nav.clear_focus(NavigationLayer.SEARCH)
            nav.focus_manager.layer_widgets[NavigationLayer.SEARCH] = []
            nav.update_hints()
            logger.info("🔍 Поиск закрыт, навигация очищена")

    def _load_games_list(self):
        """Автономная загрузка списка игр для поиска"""
        try:
            from app.modules.module_logic.game_data_manager import get_game_data_manager
            # Получаем base_dir из родительского окна или используем по умолчанию
            base_dir = Path(__file__).parent.parent.parent
            if self.parent_widget and hasattr(self.parent_widget, 'project_root'):
                base_dir = self.parent_widget.project_root
                
            manager = get_game_data_manager(base_dir)
            if manager:
                all_available_games = manager.get_all_available_games()
                self.set_game_list(all_available_games)
                logger.info(f"🔍 Автономно загружено {len(all_available_games)} игр для поиска")
            else:
                logger.error("❌ Менеджер данных игр не доступен")
        except Exception as e:
            logger.error(f"❌ Ошибка автономной загрузки списка игр: {e}")

    def prepare_and_show(self):
        """Подготовка и показ поиска - автономный метод"""
        if not self.games_data:
            self._load_games_list()
            
        if self.parent_widget:
            self.setGeometry(self.parent_widget.rect())
            self.raise_()
            self.activateWindow()

        # Очищаем предыдущий поиск
        self.search_input.clear()
        self._clear_results()
        
        # ВАЖНО: Показываем список игр сразу при открытии
        self._on_search_text_changed("")  # Показываем первые 20 игр
        
        self.show()
        self.raise_()
        self.activateWindow()

        # Активируем ввод и навигацию
        QTimer.singleShot(100, self.activate_input)
        self.searchActivated.emit()

    def _clear_results(self):
        """Очистка результатов"""
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.result_widgets.clear()

    def activate_input(self):
        """Активирует поле ввода и показывает системную клавиатуру"""
        self.search_input.setFocus()
        
        # Интеграция в навигацию
        self.register_navigation_widgets()
        
        # Показываем системную клавиатуру на Steam Deck
        self.show_virtual_keyboard()

    def activate_focused_result(self):
        """Активация сфокусированного результата поиска по кнопке A"""
        if not self.parent_widget:
            return False
            
        nav = self.parent_widget.window().navigation_controller
        if not nav:
            return False

        current_idx = nav.focus_manager.get_focus_index(NavigationLayer.SEARCH)
        widgets = nav.focus_manager.get_widgets(NavigationLayer.SEARCH)

        # Пропускаем поле ввода (индекс 0)
        if current_idx > 0 and current_idx < len(widgets):
            result_widget = widgets[current_idx]
            if hasattr(result_widget, 'activate'):
                result_widget.activate()
                return True

        return False

    def register_navigation_widgets(self):
        """Регистрация виджетов поиска в NavigationController"""
        if not self.parent_widget:
            return
            
        nav = self.parent_widget.window().navigation_controller
        if nav:
            # Собираем все виджеты для навигации (поле ввода + результаты)
            widgets = [self.search_input] + self.result_widgets

            nav.register_widgets(NavigationLayer.SEARCH, widgets)
            nav.set_focus(NavigationLayer.SEARCH, 0)
            nav.search_active = True
            nav.update_hints()
            logger.info(f"🔍 Зарегистрировано {len(widgets)} виджетов для поиска")
            
            # Автоматическая прокрутка к первому элементу если есть результаты
            if self.result_widgets:
                QTimer.singleShot(50, lambda: self._scroll_to_first_result())

    def _scroll_to_first_result(self):
        """Прокрутить к первому результату при открытии"""
        if not self.result_widgets:
            return
            
        first_result = self.result_widgets[0]
        self._ensure_widget_visible(first_result)

    def _ensure_widget_visible(self, widget):
        """Гарантирует видимость виджета в области прокрутки"""
        try:
            container = self.results_container
            widget_rect = widget.rect()
            widget_pos = widget.mapTo(container, widget_rect.topLeft())
            
            self.results_scroll.ensureVisible(
                widget_pos.x() + widget_rect.width() // 2,
                widget_pos.y() + widget_rect.height() // 2,
                widget_rect.width() // 2,
                widget_rect.height() // 2
            )
        except Exception as e:
            logger.debug(f"Ошибка прокрутки: {e}")

    def show_virtual_keyboard(self):
        """Показывает системную виртуальную клавиатуру"""
        try:
            import subprocess
            subprocess.Popen(["qdbus", "org.kde.plasmashell", "/VirtualKeyboard", "org.kde.plasmashell.VirtualKeyboard.show"])
        except Exception as e:
            logger.warning(f"Не удалось показать системную клавиатуру: {e}")

    def hide_virtual_keyboard(self):
        """Скрывает системную виртуальную клавиатуру"""
        try:
            import subprocess
            subprocess.Popen(["qdbus", "org.kde.plasmashell", "/VirtualKeyboard", "org.kde.plasmashell.VirtualKeyboard.hide"])
        except Exception as e:
            logger.warning(f"Не удалось скрыть системную клавиатуру: {e}")

    def set_game_list(self, games=None):
        """Устанавливает список игр для поиска и сортирует по алфавиту"""
        try:
            from app.modules.module_logic.game_data_manager import get_game_data_manager
            manager = get_game_data_manager()
            if manager:
                all_available_games = manager.get_all_available_games()
                self.games_data = sorted(all_available_games, key=lambda g: g.get("title", "").lower())
                logger.info(f"[SearchOverlay] Загружено {len(self.games_data)} игр из менеджера")
            else:
                self.games_data = sorted([g for g in (games or []) if isinstance(g, dict)], key=lambda g: g.get("title", "").lower())
                logger.info(f"[SearchOverlay] Загружено {len(self.games_data)} игр (fallback)")
        except Exception as e:
            logger.error(f"[SearchOverlay] Ошибка при set_game_list: {e}")
            self.games_data = sorted([g for g in (games or []) if isinstance(g, dict)], key=lambda g: g.get("title", "").lower())

        if self.isVisible():
            self._on_search_text_changed(self.search_input.text())

    def _on_search_text_changed(self, text):
        """Обработка поиска - результаты появляются по мере ввода"""
        # Очищаем предыдущие результаты
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.result_widgets.clear()

        text = (text or "").strip().lower()
        
        if not text:
            # Показываем первые 20 игр без какой-либо подсказки
            results = self.games_data[:20]
        else:
            results = [game for game in self.games_data 
                      if text in game.get("title", "").lower()]

        # Создаем виджеты результатов
        for game in results:
            result_widget = SearchResultWidget(game, self)
            self.results_layout.addWidget(result_widget)
            self.result_widgets.append(result_widget)

        # Добавляем растяжку в конец
        self.results_layout.addStretch()

        # Обновляем навигацию
        if self.isVisible():
            self.register_navigation_widgets()

    def _on_result_clicked(self, game_data):
        """Обработка выбора результата - исправленная версия"""
        logger.info(f"🎮 Выбрана игра из поиска: {game_data.get('title', 'Unknown')}")
        
        if not game_data:
            logger.error("❌ Пустые данные игры в _on_result_clicked")
            return
            
        logger.info("✅ Отправка сигнала resultSelected")
        self.resultSelected.emit(game_data)

    def keyPressEvent(self, event):
        """Обработка клавиш в оверлее поиска"""
        if event.key() in (Qt.Key.Key_B, Qt.Key.Key_Y):
            # Закрытие по B или Y
            self.hide_overlay()
            event.accept()
            return
        
        # Обработка Enter для активации выбранного результата
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.activate_focused_result():
                event.accept()
                return
        
        super().keyPressEvent(event)
