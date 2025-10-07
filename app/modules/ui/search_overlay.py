# search_overlay.py
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QFrame, QApplication, QHBoxLayout
)
from PyQt6.QtGui import QKeyEvent, QFont, QPalette, QColor
import logging

logger = logging.getLogger('ArcadeDeck.SearchOverlay')

class SearchOverlay(QWidget):
    """Современный оверлей поиска с анимациями и автоматическим фокусом"""
    resultSelected = pyqtSignal(dict)  # Сигнал выбора игры - должен открыть страницу информации
    searchClosed = pyqtSignal()
    searchActivated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.games_data = []
        self._init_ui()
        self.setup_animations()

    def _init_ui(self):
        """Инициализация интерфейса с улучшенным дизайном"""
        # Прозрачное окно поверх всех элементов
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                        Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # ЗАНИМАЕМ ВЕСЬ ЭКРАН
        screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geometry)

        # Основной контейнер с затемненным фоном
        self.container = QFrame(self)
        self.container.setObjectName("SearchOverlayContainer")
        self.container.setStyleSheet("""
            #SearchOverlayContainer {
                background: rgba(0, 0, 0, 0.95);
                border-radius: 0px;
                border: none;
            }
        """)

        # Растягиваем контейнер на весь экран
        self.container.setGeometry(self.rect())

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(100, 50, 100, 150)  # Уменьшил верхний отступ с 150 до 50
        layout.setSpacing(30)

        # Поле поиска
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите название игры...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.setFixedHeight(80)
        self.search_input.setStyleSheet("""
            QLineEdit {
                font-size: 24px;
                padding: 20px;
                border: 3px solid #555;
                border-radius: 15px;
                background: #333;
                color: white;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        layout.addWidget(self.search_input)

        # Подсказка
        hint = QLabel("Нажмите B для отмены • Enter для выбора")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #888; font-size: 14px; margin-top: 10px;")
        layout.addWidget(hint)

        self.hide()

    def setup_animations(self):
        """Настройка анимаций появления/исчезновения"""
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def show_overlay(self):
        """Показать оверлей с анимацией и автоматическим фокусом"""
        if self.parent_widget:
            self.setGeometry(self.parent_widget.rect())

        self.search_input.clear()

        # Анимация появления
        self.setWindowOpacity(0.0)
        self.show()
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()

        # Автоматический фокус на поле ввода
        QTimer.singleShot(100, self.activate_input)

    def activate_input(self):
        """Активирует поле ввода и показывает системную клавиатуру"""
        self.search_input.setFocus()
        self.searchActivated.emit()

        # Показываем системную клавиатуру на Steam Deck
        self.show_virtual_keyboard()

    def show_virtual_keyboard(self):
        """Показывает системную виртуальную клавиатуру"""
        try:
            import subprocess
            # Запускаем системную клавиатуру Steam Deck
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

    def hide_overlay(self):
        """Скрыть оверлей с анимацией"""
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.finished.connect(self._on_hide_finished)
        self.fade_animation.start()

        self.hide_virtual_keyboard()

    def _on_hide_finished(self):
        """Завершение анимации скрытия"""
        self.fade_animation.finished.disconnect(self._on_hide_finished)
        self.hide()
        self.searchClosed.emit()

    def set_game_list(self, games):
        """Устанавливает список игр для поиска - КАК В СТАРОМ ФАЙЛЕ"""
        try:
            from app.modules.module_logic.game_data_manager import get_game_data_manager
            manager = get_game_data_manager()
            if manager:
                all_available_games = manager.get_all_available_games()
                self.games_data = all_available_games
                logger.info(f"[SearchOverlay] Загружено {len(all_available_games)} игр из менеджера")
            else:
                # Fallback: используем переданные игры
                self.games_data = [g for g in (games or []) if isinstance(g, dict)]
                logger.info(f"[SearchOverlay] Загружено {len(self.games_data)} игр (fallback)")
        except Exception as e:
            logger.error(f"[SearchOverlay] Ошибка при set_game_list: {e}")
            self.games_data = [g for g in (games or []) if isinstance(g, dict)]

    def _on_search_text_changed(self, text):
        """Обработка поиска - результаты появляются по мере ввода"""
        # Удаляем предыдущие результаты (если они были добавлены в layout)
        for i in reversed(range(self.container.layout().count())):
            widget = self.container.layout().itemAt(i).widget()
            if widget and hasattr(widget, 'objectName') and (widget.objectName() == "SearchResultItem" or widget.objectName() == "PlatformBadge"):
                widget.deleteLater()

        text = (text or "").strip().lower()
        if not text:
            return

        # Поиск начинается с текста
        results = [
            game for game in self.games_data
            if (game.get("title") or "").lower().startswith(text)
        ]

        # Ограничиваем количество результатов
        displayed_results = results[:6]

        # Добавляем результаты прямо в layout под поисковой строкой
        layout = self.container.layout()
        for game in displayed_results:
            title = game.get("title", "Без названия")
            platform = game.get("platform", "Unknown")

            # Добавляем иконку статуса установки как в старом файле
            title = f"✅ {title}" if game.get("is_installed") else f"⬇️ {title}"

            # Создаем горизонтальный контейнер для результата
            result_widget = QWidget()
            result_widget.setObjectName("SearchResultItem")
            result_layout = QHBoxLayout(result_widget)
            result_layout.setContentsMargins(15, 10, 15, 10)
            result_layout.setSpacing(10)

            # Название игры
            title_label = QLabel(title)
            title_label.setObjectName("SearchResultTitle")
            result_layout.addWidget(title_label)

            # Плашка платформы
            platform_badge = QLabel(platform)
            platform_badge.setObjectName("PlatformBadge")
            platform_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            platform_badge.setMinimumWidth(60)
            result_layout.addWidget(platform_badge)

            # Растягиваем название игры
            result_layout.addStretch()

            # Обработка клика
            result_widget.mousePressEvent = lambda event, g=game: self._on_result_clicked_item(g)
            result_widget.setCursor(Qt.CursorShape.PointingHandCursor)

            layout.insertWidget(layout.indexOf(self.search_input) + 1, result_widget)

        if len(results) > 6:
            hidden_count = len(results) - 6
            result_label = QLabel(f"... и ещё {hidden_count} результатов")
            result_label.setObjectName("SearchResultItem")
            result_label.setEnabled(False)
            layout.insertWidget(layout.indexOf(self.search_input) + 1, result_label)

    def _on_result_clicked(self, item):
        """Обработка выбора результата"""
        if item.flags() & Qt.ItemFlag.ItemIsEnabled:
            game_data = item.data(Qt.ItemDataRole.UserRole)
            if game_data:
                logger.info(f"🎮 Выбрана игра из поиска: {game_data.get('title', 'Unknown')}")
                self.resultSelected.emit(game_data)
                self.hide_overlay()

    def _on_result_clicked_item(self, game_data):
        """Обработка выбора результата для новых элементов"""
        logger.info(f"🎮 Выбрана игра из поиска: {game_data.get('title', 'Unknown')}")
        self.resultSelected.emit(game_data)
        self.hide_overlay()

    def keyPressEvent(self, event: QKeyEvent):
        """Обработка нажатий клавиш с полной блокировкой других действий"""
        # В режиме поиска блокируем все действия кроме разрешенных
        if event.key() == Qt.Key.Key_Escape or event.key() == Qt.Key.Key_B:
            logger.info("🔙 Закрытие поиска по кнопке B")
            self.hide_overlay()
            event.accept()
        elif event.key() == Qt.Key.Key_Return and self.results_list.count() > 0:
            # Enter выбирает текущий или первый результат
            current = self.results_list.currentItem() or self.results_list.item(0)
            if current and current.flags() & Qt.ItemFlag.ItemIsEnabled:
                game_data = current.data(Qt.ItemDataRole.UserRole)
                logger.info(f"🎮 Выбор игры Enter: {game_data.get('title', 'Unknown')}")
                self._on_result_clicked(current)
            event.accept()
        elif event.key() == Qt.Key.Key_Down:
            if self.search_input.hasFocus() and self.results_list.count() > 0:
                self.results_list.setCurrentRow(0)
                self.results_list.setFocus()
            elif self.results_list.hasFocus():
                current_row = self.results_list.currentRow()
                if current_row < self.results_list.count() - 1:
                    self.results_list.setCurrentRow(current_row + 1)
            event.accept()
        elif event.key() == Qt.Key.Key_Up:
            if self.results_list.hasFocus():
                current_row = self.results_list.currentRow()
                if current_row > 0:
                    self.results_list.setCurrentRow(current_row - 1)
                else:
                    self.search_input.setFocus()
            event.accept()
        else:
            # Блокируем все остальные клавиши
            event.accept()

    def mousePressEvent(self, event):
        """Закрытие при клике вне области поиска"""
        if not self.container.geometry().contains(event.pos()):
            self.hide_overlay()
        else:
            super().mousePressEvent(event)
