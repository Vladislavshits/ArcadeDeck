#!/usr/bin/env python3
import sys
import webbrowser
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem, QLabel, QPushButton, QDialog,
    QSizePolicy, QSpacerItem, QDesktopWidget, QToolButton, QFrame,
    QCheckBox
)
from PyQt5.QtCore import Qt, QSize, QTimer, QSettings
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette

APP_VERSION = "0.1.4"

# Путь к JSON-файлу с гайдами
GUIDES_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guides.json")

def load_guides():
    """Загружает гайды из JSON-файла или возвращает список по умолчанию"""
    try:
        if os.path.exists(GUIDES_JSON_PATH):
            with open(GUIDES_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки guides.json: {e}")
    
    # Возвращаем список по умолчанию, если файл не найден или произошла ошибка
    return [
        {"title": "EmuDeck: Полное руководство по установке", "url": "https://example.com/emudeck"},
        {"title": "Настройка эмулятора Yuzu", "url": "https://example.com/yuzu"},
        {"title": "RPCS3 на Steam Deck", "url": "https://example.com/rpcs3"},
        {"title": "Оптимизация CEMU", "url": "https://example.com/cemu"},
        {"title": "Настройка эмулятора Dolphin", "url": "https://example.com/dolphin"},
        {"title": "Эмуляция PS2 с PCSX2", "url": "https://example.com/pcsx2"},
        {"title": "Vita3K для игр с PlayStation Vita", "url": "https://example.com/vita3k"},
        {"title": "Игры Switch на Steam Deck", "url": "https://example.com/switch"},
        {"title": "Эмуляция Xbox: руководство по Xemu", "url": "https://example.com/xemu"},
        {"title": "Настройка ядер RetroArch", "url": "https://example.com/retroarch"},
        {"title": "Настройка контроллера GameCube", "url": "https://example.com/gc_controller"},
        {"title": "Конфигурация Steam ROM Manager", "url": "https://example.com/srm"},
        {"title": "Оптимизация производительности", "url": "https://example.com/performance"},
        {"title": "Облачные сохранения для эмуляторов", "url": "https://example.com/cloud_saves"},
        {"title": "Сравнение эмуляторов Windows", "url": "https://example.com/windows_emu"},
    ]

GUIDES = load_guides()

class WelcomeDialog(QDialog):
    def __init__(self, parent=None, dark_theme=True):
        super().__init__(parent, Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Добро пожаловать в PixelDeck")
        self.setFixedSize(720, 450)
        self.dark_theme = dark_theme
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        title = QLabel("Добро пожаловать в PixelDeck!")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(22)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        main_layout.addStretch(1)
        
        text = QLabel(
            "Привет! Чтобы использовать эту программу без проблем, установи в настройках Steam Deck свой браузер по умолчанию.\n\n"
            "Как это сделать?\n"
            "1. Открыть \"Настройки\"\n"
            "2. В левой колонке долистать до пункта \"Приложения по умолчанию\"\n"
            "3. Установить браузер по умолчанию и применить изменения."
        )
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(text)
        
        main_layout.addStretch(1)
        
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.addStretch(1)
        
        self.continue_button = QPushButton("Продолжить")
        self.continue_button.setFixedSize(200, 50)
        self.continue_button.clicked.connect(self.accept)
        button_layout.addWidget(self.continue_button)
        button_layout.addStretch(1)
        
        main_layout.addWidget(button_container)
        self.apply_theme()

    def apply_theme(self):
        if self.dark_theme:
            self.setStyleSheet("""
                QDialog {
                    background-color: #323232;
                    color: white;
                }
                QLabel {
                    color: #e0e0e0;
                    font-size: 16px;
                    margin-bottom: 10px;
                }
                QPushButton {
                    background-color: #64b5f6;
                    color: black;
                    border-radius: 25px;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #5aa5e6;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f7fa;
                    color: #333;
                }
                QLabel {
                    color: #333;
                    font-size: 16px;
                    margin-bottom: 10px;
                }
                QPushButton {
                    background-color: #4285f4;
                    color: white;
                    border-radius: 25px;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #3a75d4;
                }
            """)

    def center_on_screen(self):
        screen = QDesktopWidget().screenGeometry()
        window = self.geometry()
        self.move(
            (screen.width() - window.width()) // 2,
            (screen.height() - window.height()) // 2
        )

class SettingsDialog(QDialog):
    def __init__(self, parent=None, dark_theme=True):
        super().__init__(parent, Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Настройки PixelDeck")
        # Увеличена высота окна
        self.setFixedSize(400, 250)
        self.dark_theme = dark_theme
        self.parent = parent
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        title = QLabel("Настройки")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(28)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        theme_layout = QHBoxLayout()
        theme_layout.setContentsMargins(10, 0, 10, 0)
        
        theme_label = QLabel("Темная тема:")
        theme_label.setFont(QFont("Arial", 14))
        theme_layout.addWidget(theme_label)
        
        theme_layout.addStretch(1)
        
        self.theme_toggle = QCheckBox()
        self.theme_toggle.setChecked(dark_theme)
        self.theme_toggle.setFixedSize(60, 30)
        self.theme_toggle.toggled.connect(self.toggle_theme)
        theme_layout.addWidget(self.theme_toggle)
        
        main_layout.addLayout(theme_layout)
        
        main_layout.addStretch(1)
        
        version_label = QLabel(f"PixelDeck Версия {APP_VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setObjectName("versionLabel")
        main_layout.addWidget(version_label)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        
        close_button = QPushButton("Закрыть")
        close_button.setFixedSize(120, 40)
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        button_layout.addStretch(1)
        main_layout.addLayout(button_layout)
        
        self.apply_theme()

    def toggle_theme(self, checked):
        self.dark_theme = checked
        self.apply_theme()
        
        if self.parent:
            self.parent.dark_theme = checked
            self.parent.apply_theme()
            
            settings = QSettings("PixelDeck.ini", QSettings.IniFormat)
            settings.setValue("dark_theme", checked)

    def apply_theme(self):
        if self.dark_theme:
            self.setStyleSheet("""
                QDialog {
                    background-color: #323232;
                    color: white;
                }
                QLabel {
                    color: #e0e0e0;
                }
                QLabel#versionLabel {
                    color: #aaa;
                    font-size: 12px;
                }
                QPushButton {
                    background-color: #64b5f6;
                    color: black;
                    border-radius: 20px;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #5aa5e6;
                }
                QCheckBox {
                    spacing: 10px;
                }
                QCheckBox::indicator {
                    width: 60px;
                    height: 30px;
                    border-radius: 15px;
                }
                QCheckBox::indicator:unchecked {
                    background-color: #555;
                }
                QCheckBox::indicator:checked {
                    background-color: #64b5f6;
                    image: url();
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f7fa;
                    color: #333;
                }
                QLabel {
                    color: #333;
                }
                QLabel#versionLabel {
                    color: #666;
                    font-size: 12px;
                }
                QPushButton {
                    background-color: #4285f4;
                    color: white;
                    border-radius: 20px;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #3a75d4;
                }
                QCheckBox {
                    spacing: 10px;
                }
                QCheckBox::indicator {
                    width: 60px;
                    height: 30px;
                    border-radius: 15px;
                }
                QCheckBox::indicator:unchecked {
                    background-color: #cccccc;
                }
                QCheckBox::indicator:checked {
                    background-color: #4285f4;
                    image: url();
                }
            """)

class PixelDeckApp(QMainWindow):
    def __init__(self, dark_theme=True):
        super().__init__()
        self.setWindowTitle("PixelDeck")
        self.setGeometry(400, 300, 800, 600)
        self.setMinimumSize(QSize(600, 400))
        self.dark_theme = dark_theme
        
        self.setWindowIcon(QIcon.fromTheme("system-search"))
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 10)
        
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        
        self.settings_button = QToolButton()
        self.settings_button.setFixedSize(40, 40)
        self.settings_button.setIcon(QIcon.fromTheme("preferences-system"))
        self.settings_button.setIconSize(QSize(24, 24))
        self.settings_button.setStyleSheet("QToolButton { border-radius: 20px; border: none; }")
        self.settings_button.clicked.connect(self.open_settings)
        top_bar.addWidget(self.settings_button)
        top_bar.addStretch(1)
        
        self.main_layout.addLayout(top_bar)
        self.main_layout.addStretch(1)
        
        title = QLabel("PixelDeck")
        title.setObjectName("title")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(28)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(title, alignment=Qt.AlignCenter)
        
        self.main_layout.addSpacing(30)
        
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Поиск гайдов...")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self.search_guides)
        self.search_field.setMinimumHeight(60)
        self.main_layout.addWidget(self.search_field, alignment=Qt.AlignCenter)
        
        self.main_layout.addSpacing(20)
        
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.open_guide)
        self.results_list.hide()
        self.main_layout.addWidget(self.results_list, 1, alignment=Qt.AlignCenter)
        
        self.main_layout.addStretch(1)
        
        self.apply_theme()

    def apply_theme(self):
        if self.dark_theme:
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(35, 35, 35))
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            QApplication.setPalette(palette)
            
            self.settings_button.setStyleSheet("""
                QToolButton {
                    background-color: #64b5f6;
                    border-radius: 20px;
                    border: none;
                }
                QToolButton:hover {
                    background-color: #5aa5e6;
                }
            """)
            
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #323232;
                }
                QLabel {
                    color: #e0e0e0;
                }
                QLabel#title {
                    color: #64b5f6;
                    font-weight: bold;
                    font-size: 28px;
                }
                QLineEdit {
                    background-color: #424242;
                    color: white;
                    padding: 10px 30px;
                    font-size: 18px;
                    border: 2px solid #64b5f6;
                    border-radius: 35px;
                    min-height: 60px;
                    min-width: 700px;
                }
                QListWidget {
                    background-color: #424242;
                    color: white;
                    border: 1px solid #555;
                    border-radius: 10px;
                    padding: 5px;
                    font-size: 16px;
                    min-width: 700px;
                }
                QListWidget::item {
                    background-color: #424242;
                    color: white;
                    padding: 15px;
                    border-bottom: 1px solid #555;
                    border-radius: 5px;
                }
                QListWidget::item:selected {
                    background-color: #64b5f6;
                    color: black;
                    border-radius: 5px;
                }
                QListWidget::item:hover {
                    background-color: #555;
                }
            """)
        else:
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(240, 240, 240))
            palette.setColor(QPalette.WindowText, Qt.black)
            palette.setColor(QPalette.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.Text, Qt.black)
            palette.setColor(QPalette.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ButtonText, Qt.black)
            palette.setColor(QPalette.Highlight, QColor(0, 122, 255))
            palette.setColor(QPalette.HighlightedText, Qt.white)
            QApplication.setPalette(palette)
            
            self.settings_button.setStyleSheet("""
                QToolButton {
                    background-color: #4285f4;
                    border-radius: 20px;
                    border: none;
                }
                QToolButton:hover {
                    background-color: #3a75d4;
                }
            """)
            
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #f5f7fa;
                }
                QLabel {
                    color: #333;
                }
                QLabel#title {
                    color: #4285f4;
                    font-weight: bold;
                    font-size: 28px;
                }
                QLineEdit {
                    background-color: white;
                    color: #333;
                    padding: 10px 30px;
                    font-size: 18px;
                    border: 2px solid #4285f4;
                    border-radius: 35px;
                    min-height: 60px;
                    min-width: 700px;
                }
                QListWidget {
                    background-color: white;
                    color: #333;
                    border: 1px solid #ddd;
                    border-radius: 10px;
                    padding: 5px;
                    font-size: 16px;
                    min-width: 700px;
                }
                QListWidget::item {
                    background-color: white;
                    color: #333;
                    padding: 15px;
                    border-bottom: 1px solid #eee;
                    border-radius: 5px;
                }
                QListWidget::item:selected {
                    background-color: #4285f4;
                    color: white;
                    border-radius: 5px;
                }
                QListWidget::item:hover {
                    background-color: #f0f0f0;
                }
            """)

    def open_settings(self):
        settings_dialog = SettingsDialog(self, self.dark_theme)
        settings_dialog.setModal(True)
        settings_dialog.exec_()

    def display_guides(self, guides):
        self.results_list.clear()
        if not guides:
            self.results_list.hide()
            return
            
        for guide in guides:
            item = QListWidgetItem(guide["title"])
            item.setData(Qt.UserRole, guide["url"])
            item.setFont(QFont("Arial", 14))
            self.results_list.addItem(item)
        
        self.results_list.show()
        self.results_list.updateGeometry()

    def search_guides(self, text):
        QTimer.singleShot(100, lambda: self.perform_search(text))

    def perform_search(self, text):
        if not text.strip():
            self.results_list.hide()
            return
            
        query = text.lower()
        results = [guide for guide in GUIDES if query in guide["title"].lower()]
        self.display_guides(results)

    def open_guide(self, item):
        url = item.data(Qt.UserRole)
        webbrowser.open(url)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PixelDeck.ini")
    
    if not os.path.exists(config_path):
        with open(config_path, 'w') as f:
            f.write("[Settings]\n")
    
    settings = QSettings(config_path, QSettings.IniFormat)
    welcome_shown = settings.value("welcome_shown", False, type=bool)
    dark_theme = settings.value("dark_theme", True, type=bool)
    
    if not welcome_shown:
        welcome = WelcomeDialog(dark_theme=dark_theme)
        welcome.center_on_screen()
        if welcome.exec_() == QDialog.Accepted:
            settings.setValue("welcome_shown", True)
    
    window = PixelDeckApp(dark_theme=dark_theme)
    window.showMaximized()
    sys.exit(app.exec_())
