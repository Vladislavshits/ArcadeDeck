#!/usr/bin/env python3
import os
import sys

# Принудительная установка кеш-директории
cache_root = os.path.join(os.path.expanduser("~"), "ArcadeDeck", "app", "caches")
os.makedirs(cache_root, exist_ok=True)

# Для Python 3.8+
sys.pycache_prefix = cache_root

# Отключаем кеширование байт-кода (если нужно)
sys.dont_write_bytecode = True

import logging
import traceback
import shutil
import time
import webbrowser
import json
import requests
import subprocess
import fcntl
import atexit
import signal
import errno

# Настройка логирования до проверки экземпляра
log_dir = os.path.join(os.path.expanduser("~"), "ArcadeDeck", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "arcadedeck.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('ArcadeDeck')

# Проверка на единственный экземпляр
def enforce_single_instance():
    """Обеспечивает запуск только одного экземпляра приложения"""
    lock_file = os.path.join(os.path.expanduser("~"), ".arcadedeck.lock")
    lock_fd = None

    try:
        # Открываем файл блокировки
        lock_fd = open(lock_file, 'w+')

        # Пытаемся установить эксклюзивную блокировку
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as e:
            # Обрабатываем только ошибки блокировки
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise

            # Читаем PID из файла
            lock_fd.seek(0)
            pid_str = lock_fd.read().strip()

            # Проверяем существование процесса
            if pid_str and pid_str.isdigit():
                pid = int(pid_str)
                if is_process_running(pid):
                    return False, pid

            # Если процесс не существует - продолжаем попытку
            logger.warning("Обнаружен lock-файл от несуществующего процесса")

        # Записываем PID текущего процесса
        lock_fd.seek(0)
        lock_fd.truncate()
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()

        # Регистрием очистку при выходе
        def cleanup():
            try:
                if lock_fd:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    lock_fd.close()
                if os.path.exists(lock_file):
                    os.unlink(lock_file)
            except Exception as e:
                logger.error(f"Ошибка очистки блокировки: {e}")

        atexit.register(cleanup)
        return True, None

    except Exception as e:
        logger.error(f"Ошибка установки блокировки: {e}")
        if lock_fd:
            try:
                lock_fd.close()
            except:
                pass
        return False, None

# Проверка активности процесса по PID
def is_process_running(pid):
    try:
        # Отправляем сигнал 0 (проверка существования процесса)
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.ESRCH:  # Процесс не существует
            return False
        elif err.errno == errno.EPERM:  # Нет прав, но процесс существует
            return True
        else:
            return False  # Другие ошибки считаем отсутствием процесса
    else:
        return True  # Процесс существует

# Глобальный обработчик исключений
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error(
        "Неперехваченное исключение:",
        exc_info=(exc_type, exc_value, exc_traceback))

    error_msg = f"{exc_type.__name__}: {exc_value}"

    # Проверяем существование приложения
    app = QApplication.instance()
    if not app:
        logger.error("QApplication не существует, невозможно показать ошибку")
        return

    # Попытка показать сообщение об ошибке
    try:
        # Ищем активное окно для родителя
        parent = None
        for widget in app.topLevelWidgets():
            if widget.isVisible():
                parent = widget
                break

        QMessageBox.critical(
            parent,
            "Критическая ошибка",
            f"Произошла непредвиденная ошибка:\n\n{error_msg}\n\n"
            f"Подробности в логах: {log_file}"
        )
    except Exception as e:
        logger.error(f"Ошибка при показе сообщения об ошибке: {e}")

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
    QMessageBox, QStackedWidget, QFrame, QGridLayout, QHBoxLayout, QPushButton,
    QSizePolicy, QScrollArea, QTabWidget, QDialogButtonBox, QRadioButton,
    QButtonGroup, QCheckBox, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QEvent
from PyQt6.QtGui import QIcon, QFont, QPixmap, QKeyEvent
from pathlib import Path

# Импорт из наших модулей установки
from app.modules.installer.install import InstallDialog
from app.modules.installer.game_downloader import GameDownloader

from core import APP_VERSION, CONTENT_DIR, STYLES_DIR, THEME_FILE, GUIDES_JSON_PATH, GAME_LIST_GUIDE_JSON_PATH
from settings import app_settings
from app.welcome import WelcomeWizard
from app.ui_assets.theme_manager import theme_manager
from updater import Updater, UpdateDialog  # Импортируем Updater и UpdateDialog
from navigation import NavigationController  # Импортируем NavigationController
from navigation import NavigationLayer
from app.modules.ui.game_info_page import GameInfoPage
from app.modules.module_logic.game_scanner import (
    is_game_installed,
    get_installed_games
)
from app.modules.module_logic.game_data_manager import get_game_data_manager, set_game_data_manager

# Модули настроек
from app.modules.settings_plugins.about_settings import AboutPage
from modules.settings_plugins.dev_settings import DevSettingsPage
from modules.settings_plugins.appearance_settings import AppearanceSettingsPage

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
    """Загружает данные об играх и гайдах."""
    logger.info("Загружаем данные...")
    guides = []  # Заглушка, чтобы не выдавало ошибку

    # Используем GameDataManager для загрузки игр
    try:
        manager = get_game_data_manager(Path(BASE_DIR))
        if manager is None:
            logger.error("GameDataManager не инициализирован")
            return [], []

        # Получаем все установленные игры
        final_games_list = manager.get_all_games()

        logger.info(f"Загружено {len(final_games_list)} игр.")
        return guides, final_games_list

    except Exception as e:
        logger.error(f"Ошибка загрузки игр через GameDataManager: {e}")
        return [], []

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
        webbrowser.open("https://github.com/Vladislavshits/ArcadeDeck/releases/download/v0.1.5/install.arcadedeck.sh")

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
    """Главное окно приложения с двухслойным интерфейсом"""
    def __init__(self):
        super().__init__()
        self.install_dir = BASE_DIR
        self.updater_process = None
        self.settings_tiles = []
        self.setWindowTitle("ArcadeDeck")
        self.setGeometry(400, 300, 1280, 800)
        self.setMinimumSize(800, 600)
        self.current_layer = NavigationLayer.MAIN
        icon_path = os.path.join(BASE_DIR, "app", "icon.png")
        self.setWindowIcon(QIcon(icon_path))

        # Инициализируем централизованный менеджер данных
        manager = get_game_data_manager(Path(BASE_DIR))
        set_game_data_manager(manager)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(10)

        # --- СТЕК СЛОЕВ ---
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack, 1)

        # --- НИЖНЯЯ ЧАСТЬ (подсказки) ---
        hints_layout = QHBoxLayout()
        self.hint_label = QLabel("B: Назад")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hints_layout.addWidget(self.hint_label)
        self.main_layout.addLayout(hints_layout)

        self.navigation_controller = NavigationController(self)
        self.navigation_controller.layer_changed.connect(self.switch_layer)
        self.navigation_controller.axis_moved.connect(self.handle_axis_movement)

        # ✅ Создаем все экраны
        self.init_ui()
        self.create_settings_layer()

        # ✅ НОВОЕ ИЗМЕНЕНИЕ: Создаём game_info_page и добавляем его в стек
        self.game_info_page = GameInfoPage(parent=self)
        self.stack.addWidget(self.game_info_page)

        # ✅ НОВОЕ ИЗМЕНЕНИЕ: Настраиваем колбэки для кнопок "Назад" и "Действие"
        self.game_info_page.back_callback = self.show_library_page
        self.game_info_page.action_callback = self.on_game_action

        # ✅ Устанавливаем стартовый экран
        self.stack.setCurrentIndex(0)
        self.current_layer = NavigationLayer.MAIN
        self.navigation_controller.switch_layer(NavigationLayer.MAIN)
        self.switch_layer(NavigationLayer.MAIN)

        # --- Темизация ---
        self.apply_theme(theme_manager.current_theme)
        theme_manager.theme_changed.connect(self.apply_theme)

        # --- Обновления ---
        self.updater = Updater(self)
        self.updater.update_available.connect(self.on_update_available)
        QTimer.singleShot(1000, self.updater.check_for_updates)

    def show_library_page(self):
        """Переключение на главную страницу библиотеки."""
        self.stack.setCurrentWidget(self.library_page)

    def init_ui(self):
        # Проверьте правильность импорта
        try:
            from app.modules.ui.game_library import GameLibrary
        except ImportError:
            from modules.ui.game_library import GameLibrary
        
        games_dir = os.path.join(BASE_DIR, "users", "games")
        print(f"[MAIN] Games directory: {games_dir}")
        print(f"[MAIN] Directory exists: {os.path.exists(games_dir)}")
        
        self.library_page = GameLibrary(
            games_dir=games_dir,
            parent=self
        )
        self.stack.addWidget(self.library_page)
        games_dir = os.path.join(BASE_DIR, "users", "games")

        # Регистрируем виджеты для каждого слоя
        self.register_navigation_widgets()

        # Начальное состояние
        self.stack.setCurrentIndex(0)
        self.current_layer = NavigationLayer.MAIN
        self.update_hints()

    def apply_theme(self, theme_name):
        try:
            # Загружаем стили из файла
            with open(THEME_FILE, 'r', encoding='utf-8') as f:
                stylesheet = f.read()

            # Устанавливаем свойство класса
            self.setProperty("class", f"{theme_name}-theme")

            # Применяем стили
            self.setStyleSheet(stylesheet)

            # Обновляем стили всех виджетов
            for widget in self.findChildren(QWidget):
                if widget != self:  # Исключаем главное окно
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                    widget.update()
        except Exception as e:
            logger.error(f"Ошибка применения темы: {e}")

    def register_navigation_widgets(self):
        """Регистрируем виджеты для управления в каждом слое"""
        # Для главного слоя: поисковик и кнопка «Добавить игру» на обоих экранах
        main_widgets = []

        # Добавляем виджеты из placeholder экрана
        if hasattr(self.library_page, 'search_input_ph'):
            main_widgets.append(self.library_page.search_input_ph)
        if hasattr(self.library_page, 'add_btn_ph'):
            main_widgets.append(self.library_page.add_btn_ph)

        # Добавляем виджеты из grid экрана
        if hasattr(self.library_page, 'search_input_grid'):
            main_widgets.append(self.library_page.search_input_grid)

        self.navigation_controller.register_widgets(
            NavigationLayer.MAIN,
            main_widgets
        )

        # Для слоя настроек: все плитки настроек
        self.navigation_controller.register_widgets(
            NavigationLayer.SETTINGS,
            self.settings_tiles
        )

        # Устанавливаем действия для плиток настроек
        for tile in self.settings_tiles:
            if hasattr(tile, 'action'):
                tile.activated = tile.action

        # Настройки чувствительности
        self.axis_threshold = 0.7
        self.last_axis_event = time.time()

    def handle_gamepad_input(self, button):
        """Обработка нажатий кнопок геймпада"""
        # Маппинг кнопок на действия
        action_map = {
            'A': 'A',
            'B': 'B',
            'X': 'X',
            'Y': 'Y',
            'DPAD_UP': 'UP',
            'DPAD_DOWN': 'DOWN',
            'DPAD_LEFT': 'LEFT',
            'DPAD_RIGHT': 'RIGHT',
            'SELECT': 'SELECT',
            'START': 'START'
        }

        if button in action_map:
            # Создаем искусственное событие клавиатуры
            key = self.navigation_controller.key_mapping.get(action_map[button])
            if key:
                event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
                QApplication.postEvent(self, event)

        # Специальные действия
        if button == 'SELECT':
            self.toggle_settings()
        elif button == 'START' and self.current_layer == NavigationLayer.MAIN:
            self.launch_selected_game()
        # Кнопка "Назад"
        elif button == 'B':
            if self.current_layer == NavigationLayer.SETTINGS:
                self.switch_layer(NavigationLayer.MAIN)
            elif self.current_layer == NavigationLayer.MAIN:
                self.confirm_exit()

    def toggle_settings(self):
        """Переключение между основным экраном и настройками"""
        if self.current_layer == NavigationLayer.MAIN:
            self.switch_layer(NavigationLayer.SETTINGS)
        else:
            self.switch_layer(NavigationLayer.MAIN)

    def launch_selected_game(self):
        """Запуск выбранной игры"""
        if self.navigation_controller.current_layer == NavigationLayer.MAIN:
            widgets = self.navigation_controller.layer_widgets[NavigationLayer.MAIN]
            idx = self.navigation_controller.focus_index[NavigationLayer.MAIN]
            if 0 <= idx < len(widgets):
                self.launch_game(self.games[idx])

    def handle_axis_movement(self, axis, value):
        """Обработка движения осей (для навигации в меню)"""
        # Защита от слишком частых событий
        if time.time() - self.last_axis_event < 0.2:
            return

        action = None
        if axis == 'LEFT_Y' and value < -self.axis_threshold: action = 'UP'
        elif axis == 'LEFT_Y' and value > self.axis_threshold: action = 'DOWN'
        elif axis == 'LEFT_X' and value < -self.axis_threshold: action = 'LEFT'
        elif axis == 'LEFT_X' and value > self.axis_threshold: action = 'RIGHT'

        if action:
            key = self.navigation_controller.key_mapping.get(action)
            if key:
                event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
                QApplication.postEvent(self, event)
                self.last_axis_event = time.time()

    def closeEvent(self, event):
        """Обработчик закрытия окна - завершаем все процессы"""
        logger.info("Завершение приложения...")
        try:
            # Завершаем процесс обновления, если он запущен
            if self.updater_process and self.updater_process.poll() is None:
                try:
                    # Отправляем SIGTERM для корректного завершения
                    os.kill(self.updater_process.pid, signal.SIGTERM)
                    logger.info("Отправлен SIGTERM процессу обновления")

                    # Даем время на завершение
                    time.sleep(0.5)

                    # Если процесс все еще работает, отправляем SIGKILL
                    if self.updater_process.poll() is None:
                        os.kill(self.updater_process.pid, signal.SIGKILL)
                        logger.warning("Отправлен SIGKILL процессу обновления")
                except ProcessLookupError:
                    pass  # Процесс уже завершен
                except Exception as e:
                    logger.error(f"Ошибка завершения процесса обновления: {e}")

            # Останавливаем проверку обновлений
            self.updater.stop_checking()

            # Отключаем все сигналы
            try:
                theme_manager.theme_changed.disconnect(self.apply_theme)
                self.updater.update_available.disconnect(
                    self.on_update_available)
                self.navigation_controller.layer_changed.disconnect(
                    self.switch_layer)
            except TypeError:
                pass

            # Уничтожаем дочерние объекты
            self.updater.deleteLater()
            self.navigation_controller.deleteLater()

        except Exception as e:
            logger.error(f"Ошибка при завершении: {e}")

        # Принудительно завершаем приложение
        logger.info("Принудительное завершение приложения")
        if hasattr(self, 'gamepad_manager'):
            self.gamepad_manager.stop()

    def confirm_exit(self, event=None):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Выход")
        dlg.setText("Вы хотите закрыть ArcadeDeck?")
        # Убираем стандартные кнопки и добавляем свои
        dlg.setStandardButtons(QMessageBox.StandardButton.NoButton)
        yes_btn = dlg.addButton("Да", QMessageBox.ButtonRole.AcceptRole)
        no_btn  = dlg.addButton("Нет", QMessageBox.ButtonRole.RejectRole)
        dlg.exec()

        if dlg.clickedButton() is yes_btn:
            self.close()

    def create_settings_layer(self):
        """Создаёт слой настроек с плитками и областью деталей"""
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(15, 15, 15, 15)
        settings_layout.setSpacing(15)

        # Карусель плиток
        self.carousel_container = QWidget()
        self.carousel_layout = QHBoxLayout(self.carousel_container)
        self.carousel_layout.setContentsMargins(0, 0, 0, 0)
        self.carousel_layout.setSpacing(15)

        # Список разделов
        settings_items = [
            {"name": "Общие",                  "icon": ""},
            {"name": "Управление эмуляторами", "icon": ""},
            {"name": "Внешний вид",           "icon": ""},
            {"name": "Сетевое подключение",    "icon": ""},
            {"name": "Инструменты отладки",    "icon": ""},
            {"name": "О ArcadeDeck",            "icon": ""},
            {"name": "Выход",                  "icon": ""}
        ]

        self._settings_index = {}
        self.settings_detail_stack = QStackedWidget()

        for idx, item in enumerate(settings_items):
            name = item["name"]
            icon = item.get("icon", "")

            # 1) создаём страницу
            if name == "Внешний вид":
                page = AppearanceSettingsPage(self)
            elif name == "Инструменты отладки":
                page = DevSettingsPage(self, log_path=log_file)
            elif name == "О ArcadeDeck":
                page = AboutPage(self)
            else:
                # пустая заглушка для остальных (включая «Общие», «Управление эмуляторами», «Сетевое подключение» и «Выход»)
                page = QWidget()
                pl = QVBoxLayout(page)
                lbl = QLabel(f"Раздел '{name}' в разработке")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setFont(QFont("Arial", 14))
                pl.addWidget(lbl)
            self.settings_detail_stack.addWidget(page)

            # 2) выбираем handler
            if name == "Выход":
                handler = self.confirm_exit
            else:
                handler = self._make_tile_click_handler(idx)

            # 3) создаём и регистрируем плитку
            tile = self.create_settings_tile(name, icon_path=icon, action=handler)
            self.settings_tiles.append(tile)
            self.carousel_layout.addWidget(tile)
            self._settings_index[name] = idx

        # обёртка карусели
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setWidget(self.carousel_container)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        settings_layout.addWidget(self.scroll_area)

        # область деталей
        settings_layout.addWidget(self.settings_detail_stack, 1)
        self.stack.addWidget(settings_widget)

    def _make_tile_click_handler(self, index):
        """Возвращает функцию-обработчик клика, которая переключает стек"""
        def handler(event=None):
            # При клике на плитку переключаем детальную область
            self.settings_detail_stack.setCurrentIndex(index)
        return handler

    def create_settings_tile(self, name, icon_path, action):
        """Создает плитку настроек"""
        tile = QFrame()
        tile.setObjectName("SettingsTile")
        tile.setMinimumSize(200, 150)
        tile.setMaximumSize(400, 220)

        tile_layout = QVBoxLayout(tile)
        tile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if icon_path:
            icon_label = QLabel()
            icon_pixmap = QPixmap(icon_path)
            icon_label.setPixmap(icon_pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio))
            tile_layout.addWidget(icon_label)

        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setFont(QFont("Arial", 10))
        tile_layout.addWidget(name_label)

        # Привязываем действие по клику (если задано)
        if action:
            tile.action = action
            tile.mousePressEvent = lambda event: action()

        return tile

    def switch_layer(self, new_layer):
        """Переключает между слоями"""
        self.current_layer = new_layer

        if new_layer == NavigationLayer.MAIN:
            self.stack.setCurrentIndex(0)
        elif new_layer == NavigationLayer.SETTINGS:
            self.stack.setCurrentIndex(1)
            self.update_hints()

    def update_hints(self):
        """Обновляет подсказки в зависимости от текущего слоя"""
        if self.current_layer == NavigationLayer.MAIN:
            hints = "↓: Настройки  |  A: Запустить  |  Y: Поиск  |  B: Назад"
        elif self.current_layer == NavigationLayer.SETTINGS:
            hints = "↑: Главный экран  |  ←/→: Навигация  |  A: Выбрать  |  B: Назад"
        else:  # SEARCH
            hints = "B: Назад  |  Enter: Поиск  |  Стрелки: Навигация"

        self.hint_label.setText(hints)

    def keyPressEvent(self, event):
        """Обработка клавиш через навигационный контроллер"""
        if self.navigation_controller.handle_key_event(event):
            event.accept()
        else:
            super().keyPressEvent(event)

    def launch_game(self, game_data):
        """Запускает выбранную игру через launcher_path"""
        try:
            logger.info(f"Запуск игры: {game_data.get('title', 'Unknown')}")
            
            # Загружаем информацию об установленных играх
            installed_games_file = Path(BASE_DIR) / 'users' / 'installed_games.json'
            if not installed_games_file.exists():
                QMessageBox.warning(self, "Ошибка", "Файл installed_games.json не найден")
                return
                
            with open(installed_games_file, 'r', encoding='utf-8') as f:
                installed_games = json.load(f)
            
            game_id = game_data.get('id')
            if game_id not in installed_games:
                QMessageBox.warning(self, "Ошибка", "Игра не установлена")
                return
                
            game_info = installed_games[game_id]
            launcher_path = game_info.get('launcher_path')
            
            if not launcher_path or not os.path.exists(launcher_path):
                QMessageBox.warning(self, "Ошибка", f"Лаунчер не найден: {launcher_path}")
                return
                
            # Запускаем скрипт
            import subprocess
            subprocess.Popen(['bash', launcher_path], start_new_session=True)
            logger.info(f"✅ Запущена игра: {game_data.get('title')}")
            
        except Exception as e:
            logger.error(f"Ошибка запуска игры: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить игру: {e}")

    def show_game_info(self, game):
        """
        Показать страницу с информацией об игре.
        """
        # 1. Обработка сброса поиска (можно оставить, это не зависит от логики игры)
        try:
            lib_page = getattr(self, "library_page", None) or getattr(self, "game_library_page", None)
            if lib_page and hasattr(lib_page, "search_input_grid"):
                lib_page.search_input_grid.reset_search()
        except Exception:
            pass

        # 2. Быстрая валидация
        if not game:
            QMessageBox.warning(self, "Ошибка", "Нет данных об игре.")
            return

        # 3. Передаем данные напрямую в game_info_page
        try:
            self.game_info_page.load_game(game)
        except Exception as e:
            logger.exception(f"Не удалось вызвать load_game у game_info_page: {e}")
            QMessageBox.critical(self, "Ошибка", "Не удалось отобразить страницу информации об игре.")
            return

        # 4. Покажем страницу
        try:
            if hasattr(self, "stacked_widget"):
                self.stacked_widget.setCurrentWidget(self.game_info_page)
            elif hasattr(self, "stack"):
                self.stack.setCurrentWidget(self.game_info_page)
            else:
                self.game_info_page.show()
        except Exception as e:
            logger.exception(f"Ошибка при отображении game_info_page: {e}")

    def on_game_action(self, game_data, is_installed):
        if is_installed:
            self.launch_game(game_data)
        else:
            self.install_game(game_data)

    def install_game(self, game_data):
        """Установка выбранной игры"""
        logger.info(f"Начало установки игры: {game_data['title']}")

        # Создаем и показываем диалог установки
        try:
            installer_dialog = InstallDialog(
                game_data=game_data,
                project_root=Path(BASE_DIR),
                parent=self
            )
            # Просто показываем диалог, не подключаем никаких сигналов
            installer_dialog.exec()
            
            # После закрытия диалога обновляем статус
            self._update_game_status_after_installation(game_data)
            
        except Exception as e:
            logger.error(f"Не удалось запустить диалог установки: {e}")
            QMessageBox.critical(self, "Ошибка установки", f"Не удалось начать установку: {e}")

    def _update_game_status_after_installation(self, game_data):
        """Обновляет статус игры после установки"""
        try:
            game_id = game_data.get('id')
            
            # Проверяем, установлена ли игра
            installed_games_file = Path(BASE_DIR) / 'users' / 'installed_games.json'
            is_installed = False
            
            if installed_games_file.exists():
                with open(installed_games_file, 'r', encoding='utf-8') as f:
                    installed_games = json.load(f)
                    is_installed = game_id in installed_games
            
            # Обновляем GameInfoPage если она открыта для этой игры
            if (hasattr(self, 'game_info_page') and 
                self.game_info_page and 
                self.game_info_page.game_data.get('id') == game_id):
                self.game_info_page.update_installation_status(is_installed)
            
            # Обновляем библиотеку
            if hasattr(self, 'library_page') and self.library_page:
                self.library_page.load_games()
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса игры: {e}")

    def on_installation_complete(self, game_data):
        """Обработчик завершения установки игры"""
        try:
            game_id = game_data.get('id')
            logger.info(f"Установка завершена для игры: {game_data.get('title')}")
            
            # Обновляем статус игры в GameInfoPage если она открыта
            if (hasattr(self, 'game_info_page') and 
                self.game_info_page.game_data.get('id') == game_id):
                self.game_info_page.update_installation_status(True)
            
            # Обновляем библиотеку игр
            if hasattr(self, 'library_page'):
                self.library_page.load_games()
                logger.info("Библиотека игр обновлена")
            
            # Показываем сообщение об успехе
            QMessageBox.information(
                self,
                "Установка завершена",
                f"Игра '{game_data.get('title')}' успешно установлена!",
                QMessageBox.StandardButton.Ok
            )
            
        except Exception as e:
            logger.error(f"Ошибка при обработке завершения установки: {e}")
            QMessageBox.warning(
                self,
                "Ошибка",
                f"Игра установлена, но произошла ошибка при обновлении интерфейса: {e}",
                QMessageBox.StandardButton.Ok
            )

    def on_update_available(self, update_info):
        if not self.isVisible():
            logger.warning("Главное окно закрыто, игнорируем обновление")
            return

        # Защита от отсутствия ключей в словаре
        latest_version = update_info.get('version')
        changelog = update_info.get('release', {}).get("body", "Нет информации об изменениях")
        download_url = update_info.get('download_url')
        asset_name = update_info.get('asset_name')

        # Проверяем, что все данные для обновления получены
        if not all([latest_version, download_url, asset_name]):
            logger.error(f"Неполные данные об обновлении: {update_info}")
            QMessageBox.warning(self, "Ошибка обновления", "Не удалось получить полную информацию о последней версии.")
            return

        try:
            # Показываем диалог с обновлением
            dialog = UpdateDialog(
                APP_VERSION,
                latest_version,
                changelog,
                download_url,
                self.install_dir,
                asset_name,
                self  # Указываем родительское окно
            )
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.exec()
        finally:
            # Фокус возвращается на главное окно
            self.activateWindow()
            self.raise_()


