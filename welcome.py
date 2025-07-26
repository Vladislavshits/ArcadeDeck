[file name]: welcome (3).py
[file content begin]
from PyQt6.QtWidgets import QWizard, QWizardPage, QLabel, QVBoxLayout, QCheckBox, QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from settings import app_settings

class WelcomeWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добро пожаловать в PixelDeck!")
        self.setFixedSize(800, 600)
        
        # Страница 1: Приветствие
        self.page1 = QWizardPage()
        self.page1.setTitle("Добро пожаловать")
        layout1 = QVBoxLayout()
        title = QLabel("PixelDeck")
        title_font = QFont("Arial", 32, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout1.addWidget(title)
        
        desc = QLabel("Ваш помощник в настройке игр для Steam Deck")
        desc.setFont(QFont("Arial", 16))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout1.addWidget(desc)
        
        self.page1.setLayout(layout1)
        self.addPage(self.page1)
        
        # Страница 2: Выбор темы
        self.page2 = QWizardPage()
        self.page2.setTitle("Выбор темы")
        layout2 = QVBoxLayout()
        
        theme_label = QLabel("Выберите предпочитаемую цветовую схему:")
        theme_label.setFont(QFont("Arial", 14))
        layout2.addWidget(theme_label)
        
        self.theme_toggle = QCheckBox("Темная тема")
        self.theme_toggle.setChecked(True)
        self.theme_toggle.setFont(QFont("Arial", 12))
        layout2.addWidget(self.theme_toggle)
        
        self.page2.setLayout(layout2)
        self.addPage(self.page2)
        
        # Сигналы
        self.theme_toggle.toggled.connect(self.toggle_theme)
        
    def toggle_theme(self, checked):
        theme = 'dark' if checked else 'light'
        app_settings.set_theme(theme)
        
        # Применяем тему сразу к приложению
        app = QApplication.instance()
        if app:
            app.setProperty("class", "dark-theme" if checked else "light-theme")
        
    def center_on_screen(self):
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
[file content end]
