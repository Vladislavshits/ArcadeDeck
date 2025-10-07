import sys
import json
import logging
import time
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QLabel,
                           QProgressBar, QPushButton, QHBoxLayout, QMessageBox,
                           QTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

# Импорты системы установки
from .emulator_manager import EmulatorManager
from .bios_manager import BIOSManager
from .config_manager import ConfigManager
from .game_downloader import GameDownloader
from .archive_extractor import ArchiveExtractor
from .launch_manager import LaunchManager

# Импорт каталога установки
from core import get_users_path
from core import get_users_subpath

# Создаем основной логгер приложения
logger = logging.getLogger('PixelDeck')


class InstallThread(QThread):

    finished = pyqtSignal()

    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    cancelled = pyqtSignal()
    set_indeterminate = pyqtSignal(bool)

    def __init__(self, game_data: dict, install_dir: Path, project_root: Path, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.install_dir = install_dir
        self.project_root = project_root
        self._cancelled = False
        self._was_cancelled = False
        self.installed_games_file = Path(get_users_path()) / 'installed_games.json'

        self.emulator_manager = EmulatorManager(self.project_root, test_mode=False)
        self.bios_manager = BIOSManager(self.project_root)
        self.game_downloader = GameDownloader(self.game_data, self.install_dir)
        self.archive_extractor = ArchiveExtractor(self.game_data, self.install_dir)
        self.extracted_files = []
        self.config_manager = ConfigManager(self.project_root)
        self.launch_manager = LaunchManager(self.project_root)  # Создаем экземпляр LaunchManager

    def get_installed_games(self):
        """Возвращает словарь установленных игр"""
        if self.installed_games_file.exists():
            try:
                with open(self.installed_games_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def run(self):
        try:
            # Шаг 1: Проверка и установка эмулятора
            self.progress_updated.emit(5, "Этап 1: Проверка и установка эмулятора...")
            if self._cancelled:
                self._was_cancelled = True
                return

            # Используем ensure_emulator_for_game
            if not self.emulator_manager.ensure_emulator_for_game(self.game_data):
                self.error_occurred.emit("Ошибка при установке эмулятора.")
                return

            if self._cancelled:
                self._was_cancelled = True
                return

            # Шаг 2: Проверка и установка BIOS
            self.progress_updated.emit(30, "Этап 2: Проверка и установка BIOS...")
            if self._cancelled:
                self._was_cancelled = True
                return

            if not self.bios_manager.ensure_bios_for_platform(self.game_data.get('platform')):
                self.error_occurred.emit("Ошибка при установке BIOS.")
                return

            if self._cancelled:
                self._was_cancelled = True
                return

            # Шаг 3: Скачивание игры
            self.progress_updated.emit(50, "Этап 3: Подготовка к загрузке игры...")
            self.set_indeterminate.emit(True)

            # Подключаем сигналы game_downloader
            self.game_downloader.progress_updated.connect(self.progress_updated)
            self.game_downloader.finished.connect(self.on_download_finished)
            self.game_downloader.error_occurred.connect(self.on_download_error)

            # Запускаем загрузку в отдельном потоке
            self.game_downloader.start()

            # Ждем завершения загрузки
            while self.game_downloader.isRunning() and not self._cancelled:
                self.msleep(100)

            if self._cancelled:
                self.game_downloader.cancel()
                self.game_downloader.wait()
                self._was_cancelled = True
                return

            # Отключаем сигналы
            self.game_downloader.progress_updated.disconnect(self.progress_updated)
            self.game_downloader.finished.disconnect(self.on_download_finished)
            self.game_downloader.error_occurred.disconnect(self.on_download_error)

            if self._cancelled:
                self._was_cancelled = True
                return

            # Шаг 4: Обработка файлов (распаковка если нужно)
            self.set_indeterminate.emit(False)
            self.progress_updated.emit(75, "Этап 4: Обработка скачанных файлов...")
            if self._cancelled:
                self._was_cancelled = True
                return

            # Подключаем сигналы archive_extractor
            self.archive_extractor.progress_updated.connect(self.progress_updated)
            self.archive_extractor.finished.connect(self.on_extraction_finished)
            self.archive_extractor.error_occurred.connect(self.on_extraction_error)
            self.archive_extractor.files_extracted.connect(self.on_files_extracted)  # Новый сигнал

            # Запускаем обработку файлов
            self.archive_extractor.start()

            # Ждем завершения
            while self.archive_extractor.isRunning() and not self._cancelled:
                self.msleep(100)

            if self._cancelled:
                self.archive_extractor.cancel()
                self.archive_extractor.wait()
                self._was_cancelled = True
                return

            # Отключаем сигналы
            self.archive_extractor.progress_updated.disconnect(self.progress_updated)
            self.archive_extractor.finished.disconnect(self.on_extraction_finished)
            self.archive_extractor.error_occurred.disconnect(self.on_extraction_error)
            self.archive_extractor.files_extracted.disconnect(self.on_files_extracted)

            if self._cancelled:
                self._was_cancelled = True
                return

            # Шаг 5: Конфиги
            self.progress_updated.emit(85, "Этап 5: Установка конфигов...")
            if self._cancelled:
                self._was_cancelled = True
                return

            self.config_manager.apply_config(
                self.game_data.get('id'),
                self.game_data.get('platform')
            )

            if self._cancelled:
                self._was_cancelled = True
                return

            # Шаг 6: Создание лаунчера и регистрация игры через LaunchManager
            self.progress_updated.emit(90, "Этап 6: Создание ярлыка для запуска...")
            if self._cancelled:
                self._was_cancelled = True
                return

            # Находим файл игры
            game_file = self.find_game_file()

            if game_file and game_file.is_file():
                # Используем LaunchManager для создания лаунчера
                try:
                    success = self.launch_manager.create_launcher(self.game_data, game_file)

                    if success:
                        # Получаем путь к созданному лаунчеру
                        launcher_path = self.launch_manager.scripts_dir / f"{self.game_data.get('id')}.sh"

                        # Получаем путь к обложке с логированием
                        logger.info(f"🔍 Поиск обложки для игры {self.game_data.get('id')}")
                        cover_path = self.launch_manager._get_cover_path(self.game_data)
                        logger.info(f"📁 Путь к обложке: {cover_path}")

                        # Регистрируем игру
                        installed_games = self.get_installed_games()
                        game_info = {
                            'title': self.game_data.get('title'),
                            'platform': self.game_data.get('platform'),
                            'install_path': str(game_file.absolute()),
                            'launcher_path': str(launcher_path.absolute()),
                            'install_date': time.time(),
                            'cover_path': cover_path  # Добавляем путь к обложке
                        }

                        installed_games[self.game_data.get('id')] = game_info
                        logger.info(f"💾 Сохранение информации об игре: {game_info}")

                        # Сохраняем реестр
                        with open(self.installed_games_file, 'w', encoding='utf-8') as f:
                            json.dump(installed_games, f, ensure_ascii=False, indent=2)

                        logger.info(f"✅ Игра успешно зарегистрирована в installed_games.json")

                        self.progress_updated.emit(95, "✅ Лаунчер создан и игра зарегистрирована!")
                        self.finished.emit(self.game_data)
                    else:
                        # Улучшенная обработка ошибки создания лаунчера
                        error_msg = "Не удалось создать лаунчер для игры"
                        logger.error(f"❌ {error_msg}")
                        self.progress_updated.emit(90, "❌ Не удалось создать ярлык для запуска")
                        self.error_occurred.emit(error_msg)
                        return

                except Exception as e:
                    error_msg = f"Ошибка при создании лаунчера: {e}"
                    logger.error(f"❌ {error_msg}")
                    self.progress_updated.emit(90, "❌ Ошибка создания ярлыка")
                    self.error_occurred.emit(error_msg)
                    return
            else:
                error_msg = "Не удалось найти файл игры после установки"
                logger.error(f"❌ {error_msg}")
                self.progress_updated.emit(90, "❌ Файл игры не найден")
                self.error_occurred.emit(error_msg)
                return

        except Exception as e:
            if not self._was_cancelled:
                self.error_occurred.emit(f"Установка прервана из-за ошибки: {e}")
        finally:
            self.set_indeterminate.emit(False)
            if self._was_cancelled:
                self.cancelled.emit()

    def on_files_extracted(self, files_list):
        """Сохраняем список распакованных файлов"""
        self.extracted_files = files_list
        logger.info(f"📋 Получен список распакованных файлов: {[f.name for f in files_list]}")

    def find_game_file(self):
        """Находит файл игры по поддерживаемым расширениям платформы"""
        try:
            platform_id = self.game_data.get('platform')
            logger.info(f"🔍 Поиск файлов игры для платформы: {platform_id}")

            # Получаем поддерживаемые форматы из конфига платформы
            platform_config_path = self.project_root / 'app' / 'registry' / 'platforms' / platform_id / 'config.py'

            supported_formats = []
            if platform_config_path.exists():
                try:
                    # Динамически импортируем конфиг платформы
                    import importlib.util
                    spec = importlib.util.spec_from_file_location(f"{platform_id}_config", platform_config_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    if hasattr(module, 'get_config'):
                        config = module.get_config()
                        supported_formats = config.get('supported_formats', [])
                        logger.info(f"✅ Загружены поддерживаемые форматы из конфига: {supported_formats}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось загрузить конфиг платформы: {e}")

            # Fallback: если форматы не найдены, используем стандартные для платформы
            if not supported_formats:
                platform_formats = {
                    "PSP": [".iso", ".cso", ".pbp", ".elf"],
                    "ppsspp": [".iso", ".cso", ".pbp", ".elf"],
                    "PS1": [".bin", ".cue", ".img", ".mdf", ".pbp"],
                    "duckstation": [".bin", ".cue", ".img", ".mdf", ".pbp"],
                    "PS2": [".iso", ".bin", ".mdf", ".gz"],
                    "pcsx2": [".iso", ".bin", ".mdf", ".gz"],
                    "GBA": [".gba", ".agb", ".bin"],
                    "NDS": [".nds", ".srl", ".bin"],
                    "N64": [".n64", ".v64", ".z64", ".bin"],
                    "SNES": [".smc", ".sfc", ".fig", ".swc"],
                    "NES": [".nes", ".fds", ".unf", ".unif"]
                }
                supported_formats = platform_formats.get(platform_id, [".iso", ".bin", ".img"])
                logger.warning(f"⚠️ Для платформы {platform_id} не найдены supported_formats, использую fallback: {supported_formats}")

            logger.info(f"🔍 Форматы для поиска: {supported_formats}")

            # Получаем ID игры для поиска соответствующих файлов
            game_id = self.game_data.get('id', '').lower()
            logger.info(f"🔍 Ищем файлы для игры ID: {game_id}")

            # Сначала проверяем распакованные файлы
            if self.extracted_files:
                logger.info("🔍 Проверяем распакованные файлы...")
                for file_path in self.extracted_files:
                    if (file_path.is_file() and
                        file_path.suffix.lower() in supported_formats):
                        logger.info(f"✅ Найден распакованный файл: {file_path.name}")
                        return file_path

            # Если нет распакованных файлов или не нашли подходящий, ищем в директории
            logger.info("🔍 Проверяем файлы в директории установки...")
            game_files = []
            for file_path in self.install_dir.iterdir():
                if (file_path.is_file() and
                    file_path.suffix.lower() in supported_formats):

                    # Проверяем соответствие имени файла ID игры
                    filename_lower = file_path.name.lower()
                    if game_id in filename_lower or any(
                        word in filename_lower for word in game_id.split('_')
                    ):
                        logger.info(f"✅ Найден соответствующий файл: {file_path.name}")
                        game_files.append(file_path)
                    else:
                        logger.info(f"⚠️ Файл не соответствует ID игры: {file_path.name}")

            if game_files:
                # Возвращаем самый подходящий файл (по размеру или точному соответствию)
                result = max(game_files, key=lambda f: f.stat().st_size)
                logger.info(f"✅ Выбран файл игры: {result.name}")
                return result

            # Fallback: если не нашли по соответствию, ищем любой подходящий файл
            all_files = [f for f in self.install_dir.iterdir()
                        if f.is_file() and f.suffix.lower() in supported_formats]

            if all_files:
                result = max(all_files, key=lambda f: f.stat().st_size)
                logger.warning(f"⚠️ Точное соответствие не найдено, использую: {result.name}")
                return result

            logger.error("❌ Не найдено ни одного файла в директории установки")
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка при поиске файла игры: {e}")
            return None

    def on_download_finished(self):
        self.progress_updated.emit(70, "✅ Загрузка игры завершена!")

    def on_download_error(self, error_msg):
        self.error_occurred.emit(f"Ошибка загрузки: {error_msg}")

    def on_extraction_finished(self):
        """Обработка завершения обработки файлов"""
        self.progress_updated.emit(80, "✅ Обработка файлов завершена!")

    def on_extraction_error(self, error_msg):
        """Обработка ошибки обработки файлов"""
        self.error_occurred.emit(f"Ошибка обработки файлов: {error_msg}")

    def cancel(self):
        self._cancelled = True
        self._was_cancelled = True
        self.game_downloader.cancel()
        self.archive_extractor.cancel()
        self.emulator_manager.cancel()
        self.bios_manager.cancel()
        self.config_manager.cancel()


class InstallDialog(QDialog):
    """
    Основной диалог для отображения процесса установки.
    """

    installation_finished = pyqtSignal()

    def __init__(self, game_data: dict, project_root: Path, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.project_root = project_root
        self.dialog_is_finished = False
        self.installation_cancelled = False

        self.install_dir = Path(get_users_subpath("games")) / self.game_data.get('platform')
        self.install_dir.mkdir(parents=True, exist_ok=True)

        self.thread = None
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_value = 0
        self.is_indeterminate = False
        
        self.init_ui()
        self.start_installation()

    def init_ui(self):
        self.setWindowTitle("Установка игры")
        self.setFixedWidth(650)

        layout = QVBoxLayout()

        self.title_label = QLabel(f"<b>{self.game_data.get('title')}</b>", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.status_label = QLabel("Подготовка к установке...", self)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.log_output = QTextEdit(self)
        self.log_output.setReadOnly(True)
        # Скрываем лог-окно по умолчанию
        self.log_output.hide()
        layout.addWidget(self.log_output)

        button_layout = QHBoxLayout()
        # Новая кнопка для отображения/скрытия логов
        self.show_log_button = QPushButton("Лог установки", self)
        self.show_log_button.clicked.connect(self.toggle_log_visibility)
        button_layout.addWidget(self.show_log_button)

        self.cancel_button = QPushButton("Отмена", self)
        self.cancel_button.clicked.connect(self.on_cancel_button_clicked)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def start_installation(self):
        self.thread = InstallThread(self.game_data, self.install_dir, self.project_root)
        self.thread.progress_updated.connect(self.update_progress)
        self.thread.error_occurred.connect(self.handle_error)
        self.thread.finished.connect(self.on_thread_finished)
        self.thread.cancelled.connect(self.on_thread_cancelled)
        self.thread.set_indeterminate.connect(self.set_progress_indeterminate)
        self.thread.start()

    def update_progress(self, percentage: int, message: str):
        if not self.is_indeterminate:
            self.progress_bar.setValue(percentage)
        self.status_label.setText(message)
        self.log_output.append(message)

    def set_progress_indeterminate(self, indeterminate: bool):
        self.is_indeterminate = indeterminate
        if indeterminate:
            self.animation_timer.start(50)  # Обновление анимации каждые 50мс
        else:
            self.animation_timer.stop()
            self.progress_bar.setValue(self.progress_bar.value())

    def update_animation(self):
        # Анимация "пульсации" для неопределенного прогресса
        self.animation_value = (self.animation_value + 2) % 100
        self.progress_bar.setValue(self.animation_value)

    def handle_error(self, message: str):
        self.status_label.setText("Ошибка: " + message)
        self.log_output.append("ОШИБКА: " + message)
        QMessageBox.critical(self, "Ошибка установки", message)
        self.cancel_button.setEnabled(False)
        self.show_log_button.setEnabled(False)
        # Показываем лог при ошибке, чтобы пользователь сразу увидел детали
        self.log_output.show()

    def toggle_log_visibility(self):
        """
        Показывает или скрывает окно логов и подстраивает размер окна.
        """
        if self.log_output.isVisible():
            self.log_output.hide()
            self.show_log_button.setText("Показать лог")
        else:
            self.log_output.show()
            self.show_log_button.setText("Скрыть лог")
        self.adjustSize()

    def on_thread_finished(self, game_data):
        if self.installation_cancelled:
            self.progress_bar.setValue(0)
            self.status_label.setText("Установка отменена ❌")
        else:
            self.progress_bar.setValue(100)
            self.status_label.setText("Установка завершена! ✅")

            # Обновление статуса в библиотеке
            if hasattr(self.parent(), 'game_library'):
                self.parent().game_library.load_games()

            self.installation_finished.emit()

        # Меняем кнопку "Отмена" на "Закрыть"
        self.cancel_button.setText("Закрыть")
        self.cancel_button.setEnabled(True)
        self.dialog_is_finished = True
        self.animation_timer.stop()

    def on_thread_cancelled(self):
        self.installation_cancelled = True
        self.status_label.setText("Установка отменена ❌")
        self.log_output.append("❌ Установка отменена пользователем.")
        self.cancel_button.setText("Закрыть")
        self.cancel_button.setEnabled(True)
        self.dialog_is_finished = True
        self.animation_timer.stop()

    def on_cancel_button_clicked(self):
        # Проверяем, завершена ли установка
        if self.dialog_is_finished:
            # Если завершена, закрываем диалог
            self.accept()
            return

        reply = QMessageBox.question(self, "Отмена установки", "Вы уверены, что хотите отменить установку?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.cancel_installation()

    def cancel_installation(self):
        self.installation_cancelled = True
        self.status_label.setText("Отмена установки...")
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
        self.cancel_button.setEnabled(False)
        self.show_log_button.setEnabled(False)
        self.log_output.append("❌ Запрос на отмену установки...")
        self.animation_timer.stop()

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            reply = QMessageBox.question(self, "Отмена установки", "Установка еще выполняется. Вы уверены, что хотите выйти и отменить её?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.cancel_installation()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python install.py <game_data.json> <project_root>")
        sys.exit(1)

    try:
        with open(sys.argv[1], 'r') as f:
            game_data = json.load(f)
        app = QApplication(sys.argv)
        dialog = InstallDialog(game_data, Path(sys.argv[2]))
        dialog.exec()
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в главном приложении: {e}")
        sys.exit(1)
