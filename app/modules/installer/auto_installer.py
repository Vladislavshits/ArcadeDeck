# auto_installer.py
import sys
import os
import time
import argparse
import json
import logging
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from .emulator_manager import EmulatorManager
from .bios_manager import BIOSManager
from .config_manager import ConfigManager
from .game_downloader import GameDownloader

logger = logging.getLogger('Installer')
LOG_DIR = os.path.join(os.getcwd(), "logs")
LOG_FILE = os.path.join(LOG_DIR, "auto_install.log")
os.makedirs(LOG_DIR, exist_ok=True)


def log(message):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


class AutoInstaller(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, game_data: dict, install_dir: Path, project_root: Path, test_mode=True, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.install_dir = install_dir
        self.project_root = project_root
        self.test_mode = test_mode
        self.progress = 0
        self._should_pause = False
        self._should_stop = False
        self._is_paused = False
        self.downloader = None # Добавляем ссылку на GameDownloader

        self.log_handler = LoggingSignalHandler(self.progress_updated)
        logger.addHandler(self.log_handler)
        logger.setLevel(logging.INFO)

    def pause(self):
        self._should_pause = True
        if self.downloader:
            self.downloader.pause_download() # Предполагаем, что такой метод есть

    def resume(self):
        self._should_pause = False
        if self.downloader:
            self.downloader.resume_download() # Предполагаем, что такой метод есть

    def stop(self):
        self._should_stop = True
        if self.downloader:
            self.downloader.cancel_download() # Корректно вызываем отмену

    def check_pause(self):
        while self._should_pause:
            time.sleep(0.5)

    def check_stop(self):
        if self._should_stop:
            raise InterruptedError("Установка была отменена пользователем.")

    def run(self):
        start_time = time.time()
        game_info = self.game_data

        try:
            self._update_progress(10, "Этап 1: Проверка эмулятора")
            self.check_pause()
            logger.info("Начинаем установку...")

            emulator_manager = EmulatorManager(self.project_root, self.test_mode)
            if not emulator_manager.ensure_emulator(game_info['preferred_emulator']):
                raise RuntimeError("Ошибка эмулятора")

            self._update_progress(25, "Этап 2: Проверка BIOS")
            self.check_pause()
            self.check_stop()

            bios_manager = BIOSManager(self.project_root)
            if not bios_manager.ensure_bios_for_platform(game_info['platform']):
                raise RuntimeError("Ошибка BIOS")

            self._update_progress(50, "Этап 3: Конфиги")
            self.check_pause()
            self.check_stop()
            config_manager = ConfigManager(self.project_root, log, self.test_mode)
            if not config_manager.apply_config(game_info['id'], game_info['platform']):
                raise RuntimeError("Ошибка конфигов")

            self._update_progress(75, "Этап 4: Скачивание")
            self.check_pause()
            self.check_stop()

            # Создаем экземпляр GameDownloader
            self.downloader = GameDownloader(self.game_data, self.install_dir)

            # Подключаем сигналы GameDownloader напрямую к сигналам AutoInstaller
            self.downloader.progress_updated.connect(self.progress_updated.emit)
            self.downloader.error_occurred.connect(self.error_occurred.emit)
            self.downloader.finished.connect(self.finished.emit)

            # Теперь вызываем run() в этом же потоке
            self.downloader.run()

        except InterruptedError as e:
            log(f"❌ Установка отменена: {str(e)}")
            self.error_occurred.emit(str(e))
        except Exception as e:
            log(f"❌ Критическая ошибка установки: {str(e)}")
            self.error_occurred.emit(str(e))
            # Важно: при ошибке мы не вызываем self.finished.emit()

    def _update_progress(self, value, text):
        logger.info(text)
        self.progress = value
        self.progress_updated.emit(value, text)

    def _handle_error(self, message):
        logger.error(f"❌ {message}")
        self.error_occurred.emit(message)


class LoggingSignalHandler(logging.Handler, QObject):
    log_signal = pyqtSignal(int, str)

    def __init__(self, ui_signal: pyqtSignal):
        super().__init__()
        QObject.__init__(self)
        self.log_signal.connect(ui_signal.emit)

    def emit(self, record):
        if record.levelno >= logging.INFO:
            self.log_signal.emit(0, record.getMessage())
