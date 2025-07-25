#!/usr/bin/env python3
import sys
import os
import logging
import traceback
import shutil
import time

# Глобальная переменная для хранения стилей
global_stylesheet = ""

# Настройка логирования
log_dir = os.path.join(os.path.expanduser("~"), "PixelDeck", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "pixeldeck.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('PixelDeck')

# Глобальный обработчик исключений
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.error(
        "Неперехваченное исключение:",
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    
    error_msg = f"{exc_type.__name__}: {exc_value}"
    
    # Попытка показать сообщение об ошибке
    try:
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
            
        QMessageBox.critical(
            None,
            "Критическая ошибка",
            f"Произошла непредвиденная ошибка:\n\n{error_msg}\n\n"
            f"Подробности в логах: {log_file}"
        )
    except Exception:
        pass

sys.excepthook = handle_exception

# Проверка виртуального окружения
def is_venv_active():
    return (hasattr(sys, 'real_prefix') or 
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))

if not is_venv_active():
    logger.warning("ВНИМАНИЕ: Виртуальное окружение не активировано!")

# Определяем корневую директорию проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Добавляем пути к модулям
sys.path.insert(0, BASE_DIR)

import webbrowser
import json
import requests
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QAbstractItemView, QMainWindow, QWidget,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QSizePolicy, QToolButton, QButtonGroup,
    QCheckBox, QDialog, QTextEdit, QMessageBox, QProgressDialog
)
from PyQt6.QtCore import Qt, QTimer, QSettings, QFile, QTextStream, QSize, QUrl
from PyQt6.QtGui import QIcon, QFont, QColor, QPalette, QScreen

# Импорт из нашего приложения
from core import (
    APP_VERSION,
    CONTENT_DIR,
    STYLES_DIR,
    THEME_FILE,
    GUIDES_JSON_PATH,
    GAME_LIST_GUIDE_JSON_PATH
)
from settings import app_settings

# Безопасная загрузка JSON
def safe_load_json(path, default):
    try:
        if not os.path.exists(path):
            logger.warning(f"Файл не найден: {path}")
            return default
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
        if not content:
            logger.info(f"Файл пуст: {path}")
            return default
            
        return json.loads(content)
        
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON в {path}: {e}")
        # Создаем резервную копию битого файла
        backup_path = f"{path}.corrupted.{int(time.time())}"
        shutil.copyfile(path, backup_path)
        logger.info(f"Создана резервная копия: {backup_path}")
        
        # Восстанавливаем исходный файл
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Восстановлен исходный файл: {path}")
        return default
        
    except Exception as e:
        logger.error(f"Критическая ошибка при загрузке {path}: {e}")
        return default

def load_content():
    """
    Загружает контент из JSON-файлов с обработкой ошибок.
    """
    # Проверяем и создаем необходимые директории
    os.makedirs(CONTENT_DIR, exist_ok=True)
    
    # Загрузка гайдов
    guides = safe_load_json(GUIDES_JSON_PATH, [])
    
    # Загрузка игр
    games = safe_load_json(GAME_LIST_GUIDE_JSON_PATH, [])
    
    logger.info(f"Загружено гайдов: {len(guides)}, игр: {len(games)}")
    return guides, games

def show_style_error(missing_resources):
    """
    Показывает диалоговое окно с ошибкой отсутствия ресурсов.
    """
    # Создаем временное приложение для показа сообщения
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    
    error_dialog = QMessageBox()
    error_dialog.setWindowTitle("Ошибка запуска! Код #1!")
    error_dialog.setIcon(QMessageBox.Icon.Critical)

    message = "Отсутствуют критические ресурсы. Переустановите программу.\n\n"
    message += "Отсутствующие файлы/директории:\n"
    for resource in missing_resources:
        message += f"- {resource}\n"

    error_dialog.setText(message)

    download_button = error_dialog.addButton("Скачать установщик", QMessageBox.ActionRole)
    close_button = error_dialog.addButton("Закрыть", QMessageBox.RejectRole)

    error_dialog.exec()

    if error_dialog.clickedButton() == download_button:
        webbrowser.open("https://github.com/Vladislavshits/PixelDeck/releases/download/v0.1.5/install.pixeldeck.sh")

