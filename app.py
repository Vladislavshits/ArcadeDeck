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
    QMessageBox, QStackedWidget, QFrame, QGridLayout, QHBoxLayout
)
from PyQt6.QtCore import Qt, QTimer, QEasingCurve, QPoint, QPropertyAnimation
from PyQt6.QtGui import QIcon, QFont, QPixmap

# Импорт из нашего приложения
from core import APP_VERSION, CONTENT_DIR, STYLES_DIR, THEME_FILE, GUIDES_JSON_PATH, GAME_LIST_GUIDE_JSON_PATH
from settings import app_settings
from welcome import WelcomeWizard
from app.ui_assets.theme_manager import theme_manager

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

    global GUIDES, GAMES

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

class MainWindow(QMainWindow):
    """Главное окно приложения с двухслойным интерфейсом"""

    def __init__(self):
        super().__init__()
        # Настройка окна
        self.setWindowTitle("PixelDeck")
        self.setGeometry(400, 300, 1280, 800)
        self.setMinimumSize(800, 600)
        self.current_layer = 0  # 0 = основной слой, 1 = слой настроек
        self.animation_duration = 300  # мс

        # Устанавливаем иконку приложения
        self.setWindowIcon(QIcon.fromTheme("system-search"))

        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной вертикальный лэйаут
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # --- ВЕРХНЯЯ ЧАСТЬ (поиск) ---
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 10)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Введите название игры или гайда...")
        self.search_field.textChanged.connect(self.search_content)
        self.search_field.setMinimumHeight(40)
        search_layout.addWidget(self.search_field)

        main_layout.addLayout(search_layout)

        # --- СТЕК СЛОЕВ ---
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)

        # --- НИЖНЯЯ ЧАСТЬ (подсказки) ---
        hints_layout = QHBoxLayout()
        self.hint_label = QLabel("B: Назад")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hints_layout.addWidget(self.hint_label)

        main_layout.addLayout(hints_layout)

        # --- СОЗДАЕМ СЛОИ ---
        self.create_main_layer()    # Слой 0: Основной
        self.create_settings_layer() # Слой 1: Настройки

        # Начальное состояние
        self.stack.setCurrentIndex(0)
        self.update_hints()

        # Применяем текущую тему
        self.apply_theme(theme_manager.current_theme)

        # Подписываемся на изменения темы
        theme_manager.theme_changed.connect(self.apply_theme)

        # Устанавливаем фокус
        self.search_field.setFocus()

        # Добавляем список для результатов поиска
        self.search_results_list = QListWidget()
        self.search_results_list.setParent(self)
        self.search_results_list.hide()
        self.search_results_list.itemClicked.connect(self.open_item)
        self.search_results_list.setGeometry(50, 100, self.width() - 100, self.height() - 200)
        self.search_results_list.setStyleSheet("""
            background-color: palette(window);
            border: 1px solid palette(mid);
            border-radius: 10px;
        """)

    # ДОБАВЛЕННЫЕ МЕТОДЫ ДЛЯ СОЗДАНИЯ СЛОЕВ
    def create_main_layer(self):
        """Создает основной слой с играми"""
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(20)

        # --- ПОСЛЕДНЯЯ ИГРА (большая плитка) ---
        last_game_frame = QFrame()
        last_game_frame.setObjectName("LastGameFrame")
        last_game_frame.setMinimumHeight(200)

        last_game_layout = QVBoxLayout(last_game_frame)
        last_game_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.last_game_label = QLabel("The Witcher 3: Wild Hunt")
        self.last_game_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.last_game_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        last_game_layout.addWidget(self.last_game_label)

        self.last_game_icon = QLabel()
        self.last_game_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Используем placeholder, если иконки нет
        pixmap = QPixmap()
        if pixmap.isNull():
            # Создаем пустую иконку с серым фоном
            pixmap = QPixmap(100, 100)
            pixmap.fill(Qt.GlobalColor.gray)
        self.last_game_icon.setPixmap(pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio))
        last_game_layout.addWidget(self.last_game_icon)

        self.last_game_time = QLabel("Последний запуск: 2 часа назад")
        self.last_game_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        last_game_layout.addWidget(self.last_game_time)

        main_layout.addWidget(last_game_frame, 1)  # Растягиваем

        # --- БИБЛИОТЕКА ИГР (сетка плиток) ---
        games_label = QLabel("Библиотека игр")
        games_label.setFont(QFont("Arial", 14))
        main_layout.addWidget(games_label)

        # Сетка игр
        self.games_grid = QGridLayout()
        self.games_grid.setSpacing(15)

        # Заполняем демо-играми
        games = [
            {"name": "Cyberpunk 2077", "system": "PC"},
            {"name": "God of War", "system": "PS4"},
            {"name": "Hollow Knight", "system": "Switch"},
            {"name": "Elden Ring", "system": "PC"},
            {"name": "Stardew Valley", "system": "PC"},
            {"name": "The Last of Us", "system": "PS4"}
        ]

        for i, game in enumerate(games):
            row = i // 3
            col = i % 3

            game_frame = QFrame()
            game_frame.setObjectName("GameTile")
            game_frame.setMinimumSize(150, 150)
            game_frame.setMaximumSize(200, 200)

            game_layout = QVBoxLayout(game_frame)
            game_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            name_label = QLabel(game["name"])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setFont(QFont("Arial", 10))
            game_layout.addWidget(name_label)

            system_label = QLabel(game["system"])
            system_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            system_label.setFont(QFont("Arial", 8))
            game_layout.addWidget(system_label)

            self.games_grid.addWidget(game_frame, row, col)

        games_container = QWidget()
        games_container.setLayout(self.games_grid)
        main_layout.addWidget(games_container, 3)  # Больше места для игр

        self.stack.addWidget(main_widget)

    def create_settings_layer(self):
        """Создает слой настроек и инструментов"""
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(50, 50, 50, 50)
        settings_layout.setSpacing(30)

        # Заголовок
        settings_title = QLabel("Системные настройки")
        settings_title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        settings_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_layout.addWidget(settings_title)

        # Сетка настроек
        settings_grid = QGridLayout()
        settings_grid.setSpacing(20)

        # Элементы настроек
        settings_items = [
            {"name": "Настройки системы", "icon": "settings.png"},
            {"name": "Управление эмуляторами", "icon": "emulator.png"},
            {"name": "Внешний вид", "icon": "appearance.png"},
            {"name": "Сетевое подключение", "icon": "network.png"},
            {"name": "Обновления", "icon": "update.png"},
            {"name": "О программе", "icon": "info.png"},
            {"name": "Инструменты разработчика", "icon": "tools.png"},
            {"name": "Выход", "icon": "exit.png"}
        ]

        for i, item in enumerate(settings_items):
            row = i // 4
            col = i % 4

            item_frame = QFrame()
            item_frame.setObjectName("SettingsTile")
            item_frame.setMinimumSize(120, 120)

            item_layout = QVBoxLayout(item_frame)
            item_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            name_label = QLabel(item["name"])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setFont(QFont("Arial", 9))
            item_layout.addWidget(name_label)

            settings_grid.addWidget(item_frame, row, col)

        settings_container = QWidget()
        settings_container.setLayout(settings_grid)
        settings_layout.addWidget(settings_container, 1)

        self.stack.addWidget(settings_widget)

    # ДОБАВЛЕННЫЙ МЕТОД ДЛЯ ПОИСКА
    def search_content(self, text):
        """Обработчик изменения текста в поле поиска."""
        QTimer.singleShot(100, lambda: self.perform_search(text))

    # ДОБАВЛЕННЫЙ МЕТОД ДЛЯ ПОИСКА
    def perform_search(self, text):
        """Выполняет поиск по гайдам и играм."""
        if not text.strip():
            self.search_results_list.hide()
            return

        query = text.lower()
        results = []

        # Используем глобальные переменные GUIDES и GAMES
        global GUIDES, GAMES

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

        self.display_search_results(results)

    # ДОБАВЛЕННЫЙ МЕТОД ДЛЯ ПОИСКА
    def display_search_results(self, results):
        """Отображает результаты поиска."""
        self.search_results_list.clear()
        if not results:
            self.search_results_list.hide()
            return

        for item in results:
            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, item['url'])
            item_widget = SearchItemWidget(item['title'], item['type'])
            list_item.setSizeHint(item_widget.sizeHint())
            self.search_results_list.addItem(list_item)
            self.search_results_list.setItemWidget(list_item, item_widget)

        self.search_results_list.show()
        self.search_results_list.raise_()  # Поднимаем над другими виджетами

    # ДОБАВЛЕННЫЙ МЕТОД ДЛЯ ПОИСКА
    def open_item(self, item):
        """Открывает выбранный элемент в браузере по умолчанию."""
        url = item.data(Qt.ItemDataRole.UserRole)
        webbrowser.open(url)
        self.search_results_list.hide()

    def apply_theme(self, theme_name):
        """Применяет указанную тему к окну и всем дочерним виджетам"""
        try:
            # Загружаем стили из файла
            from core import THEME_FILE
            with open(THEME_FILE, 'r', encoding='utf-8') as f:
                stylesheet = f.read()

            # Устанавливаем свойство класса
            self.setProperty("class", f"{theme_name}-theme")

            # Применяем стили
            self.setStyleSheet(stylesheet)

            # Обновляем стили всех виджетов
            for widget in self.findChildren(QWidget):
                widget.style().unpolish(widget)
                widget.style().polish(widget)
        except Exception as e:
            logger.error(f"Ошибка применения темы: {e}")

    def switch_layer(self, direction):
        """Переключает между слоями с анимацией"""
        if direction == "down" and self.current_layer == 0:
            target_layer = 1
            self.animate_transition(target_layer, 0, -50)
        elif direction == "up" and self.current_layer == 1:
            target_layer = 0
            self.animate_transition(target_layer, 0, 50)
        else:
            return

    def animate_transition(self, target_layer, start_y, delta_y):
        """Анимирует переход между слоями"""
        # Сохраняем текущую позицию
        current_pos = self.stack.pos()

        # Создаем анимацию
        self.animation = QPropertyAnimation(self.stack, b"pos")
        self.animation.setDuration(self.animation_duration)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        # Начальное положение - смещение вниз/вверх
        self.stack.move(current_pos.x(), current_pos.y() + delta_y)
        self.animation.setStartValue(QPoint(current_pos.x(), current_pos.y() + delta_y))

        # Конечное положение - исходное
        self.animation.setEndValue(current_pos)

        # Запускаем анимацию
        self.animation.start()

        # После завершения анимации переключаем слой
        self.animation.finished.connect(lambda: self.finalize_layer_switch(target_layer))

    def finalize_layer_switch(self, target_layer):
        """Завершает переключение слоя"""
        self.stack.setCurrentIndex(target_layer)
        self.current_layer = target_layer
        self.update_hints()
        self.animation.deleteLater()

    def update_hints(self):
        """Обновляет подсказки в зависимости от текущего слоя"""
        if self.current_layer == 0:
            hints = "↓: Настройки  |  A: Запустить  |  Y: Поиск  |  B: Назад"
        else:
            hints = "↑: Главный экран  |  A: Выбрать  |  B: Назад"

        self.hint_label.setText(hints)

    def keyPressEvent(self, event):
        """Обрабатывает нажатия клавиш"""
        if event.key() == Qt.Key.Key_Down:
            self.switch_layer("down")
            event.accept()
        elif event.key() == Qt.Key.Key_Up:
            self.switch_layer("up")
            event.accept()
        else:
            super().keyPressEvent(event)

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
        
        # Инициализируем менеджер тем с текущей настройкой
        theme_manager.set_theme(app_settings.get_theme())

        # Устанавливаем класс темы
        app.setProperty("class", "dark-theme" if dark_theme else "light-theme")
        
        if not welcome_shown:
            logger.info("Показываем приветственное окно")
            welcome = WelcomeWizard()
            welcome.center_on_screen()
            result = welcome.exec()
            
            # Всегда устанавливаем флаг после показа
            app_settings.set_welcome_shown(True)
            
            # Обновляем тему после мастера
            dark_theme = app_settings.get_theme() == 'dark'
            app.setProperty("class", "dark-theme" if dark_theme else "light-theme")
        
        window = MainWindow()
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
