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
import threading

# Настройка логирования до проверки экземпляра
log_dir = os.path.join(os.path.expanduser("~"), "ArcadeDeck", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "arcadedeck.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='w'),
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
        lock_fd = open(lock_file, 'w+')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as e:
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise

            lock_fd.seek(0)
            pid_str = lock_fd.read().strip()

            if pid_str and pid_str.isdigit():
                pid = int(pid_str)
                if is_process_running(pid):
                    return False, pid

            logger.warning("Обнаружен lock-файл от несуществующего процесса")

        lock_fd.seek(0)
        lock_fd.truncate()
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()

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


def is_process_running(pid):
    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.ESRCH:
            return False
        elif err.errno == errno.EPERM:
            return True
        else:
            return False
    else:
        return True


# Глобальный обработчик исключений
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error(
        "Неперехваченное исключение:",
        exc_info=(exc_type, exc_value, exc_traceback))

    error_msg = f"{exc_type.__name__}: {exc_value}"

    app = QApplication.instance()
    if not app:
        logger.error("QApplication не существует, невозможно показать ошибку")
        return

    try:
        parent = None
        for widget in app.topLevelWidgets():
            if widget.isVisible():
                parent = widget
                break

        # Заменяем QMessageBox.critical на кастомный диалог
        from app.modules.ui.message_dialog import show_error
        show_error(
            parent,
            "Критическая ошибка",
            f"Произошла непредвиденная ошибка:\n\n{error_msg}\n\n"
            f"Подробности в логах: {log_file}",
            nav_controller=None  # при падении навигация может быть недоступна
        )
    except Exception as e:
        logger.error(f"Ошибка при показе сообщения об ошибке: {e}")

sys.excepthook = handle_exception


def is_venv_active():
    return (hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))

