import os
import json
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QScrollArea,
    QLabel, QStackedWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap

# Импорт модулей настроек
from app.modules.settings_plugins.about_settings import AboutPage
from modules.settings_plugins.general_settings import GeneralSettingsPage
from modules.settings_plugins.appearance_settings import AppearanceSettingsPage
from modules.settings_plugins.dev_settings import DevSettingsPage

logger = logging.getLogger('ArcadeDeck.SettingsPage')

class SettingsTile(QFrame):
    """Плитка настроек с улучшенной навигацией"""
    activated = pyqtSignal()
    focused = pyqtSignal()

    def __init__(self, name, icon_path="", action=None):
        super().__init__()
        self.name = name
        self.icon_path = icon_path
        self.action = action
        self.setObjectName("SettingsTile")
        self._focused = False

        # Адаптивные размеры
        self.setMinimumSize(200, 112)
        self.setMaximumSize(300, 150)

        # Устанавливаем свойства для стилей
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        logger.debug(f"🔄 Создана плитка настроек: {name}")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Иконка (если есть)
        if self.icon_path and os.path.exists(self.icon_path):
            icon_label = QLabel()
            icon_pixmap = QPixmap(self.icon_path)
            icon_label.setPixmap(icon_pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_label)

        # Название раздела
        name_label = QLabel(self.name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        name_label.setWordWrap(True)
        name_label.setMaximumHeight(40)
        layout.addWidget(name_label)

    def set_focused(self, focused):
        """Установка состояния фокуса"""
        self._focused = focused
        self.setProperty("focused", focused)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

        if focused:
            self.focused.emit()

    def activate(self):
        """Активация плитки"""
        logger.debug(f"🎮 Активация плитки: {self.name}")
        if self.action:
            self.action()
        self.activated.emit()

    def mousePressEvent(self, event):
        """Обработка клика мышью"""
        self.activate()

    def keyPressEvent(self, event):
        """Обработка нажатия клавиш"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activate()
            event.accept()
        else:
            super().keyPressEvent(event)


class SettingsPage(QWidget):
    """Страница настроек с улучшенной навигацией для геймпада"""
    tile_activated = pyqtSignal(int)
    focus_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.tiles = []
        self.current_tile_index = 0
        self._settings_index = {}
        self.in_details_mode = False  # Режим детальных настроек
        self._exit_dialog_open = False  # Защита от дублирования диалога

        logger.info("🔄 Инициализация SettingsPage с улучшенной навигацией")

        self.setObjectName("SettingsPage")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.setup_ui()
        self.create_settings_sections()
        logger.info(f"✅ SettingsPage инициализирован с {len(self.tiles)} плитками")

    def setup_ui(self):
        """Настройка интерфейса с улучшенной навигацией"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(30)

        # Левая часть - вертикальный список плиток
        left_widget = QWidget()
        left_widget.setObjectName("SettingsSidebar")
        left_widget.setMaximumWidth(350)
        left_widget.setMinimumWidth(250)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        # Заголовок сайдбара
        sidebar_title = QLabel("Настройки")
        sidebar_title.setObjectName("SettingsTitle")
        sidebar_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        left_layout.addWidget(sidebar_title)

        # Контейнер для плиток
        self.tiles_container = QWidget()
        self.tiles_layout = QVBoxLayout(self.tiles_container)
        self.tiles_layout.setContentsMargins(5, 5, 5, 5)
        self.tiles_layout.setSpacing(10)
        self.tiles_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Область прокрутки
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("SettingsTilesScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.tiles_container)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        left_layout.addWidget(self.scroll_area)
        main_layout.addWidget(left_widget, 1)

        # Правая часть - детальные настройки
        right_widget = QWidget()
        right_widget.setObjectName("SettingsDetailsPanel")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # Заголовок детальных настроек
        self.details_title = QLabel("Детальные настройки")
        self.details_title.setObjectName("DetailsTitle")
        self.details_title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.details_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        right_layout.addWidget(self.details_title)

        # Стек для детальных настроек
        self.settings_detail_stack = QStackedWidget()
        self.settings_detail_stack.setObjectName("SettingsDetails")
        right_layout.addWidget(self.settings_detail_stack, 1)

        main_layout.addWidget(right_widget, 3)

    def create_settings_sections(self):
        """Создание разделов настроек"""
        settings_items = [
            {"name": "Общие", "icon": "", "page": GeneralSettingsPage},
            {"name": "Внешний вид", "icon": "", "page": AppearanceSettingsPage},
            {"name": "Инструменты отладки", "icon": "", "page": DevSettingsPage},
            {"name": "О ArcadeDeck", "icon": "", "page": AboutPage},
            {"name": "Выход", "icon": "", "page": None}
        ]

        logger.info(f"📋 Создание {len(settings_items)} разделов настроек")

        for idx, item in enumerate(settings_items):
            self.add_settings_section(idx, item)

        self.tiles_layout.addStretch(1)

        # Устанавливаем фокус на первую плитку
        if self.tiles:
            self.set_current_tile(0)

    def add_settings_section(self, index, item):
        """Добавление раздела настроек"""
        name = item["name"]
        icon = item.get("icon", "")
        page_class = item.get("page")

        logger.debug(f"➕ Добавление раздела {index}: {name}")

        # Создаем страницу настроек (если есть класс)
        page = None
        if page_class:
            try:
                page = page_class(self.parent)
                page.setObjectName(f"SettingsPage_{name.replace(' ', '')}")
                self.settings_detail_stack.addWidget(page)
            except Exception as e:
                logger.error(f"❌ Ошибка создания страницы {name}: {e}")
                page = self.create_placeholder_page(name)
                self.settings_detail_stack.addWidget(page)
        else:
            # Для кнопки "Выход" создаем заглушку
            page = self.create_placeholder_page(name)
            self.settings_detail_stack.addWidget(page)

        # Создаем плитку
        tile = SettingsTile(name, icon_path=icon)

        # 🔥 ИСПРАВЛЕНИЕ: Для кнопки "Выход" используем ТОЛЬКО специальный обработчик
        if name == "Выход":
            # Устанавливаем обработчик и НЕ подключаем сигнал activated
            tile.action = self.handle_exit
        else:
            # Для обычных плиток используем стандартную обработку
            tile.action = lambda idx=index: self.on_tile_activated(idx)
            tile.activated.connect(lambda idx=index: self.on_tile_activated(idx))

        # Фокус всегда подключаем
        tile.focused.connect(lambda idx=index: self.on_tile_focused(idx))

        self.tiles.append(tile)
        self.tiles_layout.addWidget(tile)
        self._settings_index[name] = index

    def create_placeholder_page(self, name):
        """Создает заглушку для нереализованных разделов"""
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(f"Раздел '{name}' в разработке")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Arial", 14))
        layout.addWidget(label)
        return page

    def handle_exit(self):
        """Обработчик кнопки Выход с защитой от дублирования"""
        if self._exit_dialog_open:
            logger.warning("🚫 Диалог выхода уже открыт, игнорируем повторный вызов")
            return

        self._exit_dialog_open = True
        logger.info("🚪 Запрос выхода из приложения из настроек")

        if hasattr(self.parent, 'confirm_exit'):
            # Передаем управление главному окну
            self.parent.confirm_exit()

        # Сбрасываем флаг после завершения (на всякий случай)
        QTimer.singleShot(1000, lambda: setattr(self, '_exit_dialog_open', False))

    def on_tile_activated(self, index):
        """Обработка активации плитки"""
        logger.info(f"🎮 Активация плитки с индексом {index}")

        # 🔥 ИСПРАВЛЕНИЕ: Убрана дублирующая проверка для кнопки "Выход"
        # Теперь кнопка "Выход" обрабатывается ТОЛЬКО через handle_exit()

        # Показываем соответствующие детальные настройки
        self.settings_detail_stack.setCurrentIndex(index)
        self.tile_activated.emit(index)

        # Переходим в режим детальных настроек
        self.enter_details_mode()

    def on_tile_focused(self, index):
        """Обработка фокусировки на плитке"""
        self.current_tile_index = index
        self.focus_changed.emit(index)

    def enter_details_mode(self):
        """Вход в режим детальных настроек"""
        if not self.in_details_mode:
            self.in_details_mode = True
            logger.debug("🔍 Вход в режим детальных настроек")

            # Снимаем фокус с плиток
            for tile in self.tiles:
                tile.set_focused(False)

            # Фокус переходит на первый элемент детальных настроек
            current_page = self.settings_detail_stack.currentWidget()
            if hasattr(current_page, 'focus_first_element'):
                current_page.focus_first_element()
            else:
                # Автоматически ищем первый фокусируемый элемент
                self.focus_first_available_widget(current_page)

    def focus_first_available_widget(self, widget):
        """Рекурсивно ищет первый доступный для фокуса виджет"""
        if widget is None:
            return False

        # Проверяем, можно ли установить фокус на текущий виджет
        if widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
            widget.setFocus()
            return True

        # Рекурсивно проверяем дочерние виджеты
        for child in widget.findChildren(QWidget):
            if child.focusPolicy() != Qt.FocusPolicy.NoFocus:
                child.setFocus()
                return True

        return False

    def exit_details_mode(self):
        """Выход из режима детальных настроек"""
        if self.in_details_mode:
            self.in_details_mode = False
            logger.debug("🔙 Выход из режима детальных настроек")

            # Возвращаем фокус на текущую плитку
            self.set_current_tile(self.current_tile_index)

    def navigate_up(self):
        """Навигация вверх"""
        if self.in_details_mode:
            # В режиме детальных настроек передаем навигацию текущей странице
            current_page = self.settings_detail_stack.currentWidget()
            if hasattr(current_page, 'navigate_up'):
                handled = current_page.navigate_up()
                if handled:
                    return True

            # Если страница не поддерживает навигацию или не обработала, выходим из режима
            self.exit_details_mode()
            return True
        else:
            # Навигация по плиткам вверх
            if self.tiles:
                new_index = (self.current_tile_index - 1) % len(self.tiles)
                self.set_current_tile(new_index)
                return True
        return False

    def navigate_down(self):
        """Навигация вниз"""
        if self.in_details_mode:
            # В режиме детальных настроек передаем навигацию текущей странице
            current_page = self.settings_detail_stack.currentWidget()
            if hasattr(current_page, 'navigate_down'):
                handled = current_page.navigate_down()
                if handled:
                    return True

            # Если страница не поддерживает навигацию или не обработала, выходим из режима
            self.exit_details_mode()
            return True
        else:
            # Навигация по плиткам вниз
            if self.tiles:
                new_index = (self.current_tile_index + 1) % len(self.tiles)
                self.set_current_tile(new_index)
                return True
        return False

    def navigate_right(self):
        """Навигация вправо - вход в детальные настройки"""
        if not self.in_details_mode and self.current_tile_index != len(self.tiles) - 1:
            # Вход в детальные настройки (кроме кнопки "Выход")
            self.enter_details_mode()
            return True
        return False

    def navigate_left(self):
        """Навигация влево - выход из детальных настроек"""
        if self.in_details_mode:
            self.exit_details_mode()
            return True
        return False

    def activate_current(self):
        """Активация текущего элемента"""
        if self.in_details_mode:
            # В режиме детальных настроек передаем активацию текущей странице
            current_page = self.settings_detail_stack.currentWidget()
            if hasattr(current_page, 'activate_current'):
                return current_page.activate_current()
            return False
        else:
            # Активация текущей плитки
            if 0 <= self.current_tile_index < len(self.tiles):
                self.tiles[self.current_tile_index].activate()
                return True
        return False

    def set_current_tile(self, index):
        """Устанавливает текущую активную плитку"""
        if 0 <= index < len(self.tiles):
            # Снимаем фокус со всех плиток
            for tile in self.tiles:
                tile.set_focused(False)

            # Устанавливаем фокус на выбранную плитку
            self.tiles[index].set_focused(True)
            self.current_tile_index = index

            # Прокручиваем к выбранной плитке
            self.ensure_tile_visible(index)

            # Показываем соответствующие детальные настройки (если не в режиме деталей)
            if not self.in_details_mode and index != len(self.tiles) - 1:
                self.settings_detail_stack.setCurrentIndex(index)

            logger.debug(f"🎯 Установлена текущая плитка: {index}")

    def ensure_tile_visible(self, index):
        """Обеспечивает видимость выбранной плитки"""
        if 0 <= index < len(self.tiles):
            tile = self.tiles[index]
            # Прокручиваем область к выбранной плитке
            self.scroll_area.ensureWidgetVisible(tile)

    def get_tiles(self):
        """Возвращает список плиток для навигации"""
        return self.tiles

    def get_current_tile_index(self):
        """Возвращает индекс текущей активной плитки"""
        return self.current_tile_index

    def showEvent(self, event):
        """Обработчик показа страницы"""
        logger.info("⚙️ SettingsPage показан")
        # Устанавливаем фокус на текущую плитку
        if self.tiles and not self.in_details_mode:
            self.set_current_tile(self.current_tile_index)
        super().showEvent(event)