def check_and_show_updates(dark_theme):
    """Запускает внешний updater и возвращает объект процесса"""
    try:
        current_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        updater_path = os.path.join(BASE_DIR, "app", "updater.py")
        theme_flag = "--dark" if dark_theme else "--light"

        process = subprocess.Popen(  # Сохраняем объект процесса
            [sys.executable, updater_path, theme_flag],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return process
    except Exception as e:
        logger.error(f"Ошибка запуска updater: {e}")
        return None


# Точка входа в приложение
if __name__ == "__main__":

    # Проверка на единственный экземпляр
    lock_result, existing_pid = enforce_single_instance()

    if not lock_result:
        if existing_pid:
            # Создаем временное приложение для диалога
            temp_app = QApplication(sys.argv)

            # Применяем текущую тему (если возможно)
            try:
                # Загружаем стили из файла темы
                with open(THEME_FILE, 'r', encoding='utf-8') as f:
                    stylesheet = f.read()
                    temp_app.setStyleSheet(stylesheet)
            except Exception as e:
                logger.error(f"Ошибка загрузки стилей для диалога: {e}")

            # Создаем диалоговое окно
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Программа уже запущена")
            msg_box.setText(
                "ArcadeDeck уже запущен! Проверьте панель задач.\n\n"
                "Если программа не отвечает, вы можете принудительно перезапустить ее."
            )

            # Добавляем кнопки
            restart_button = msg_box.addButton("Перезапустить ArcadeDeck", QMessageBox.ButtonRole.ActionRole)
            ok_button = msg_box.addButton("ОК", QMessageBox.ButtonRole.AcceptRole)
            msg_box.setDefaultButton(ok_button)

            # Показываем диалог
            msg_box.exec()

            # Обработка выбора
            if msg_box.clickedButton() == restart_button:
                logger.info(f"Пользователь выбрал перезапуск. Завершаем процесс {existing_pid}...")
                try:
                    # Посылаем сигнал SIGTERM для корректного завершения
                    os.kill(existing_pid, signal.SIGTERM)
                    # Ждем 2 секунды, чтобы процесс успел завершиться
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Ошибка при завершении процесса: {e}")

                # Определяем путь к скрипту ArcadeDeck.sh (в корне проекта)
                # BASE_DIR - это директория проекта
                project_root = os.path.dirname(BASE_DIR)
                script_path = os.path.join(project_root, "ArcadeDeck.sh")

                if not os.path.exists(script_path):
                    logger.error(f"Скрипт запуска не найден: {script_path}")
                    # Покажем сообщение об ошибке?
                    error_msg = QMessageBox()
                    error_msg.setIcon(QMessageBox.Icon.Critical)
                    error_msg.setText("Ошибка перезапуска")
                    error_msg.setInformativeText(f"Файл запуска не найден: {script_path}")
                    error_msg.exec()
                else:
                    # Запускаем новый экземпляр программы через скрипт
                    subprocess.Popen([script_path], start_new_session=True)

            # Завершаем временное приложение и выходим
            sys.exit(0)
        else:
            logger.error("Ошибка блокировки без указания PID")
            sys.exit(1)

    logger.info("Запуск ArcadeDeck")
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

        # Инициализация настроек ДО создания QApplication
        app_settings._ensure_settings()
        theme_name = app_settings.get_theme()

        # Создаем приложение ОДИН РАЗ
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        # Применяем стиль и тему
        app.setStyleSheet(global_stylesheet)
        app.setProperty("class", f"{theme_name}-theme")

        # Инициализируем менеджер тем
        theme_manager.set_theme(theme_name)

        # Загружаем контент
        global GUIDES, GAMES
        GUIDES, GAMES = load_content()

        welcome_shown = app_settings.get_welcome_shown()
        dark_theme = (theme_name == 'dark')

        if not welcome_shown:
            logger.info("Показываем приветственное окно")
            welcome = WelcomeWizard()
            welcome.center_on_screen()
            result = welcome.exec()

            # Обновляем настройки после мастера
            app_settings.set_welcome_shown(True)
            new_theme = app_settings.get_theme()

            # Обновляем тему приложения
            theme_manager.set_theme(new_theme)
            app.setProperty("class", f"{new_theme}-theme")
            dark_theme = (new_theme == 'dark')

        window = MainWindow()
        window.showMaximized()

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