def check_resources():
    """Проверяет наличие всех критических ресурсов"""
    missing = []
    
    # Список обязательных файлов
    required_files = [
        THEME_FILE,
        GUIDES_JSON_PATH,
        GAME_LIST_GUIDE_JSON_PATH
    ]
    
    # Проверяем каждый файл
    for path in required_files:
        if not os.path.exists(path):
            missing.append(os.path.basename(path))
            logger.error(f"Отсутствует обязательный файл: {path}")
    
    # Проверяем директории
    required_dirs = [STYLES_DIR, CONTENT_DIR]
    for dir_path in required_dirs:
        if not os.path.isdir(dir_path):
            missing.append(os.path.basename(dir_path))
            logger.error(f"Отсутствует обязательная директория: {dir_path}")
    
    return missing

class WelcomeScreen(QWidget):
    """Экран приветствия"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        title = QLabel("PixelDeck")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title, 1)

class WelcomeDialog(QDialog):
    """Диалоговое окно приветствия при первом запуске."""
    
    def __init__(self, dark_theme=True, parent=None):
        super().__init__(parent)
        self.dark_theme = dark_theme
        self.setup_ui()
        self.center_on_screen()
        
    def center_on_screen(self):
        """Центрирует окно на экране."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
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
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        description_font = QFont()
        description_font.setPointSize(14)
        description.setFont(description_font)
        layout.addWidget(description)
        
        layout.addStretch(1)
        
        # Кнопка GitHub
        github_button = QPushButton("Проект на GitHub")
        github_button.setFixedHeight(50)
        github_button.clicked.connect(lambda: webbrowser.open("https://github.com/Vladislavshits/PixelDeck"))
        layout.addWidget(github_button)
        
        # Кнопка продолжения
        continue_button = QPushButton("Продолжить")
        continue_button.setFixedHeight(50)
        continue_button.clicked.connect(self.accept)
        layout.addWidget(continue_button)

class SettingsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        
        # Загружаем текущую тему
        current_theme = app_settings.get_theme()
        # Устанавливаем состояние переключателя на основе текущей темы
        self.theme_toggle.setChecked(current_theme == 'dark')

    def toggle_theme(self, checked):
        """Обработчик изменения темы"""
        theme = 'dark' if checked else 'light'
        app_settings.set_theme(theme)
    
        # Применяем новую тему
        app = QApplication.instance()
        app.setProperty("class", f"{theme}-theme")
    
        # Перезагружаем стили
        app.setStyleSheet("")
        app.setStyleSheet(global_stylesheet)

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
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        # Убрали установку состояния здесь - она делается в __init__ после setup_ui
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
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setObjectName("versionLabel")
        main_layout.addWidget(version_label)


class DummyScreen(QWidget):
    """Заглушка для дополнительного экрана."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        label = QLabel("Этот экран пока не реализован")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

class SearchScreen(QWidget):
    """Экран поиска гайдов и игр."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        # Создаем основной лэйаут
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Заголовок
        title = QLabel("Поиск")
        title.setObjectName("title")
        title_font = QFont("Arial", 28)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Поле поиска
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Введите название игры или гайда...")
        self.search_field.textChanged.connect(self.search_content)
        layout.addWidget(self.search_field)

        # Список результатов
        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self.open_item)
        self.results_list.hide()  # Скрываем изначально
        layout.addWidget(self.results_list, 1)  # Растягиваем

        # Настраиваем список результатов
        self.results_list.setSpacing(10)  # Отступ между элементами
        self.results_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

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
            # Создаем элемент списка
            list_item = QListWidgetItem()
            
            # Сохраняем URL в пользовательских данных элемента
            list_item.setData(Qt.ItemDataRole.UserRole, item['url'])

            # Создаем кастомный виджет для элемента
            item_widget = SearchItemWidget(item['title'], item['type'])

            # Устанавливаем виджет в элемент списка
            list_item.setSizeHint(item_widget.sizeHint())
            self.results_list.addItem(list_item)
            self.results_list.setItemWidget(list_item, item_widget)

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
        url = item.data(Qt.ItemDataRole.UserRole)
        webbrowser.open(url)

