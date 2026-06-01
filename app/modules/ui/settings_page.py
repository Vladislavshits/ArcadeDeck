import os
import json
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QScrollArea,
    QLabel, QStackedWidget, QSizePolicy, QPushButton, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap

# Импорт модулей настроек
from app.modules.settings_plugins.about_settings import AboutPage
from app.modules.settings_plugins.general_settings import GeneralSettingsPage
from app.modules.settings_plugins.appearance_settings import AppearanceSettingsPage
from app.modules.settings_plugins.dev_settings import DevSettingsPage

logger = logging.getLogger('Экран "Настройки"')


class SettingsTile(QFrame):
    """Плитка настроек"""
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


class SettingsPage(QWidget):
    """Страница настроек"""
    tile_activated = pyqtSignal(int)
    focus_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.tiles = []
        self.current_tile_index = 0
        self._settings_index = {}
        self.in_details_mode = False
        self._exit_dialog_open = False
        self.current_detail_widget_index = 0
        self.detail_widgets = []

        # Флаг блокировки навигации между вкладками
        self.navigation_locked = False

        logger.info("🔄 Инициализация экрана настроек")

        self.setObjectName("SettingsPage")

        self.setup_ui()
        self.create_settings_sections()
        logger.info(f"✅ Страница настроек инициализирована с {len(self.tiles)} плитками")

    def setup_ui(self):
        """Настройка интерфейса"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(30)

        # Левая часть - список плиток
        left_widget = QWidget()
        left_widget.setObjectName("SettingsSidebar")
        left_widget.setMaximumWidth(350)
        left_widget.setMinimumWidth(250)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        sidebar_title = QLabel("Настройки")
        sidebar_title.setObjectName("SettingsTitle")
        sidebar_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        left_layout.addWidget(sidebar_title)

        self.tiles_container = QWidget()
        self.tiles_layout = QVBoxLayout(self.tiles_container)
        self.tiles_layout.setContentsMargins(5, 5, 5, 5)
        self.tiles_layout.setSpacing(10)
        self.tiles_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

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

        self.details_title = QLabel("Детальные настройки")
        self.details_title.setObjectName("DetailsTitle")
        self.details_title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.details_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        right_layout.addWidget(self.details_title)

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

        if self.tiles:
            self.set_current_tile(0)

    def add_settings_section(self, index, item):
        """Добавление раздела настроек"""
        name = item["name"]
        icon = item.get("icon", "")
        page_class = item.get("page")

        logger.debug(f"➕ Добавление раздела {index}: {name}")

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
            page = self.create_placeholder_page(name)
            self.settings_detail_stack.addWidget(page)

        tile = SettingsTile(name, icon_path=icon)
        tile.action = lambda idx=index: self.on_tile_activated(idx)
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
        """Обработчик плитки Выход – вызывает диалог выхода."""
        if self._exit_dialog_open:
            return
        self._exit_dialog_open = True
        logger.info("🚪 Запрос закрытия ArcadeDeck из экрана настроек")
        if hasattr(self.parent, 'confirm_exit'):
            self.parent.confirm_exit()
        QTimer.singleShot(1000, lambda: setattr(self, '_exit_dialog_open', False))

    def open_dialog_with_navigation(self, dialog, widgets):
        """Открывает диалог."""
        nav = self.parent.navigation_controller if hasattr(self.parent, 'navigation_controller') else None
        if nav:
            nav.add_managed_window(dialog)
            nav.set_dialog_open(True)
            nav.register_widgets(NavigationLayer.DIALOG, widgets)
            nav.switch_layer(NavigationLayer.DIALOG)
        result = dialog.exec()
        if nav:
            nav.remove_managed_window(dialog)
            nav.set_dialog_open(False)
            # Возвращаемся к слою SETTINGS и восстанавливаем фокус на плитку "Выход"
            nav.switch_layer(NavigationLayer.SETTINGS)
            # Находим индекс плитки "Выход"
            exit_index = len(self.tiles) - 1
            self.set_current_tile(exit_index)
            nav.set_focus(NavigationLayer.SETTINGS, exit_index)
        return result

    def on_tile_activated(self, index):
        """Обработка активации плитки"""
        logger.info(f"🎮 Активация плитки с индексом {index}")

        if index == len(self.tiles) - 1:
            self.handle_exit()
            return

        # Для остальных плиток показываем детальные настройки
        self.settings_detail_stack.setCurrentIndex(index)
        self.tile_activated.emit(index)
        self.enter_details_mode()

    def on_tile_focused(self, index):
        """Обработка фокусировки на плитке"""
        self.current_tile_index = index
        self.focus_changed.emit(index)
        
        # Для плитки "Выход" не показываем детальные настройки
        if index != len(self.tiles) - 1:
            self.settings_detail_stack.setCurrentIndex(index)

    def enter_details_mode(self):
        """Вход в режим детальных настроек"""
        if not self.in_details_mode:
            self.in_details_mode = True
            logger.debug("🔍 Вход в режим детальных настроек")
            self.collect_detail_widgets()

            if self.detail_widgets:
                self.current_detail_widget_index = 0
                self.detail_widgets[0].setFocus()
            else:
                self.in_details_mode = False
                # Если нет виджетов для навигации - не блокируем
                self.navigation_locked = False

    def collect_detail_widgets(self):
        """Собирает все виджеты для навигации на текущей странице"""
        self.detail_widgets = []
        current_page = self.settings_detail_stack.currentWidget()

        if current_page:
            self._collect_focusable_widgets(current_page)

        logger.debug(f"🔍 Найдено {len(self.detail_widgets)} виджетов для навигации")

        # Если нет виджетов для навигации - не блокируем навигацию между вкладками
        if not self.detail_widgets:
            self.navigation_locked = False
            self.in_details_mode = False

    def _collect_focusable_widgets(self, widget):
        """Рекурсивно собирает фокусируемые виджеты"""
        # Cписок поддерживаемых виджетов
        supported_widgets = (QPushButton, QComboBox, QCheckBox)

        if (isinstance(widget, supported_widgets) and
            widget.isVisible() and widget.isEnabled() and
            widget.focusPolicy() != Qt.FocusPolicy.NoFocus):
            self.detail_widgets.append(widget)

        # Cобираем кастомные виджеты
        for child in widget.findChildren(QWidget):
            if (child not in self.detail_widgets and
                child.isVisible() and child.isEnabled() and
                child.focusPolicy() != Qt.FocusPolicy.NoFocus and
                hasattr(child, 'setFocus')):
                self.detail_widgets.append(child)

    def exit_details_mode(self):
        """Выход из режима детальных настроек"""
        if self.in_details_mode:
            self.in_details_mode = False
            self.detail_widgets = []
            self.current_detail_widget_index = 0
            # Разблокируем навигацию между вкладками
            self.navigation_locked = False
            logger.debug("🔙 Выход из режима детальных настроек")
            self.set_current_tile(self.current_tile_index)

    def navigate_up(self):
        """Навигация вверх"""
        # Если навигация заблокирована - работаем только внутри детальных настроек
        if self.navigation_locked or self.in_details_mode:
            if self.detail_widgets:
                self.current_detail_widget_index = (self.current_detail_widget_index - 1) % len(self.detail_widgets)
                self.detail_widgets[self.current_detail_widget_index].setFocus()
                return True
            return False
        else:
            if self.tiles:
                new_index = (self.current_tile_index - 1) % len(self.tiles)
                self.set_current_tile(new_index)
                return True
        return False

    def navigate_down(self):
        """Навигация вниз"""
        # Если навигация заблокирована - работаем только внутри детальных настроек
        if self.navigation_locked or self.in_details_mode:
            if self.detail_widgets:
                self.current_detail_widget_index = (self.current_detail_widget_index + 1) % len(self.detail_widgets)
                self.detail_widgets[self.current_detail_widget_index].setFocus()
                return True
            return False
        else:
            if self.tiles:
                new_index = (self.current_tile_index + 1) % len(self.tiles)
                self.set_current_tile(new_index)
                return True
        return False

    def navigate_right(self):
        """Навигация вправо - вход в детальные настройки"""
        if not self.in_details_mode and self.current_tile_index != len(self.tiles) - 1:
            self.enter_details_mode()
            # Блокируем навигацию между вкладками при входе в детальные настройки
            self.navigation_locked = True
            return True
        return False

    def navigate_left(self):
        """Навигация влево - выход из детальных настроек"""
        if self.in_details_mode:
            self.exit_details_mode()
            # Разблокируем навигацию между вкладками при выходе
            self.navigation_locked = False
            return True
        return False

    def activate_current(self):
        """Активация текущего элемента в детальных настройках"""
        if self.detail_widgets and 0 <= self.current_detail_widget_index < len(self.detail_widgets):
            widget = self.detail_widgets[self.current_detail_widget_index]
            if isinstance(widget, QPushButton):
                QTimer.singleShot(0, widget.click)
                return True
            elif isinstance(widget, QComboBox):
                widget.showPopup()
                return True
            elif isinstance(widget, QCheckBox):
                widget.toggle()
                return True
        return False

    def set_current_tile(self, index):
        """Устанавливает текущую активную плитку"""
        if 0 <= index < len(self.tiles):
            for tile in self.tiles:
                tile.set_focused(False)

            self.tiles[index].set_focused(True)
            self.current_tile_index = index
            self.ensure_tile_visible(index)

            if not self.in_details_mode and index != len(self.tiles) - 1:
                self.settings_detail_stack.setCurrentIndex(index)

            logger.debug(f"🎯 Установлена текущая плитка: {index}")

    def ensure_tile_visible(self, index):
        """Обеспечивает видимость выбранной плитки"""
        if 0 <= index < len(self.tiles):
            tile = self.tiles[index]
            self.scroll_area.ensureWidgetVisible(tile)

    def get_navigation_widgets(self):
        """Возвращает список плиток для навигации"""
        logger.debug(f"Экран \"Настройки\": возвращаю {len(self.tiles)} плиток для навигации")
        return self.tiles

    def get_tiles(self):
        """Возвращает список плиток для навигации"""
        return self.tiles

    def get_current_tile_index(self):
        """Возвращает индекс текущей активной плитки"""
        return self.current_tile_index

    def showEvent(self, event):
        """Обработчик показа страницы"""
        logger.info("Экран настроек показан")
        if self.tiles and not self.in_details_mode:
            self.set_current_tile(self.current_tile_index)
        super().showEvent(event)
