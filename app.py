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
import fcntl
import atexit
import signal
import errno
import pygame

# Настройка логирования ДО проверки экземпляра
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

# Проверка на единственный экземпляр
def enforce_single_instance():
    """Обеспечивает запуск только одного экземпляра приложения"""
    lock_file = os.path.join(os.path.expanduser("~"), ".pixeldeck.lock")
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
    QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QEvent
from PyQt6.QtGui import QIcon, QFont, QPixmap, QKeyEvent

# Импорт из нашего приложения
from core import APP_VERSION, CONTENT_DIR, STYLES_DIR, THEME_FILE, GUIDES_JSON_PATH, GAME_LIST_GUIDE_JSON_PATH
from settings import app_settings
from welcome import WelcomeWizard
from app.ui_assets.theme_manager import theme_manager
from updater import Updater, UpdateDialog  # Импортируем Updater и UpdateDialog
from navigation import NavigationController  # Импортируем NavigationController
from navigation import NavigationLayer

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

class GamepadManager(QObject):
    """Менеджер обработки ввода геймпада через Pygame"""
    button_pressed = pyqtSignal(str)  # Сигнал для нажатий кнопок
    axis_moved = pyqtSignal(str, float)  # Сигнал для движения осей

    def __init__(self, parent=None):
        super().__init__(parent)
        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        self.last_button_press = {}  # Инициализируем словарь для отслеживания нажатий
        self.button_cooldown = 5.0  # Задержка между нажатиями в секундах
        self.axis_cooldown = 0.1   # Задержка для осей

        # Инициализация геймпада
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            logger.info(f"Геймпад подключен: {self.joystick.get_name()}")

        # Таймер для опроса геймпада
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_gamepad)
        self.timer.start(30)  # ~33 FPS

    def poll_gamepad(self):
        """Опрос состояния геймпада с защитой от повторных нажатий"""
        try:
            pygame.event.pump()
            if not self.joystick:
                return

            current_time = time.time()
            button_map = {
                0: 'A', 1: 'B', 2: 'X', 3: 'Y',
                4: 'L1', 5: 'R1', 6: 'SELECT', 7: 'START'
            }

            # Обработка кнопок с антиспамом
            for btn_index, btn_name in button_map.items():
                if self.joystick.get_button(btn_index):
                    last_press = self.last_button_press.get(btn_name, 0)
                    if current_time - last_press > self.button_cooldown:
                        self.last_button_press[btn_name] = current_time
                        self.button_pressed.emit(btn_name)
                        logger.debug(f"Кнопка {btn_name} нажата")
                else:
                    # Сбрасываем при отпускании кнопки
                    if btn_name in self.last_button_press:
                        del self.last_button_press[btn_name]

            # Обработка осей с deadzone
            axis_map = {
                0: ('LEFT_X', 0.15),
                1: ('LEFT_Y', 0.15),
                2: ('RIGHT_X', 0.15),
                3: ('RIGHT_Y', 0.15),
                4: ('L2', 0.05),
                5: ('R2', 0.05)
            }

            for axis_index, (axis_name, deadzone) in axis_map.items():
                value = self.joystick.get_axis(axis_index)
                if abs(value) > deadzone:
                    self.axis_moved.emit(axis_name, value)

            # Обработка D-PAD
            if self.joystick.get_numhats() > 0:
                hat = self.joystick.get_hat(0)
                if hat[1] > 0: self.button_pressed.emit('DPAD_UP')
                if hat[1] < 0: self.button_pressed.emit('DPAD_DOWN')
                if hat[0] < 0: self.button_pressed.emit('DPAD_LEFT')
                if hat[0] > 0: self.button_pressed.emit('DPAD_RIGHT')

        except Exception as e:
            logger.error(f"Ошибка в poll_gamepad: {str(e)}")

    def stop(self):
        """Остановка менеджера"""
        self.timer.stop()
        pygame.quit()