class SearchItemWidget(QWidget):
    """Кастомный виджет для отображения результата поиска"""
    def __init__(self, title, item_type, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchItemWidget")
        self.setup_ui(title, item_type)
        
    def setup_ui(self, title, item_type):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Заголовок
        self.title_label = QLabel(title)
        title_font = QFont("Arial", 16)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)  # Разрешаем перенос текста
        layout.addWidget(self.title_label)
        
        # Тип
        self.type_label = QLabel(f"Тип: {item_type}")
        type_font = QFont("Arial", 14)
        self.type_label.setFont(type_font)
        layout.addWidget(self.type_label)
        
        # Устанавливаем минимальную высоту
        self.setMinimumHeight(100)

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
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
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
        
        # Создаем экраны
        self.welcome_screen = WelcomeScreen()
        self.search_screen = SearchScreen(self)
        self.dummy_screen = DummyScreen()
        self.settings_screen = SettingsScreen(self)  # Без передачи dark_theme
        
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

    def switch_to_search(self):
        """Переключает на экран поиска."""
        self.stacked_widget.setCurrentIndex(1)
        self.nav_bar.search_button.setChecked(True)

    def switch_to_settings(self):
        """Переключает на экран настроек."""
        self.stacked_widget.setCurrentIndex(3)
        self.nav_bar.settings_button.setChecked(True)

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
        logger.error(f"Ошибка запуска updater: {e}")

# Точка входа в приложение
if __name__ == "__main__":
    logger.info("Запуск PixelDeck")
    logger.info(f"Версия: {APP_VERSION}")
    logger.info(f"Рабочая директория: {os.getcwd()}")
    
    try:
        # Создаем необходимые директории
        os.makedirs(STYLES_DIR, exist_ok=True)
        os.makedirs(CONTENT_DIR, exist_ok=True)
        
        # Проверка ресурсов
        missing_resources = check_resources()
        if missing_resources:
            logger.critical("Отсутствуют критические ресурсы")
            show_style_error(missing_resources)
            sys.exit(1)
        
        # Загружаем глобальный стиль
        try:
            with open(THEME_FILE, 'r', encoding='utf-8') as f:
                global_stylesheet = f.read()
        except Exception as e:
            logger.error(f"Ошибка загрузки стилей: {e}")
            show_style_error([THEME_FILE])
            sys.exit(1)
        
        # Создаем экземпляр приложения
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        
        # Устанавливаем глобальный стиль
        app.setStyleSheet(global_stylesheet)
        
        # Создаем каталог для настроек
        config_dir = os.path.join(os.path.expanduser("~"), "PixelDeck")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "pixeldeck.ini")
        settings = QSettings(config_path, QSettings.Format.IniFormat)
        
        # Читаем настройки
        welcome_shown = settings.value("welcome_shown", False, type=bool)
        dark_theme = settings.value("dark_theme", True, type=bool)
        
        # Устанавливаем класс темы
        app.setProperty("class", "dark-theme" if dark_theme else "light-theme")
        
        # Инициализируем app_settings
        app_settings._ensure_settings()
        
        # Загружаем контент ПОСЛЕ создания QApplication
        global GUIDES, GAMES
        GUIDES, GAMES = load_content()
        
        # Приветственное окно
        if not welcome_shown:
            welcome = WelcomeDialog(dark_theme=dark_theme)
            if welcome.exec() == QDialog.DialogCode.Accepted:
                settings.setValue("welcome_shown", True)
        
        # Главное окно
        window = MainWindow(dark_theme=dark_theme)
        window.showMaximized()
        
        # Проверка обновлений
        QTimer.singleShot(1000, lambda: check_and_show_updates(window))
        
        sys.exit(app.exec())
        
    except Exception as e:
        logger.exception("Критическая ошибка при запуске")
        # Попытка показать сообщение об ошибке
        try:
            # Создаем временное приложение для отображения ошибки
            temp_app = QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "Ошибка запуска",
                f"Произошла критическая ошибка: {str(e)}\n\n"
                f"Подробности в логах: {log_file}"
            )
            temp_app.exec()
        except Exception as ex:
            logger.error(f"Ошибка при показе сообщения об ошибке: {ex}")
        sys.exit(1)