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

from core import APP_VERSION, STYLES_DIR, THEME_FILE
from settings import app_settings
from app.welcome import WelcomeWizard
from app.ui_assets.theme_manager import theme_manager
from updater import Updater, UpdateDialog  # Импортируем Updater и UpdateDialog
from navigation import NavigationController, NavigationLayer
from app.modules.ui.game_info_page import GameInfoPage
from app.modules.ui.search_overlay import SearchOverlay
from app.modules.ui.settings_page import SettingsPage
from app.modules.module_logic.game_scanner import (
    is_game_installed,
    get_installed_games
)
from app.modules.module_logic.game_data_manager import get_game_data_manager, set_game_data_manager

# Модули настроек
from app.modules.settings_plugins.about_settings import AboutPage
from modules.settings_plugins.general_settings import GeneralSettingsPage
from modules.settings_plugins.appearance_settings import AppearanceSettingsPage
from modules.settings_plugins.dev_settings import DevSettingsPage

# Импорт пути игровых данных
from core import get_users_path

class MainWindow(QMainWindow):
    """Главное окно приложения с модульной навигацией"""
    def __init__(self):
        super().__init__()
        self.install_dir = BASE_DIR
        self.updater_process = None

        self.setWindowTitle("ArcadeDeck")
        self.setGeometry(400, 300, 1280, 800)
        self.setMinimumSize(800, 600)

        icon_path = os.path.join(BASE_DIR, "app", "icon.png")
        self.setWindowIcon(QIcon(icon_path))

        # Инициализируем централизованный менеджер данных
        manager = get_game_data_manager(Path(BASE_DIR))
        set_game_data_manager(manager)

        # Основной layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(10)

        # Стек виджетов
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack, 1)

        # Подсказки
        hints_layout = QHBoxLayout()
        self.hint_label = QLabel("B: Назад")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hints_layout.addWidget(self.hint_label)
        self.main_layout.addLayout(hints_layout)

        # Навигационный контроллер
        self.navigation_controller = NavigationController(self)
        self.navigation_controller.set_hint_widget(self.hint_label)
        self.navigation_controller.layer_changed.connect(self.switch_layer)
        self.navigation_controller.button_pressed.connect(self.handle_gamepad_input)

        # Инициализация UI
        self.init_ui()
        self.apply_theme(theme_manager.current_theme)
        theme_manager.theme_changed.connect(self.apply_theme)

        # Проверка обновлений
        self.updater = Updater(self)
        self.updater.update_available.connect(self.on_update_available)
        QTimer.singleShot(1000, self.updater.check_for_updates)

        # Инициализация поиска
        self.setup_search_overlay()

    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        # Страница библиотеки игр
        try:
            from app.modules.ui.game_library import GameLibrary
        except ImportError:
            from modules.ui.game_library import GameLibrary

        games_dir = os.path.join(BASE_DIR, "users", "games")
        self.library_page = GameLibrary(games_dir=games_dir, parent=self)
        self.stack.addWidget(self.library_page)

        # Страница настроек (теперь из отдельного модуля)
        self.settings_page = SettingsPage(parent=self)
        self.stack.addWidget(self.settings_page)

        # Страница информации об игре
        self.game_info_page = GameInfoPage(parent=self)
        self.game_info_page.back_callback = self.show_library_page
        self.game_info_page.action_callback = self.on_game_action
        self.stack.addWidget(self.game_info_page)

        # Регистрация виджетов для навигации
        self.register_navigation_widgets()

        # Начальное состояние
        self.stack.setCurrentIndex(0)
        self.navigation_controller.switch_layer(NavigationLayer.MAIN)

    def setup_search_overlay(self):
        """Настройка оверлея поиска"""
        self.search_overlay = SearchOverlay(self)
        self.search_overlay.setParent(self)
        self.search_overlay.searchClosed.connect(self.on_search_closed)
        self.search_overlay.resultSelected.connect(self.on_search_result_selected)
        self.search_overlay.searchActivated.connect(self.on_search_activated)

    def on_search_closed(self):
        """Обработчик закрытия поиска"""
        self.navigation_controller.search_active = False
        self.navigation_controller.update_hints()

    def on_search_result_selected(self, game_data):
        """Обработчик выбора игры из поиска"""
        # Открытие страницы с нужной игрой!
        self.show_game_info(game_data)

    def on_search_activated(self):
        """Обработчик активации поиска"""
        # Обновляем список игр при каждом открытии
        if hasattr(self, 'library_page'):
            games = self.library_page.all_games
            self.search_overlay.set_game_list(games)

    def show_library_page(self):
        """Переключение на главную страницу библиотеки."""
        self.stack.setCurrentWidget(self.library_page)

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
        """Регистрация виджетов для навигационного контроллера"""
        logger.info("Начало регистрации навигационных виджетов")

        # Главный слой
        main_widgets = []
        if hasattr(self.library_page, 'search_input_ph'):
            main_widgets.append(self.library_page.search_input_ph)
        if hasattr(self.library_page, 'add_btn_ph'):
            main_widgets.append(self.library_page.add_btn_ph)
        if hasattr(self.library_page, 'search_input_grid'):
            main_widgets.append(self.library_page.search_input_grid)

        logger.info(f"Главный слой: {len(main_widgets)} виджетов")
        self.navigation_controller.register_widgets(
            NavigationLayer.MAIN,
            main_widgets
        )

        # Слой настроек
        settings_widgets = self.settings_page.get_tiles()
        logger.info(f"Слой настроек: {len(settings_widgets)} плиток")

        # Находим плитку "Выход" и устанавливаем правильный обработчик
        exit_tile_found = False
        for tile in settings_widgets:
            if tile.name == "Выход":
                tile.action = self.confirm_exit
                exit_tile_found = True
                logger.info("Обработчик выхода установлен для плитки 'Выход'")
                break

        if not exit_tile_found:
            logger.warning("Плитка 'Выход' не найдена!")

        self.navigation_controller.register_widgets(
            NavigationLayer.SETTINGS,
            settings_widgets
        )

        # Слой информации об игре - регистрируем все кнопки
        game_info_widgets = [
            self.game_info_page.action_button,
            self.game_info_page.back_button,
            self.game_info_page.menu_button  # Добавляем кнопку меню
        ]
        logger.info(f"Слой информации об игре: {len(game_info_widgets)} виджетов")

        self.navigation_controller.register_widgets(
            NavigationLayer.GAME_INFO,
            game_info_widgets
        )

        logger.info("Регистрация навигационных виджетов завершена")

    def handle_gamepad_input(self, button):
        """Обработка глобальных действий геймпада"""
        if button == 'SELECT':
            self.toggle_settings()
        elif button == 'START' and self.navigation_controller.current_layer == NavigationLayer.MAIN:
            self.launch_selected_game()
        elif button == 'Y' and self.navigation_controller.current_layer == NavigationLayer.MAIN:
            # Активация поиска по кнопке Y
            self.search_overlay.show_overlay()

    def toggle_settings(self):
        """Переключение между основным экраном и настройками"""
        current_layer = self.navigation_controller.current_layer
        if current_layer == NavigationLayer.MAIN:
            self.navigation_controller.switch_layer(NavigationLayer.SETTINGS)
        else:
            self.navigation_controller.switch_layer(NavigationLayer.MAIN)

    def launch_selected_game(self):
        """Запуск выбранной игры"""
        if self.navigation_controller.current_layer == NavigationLayer.MAIN:
            widgets = self.navigation_controller.layer_widgets[NavigationLayer.MAIN]
            idx = self.navigation_controller.focus_index[NavigationLayer.MAIN]
            if 0 <= idx < len(widgets):
                # Нужно получить данные игры - возможно, нужно доработать
                logger.info("Запуск игры из главного меню")

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

    def confirm_exit(self, event=None):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Выход")
        dlg.setText("Вы хотите закрыть ArcadeDeck?")
        dlg.setStandardButtons(QMessageBox.StandardButton.NoButton)

        yes_btn = dlg.addButton("Да", QMessageBox.ButtonRole.AcceptRole)
        no_btn = dlg.addButton("Нет", QMessageBox.ButtonRole.RejectRole)

        # Устанавливаем фокус на кнопку "Нет" для безопасности
        dlg.setDefaultButton(no_btn)

        # Сохраняем ссылки на кнопки для навигации
        self.exit_dialog_buttons = [no_btn, yes_btn]
        self.exit_dialog_current_index = 0
        no_btn.setFocus()

        # Подключаем обработчики клавиш для диалога
        dlg.keyPressEvent = self._exit_dialog_key_handler

        result = dlg.exec()

        if dlg.clickedButton() is yes_btn:
            self.close()

    def _exit_dialog_key_handler(self, event):
        """Обработчик клавиш для диалога выхода"""
        # Обработка геймпада
        if hasattr(self, 'navigation_controller'):
            # Преобразуем клавиши в кнопки геймпада
            key_map = {
                Qt.Key.Key_Left: 'LEFT',
                Qt.Key.Key_Right: 'RIGHT',
                Qt.Key.Key_Return: 'A',
                Qt.Key.Key_Escape: 'B',
                Qt.Key.Key_A: 'A',
                Qt.Key.Key_B: 'B'
            }

            button = key_map.get(event.key())
            if button:
                if button == 'LEFT':
                    self.exit_dialog_current_index = (self.exit_dialog_current_index - 1) % len(self.exit_dialog_buttons)
                    self.exit_dialog_buttons[self.exit_dialog_current_index].setFocus()
                    event.accept()
                elif button == 'RIGHT':
                    self.exit_dialog_current_index = (self.exit_dialog_current_index + 1) % len(self.exit_dialog_buttons)
                    self.exit_dialog_buttons[self.exit_dialog_current_index].setFocus()
                    event.accept()
                elif button == 'A':
                    self.exit_dialog_buttons[self.exit_dialog_current_index].click()
                    event.accept()
                elif button == 'B':
                    self.exit_dialog_buttons[0].click()  # "Нет"
                    event.accept()
                return

        # Стандартная обработка клавиатуры
        if event.key() == Qt.Key.Key_Left:
            self.exit_dialog_current_index = (self.exit_dialog_current_index - 1) % len(self.exit_dialog_buttons)
            self.exit_dialog_buttons[self.exit_dialog_current_index].setFocus()
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            self.exit_dialog_current_index = (self.exit_dialog_current_index + 1) % len(self.exit_dialog_buttons)
            self.exit_dialog_buttons[self.exit_dialog_current_index].setFocus()
            event.accept()
        elif event.key() == Qt.Key.Key_A or event.key() == Qt.Key.Key_Return:
            self.exit_dialog_buttons[self.exit_dialog_current_index].click()
            event.accept()
        elif event.key() == Qt.Key.Key_B or event.key() == Qt.Key.Key_Escape:
            self.exit_dialog_buttons[0].click()
            event.accept()
        else:
            event.accept()

    def switch_layer(self, new_layer):
        """Переключение между слоями интерфейса"""
        logger.info(f"Переключение на слой: {new_layer}")

        if new_layer == NavigationLayer.MAIN:
            self.stack.setCurrentWidget(self.library_page)
            logger.info("Установлена страница библиотеки")
        elif new_layer == NavigationLayer.SETTINGS:
            self.stack.setCurrentWidget(self.settings_page)
            logger.info("Установлена страница настроек")
        elif new_layer == NavigationLayer.GAME_INFO:
            self.stack.setCurrentWidget(self.game_info_page)
            logger.info("Установлена страница информации об игре")

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
            installed_games_file = Path(get_users_path()) / 'installed_games.json'
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
        Показать страницу с информацией об игре
        """
        try:
            # 1. Передаем данные в game_info_page
            self.game_info_page.load_game(game)

            # 2. Показываем страницу
            self.stack.setCurrentWidget(self.game_info_page)

            # 3. Переключаем слой навигации
            self.navigation_controller.switch_layer(NavigationLayer.GAME_INFO)

            logger.info(f"✅ Переход на страницу игры: {game.get('title', 'Unknown')}")

        except Exception as e:
            logger.error(f"❌ Ошибка перехода на страницу игры: {e}")
            QMessageBox.critical(self, "Ошибка", "Не удалось открыть страницу информации об игре.")

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
            installed_games_file = Path(get_users_path()) / 'installed_games.json'
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

    # Автоматическое включение виртуальной клавиатуры
    def enable_virtual_keyboard():
        # Для Steam Deck
        os.environ['QT_IM_MODULE'] = 'qtvirtualkeyboard'
        # Включение виртуальной клавиатуры при фокусе
        os.environ['QT_ENABLE_GLYPH_CACHE_WORKAROUND'] = '1'

    # Вызовите эту функцию до создания QApplication
    enable_virtual_keyboard()

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
        window.showNormal()

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
