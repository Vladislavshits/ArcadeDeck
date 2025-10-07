from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QButtonGroup, QLabel, QFrame)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, pyqtSignal
from app.ui_assets.theme_manager import theme_manager
from settings import app_settings

class ModernToggleButton(QPushButton):
    """Современная кнопка-переключатель с индикатором выбора."""
    def __init__(self, text, is_selected=False, parent=None):
        super().__init__(text, parent)
        self.is_selected = is_selected
        self.setCheckable(True)
        self.setFixedHeight(40)
        self.setFixedWidth(120)
        # Стили теперь задаются в theme.qs5
        # self.update_style()

    def set_selected(self, selected):
        self.is_selected = selected
        self.setChecked(selected)
        # Обновление стиля не требуется, так как этим занимается QSS
        # self.update_style()


class ThemeToggleWidget(QFrame):
    """Виджет переключения темы"""
    themeChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Создаем контейнер для кнопок с рамкой
        self.container = QFrame()
        self.container.setObjectName("ThemeToggleFrame")

        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(10, 10, 10, 20)  # Теперь можно использовать одинаковые значения
        container_layout.setSpacing(10)  # Расстояние между кнопками 10px

        # Создаем кнопки
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

        container_layout.addWidget(self.dark_btn)
        container_layout.addWidget(self.light_btn)

        # Центрируем содержимое по вертикали и горизонтали
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.container)
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
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        title = QLabel("Тема интерфейса")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Современный переключатель темы
        self.theme_toggle = ThemeToggleWidget()
        layout.addWidget(self.theme_toggle, alignment=Qt.AlignmentFlag.AlignCenter)

        # Обработка смены темы
        self.theme_toggle.themeChanged.connect(self.on_theme_changed)

        layout.addStretch(1)

    def on_theme_changed(self, theme_name):
        """Обрабатывает смену темы."""
        theme_manager.set_theme(theme_name)
        app_settings.set_theme(theme_name)
