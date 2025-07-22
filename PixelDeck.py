#!/usr/bin/env python3
# Импорт необходимых модулей
import sys
import os

# Проверка виртуального окружения
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    print("ВНИМАНИЕ: Виртуальное окружение не активировано!")

# Добавить родительскую директорию в путь поиска модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import webbrowser
import json
import requests
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem, QLabel, QPushButton, QDialog,
    QSizePolicy, QSpacerItem, QDesktopWidget, QToolButton, QFrame,
    QCheckBox, QMessageBox, QStackedWidget, QButtonGroup, QGridLayout
)
from PyQt5.QtCore import Qt, QSize, QTimer, QSettings, QFile, QTextStream
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette
from common import APP_VERSION, CONTENT_DIR, STYLES_DIR, DARK_STYLE, LIGHT_STYLE, load_stylesheet, \
    GUIDES_JSON_PATH, GAME_LIST_GUIDE_JSON_PATH  # Импорт путей к файлам

def load_content():
    """
    Загружает контент из JSON-файлов (guides.json и game-list-guides.json).
    Возвращает два списка: гайды и игры.
    """
    guides = []
    games = []

    # АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ОТСУТСТВУЮЩИХ ФАЙЛОВ (НОВЫЙ КОД)
    for path in [GUIDES_JSON_PATH, GAME_LIST_GUIDE_JSON_PATH]:
        if not os.path.exists(path):
            with open(path, 'w', encoding='utf-8') as f:
                json.dump([], f)
                print(f"Создан пустой файл: {os.path.basename(path)}")

    # Проверяем существование папки Content
    if not os.path.exists(CONTENT_DIR):
        print(f"Папка контента не найдена: {CONTENT_DIR}")
        return guides, games

    # Загрузка гайдов
    try:
        if os.path.exists(GUIDES_JSON_PATH):
            print(f"Загрузка файла гайдов: {GUIDES_JSON_PATH}")
            with open(GUIDES_JSON_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
                if content:
                    guides_data = json.loads(content)
                    if isinstance(guides_data, list):
                        guides = guides_data
                        print(f"Загружено гайдов: {len(guides)}")
                    else:
                        print(f"Ошибка: файл гайдов не содержит список")
                else:
                    print(f"Файл гайдов пуст: {GUIDES_JSON_PATH}")
        else:
            print(f"Файл гайдов не найден: {GUIDES_JSON_PATH}")
    except json.JSONDecodeError as e:
        print(f"Ошибка декодирования JSON в файле гайдов: {e}")
    except Exception as e:
        print(f"Ошибка загрузки гайдов: {e}")

    # Загрузка списка игр
    try:
        if os.path.exists(GAME_LIST_GUIDE_JSON_PATH):
            print(f"Загрузка файла игр: {GAME_LIST_GUIDE_JSON_PATH}")
            with open(GAME_LIST_GUIDE_JSON_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
                if content:
                    games_data = json.loads(content)
                    if isinstance(games_data, list):
                        games = games_data
                        print(f"Загружено игр: {len(games)}")
                    else:
                        print(f"Ошибка: файл игр не содержит список")
                else:
                    print(f"Файл игр пуст: {GAME_LIST_GUIDE_JSON_PATH}")
        else:
            print(f"Файл игр не найден: {GAME_LIST_GUIDE_JSON_PATH}")
    except json.JSONDecodeError as e:
        print(f"Ошибка декодирования JSON в файле игр: {e}")
    except Exception as e:
        print(f"Ошибка загрузки игр: {e}")

    return guides, games

# Загружаем контент
GUIDES, GAMES = load_content()

def show_style_error(missing_styles):
    """
    Показывает диалоговое окно с ошибкой отсутствия файлов стилей.

    :param missing_styles: Список отсутствующих файлов стилей
    """
    # Создаем диалоговое окно с ошибкой
    error_dialog = QMessageBox()
    error_dialog.setWindowTitle("Ошибка запуска! Код #1!")
    error_dialog.setIcon(QMessageBox.Critical)

    # Формируем текст сообщения
    message = "Отсутствуют файлы стилей. Переустановите программу с сайта проекта.\n\n"
    message += "Отсутствующие файлы:\n"
    for style in missing_styles:
        message += f"- {os.path.basename(style)}\n"

    error_dialog.setText(message)

    # Добавляем кнопки
    download_button = error_dialog.addButton("Скачать установщик", QMessageBox.ActionRole)
    close_button = error_dialog.addButton("Закрыть", QMessageBox.RejectRole)

    # Показываем диалог
    error_dialog.exec_()

    # Обрабатываем нажатие кнопок
    if error_dialog.clickedButton() == download_button:
        webbrowser.open("https://github.com/Vladislavshits/PixelDeck/releases/download/v0.1.5/install.pixeldeck.sh")

    return False

class WelcomeScreen(QWidget):
    """Экран приветствия, показываемый при запуске приложения."""

    def __init__(self, parent=None):
        """
        Инициализация экрана приветствия.

        :param parent: Родительское окно
        """
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Заголовок во весь экран
        title = QLabel("PixelDeck")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 80px;
            font-weight: bold;
            color: #2a9fd6;
            padding: 30px;
        """)
        layout.addWidget(title, 1)  # Растягиваем на все доступное пространство

class WelcomeDialog(QDialog):
    """Диалоговое окно приветствия при первом запуске."""
    
    def __init__(self, dark_theme=True, parent=None):
        super().__init__(parent)
        self.dark_theme = dark_theme
        self.setup_ui()
        self.center_on_screen()
        self.apply_theme()
        
    def center_on_screen(self):
        """Центрирует окно на экране."""
        screen_geometry = QApplication.desktop().screenGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
        
    def setup_ui(self):
        self.setWindowTitle("Добро пожаловать в PixelDeck!")
        self.setMinimumSize(600, 500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Заголовок
        title = QLabel("Добро пожаловать в PixelDeck!")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(24)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Описание
        description = QLabel(
            "Эта программа разрабатывается для автоматизации процесса эмуляции, "
            "автоустановки игр, а так же многое другое ждет вас в будущем!\n\n"
            "Приятного пользования!"
        )
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        description_font = QFont()
        description_font.setPointSize(14)
        description.setFont(description_font)
        layout.addWidget(description)
        
        layout.addStretch(1)
        
        # Кнопка GitHub
        github_button = QPushButton("Проект на GitHub")
        github_button.setFixedHeight(50)
        github_button.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        github_button.clicked.connect(lambda: webbrowser.open("https://github.com/Vladislavshits/PixelDeck"))
        layout.addWidget(github_button)
        
        # Кнопка продолжения
        continue_button = QPushButton("Продолжить")
        continue_button.setFixedHeight(50)
        continue_button.setStyleSheet("""
            QPushButton {
                background-color: #2a9fd6;
                color: white;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3ab0e6;
            }
        """)
        continue_button.clicked.connect(self.accept)
        layout.addWidget(continue_button)
        
    def apply_theme(self):
        """Применяет выбранную тему (темную или светлую) к диалогу."""
        if self.dark_theme:
            style = load_stylesheet(DARK_STYLE)
        else:
            style = load_stylesheet(LIGHT_STYLE)

        if style:
            self.setStyleSheet(style)

class SettingsScreen(QWidget):
    """Экран настроек приложения."""

    def __init__(self, parent=None, dark_theme=True):
        """
        Инициализация экрана настроек.

        :param parent: Родительское окно
        :param dark_theme: Использовать темную тему (по умолчанию True)
        """
        super().__init__(parent)
        self.dark_theme = dark_theme
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # Заголовок
        title = QLabel("Настройки")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(32)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Лэйаут для переключателя темы
        theme_layout = QHBoxLayout()
        theme_layout.setContentsMargins(10, 0, 10, 0)

        # Метка для переключателя
        theme_label = QLabel("Темная тема:")
        theme_label.setFont(QFont("Arial", 18))  # Увеличенный размер шрифта
        theme_layout.addWidget(theme_label)

        theme_layout.addStretch(1)  # Гибкий промежуток

        # Переключатель темы (тумблер)
        self.theme_toggle = QCheckBox()
        self.theme_toggle.setChecked(self.dark_theme)
        self.theme_toggle.setFixedSize(80, 40)  # Больший размер
        # Стиль для тумблера
        self.theme_toggle.setStyleSheet("""
            QCheckBox::indicator {
                width: 80px;
                height: 40px;
                border-radius: 20px;
                background-color: #777;
            }
            QCheckBox::indicator:checked {
                background-color: #2a9fd6;
            }
            QCheckBox::indicator:unchecked {
                background-color: #ccc;
            }
            QCheckBox::indicator:checked:disabled {
                background-color: #555;
            }
            QCheckBox::indicator:unchecked:disabled {
                background-color: #aaa;
            }
        """)
        # Подключаем обработчик изменения состояния
        self.theme_toggle.toggled.connect(self.toggle_theme)
        theme_layout.addWidget(self.theme_toggle)

        main_layout.addLayout(theme_layout)

        main_layout.addStretch(1)  # Гибкий промежуток

        # Метка с версией приложения
        version_label = QLabel(f"Версия {APP_VERSION}")
        version_label.setFont(QFont("Arial", 14))
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setObjectName("versionLabel")
        main_layout.addWidget(version_label)

    def toggle_theme(self, checked):
        """
        Обработчик изменения состояния переключателя темы.

        :param checked: Новое состояние переключателя (включена темная тема)
        """
        self.dark_theme = checked
        # Обновляем тему текущего экрана
        self.apply_theme()

        if self.parent:
            # Обновляем тему родительского окна
            self.parent.dark_theme = checked
            self.parent.apply_theme()

            # Сохраняем настройку темы в конфигурационный файл
            config_dir = os.path.join(os.path.expanduser("~"), "PixelDeck")
            config_path = os.path.join(config_dir, "pixeldeck.ini")
            settings = QSettings(config_path, QSettings.IniFormat)
            settings.setValue("dark_theme", checked)

    def apply_theme(self):
        """Применяет выбранную тему (темную или светлую) к экрану настроек."""
        if self.dark_theme:
            style = load_stylesheet(DARK_STYLE)
        else:
            style = load_stylesheet(LIGHT_STYLE)

        if style:
            self.setStyleSheet(style)

class DummyScreen(QWidget):
    """Заглушка для дополнительного экрана."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        label = QLabel("Этот экран пока не реализован")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

class SearchScreen(QWidget):
    """Экран поиска гайдов и игр."""

    def __init__(self, parent=None, dark_theme=True):
        """
        Инициализация экрана поиска.

        :param parent: Родительское окно
        :param dark_theme: Использовать темную тему (по умолчанию True)
        """
        super().__init__(parent)
        self.dark_theme = dark_theme
        self.setup_ui()

    def setup_ui(self):
        # Основной вертикальный лэйаут
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 10)
        self.main_layout.setSpacing(10)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.addStretch(1)  # Гибкий промежуток
        self.main_layout.addLayout(top_bar)

        # Поле поиска
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Поиск гайдов и игр...")
        self.search_field.setClearButtonEnabled(True)  # Кнопка очистки
        # Подключаем обработчик изменения текста
        self.search_field.textChanged.connect(self.search_content)
        self.search_field.setMinimumHeight(60)
        self.search_field.setObjectName("searchField")
        self.main_layout.addWidget(self.search_field)

        # Список результатов поиска
        self.results_list = QListWidget()
        # Подключаем обработчик двойного клика по элементу
        self.results_list.itemDoubleClicked.connect(self.open_item)
        self.results_list.hide()  # Скрываем список до начала поиска
        self.results_list.setObjectName("resultsList")
        self.main_layout.addWidget(self.results_list, 1)  # Растягиваем на оставшееся пространство

        # Применяем выбранную тему
        self.apply_theme()

    def apply_theme(self):
        """Применяет выбранную тему (темную или светлую) к экрану поиска."""
        if self.dark_theme:
            style = load_stylesheet(DARK_STYLE)
        else:
            style = load_stylesheet(LIGHT_STYLE)

        if style:
            self.setStyleSheet(style)

    def display_results(self, results):
        """
        Отображает результаты поиска в виджете списка.

        :param results: Список результатов (каждый элемент - словарь с ключами 'type', 'title', 'url')
        """
        self.results_list.clear()  # Очищаем предыдущие результаты
        # Если результатов нет, скрываем виджет
        if not results:
            self.results_list.hide()
            return

        # Добавляем каждый результат в список
        for item in results:
            list_item = QListWidgetItem()

            # Создаем виджет для отображения результата
            item_widget = QWidget()
            item_layout = QVBoxLayout(item_widget)
            item_layout.setContentsMargins(15, 15, 15, 15)  # Увеличили отступы

            # Заголовок
            title_label = QLabel(item['title'])
            title_font = QFont("Arial", 14)
            title_font.setBold(True)
            title_label.setFont(title_font)

            # Тип (гайд или игра)
            type_label = QLabel(f"Тип: {item['type']}")
            type_label.setFont(QFont("Arial", 12))  # Увеличили размер шрифта
            if item['type'] == "Гайд":
                type_label.setStyleSheet("color: #4CAF50;")
            else:
                type_label.setStyleSheet("color: #2196F3;")

            item_layout.addWidget(title_label)
            item_layout.addWidget(type_label)

            # Устанавливаем виджет в элемент списка
            list_item.setSizeHint(item_widget.sizeHint())
            self.results_list.addItem(list_item)
            self.results_list.setItemWidget(list_item, item_widget)

            # Сохраняем URL в пользовательских данных элемента
            list_item.setData(Qt.UserRole, item['url'])

        # Показываем виджет с результатами
        self.results_list.show()
        self.results_list.updateGeometry()  # Обновляем геометрию виджета

    def search_content(self, text):
        """
        Обработчик изменения текста в поле поиска.
        Использует таймер для отложенного поиска.

        :param text: Текст для поиска
        """
        # Запускаем поиск через 100 мс для оптимизации
        QTimer.singleShot(100, lambda: self.perform_search(text))

    def perform_search(self, text):
        """
        Выполняет поиск по гайдам и играм.

        :param text: Текст для поиска
        """
        # Если поле поиска пустое, скрываем результаты
        if not text.strip():
            self.results_list.hide()
            return

        # Приводим запрос к нижнему регистру для регистронезависимого поиска
        query = text.lower()
        results = []

        # Поиск в гайдах
        for guide in GUIDES:
            if query in guide["title"].lower():
                results.append({
                    'type': 'Гайд',
                    'title': guide["title"],
                    'url': guide["url"]
                })

        # Поиск в играх
        for game in GAMES:
            if query in game["title"].lower():
                results.append({
                    'type': 'Игра',
                    'title': game["title"],
                    'url': game["url"]
                })

        # Отображаем результаты
        self.display_results(results)

    def open_item(self, item):
        """
        Открывает выбранный элемент в браузере по умолчанию.

        :param item: Элемент списка, по которому кликнули
        """
        # Получаем URL из пользовательских данных элемента
        url = item.data(Qt.UserRole)
        # Открываем URL в браузере по умолчанию
        webbrowser.open(url)

class NavigationBar(QWidget):
    """Нижняя панель навигации для переключения между экранами."""
    
    def __init__(self, stacked_widget, parent=None):
        super().__init__(parent)
        self.stacked_widget = stacked_widget
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(20)
        
        # Кнопки навигации (поменяли местами Настройки и Дополнительно)
        self.home_button = self.create_nav_button("Домой", "go-home")
        self.search_button = self.create_nav_button("Поиск", "system-search")
        self.dummy_button = self.create_nav_button("Дополнительно", "applications-other")
        self.settings_button = self.create_nav_button("Настройки", "preferences-system")
        
        # Группируем кнопки для управления состоянием
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.addButton(self.home_button, 0)
        self.button_group.addButton(self.search_button, 1)
        self.button_group.addButton(self.dummy_button, 2)  # Было 3
        self.button_group.addButton(self.settings_button, 3)  # Было 2
        
        # Добавляем кнопки в лэйаут
        layout.addWidget(self.home_button)
        layout.addWidget(self.search_button)
        layout.addWidget(self.dummy_button)
        layout.addWidget(self.settings_button)
        
        # По умолчанию активна кнопка поиска
        self.search_button.setChecked(True)
        
        # Подключаем обработчики
        self.home_button.clicked.connect(lambda: self.switch_screen(0))
        self.search_button.clicked.connect(lambda: self.switch_screen(1))
        self.dummy_button.clicked.connect(lambda: self.switch_screen(2))
        self.settings_button.clicked.connect(lambda: self.switch_screen(3))
    
    def create_nav_button(self, text, icon_name):
        """Создает кнопку навигации с иконкой."""
        button = QToolButton()
        button.setText(text)
        button.setIcon(QIcon.fromTheme(icon_name))
        button.setIconSize(QSize(24, 24))
        button.setCheckable(True)
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setStyleSheet("""
            QToolButton {
                padding: 10px;
                font-size: 12px;
            }
            QToolButton:checked {
                background-color: #2a9fd6;
                color: white;
            }
        """)
        return button
    
    def switch_screen(self, index):
        """Переключает экран в стеке виджетов."""
        self.stacked_widget.setCurrentIndex(index)

class MainWindow(QMainWindow):
    """Главное окно приложения с системой многоконного интерфейса."""

    def __init__(self, dark_theme=True):
        """
        Инициализация главного окна приложения.

        :param dark_theme: Использовать темную тему (по умолчанию True)
        """
        super().__init__()
        # Настройка окна
        self.setWindowTitle("PixelDeck")
        self.setGeometry(400, 300, 1280, 800)
        self.setMinimumSize(QSize(800, 600))
        self.dark_theme = dark_theme

        # Устанавливаем иконку приложения
        self.setWindowIcon(QIcon.fromTheme("system-search"))

        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной вертикальный лэйаут
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Создаем стек виджетов для управления экранами
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget, 1)  # Растягиваем на все пространство
        
        # Создаем экраны (поменяли местами DummyScreen и SettingsScreen)
        self.welcome_screen = WelcomeScreen()
        self.search_screen = SearchScreen(self, dark_theme)
        self.dummy_screen = DummyScreen()
        self.settings_screen = SettingsScreen(self, dark_theme)
        
        # Добавляем экраны в стек
        self.stacked_widget.addWidget(self.welcome_screen)
        self.stacked_widget.addWidget(self.search_screen)
        self.stacked_widget.addWidget(self.dummy_screen)  # Индекс 2
        self.stacked_widget.addWidget(self.settings_screen)  # Индекс 3
        
        # По умолчанию показываем экран приветствия
        self.stacked_widget.setCurrentIndex(0)
        
        # Создаем панель навигации
        self.nav_bar = NavigationBar(self.stacked_widget)
        main_layout.addWidget(self.nav_bar)
        
        # Применяем выбранную тему
        self.apply_theme()

    def switch_to_search(self):
        """Переключает на экран поиска."""
        self.stacked_widget.setCurrentIndex(1)
        self.nav_bar.search_button.setChecked(True)

    def switch_to_settings(self):
        """Переключает на экран настроек."""
        self.stacked_widget.setCurrentIndex(3)
        self.nav_bar.settings_button.setChecked(True)

    def apply_theme(self):
        """Применяет выбранную тему (темную или светлую) ко всем экранам."""
        if self.dark_theme:
            style = load_stylesheet(DARK_STYLE)
        else:
            style = load_stylesheet(LIGHT_STYLE)

        if style:
            self.setStyleSheet(style)
            # Применяем тему ко всем экранам
            self.welcome_screen.setStyleSheet(style)
            self.search_screen.apply_theme()
            self.settings_screen.apply_theme()
            self.dummy_screen.setStyleSheet(style)

