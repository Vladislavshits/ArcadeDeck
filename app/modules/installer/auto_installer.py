# ==============================================================================
# ФАЙЛ: auto_installer.py
# ==============================================================================
import sys
import os
import time
import argparse
import json
import logging
from pathlib import Path
from typing import Optional
import shutil
import zipfile
import subprocess

from .emulator_manager import EmulatorManager
from .bios_manager import BIOSManager
from .config_manager import ConfigManager
from .game_downloader import GameDownloader
from .archive_extractor import ArchiveExtractor

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

class LoggingSignalHandler(logging.Handler):
    def __init__(self, signal_emitter):
        super().__init__()
        self.signal_emitter = signal_emitter

    def emit(self, record):
        message = self.format(record)
        self.signal_emitter.emit(0, message)

class AutoInstaller:
    """
    Класс для управления процессом автоматической установки.
    Отвечает за последовательное выполнение всех этапов установки (эмулятор, BIOS, игра, конфиг)
    и передачу информации о прогрессе.
    """
    def __init__(self, game_data: dict, install_dir: Path, project_root: Path, test_mode: bool = False):
        self.game_data = game_data
        self.install_dir = install_dir
        self.project_root = project_root
        self.test_mode = test_mode
        self.emulator_manager = EmulatorManager(self.project_root, self.test_mode)
        self.bios_manager = BIOSManager(self.project_root)
        self.game_downloader = GameDownloader(self.game_data, self.install_dir)
        self.archive_extractor = ArchiveExtractor(self.game_data, self.install_dir)  # Новый объект
        self.config_manager = ConfigManager(self.project_root)
        self._should_stop = False

    def run(self):
        """
        Запускает полный цикл установки.
        """
        try:
            # Этап 1: Проверка и установка эмулятора
            log("🔧 Этап 1: Проверка и установка эмулятора...")
            if not self.emulator_manager.ensure_emulator(self.game_data.get('preferred_emulator')):
                log("❌ Не удалось установить эмулятор. Установка отменена.")
                return False

            # Этап 2: Проверка и установка BIOS
            log("🔧 Этап 2: Проверка и установка BIOS...")
            if not self.bios_manager.ensure_bios_for_platform(self.game_data.get('platform')):
                log("❌ Не удалось установить BIOS. Установка отменена.")
                return False

            # Этап 3: Загрузка игры
            log("🔧 Этап 3: Загрузка игры...")
            if not self.game_downloader.run():
                log("❌ Не удалось скачать игру. Установка отменена.")
                return False

            # Этап 4: Обработка файлов (распаковка если нужно)
            log("🔧 Этап 4: Обработка скачанных файлов...")
            if not self.archive_extractor.run():
                log("❌ Ошибка при обработке файлов. Установка отменена.")
                return False

            # Этап 5: Установка конфигов
            log("🔧 Этап 5: Установка конфигов...")
            self.config_manager.apply_config(self.game_data.get('id'), self.game_data.get('platform'))

            log("✅ Установка успешно завершена.")
            return True

        except Exception as e:
            log(f"Установка прервана из-за непредвиденной ошибки: {e}")
            return False

    def cancel_installation(self):
        self._should_stop = True
        self.game_downloader.cancel_download()
        self.archive_extractor.cancel()  # Новый вызов
        log("Установка отменена пользователем.")

    def _unpack_game(self, game_file_path: Path):
        """Распаковывает скачанный игровой файл."""
        if self._should_stop:
            raise InterruptedError("Распаковка отменена.")

        if zipfile.is_zipfile(game_file_path):
            logger.info("🔄 Распаковываю ZIP-архив...")
            with zipfile.ZipFile(game_file_path, 'r') as zip_ref:
                zip_ref.extractall(self.install_dir)
            os.remove(game_file_path)
            logger.info("✅ Распаковка завершена.")
        else:
            logger.warning("⚠️ Файл не является ZIP-архивом, распаковка пропущена.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Автоматический установщик игр для PixelDeck.")
    parser.add_argument("game_id", help="ID игры из файла registry_games.json")
    parser.add_argument("project_root", help="Корневая директория проекта")
    parser.add_argument("--test-mode", action="store_true", help="Включить тестовый режим (без реальной установки)")

    args = parser.parse_args()

    # Загружаем данные игры из реестра
    registry_path = Path(args.project_root) / 'app' / 'registry' / 'registry_games.json'
    game_data = None
    if registry_path.exists():
        with open(registry_path, 'r', encoding='utf-8') as f:
            registry = json.load(f)
            for game in registry:
                if game['id'] == args.game_id:
                    game_data = game
                    break

    if not game_data:
        print(f"Ошибка: Игра с ID '{args.game_id}' не найдена в реестре.")
        sys.exit(1)

    # Определяем директорию для установки
    install_dir = Path(args.project_root) / 'users' / 'games' / game_data.get('platform') / game_data.get('id')
    install_dir.mkdir(parents=True, exist_ok=True)

    installer = AutoInstaller(game_data, install_dir, Path(args.project_root), args.test_mode)
    if installer.run():
        print("Установка завершена успешно!")
    else:
        print("Установка завершилась с ошибкой.")
