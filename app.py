[file name]: app.py
[file content begin]
#!/usr/bin/env python3
import sys
import os
import logging
import traceback
import shutil
import time
import webbrowser
import json
import requests
import subprocess

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

from PyQt6.QtWidgets import (
    QApplication, QAbstractItemView, QMainWindow, QWidget, QDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout,
    QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont

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
from welcome import WelcomeWizard

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
    """Загружает контент из JSON-файлов с обработкой ошибок."""
    # Проверяем и создаем необходимые директории
    os.makedirs(CONTENT_DIR, exist_ok=True)
    
    # Загрузка гайдов
    guides = safe_load_json(GUIDES_JSON_PATH, [])
    
    # Загрузка игр
    games = safe_load_json(GAME_LIST_GUIDE_JSON_PATH, [])
    
    logger.info(f"Загружено гайдов: {len(guides)}, игр: {len(games)}")
    return guides, games

def show_style_error(missing_resources):
    """Показывает диалоговое окно с ошибкой отсутствия ресурсов."""
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

class MainWindow(QMainWindow):
    """Главное окно приложения с системой поиска."""

    def __init__(self, dark_theme=True):
        super().__init__()
        # Настройка окна
        self.setWindowTitle("PixelDeck")
        self.setGeometry(400, 300, 1280, 800)
        self.setMinimumSize(800, 600)
        self.dark_theme = dark_theme

        # Устанавливаем иконку приложения
        self.setWindowIcon(QIcon.fromTheme("system-search"))

        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной вертикальный лэйаут
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        # Заголовок
        title = QLabel("PixelDeck")
        title.setObjectName("title")
        title_font = QFont("Arial", 28)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Поле поиска
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Введите название игры или гайда...")
        self.search_field.textChanged.connect(self.search_content)
        main_layout.addWidget(self.search_field)

        # Список результатов
        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self.open_item)
        self.results_list.hide()  # Скрываем изначально
        main_layout.addWidget(self.results_list, 1)  # Растягиваем

        # Настраиваем список результатов
        self.results_list.setSpacing(10)  # Отступ между элементами
        self.results_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def display_results(self, results):
        """Отображает результаты поиска в виджете списка."""
        self.results_list.clear()  # Очищаем предыдущие результаты
        if not results:
            self.results_list.hide()
            return

        for item in results:
            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, item['url'])
            item_widget = SearchItemWidget(item['title'], item['type'])
            list_item.setSizeHint(item_widget.sizeHint())
            self.results_list.addItem(list_item)
            self.results_list.setItemWidget(list_item, item_widget)

        self.results_list.show()
        self.results_list.updateGeometry()

    def search_content(self, text):
        """Обработчик изменения текста в поле поиска."""
        QTimer.singleShot(100, lambda: self.perform_search(text))

    def perform_search(self, text):
        """Выполняет поиск по гайдам и играм."""
        if not text.strip():
            self.results_list.hide()
            return

        query = text.lower()
        results = []

        for guide in GUIDES:
            if query in guide["title"].lower():
                results.append({
                    'type': 'Гайд',
                    'title': guide["title"],
                    'url': guide["url"]
                })

        for game in GAMES:
            if query in game["title"].lower():
                results.append({
                    'type': 'Игра',
                    'title': game["title"],
                    'url': game["url"]
                })

        self.display_results(results)

    def open_item(self, item):
        """Открывает выбранный элемент в браузере по умолчанию."""
        url = item.data(Qt.ItemDataRole.UserRole)
        webbrowser.open(url)

class SearchItemWidget(QWidget):
    """Кастомный виджет для отображения результата поиска"""
    def __init__(self, title, item_type, parent=None):
        super().__init__(parent)
        self.setup_ui(title, item_type)
        
    def setup_ui(self, title, item_type):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        self.title_label = QLabel(title)
        title_font = QFont("Arial", 16)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        
        self.type_label = QLabel(f"Тип: {item_type}")
        type_font = QFont("Arial", 14)
        self.type_label.setFont(type_font)
        layout.addWidget(self.type_label)
        self.setMinimumHeight(100)

def check_and_show_updates(dark_theme):
    """Запускает внешний updater"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        updater_path = os.path.join(current_dir, "Programm", "updater.py")
        theme_flag = "--dark" if dark_theme else "--light"
        version_arg = f"--current-version={APP_VERSION}"
        
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
        os.makedirs(STYLES_DIR, exist_ok=True)
        os.makedirs(CONTENT_DIR, exist_ok=True)
        
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
        
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setStyleSheet(global_stylesheet)
        
        app_settings._ensure_settings()
        
        global GUIDES, GAMES
        GUIDES, GAMES = load_content()
        
        welcome_shown = app_settings.get_welcome_shown()
        dark_theme = app_settings.get_theme() == 'dark'
        
        # Устанавливаем класс темы
        app.setProperty("class", "dark-theme" if dark_theme else "light-theme")
        
        if not welcome_shown:
            welcome = WelcomeWizard()
            welcome.center_on_screen()
            result = welcome.exec()
            if result == QDialog.DialogCode.Accepted:
                app_settings.set_welcome_shown(True)
            
            # Обновляем тему после мастера
            dark_theme = app_settings.get_theme() == 'dark'
            app.setProperty("class", "dark-theme" if dark_theme else "light-theme")
        
        window = MainWindow(dark_theme=dark_theme)
        window.showMaximized()
        
        QTimer.singleShot(1000, lambda: check_and_show_updates(dark_theme))
        
        sys.exit(app.exec())
        
    except Exception as e:
        logger.exception("Критическая ошибка при запуске")
        try:
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
[file content end]