# Точка входа в приложение
if __name__ == "__main__":
    # Создаем необходимые директории
    os.makedirs(STYLES_DIR, exist_ok=True)
    os.makedirs(CONTENT_DIR, exist_ok=True)
    
    # Создаем экземпляр приложения
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Устанавливаем стиль Fusion

    # --- ПРОВЕРКА НАЛИЧИЯ ФАЙЛОВ СТИЛЕЙ ---
    # Список обязательных файлов стилей
    required_styles = [
        DARK_STYLE,
        LIGHT_STYLE
    ]

    # Проверяем наличие каждого файла стиля
    missing_styles = [style for style in required_styles if not os.path.exists(style)]

    # Если директория со стилями не существует, считаем все стили отсутствующими
    if not os.path.exists(STYLES_DIR):
        missing_styles = required_styles

    # Если какие-то файлы отсутствуют
    if missing_styles:
        # Показываем диалог с ошибкой
        show_style_error(missing_styles)
        sys.exit(1)  # Выходим с ошибкой

    # --- НАСТРОЙКА КОНФИГУРАЦИИ ПРИЛОЖЕНИЯ ---
    # Создаем каталог для настроек в домашней директории пользователя
    config_dir = os.path.join(os.path.expanduser("~"), "PixelDeck")
    os.makedirs(config_dir, exist_ok=True)  # Создаем, если не существует

    # Путь к файлу настроек
    config_path = os.path.join(config_dir, "pixeldeck.ini")
    # Создаем объект для работы с настройками
    settings = QSettings(config_path, QSettings.IniFormat)

    # Читаем настройки
    welcome_shown = settings.value("welcome_shown", False, type=bool)
    dark_theme = settings.value("dark_theme", True, type=bool)

    # Если приветственное окно еще не показывалось
    if not welcome_shown:
        # Создаем и показываем приветственное окно
        welcome = WelcomeDialog(dark_theme=dark_theme)
        # Если пользователь нажал "Продолжить"
        if welcome.exec_() == QDialog.Accepted:
            # Сохраняем флаг, что окно было показано
            settings.setValue("welcome_shown", True)

    # Создаем и показываем главное окно приложения
    window = MainWindow(dark_theme=dark_theme)
    window.showMaximized()  # Показываем в полноэкранном режиме
    
    # Проверяем обновления с помощью updater.py
    QTimer.singleShot(3000, lambda: check_and_show_updates(window))
    
    # Запускаем главный цикл обработки событий
    sys.exit(app.exec_())

def check_and_show_updates(parent_window):
    """Запускает внешний updater"""
    try:
        # Получаем путь к текущей директории
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Формируем путь к updater.py
        updater_path = os.path.join(current_dir, "Programm", "updater.py")
        
        # Определяем флаг темы
        theme_flag = "--dark" if parent_window.dark_theme else "--light"
        
        # Запускаем updater в фоновом режиме
        subprocess.Popen(
            [sys.executable, updater_path, theme_flag],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    except Exception as e:
        print(f"Ошибка запуска updater: {e}")
