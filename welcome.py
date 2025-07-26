from PyQt6.QtWidgets import QWizard, QWizardPage, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QButtonGroup, QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from settings import app_settings

class WelcomeWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добро пожаловать в PixelDeck!")
        self.setFixedSize(1000, 700)  # Увеличим размер для больших кнопок
        
        # Важно: добавляем кнопку "Готово"
        self.setButtonText(QWizard.WizardButton.FinishButton, "Готово")
        
        # Страница 1: Приветствие
        self.page1 = QWizardPage()
        self.page1.setTitle("Добро пожаловать")
        layout1 = QVBoxLayout()
        title = QLabel("PixelDeck")
        title_font = QFont("Arial", 48, QFont.Weight.Bold)  # Увеличим шрифт
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout1.addWidget(title)
        
        desc = QLabel("Ваш помощник в настройке игр для Steam Deck")
        desc_font = QFont("Arial", 24)  # Увеличим шрифт
        desc.setFont(desc_font)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout1.addWidget(desc)
        
        self.page1.setLayout(layout1)
        self.addPage(self.page1)
        
        # Страница 2: Выбор темы
        self.page2 = QWizardPage()
        self.page2.setTitle("Выбор темы")
        layout2 = QVBoxLayout()
        
        theme_label = QLabel("Выберите предпочитаемую цветовую схему:")
        theme_label_font = QFont("Arial", 20)  # Увеличим шрифт
        theme_label.setFont(theme_label_font)
        theme_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout2.addWidget(theme_label)
        
        # Горизонтальный лейаут для кнопок тем
        buttons_layout = QHBoxLayout()
        
        # Группа кнопок для темы
        self.theme_group = QButtonGroup()
        
        # Кнопка темной темы
        self.dark_theme_btn = QPushButton("Темная тема")
        self.dark_theme_btn.setCheckable(True)
        self.dark_theme_btn.setFixedSize(300, 200)  # Большая кнопка
        self.dark_theme_btn.setFont(QFont("Arial", 18))
        self.dark_theme_btn.setStyleSheet("""
            QPushButton {
                background-color: #252525;
                color: white;
                border: 2px solid #64b5f6;
                border-radius: 10px;
            }
            QPushButton:checked {
                background-color: #64b5f6;
                color: black;
            }
            QPushButton:hover {
                background-color: #353535;
            }
        """)
        
        # Кнопка светлой темы
        self.light_theme_btn = QPushButton("Светлая тема")
        self.light_theme_btn.setCheckable(True)
        self.light_theme_btn.setFixedSize(300, 200)
        self.light_theme_btn.setFont(QFont("Arial", 18))
        self.light_theme_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #333333;
                border: 2px solid #4285f4;
                border-radius: 10px;
            }
            QPushButton:checked {
                background-color: #4285f4;
                color: white;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        
        # Добавляем кнопки в группу
        self.theme_group.addButton(self.dark_theme_btn, 0)
        self.theme_group.addButton(self.light_theme_btn, 1)
        
        # По умолчанию выбрана темная тема
        self.dark_theme_btn.setChecked(True)
        
        buttons_layout.addWidget(self.dark_theme_btn)
        buttons_layout.addWidget(self.light_theme_btn)
        layout2.addLayout(buttons_layout)
        
        self.page2.setLayout(layout2)
        self.addPage(self.page2)
        
        # Сигналы
        self.theme_group.buttonToggled.connect(self.toggle_theme)
        
        # Важно: при завершении мастера принимаем его
        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self.accept)
        
    def toggle_theme(self, button, checked):
        # Обрабатываем только нажатие (когда кнопка становится выбранной)
        if checked:
            if button == self.dark_theme_btn:
                theme = 'dark'
            else:
                theme = 'light'
            app_settings.set_theme(theme)
            
            # Применяем тему сразу к приложению
            app = QApplication.instance()
            if app:
                app.setProperty("class", theme + "-theme")
        
    def center_on_screen(self):
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