class MainWindow(QMainWindow):
    """Главное окно приложения с двухслойным интерфейсом"""

    def __init__(self):
        super().__init__()
        self.install_dir = BASE_DIR  # Определяем директорию установки

        # Инициализация процесса обновления
        self.updater_process = None
        # Инициализируем список для плиток настроек
        self.settings_tiles = []

        # Настройка окна
        self.setWindowTitle("PixelDeck")
        self.setGeometry(400, 300, 1280, 800)
        self.setMinimumSize(800, 600)
        self.current_layer = 0  # 0 = основной слой, 1 = слой настроек

        # Устанавливаем иконку приложения
        self.setWindowIcon(QIcon.fromTheme("system-search"))

        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной вертикальный layout (теперь это атрибут класса)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(10)

        # --- ВЕРХНЯЯ ЧАСТЬ (поиск) ---
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 10)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Введите название игры или гайда...")
        self.search_field.textChanged.connect(self.search_content)
        self.search_field.setMinimumHeight(40)
        search_layout.addWidget(self.search_field)

        self.main_layout.addLayout(search_layout)

        # --- СТЕК СЛОЕВ ---
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack, 1)

        # --- НИЖНЯЯ ЧАСТЬ (подсказки) ---
        hints_layout = QHBoxLayout()
        self.hint_label = QLabel("B: Назад")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hints_layout.addWidget(self.hint_label)

        self.main_layout.addLayout(hints_layout)

        # --- СОЗДАЕМ СЛОИ ---
        self.create_main_layer()  # Слой 0: Основной
        self.create_settings_layer()  # Слой 1: Настройки

        # Начальное состояние
        self.stack.setCurrentIndex(0)
        self.update_hints()

        # Применяем текущую тему
        self.apply_theme(theme_manager.current_theme)

        # Подписываемся на изменения темы
        theme_manager.theme_changed.connect(self.apply_theme)

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

        # Инициализируем Updater
        self.updater = Updater(self)
        self.updater.update_available.connect(self.on_update_available)

        # Запускаем проверку обновлений
        QTimer.singleShot(1000, self.updater.check_for_updates)  # Задержка для стабильности

        # Инициализируем контроллер навигации
        self.navigation_controller = NavigationController(self)
        self.navigation_controller.layer_changed.connect(self.switch_layer)
        
        # Регистрируем виджеты для каждого слоя
        self.register_navigation_widgets()

    def apply_theme(self, theme_name):
        """Применяет указанную тему к окну и всем дочерним виджетам"""
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
                widget.style().unpolish(widget)
                widget.style().polish(widget)
        except Exception as e:
            logger.error(f"Ошибка применения темы: {e}")

    def register_navigation_widgets(self):
        """Регистрируем виджеты для управления в каждом слое"""
        # Для главного слоя: все игровые плитки
        main_widgets = []
        for i in range(self.games_grid.count()):
            widget = self.games_grid.itemAt(i).widget()
            if widget:
                widget.activated = lambda game=self.games[i]: self.launch_game(game)
                main_widgets.append(widget)
        
        self.navigation_controller.register_widgets(
            NavigationLayer.MAIN, 
            main_widgets
        )
        
        # Для слоя настроек: все плитки настроек
        self.navigation_controller.register_widgets(
            NavigationLayer.SETTINGS, 
            self.settings_tiles
        )
        
        # Для слоя поиска: поле поиска и список результатов
        self.navigation_controller.register_widgets(
            NavigationLayer.SEARCH, 
            [self.search_field, self.search_results_list]
        )
        
        # Устанавливаем действия для плиток настроек
        for tile in self.settings_tiles:
            if hasattr(tile, 'action'):
                tile.activated = tile.action

        # Инициализация менеджера геймпада
        self.gamepad_manager = GamepadManager(self)
        self.gamepad_manager.button_pressed.connect(self.handle_gamepad_input)
        self.gamepad_manager.axis_moved.connect(self.handle_axis_movement)

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
                self.updater.update_available.disconnect(self.on_update_available)
                self.navigation_controller.layer_changed.disconnect(self.switch_layer)
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

        self.last_game_label.setStyleSheet("background-color: transparent;")

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

        self.last_game_time.setStyleSheet("background-color: transparent;")

        last_game_layout.addWidget(self.last_game_time)

        main_layout.addWidget(last_game_frame, 1)  # Растягиваем

        # --- БИБЛИОТЕКА ИГР (сетка плиток) ---
        games_label = QLabel("Библиотека игр")
        games_label.setFont(QFont("Arial", 14))
        main_layout.addWidget(games_label)

        # Заполняем демо-играми
        games = [
            {"name": "Cyberpunk 2077", "system": "PC"},
            {"name": "God of War", "system": "PS4"},
            {"name": "Hollow Knight", "system": "Switch"},
            {"name": "Elden Ring", "system": "PC"},
            {"name": "Stardew Valley", "system": "PC"},
            {"name": "The Last of Us", "system": "PS4"}
        ]

        # Сохраняем список игр для последующего использования
        self.games = games

        # Сетка игр
        self.games_grid = QGridLayout()
        self.games_grid.setSpacing(15)

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

            name_label.setStyleSheet("background-color: transparent;")

            game_layout.addWidget(name_label)

            system_label = QLabel(game["system"])
            system_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            system_label.setFont(QFont("Arial", 8))

            system_label.setStyleSheet("background-color: transparent;")

            game_layout.addWidget(system_label)

            self.games_grid.addWidget(game_frame, row, col)

        games_container = QWidget()
        games_container.setLayout(self.games_grid)
        main_layout.addWidget(games_container, 3)  # Больше места для игр

        self.stack.addWidget(main_widget)

    def create_settings_layer(self):
        """Создает слой настроек в виде карусели плиток"""
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)

        # Отступы и расстояние
        settings_layout.setContentsMargins(15, 15, 15, 15)
        settings_layout.setSpacing(15)

        # Контейнер для карусели с фиксированной шириной
        self.carousel_container = QWidget()
        self.carousel_layout = QHBoxLayout(self.carousel_container)
        self.carousel_layout.setContentsMargins(0, 0, 0, 0)
        self.carousel_layout.setSpacing(15)  # Было 30 - уменьшили расстояние между плитками

        # Элементы настроек
        settings_items = [
            {"name": "Общие", "icon": "settings.png", "action": self.open_system_settings},
            {"name": "Управление эмуляторами", "icon": "emulator.png", "action": self.open_appearance_settings},
            {"name": "Внешний вид", "icon": "appearance.png", "action": self.open_emulator_settings},
            {"name": "Сетевое подключение", "icon": "network.png", "action": self.open_network_settings},
            {"name": "Инструменты отладки", "icon": "update.png", "action": self.open_tools_settings},
            {"name": "О PixelDeck", "icon": "tools.png", "action": self.open_about_settings},
            {"name": "Выход", "icon": "exit.png", "action": self.close_app}
            ]

        # Сохраняем действия в плитках
        for i, item in enumerate(settings_items):
            tile = self.create_settings_tile(item["name"], item["icon"], item["action"])
            tile.action = item["action"]  # Сохраняем действие для активации
            self.settings_tiles.append(tile)
            self.carousel_layout.addWidget(tile)

        # Устанавливаем фиксированную ширину контейнера
        self.carousel_container.setFixedWidth(len(settings_items) * 300)  # 270 + spacing

        # Настройка скролла
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)  # Отключаем автоматическое изменение размера
        self.scroll_area.setWidget(self.carousel_container)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        settings_layout.addWidget(self.scroll_area, 1)
        self.stack.addWidget(settings_widget)

    def create_settings_tile(self, name, icon_path, action):
        """Создает плитку настроек"""
        tile = QFrame()
        tile.setObjectName("SettingsTile")
        tile.setMinimumSize(200, 150)
        tile.setMaximumSize(400, 220)

        tile_layout = QVBoxLayout(tile)
        tile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel()
        icon_pixmap = QPixmap(icon_path)
        icon_label.setPixmap(icon_pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio))
        tile_layout.addWidget(icon_label)

        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setFont(QFont("Arial", 10))
        tile_layout.addWidget(name_label)

        # Сохраняем действие для активации через навигацию
        tile.action = action
        tile.mousePressEvent = lambda event: action()

        return tile

        # Добавляем заглушки для всех плиток настроек
    def open_emulator_settings(self):
        QMessageBox.information(
            self,
            "Управление эмуляторами",
            "Раздел управления эмуляторами в разработке",
            QMessageBox.StandardButton.Ok
        )

    def open_appearance_settings(self):
        QMessageBox.information(
            self,
            "Внешний вид",
            "Раздел настроек внешнего вида в разработке",
            QMessageBox.StandardButton.Ok
        )

    def open_network_settings(self):
        QMessageBox.information(
            self,
            "Сетевое подключение",
            "Раздел сетевых настроек в разработке",
            QMessageBox.StandardButton.Ok
        )

    def open_tools_settings(self):
        QMessageBox.information(
            self,
            "Инструменты отладки",
            "Раздел инструментов отладки в разработке",
            QMessageBox.StandardButton.Ok
        )

    def open_about_settings(self):
        QMessageBox.information(
            self,
            "О PixelDeck",
            "Версия програмыы — 0.1.75-beta",
            QMessageBox.StandardButton.Ok
        )

    def open_system_settings(self):
        """Открывает окно системных настроек"""
        # Заменяем на временное решение
        QMessageBox.information(
            self,
            "Общие",
            "Раздел общих настроек в разработке",
            QMessageBox.StandardButton.Ok
        )

    def close_app(self):
        """Закрывает приложение (обработчик кнопки Выход)"""
        self.close()  # Вызывает closeEvent

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

    def switch_layer(self, new_layer):
        """Переключает между слоями"""
        if new_layer == NavigationLayer.MAIN:
            self.stack.setCurrentIndex(0)
        elif new_layer == NavigationLayer.SETTINGS:
            self.stack.setCurrentIndex(1)
        elif new_layer == NavigationLayer.SEARCH:
            # Поиск поверх всех слоев
            self.search_field.setFocus()
            
        self.update_hints()

    def update_hints(self):
        """Обновляет подсказки в зависимости от текущего слоя"""
        if self.current_layer == 0:  # MAIN
            hints = "↓: Настройки  |  A: Запустить  |  Y: Поиск  |  B: Назад"
        elif self.current_layer == 1:  # SETTINGS
            hints = "↑: Главный экран  |  ←/→: Навигация  |  A: Выбрать  |  B: Назад"
        else:  # SEARCH
            hints = "B: Назад  |  Enter: Поиск  |  Стрелки: Навигация"

        self.hint_label.setText(hints)

    def keyPressEvent(self, event):
        """Обработка клавиш через навигационный контроллер"""
        if self.navigation_controller.handle_key_event(event):
            event.accept()
        else:
            # Передаем события ввода в поле поиска
            if self.navigation_controller.current_layer == NavigationLayer.SEARCH:
                self.search_field.keyPressEvent(event)
            else:
                super().keyPressEvent(event)

    def launch_game(self, game):
        """Запускает выбранную игру"""
        logger.info(f"Запуск игры: {game['name']}")
        QMessageBox.information(
            self,
            "Запуск игры",
            f"Запускаем {game['name']} на {game['system']}",
            QMessageBox.StandardButton.Ok
        )

    def on_update_available(self, update_info):
        if not self.isVisible():
            logger.warning("Главное окно закрыто, игнорируем обновление")
            return

        latest_version = update_info['version']
        changelog = update_info['release'].get("body", "Нет информации об изменениях")
        download_url = update_info['download_url']
        asset_name = update_info['asset_name']
        
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
    """Запускает внешний updater и возвращает объект процесса"""
    try:
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
                "PixelDeck уже запущен! Проверьте панель задач.\n\n"
                "Если программа не отвечает, вы можете принудительно перезапустить ее."
            )
            
            # Добавляем кнопки
            restart_button = msg_box.addButton("Перезапустить PixelDeck", QMessageBox.ButtonRole.ActionRole)
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
                
                # Определяем путь к скрипту PixelDeck.sh (в корне проекта)
                # BASE_DIR - это директория, в которой находится app.py (т.е. app/)
                project_root = os.path.dirname(BASE_DIR)
                script_path = os.path.join(project_root, "PixelDeck.sh")
                
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
