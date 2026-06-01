from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QButtonGroup, QLabel, QFrame)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, pyqtSignal
from app.ui_assets.theme_manager import theme_manager
from settings import app_settings
import logging

logger = logging.getLogger('ArcadeDeck.AppearanceSettings')


class ModernToggleButton(QPushButton):
    """Современная кнопка-переключатель с индикатором выбора."""
    def __init__(self, text, is_selected=False, parent=None):
        super().__init__(text, parent)
        self.is_selected = is_selected
        self.setCheckable(True)
        self.setMinimumSize(140, 50)  # Увеличиваем минимальные размеры
        self.setMaximumSize(160, 60)  # Увеличиваем максимальные размеры
        
        # Настройки для навигации
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("focused", False)

    def set_selected(self, selected):
        self.is_selected = selected
        self.setChecked(selected)

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


class ThemeToggleWidget(QWidget):  # Меняем на QWidget для чистоты
    """Виджет переключения темы БЕЗ подложки"""
    themeChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)  # Увеличиваем отступы
        layout.setSpacing(25)  # Увеличиваем расстояние между кнопками

        # Создаем кнопки напрямую без контейнера с подложкой
        self.dark_btn = ModernToggleButton("Тёмная")
        self.dark_btn.setObjectName("dark_btn")
        self.light_btn = ModernToggleButton("Светлая")
        self.light_btn.setObjectName("light_btn")

        # Устанавливаем начальное состояние
        current_theme = theme_manager.current_theme
        self.dark_btn.set_selected(current_theme == "dark")
        self.light_btn.set_selected(current_theme == "light")

        # Подключаем клики
        self.dark_btn.clicked.connect(lambda: self.select_theme("dark"))
        self.light_btn.clicked.connect(lambda: self.select_theme("light"))

        layout.addWidget(self.dark_btn)
        layout.addWidget(self.light_btn)

        # Центрируем содержимое
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def select_theme(self, theme):
        """Выбирает тему и обновляет внешний вид кнопок."""
        self.dark_btn.set_selected(theme == "dark")
        self.light_btn.set_selected(theme == "light")
        self.themeChanged.emit(theme)


class AppearanceSettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)  # Увеличиваем общие отступы
        layout.setSpacing(30)  # Увеличиваем расстояние между элементами

        title = QLabel("Тема интерфейса")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))  # Увеличиваем шрифт
        layout.addWidget(title)

        # Современный переключатель темы БЕЗ подложки
        self.theme_toggle = ThemeToggleWidget()
        
        # Устанавливаем минимальную высоту для виджета переключателя
        self.theme_toggle.setMinimumHeight(100)
        
        layout.addWidget(self.theme_toggle, alignment=Qt.AlignmentFlag.AlignCenter)

        # Обработка смены темы
        self.theme_toggle.themeChanged.connect(self.on_theme_changed)

        # Добавляем растягивающееся пространство сверху и снизу
        layout.addStretch(2)

    def on_theme_changed(self, theme_name):
        """Обрабатывает смену темы."""
        theme_manager.set_theme(theme_name)
        app_settings.set_theme(theme_name)