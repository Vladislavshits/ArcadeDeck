# appearance_settings.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QRadioButton, QButtonGroup, QLabel
from PyQt6.QtCore import Qt
from app.ui_assets.theme_manager import theme_manager
from settings import app_settings

class AppearanceSettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20,20,20,20)
        layout.setSpacing(15)

        title = QLabel("Режим темы")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Радиокнопки
        self.group = QButtonGroup(self)
        rb_dark = QRadioButton("Тёмная")
        rb_light = QRadioButton("Светлая")
        self.group.addButton(rb_dark, id=0)
        self.group.addButton(rb_light, id=1)
        layout.addWidget(rb_dark)
        layout.addWidget(rb_light)

        # Устанавливаем текущее состояние
        current = theme_manager.current_theme
        rb_dark.setChecked(current == "dark")
        rb_light.setChecked(current == "light")

        # При смене – меняем тему и сохраняем
        def on_changed(button):
            name = "dark" if button is rb_dark else "light"
            theme_manager.set_theme(name)
            app_settings.set_theme(name)
        self.group.buttonClicked.connect(on_changed)

        layout.addStretch(1)