if not is_venv_active():
    logger.warning("ВНИМАНИЕ: Виртуальное окружение не активировано!")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import (
    QApplication, QAbstractItemView, QMainWindow, QWidget, QDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout,
    QMessageBox, QStackedWidget, QFrame, QGridLayout, QHBoxLayout, QPushButton,
    QSizePolicy, QScrollArea, QTabWidget, QDialogButtonBox, QRadioButton,
    QButtonGroup, QCheckBox, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QEvent, QMetaObject
from PyQt6.QtGui import QIcon, QFont, QPixmap, QKeyEvent
from pathlib import Path

# Импорт кастомных диалогов
from app.modules.ui.message_dialog import show_info, show_warning, show_error, show_question

from app.modules.installer.install import InstallDialog
from app.modules.installer.game_downloader import GameDownloader

from core import APP_VERSION, STYLES_DIR, THEME_FILE
from settings import app_settings
from app.welcome import WelcomeWizard
from app.ui_assets.theme_manager import theme_manager
from updater import Updater, UpdateDialog
from navigation import NavigationController, NavigationLayer
from app.modules.ui.game_info_page import GameInfoPage
from app.modules.ui.search_overlay import SearchOverlay
from app.modules.ui.settings_page import SettingsPage
from app.modules.module_logic.game_scanner import (
    is_game_installed,
    get_installed_games
)
from app.modules.module_logic.game_data_manager import get_game_data_manager, set_game_data_manager

from app.modules.settings_plugins.about_settings import AboutPage
from modules.settings_plugins.general_settings import GeneralSettingsPage
from modules.settings_plugins.appearance_settings import AppearanceSettingsPage
from modules.settings_plugins.dev_settings import DevSettingsPage

# Импорт пути игровых данных
from core import get_users_path


class MainWindow(QMainWindow):
    game_closed = pyqtSignal()   # сигнал без аргументов (можно добавить object, если нужны данные)

    def __init__(self):
        super().__init__()

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)           # главное окно не крадёт фокус
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)

        # Отключаем стандартную навигацию Qt по клавишам
        QApplication.setKeyboardInputInterval(0)  # уже есть
        self.setTabOrder(None, None)  # отключает Tab

        # Самое важное — фильтр событий
        self.installEventFilter(self)


        self.install_dir = BASE_DIR
        self.project_root = Path(__file__).parent.resolve()
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
        self.main_layout.setContentsMargins(15, 0, 15, 0)
        self.main_layout.setSpacing(10)

        # Стек виджетов
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack, 1)

        # Подсказки
        hints_layout = QHBoxLayout()
        self.hint_label = QLabel("B: Назад")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setFixedHeight(63)
        hints_layout.addWidget(self.hint_label)
        hints_layout.setContentsMargins(0, 0, 0, 10)
        hints_layout.setSpacing(0)
        self.main_layout.addLayout(hints_layout)

        # Навигационный контроллер
        self.navigation_controller = NavigationController(self)
        self.navigation_controller.set_hint_widget(self.hint_label)
        self.navigation_controller.layer_changed.connect(self.switch_layer)

        self.init_ui()

        self.apply_theme(theme_manager.current_theme)
        theme_manager.theme_changed.connect(self.apply_theme)

        self.updater = Updater(self)
        self.updater.update_available.connect(self.on_update_available)
        QTimer.singleShot(1000, self.start_background_update_check)

        self.installEventFilter(self)

        self.game_closed.connect(self._on_game_closed)

    def start_background_update_check(self):
        from PyQt6.QtCore import QThread

        class CheckThread(QThread):
            def __init__(self, updater):
                super().__init__()
                self.updater = updater

            def run(self):
                self.updater.check_for_updates()

        self.update_thread = CheckThread(self.updater)
        self.update_thread.start()

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
        self.game_info_page.coverUpdated.connect(self.library_page.update_game_cover)
        self.game_info_page.back_callback = self.show_library_page
        self.game_info_page.action_callback = self.on_game_action
        self.stack.addWidget(self.game_info_page)

        self.register_navigation_widgets()

        self.stack.setCurrentIndex(0)
        self.navigation_controller.switch_layer(NavigationLayer.MAIN)
        self.navigation_controller.update_hints()

        self.hint_label.setStyleSheet("""
            font-size: 16px;
            font-weight: 500;
            padding: 8px;
        """)

    def show_library_page(self):
        """Переключение на главную страницу библиотеки."""
        self.stack.setCurrentWidget(self.library_page)

    def apply_theme(self, theme_name):
        try:
            self.setProperty("class", f"{theme_name}-theme")
            for widget in self.findChildren(QWidget):
                if widget != self:
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                    widget.update()
            self.style().unpolish(self)
            self.style().polish(self)
        except Exception as e:
            logger.error(f"Ошибка применения темы: {e}")

    def register_navigation_widgets(self):
        """Регистрация виджетов для навигационного контроллера"""
        logger.info("Начало регистрации навигационных виджетов")

        settings_widgets = self.settings_page.tiles if hasattr(self.settings_page, 'tiles') else []
        logger.info(f"Слой настроек: {len(settings_widgets)} плиток")

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

        game_info_widgets = [
            self.game_info_page.action_button,
            self.game_info_page.back_button,
            self.game_info_page.menu_button
        ]
        logger.info(f"Слой информации об игре: {len(game_info_widgets)} виджетов")

        self.navigation_controller.register_widgets(
            NavigationLayer.GAME_INFO,
            game_info_widgets
        )

        logger.info("Регистрация навигационных виджетов завершена")

    def toggle_settings(self):
        current_layer = self.navigation_controller.current_layer
        if current_layer == NavigationLayer.MAIN:
            self.navigation_controller.switch_layer(NavigationLayer.SETTINGS)
        else:
            self.navigation_controller.switch_layer(NavigationLayer.MAIN)

    def launch_selected_game(self):
        if self.navigation_controller.current_layer == NavigationLayer.MAIN:
            widgets = self.navigation_controller.layer_widgets[NavigationLayer.MAIN]
            idx = self.navigation_controller.focus_index[NavigationLayer.MAIN]
            if 0 <= idx < len(widgets):
                logger.info("Запуск игры из главного меню")

    def closeEvent(self, event):
        logger.info("Завершение приложения...")
        try:
            if self.updater_process and self.updater_process.poll() is None:
                try:
                    os.kill(self.updater_process.pid, signal.SIGTERM)
                    time.sleep(0.5)
                    if self.updater_process.poll() is None:
                        os.kill(self.updater_process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except Exception as e:
                    logger.error(f"Ошибка завершения процесса обновления: {e}")

            self.updater.stop_checking()
            try:
                theme_manager.theme_changed.disconnect(self.apply_theme)
                self.updater.update_available.disconnect(self.on_update_available)
                self.navigation_controller.layer_changed.disconnect(self.switch_layer)
            except TypeError:
                pass

            self.updater.deleteLater()
            self.navigation_controller.deleteLater()

        except Exception as e:
            logger.error(f"Ошибка при завершении: {e}")

        logger.info("Принудительное завершение приложения")
        if hasattr(self, 'gamepad_manager'):
            self.gamepad_manager.stop()

    def confirm_exit(self, event=None):
        exit_dialog = QDialog(self)
        exit_dialog.setWindowTitle("Выход")
        exit_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        exit_dialog.setGeometry(0, 0, self.width(), self.height())

        exit_dialog.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 24px;
                font-weight: bold;
                qproperty-alignment: AlignCenter;
            }
        """)

        layout = QVBoxLayout(exit_dialog)
        layout.setSpacing(30)
        layout.setContentsMargins(50, 100, 50, 100)

        question_label = QLabel("Вы хотите закрыть ArcadeDeck?")
        layout.addWidget(question_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(40)

        no_btn = QPushButton("Нет")
        yes_btn = QPushButton("Да")

        no_btn.clicked.connect(exit_dialog.reject)
        yes_btn.clicked.connect(exit_dialog.accept)

        for btn in (no_btn, yes_btn):
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        button_layout.addWidget(no_btn)
        button_layout.addWidget(yes_btn)
        layout.addLayout(button_layout)

        self.exit_dialog_buttons = [no_btn, yes_btn]
        self.exit_dialog_current_index = 0
        no_btn.setFocus()

        self.navigation_controller.add_managed_window(exit_dialog)
        self.navigation_controller.set_dialog_open(True)
        self.navigation_controller.register_widgets(NavigationLayer.DIALOG, self.exit_dialog_buttons)
        self.navigation_controller.switch_layer(NavigationLayer.DIALOG)

        exit_dialog.setModal(True)

        def on_close(result):
            self.navigation_controller.remove_managed_window(exit_dialog)
            self.navigation_controller.set_dialog_open(False)
            self.navigation_controller.exit_dialog_mode()
            if result == QDialog.DialogCode.Accepted:
                self.close()

        exit_dialog.finished.connect(on_close)
        exit_dialog.show()

    def _on_exit_dialog_closed(self, result):
        """Вызывается при закрытии диалога выхода"""
        self.navigation_controller.exit_dialog_mode()
        if result == QDialog.DialogCode.Accepted:
            self.close()

    def switch_layer(self, new_layer):
        logger.info(f"Переключение на слой: {new_layer}")
        if new_layer == NavigationLayer.MAIN:
            self.stack.setCurrentWidget(self.library_page)
        elif new_layer == NavigationLayer.SETTINGS:
            self.stack.setCurrentWidget(self.settings_page)
        elif new_layer == NavigationLayer.GAME_INFO:
            self.stack.setCurrentWidget(self.game_info_page)

    def eventFilter(self, obj, event):
        """Глобальный фильтр событий — блокируем стандартную навигацию Qt"""
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            key = event.key()

            # Эти клавиши полностью забираем под свой контроль
            if key in (
                Qt.Key.Key_Up, Qt.Key.Key_Down,
                Qt.Key.Key_Left, Qt.Key.Key_Right,
                Qt.Key.Key_Return, Qt.Key.Key_Enter,
                Qt.Key.Key_Escape,
                Qt.Key.Key_Tab, Qt.Key.Key_Backtab,
                Qt.Key.Key_Y, Qt.Key.Key_S,  # для поиска
            ):
                if event.type() == QEvent.Type.KeyPress:
                    self.navigation_controller.handle_key_event(event)
                event.accept()
                return True  # блокируем дальнейшую обработку Qt

        # Для диалогов и попапов можно ослабить, но лучше держать строго
        return super().eventFilter(obj, event)

    def launch_game(self, game_data):
        """Запуск игры с блокировкой геймпада и мониторингом завершения"""
        try:
            logger.info(f"🚀 Запуск игры: {game_data.get('title', 'Unknown')}")

            installed_games_file = Path(get_users_path()) / 'installed_games.json'
            if not installed_games_file.exists():
                show_warning(self, "Ошибка", "Файл installed_games.json не найден", self.navigation_controller)
                return

            with open(installed_games_file, 'r', encoding='utf-8') as f:
                installed_games = json.load(f)

            game_id = game_data.get('id')
            if game_id not in installed_games:
                show_warning(self, "Ошибка", "Игра не установлена", self.navigation_controller)
                return

            game_info = installed_games[game_id]
            launcher_path = game_info.get('launcher_path')

            if not launcher_path or not os.path.exists(launcher_path):
                show_warning(self, "Ошибка", f"Лаунчер не найден: {launcher_path}", self.navigation_controller)
                return

            # === БЛОКИРУЕМ УПРАВЛЕНИЕ ===
            if hasattr(self, 'navigation_controller') and self.navigation_controller:
                self.navigation_controller.block_gamepad_for_game(True)

            # Запускаем .sh скрипт
            process = subprocess.Popen(
                ['bash', launcher_path],
                start_new_session=True,
                cwd=Path(launcher_path).parent
            )

            logger.info(f"✅ Игра запущена (PID: {process.pid})")

            # Запускаем мониторинг в отдельном потоке
            threading.Thread(
                target=self._monitor_game_process,
                args=(process, game_data),
                daemon=True
            ).start()

        except Exception as e:
            logger.error(f"❌ Ошибка запуска игры: {e}")
            show_error(self, "Ошибка запуска", f"Не удалось запустить игру:\n{str(e)}", self.navigation_controller)
            
            # Разблокируем в случае ошибки
            if hasattr(self, 'navigation_controller') and self.navigation_controller:
                self.navigation_controller.block_gamepad_for_game(False)

    def _monitor_game_process(self, process, game_data):
        try:
            return_code = process.wait()
            logger.info(f"🎮 Игра завершена (код: {return_code})")
            time.sleep(1.0)
            self.game_closed.emit()   # <-- сигнал, а не invokeMethod
        except Exception as e:
            logger.error(f"Ошибка мониторинга: {e}")
            self.game_closed.emit()

    def _on_game_closed(self, game_data=None):
        """Вызывается после завершения игры"""
        logger.info("✅ Игра закрыта — начинаем восстановление управления")

        try:
            if hasattr(self, 'navigation_controller') and self.navigation_controller:
                self.navigation_controller.block_gamepad_for_game(False)

            if (hasattr(self, 'game_info_page') and
                self.stack.currentWidget() == self.game_info_page):
                QTimer.singleShot(300,
                    lambda: self.game_info_page.update_installation_status(True)
                )

            logger.info("🔄 Управление успешно восстановлено")

        except Exception as e:
            logger.error(f"❌ Ошибка восстановления после игры: {e}", exc_info=True)

    def show_game_info(self, game):
        try:
            self.game_info_page.load_game(game)
            self.stack.setCurrentWidget(self.game_info_page)
            self.navigation_controller.switch_layer(NavigationLayer.GAME_INFO)
            logger.info(f"✅ Переход на страницу игры: {game.get('title', 'Unknown')}")
        except Exception as e:
            logger.error(f"❌ Ошибка перехода на страницу игры: {e}")
            show_error(self, "Ошибка", "Не удалось открыть страницу информации об игре.", self.navigation_controller)

    def on_game_action(self, game_data, is_installed):
        if is_installed:
            self.launch_game(game_data)
        else:
            self.install_game(game_data)

    def install_game(self, game_data):
        logger.info(f"Начало установки игры: {game_data['title']}")
        try:
            installer_dialog = InstallDialog(
                game_data=game_data,
                project_root=Path(BASE_DIR),
                parent=self
            )
            installer_dialog.exec()
            self._update_game_status_after_installation(game_data)
        except Exception as e:
            logger.error(f"Не удалось запустить диалог установки: {e}")
            show_error(self, "Ошибка установки", f"Не удалось начать установку: {e}", self.navigation_controller)

    def _update_game_status_after_installation(self, game_data):
        try:
            game_id = game_data.get('id')
            installed_games_file = Path(get_users_path()) / 'installed_games.json'
            is_installed = False
            if installed_games_file.exists():
                with open(installed_games_file, 'r', encoding='utf-8') as f:
                    installed_games = json.load(f)
                    is_installed = game_id in installed_games

            if (hasattr(self, 'game_info_page') and
                self.game_info_page and
                self.game_info_page.game_data.get('id') == game_id):
                self.game_info_page.update_installation_status(is_installed)

            if hasattr(self, 'library_page') and self.library_page:
                self.library_page.load_games()
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса игры: {e}")

    def on_installation_complete(self, game_data):
        try:
            game_id = game_data.get('id')
            logger.info(f"Установка завершена для игры: {game_data.get('title')}")

            if (hasattr(self, 'game_info_page') and
                self.game_info_page.game_data.get('id') == game_id):
                self.game_info_page.update_installation_status(True)

            if hasattr(self, 'library_page'):
                self.library_page.load_games()
                logger.info("Библиотека игр обновлена")

            show_info(
                self,
                "Установка завершена",
                f"Игра '{game_data.get('title')}' успешно установлена!",
                self.navigation_controller
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке завершения установки: {e}")
            show_warning(
                self,
                "Ошибка",
                f"Игра установлена, но произошла ошибка при обновлении интерфейса: {e}",
                self.navigation_controller
            )

    def on_update_available(self, update_info):
        if not self.isVisible():
            logger.warning("Главное окно закрыто, игнорируем обновление")
            return

        latest_version = update_info.get('version')
        changelog = update_info.get('release', {}).get("body", "Нет информации об изменениях")
        download_url = update_info.get('download_url')
        asset_name = update_info.get('asset_name')

        if not all([latest_version, download_url, asset_name]):
            logger.error(f"Неполные данные об обновлении: {update_info}")
            show_warning(self, "Ошибка обновления", "Не удалось получить полную информацию о последней версии.", self.navigation_controller)
            return

        try:
            dialog = UpdateDialog(
                APP_VERSION,
                latest_version,
                changelog,
                download_url,
                self.install_dir,
                asset_name,
                self,
                nav_controller=self.navigation_controller
            )
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.exec()
        finally:
            self.activateWindow()
            self.raise_()


def enable_virtual_keyboard():
    os.environ['QT_IM_MODULE'] = 'qtvirtualkeyboard'
    os.environ['QT_ENABLE_GLYPH_CACHE_WORKAROUND'] = '1'

enable_virtual_keyboard()


def check_and_show_updates(dark_theme):
    try:
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        updater_path = os.path.join(BASE_DIR, "app", "updater.py")
        theme_flag = "--dark" if dark_theme else "--light"
        process = subprocess.Popen(
            [sys.executable, updater_path, theme_flag],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return process
    except Exception as e:
        logger.error(f"Ошибка запуска updater: {e}")
        return None


if __name__ == "__main__":
    lock_result, existing_pid = enforce_single_instance()

    if not lock_result:
        if existing_pid:
            temp_app = QApplication(sys.argv)
            try:
                with open(THEME_FILE, 'r', encoding='utf-8') as f:
                    stylesheet = f.read()
                    temp_app.setStyleSheet(stylesheet)
            except Exception as e:
                logger.error(f"Ошибка загрузки стилей для диалога: {e}")

            # Заменяем QMessageBox на кастомные диалоги (без навигации)
            from app.modules.ui.message_dialog import show_question, show_error

            # Создаём простое окно-родитель
            dummy_widget = QWidget()
            result = show_question(
                dummy_widget,
                "Программа уже запущена",
                "ArcadeDeck уже запущен! Проверьте панель задач.\n\n"
                "Если программа не отвечает, вы можете принудительно перезапустить ее.\n\n"
                "Перезапустить ArcadeDeck?",
                nav_controller=None
            )
            # show_question возвращает True для Yes, False для No
            if result:
                logger.info(f"Пользователь выбрал перезапуск. Завершаем процесс {existing_pid}...")
                try:
                    os.kill(existing_pid, signal.SIGTERM)
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Ошибка при завершении процесса: {e}")

                project_root = os.path.dirname(BASE_DIR)
                script_path = os.path.join(project_root, "ArcadeDeck.sh")
                if not os.path.exists(script_path):
                    logger.error(f"Скрипт запуска не найден: {script_path}")
                    show_error(
                        dummy_widget,
                        "Ошибка перезапуска",
                        f"Файл запуска не найден: {script_path}",
                        nav_controller=None
                    )
                else:
                    subprocess.Popen([script_path], start_new_session=True)
            sys.exit(0)
        else:
            logger.error("Ошибка блокировки без указания PID")
            sys.exit(1)

    logger.info("Запуск ArcadeDeck")
    logger.info(f"Версия: {APP_VERSION}")
    logger.info(f"Рабочая директория: {os.getcwd()}")

    try:
        os.makedirs(STYLES_DIR, exist_ok=True)
        try:
            with open(THEME_FILE, 'r', encoding='utf-8') as f:
                global_stylesheet = f.read()
        except Exception as e:
            logger.error(f"Ошибка загрузки стилей: {e}")
            # Здесь можно показать ошибку, но QApplication ещё нет
            sys.exit(1)

        app_settings._ensure_settings()
        theme_name = app_settings.get_theme()

        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setKeyboardInputInterval(0)
        app.setStyleSheet(global_stylesheet)
        app.setProperty("class", f"{theme_name}-theme")

        theme_manager.set_theme(theme_name)

        welcome_shown = app_settings.get_welcome_shown()
        dark_theme = (theme_name == 'dark')

        if not welcome_shown:
            logger.info("Показываем приветственное окно")
            welcome = WelcomeWizard()
            result = welcome.exec()
            app_settings.set_welcome_shown(True)
            new_theme = app_settings.get_theme()
            theme_manager.set_theme(new_theme)
            app.setProperty("class", f"{new_theme}-theme")
            dark_theme = (new_theme == 'dark')

        window = MainWindow()
        window.showFullScreen()
        QTimer.singleShot(1000, lambda: check_and_show_updates(dark_theme))
        sys.exit(app.exec())

    except Exception as e:
        logger.exception("Критическая ошибка при запуске")
        try:
            temp_app = QApplication(sys.argv)
            from app.modules.ui.message_dialog import show_error
            show_error(None, "Ошибка запуска",
                       f"Произошла критическая ошибка: {str(e)}\n\nПодробности в логах: {log_file}",
                       nav_controller=None)
            temp_app.exec()
        except Exception as ex:
            logger.error(f"Ошибка при показе сообщения об ошибке: {ex}")
        sys.exit(1)
