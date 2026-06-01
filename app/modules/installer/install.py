import sys
import json
import logging
import time
import re
import shutil
from enum import Enum, auto

from pathlib import Path
from typing import Optional, Dict
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel,
    QProgressBar, QPushButton, QHBoxLayout, QMessageBox,
    QTextEdit, QFrame, QScrollArea, QSizePolicy, QWidget, QSpacerItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt6.QtGui import QFont

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

# Импорт модуля навигации
from navigation import NavigationLayer
from app.modules.ui.message_dialog import (
    show_error,
    MessageDialogResult,
    create_install_cancel_question,
)

# Логирование модуля
logger = logging.getLogger('Система установки')


class InstallStage(Enum):
    CHECK_EMULATOR = auto()
    CHECK_BIOS = auto()
    DOWNLOAD = auto()
    EXTRACT = auto()
    CONFIGURE = auto()
    CREATE_LAUNCHER = auto()
    FINISH = auto()

class InstallationController(QObject):
    cancelled = pyqtSignal()
    progress_updated = pyqtSignal(int, str)
    stage_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._cancel_requested = False
        self.current_task = None
        self.all_tasks = []

    def request_cancellation(self):
        if self._cancel_requested:
            return
        self._cancel_requested = True
        logger.info("🛑 ПОЛЬЗОВАТЕЛЬ ЗАПРОСИЛ ОТМЕНУ УСТАНОВКИ")
        for task in self.all_tasks:
            if task and hasattr(task, 'isRunning') and task.isRunning():
                logger.info(f"🛑 Останавливаем задачу: {task.__class__.__name__}")
                if hasattr(task, 'cancel'):
                    task.cancel()
                elif hasattr(task, 'terminate'):
                    task.terminate()
        self.cancelled.emit()

    def is_cancelled(self) -> bool:
        return self._cancel_requested

    def set_current_task(self, task):
        self.current_task = task
        if task and task not in self.all_tasks:
            self.all_tasks.append(task)
        if task:
            self.stage_changed.emit(task.__class__.__name__)

    def register_task(self, task):
        if task and task not in self.all_tasks:
            self.all_tasks.append(task)

    def reset(self):
        self._cancel_requested = False
        self.current_task = None
        self.all_tasks = []


class InstallThread(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    cancelled = pyqtSignal()
    set_indeterminate = pyqtSignal(bool)
    stage_changed = pyqtSignal(str)      # для статического заголовка этапа
    details_updated = pyqtSignal(str)    # для динамической строки

    def __init__(self, game_data: dict, install_dir: Path, project_root: Path, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.project_root = project_root
        self.is_user_game = game_data.get('is_user_game', False)
        self.stage_config = None
        self.download_range = (0, 0)
        self.extraction_range = (0, 0)
        source = game_data.get('source_path')
        self.user_source_path = Path(source) if self.is_user_game and source else None

        if self.is_user_game:
            logger.info(f"🎮 Установка пользовательской игры: {game_data.get('title')}")
            logger.info(f"📁 Источник: {self.user_source_path}")
        else:
            logger.info(f"🎮 Установка игры: {game_data.get('title')}")

        self.controller = InstallationController()
        self.controller.progress_updated.connect(self.progress_updated)
        self.controller.cancelled.connect(self._on_controller_cancelled)
        self._was_cancelled = False

        self.installed_games_file = Path(get_users_path()) / 'installed_games.json'
        self.extracted_files = []
        self.game_config = None
        self.platform_configs = {}
        self.bios_registry = {}
        self.launch_profiles = {}
        self.platform_aliases = {}

        raw_title = game_data.get('title', 'Unknown Game').strip()
        safe_title = raw_title
        platform = game_data.get('platform', 'Unknown')
        self.install_dir = Path(get_users_subpath("games")) / platform / safe_title
        self.install_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Игра будет установлена в: {self.install_dir}")

        self._load_all_configs()

        self.emulator_manager = EmulatorManager(self.project_root, test_mode=False)
        self.bios_manager = BIOSManager(self.project_root)
        self.game_downloader = GameDownloader(self.game_data, self.install_dir)
        self.archive_extractor = ArchiveExtractor(self.game_data, self.install_dir)
        self.config_manager = ConfigManager(self.project_root)
        self.launch_manager = LaunchManager(self.project_root)

        self.controller.register_task(self.emulator_manager)
        self.controller.register_task(self.bios_manager)
        self.controller.register_task(self.game_downloader)
        self.controller.register_task(self.archive_extractor)
        self.controller.register_task(self.config_manager)

    def _load_all_configs(self):
        """Загружаем все реестры при инициализации"""
        logger.info("📚 Загрузка всех конфигурационных реестров...")

        # Диагностика путей
        logger.info(f"🔍 Project root: {self.project_root}")

        self.platform_configs = self._load_all_platform_configs()
        self.bios_registry = self._load_bios_registry()
        self.launch_profiles = self._load_launch_profiles()
        self.platform_aliases = self._load_platform_aliases()

        logger.info(f"✅ Загружено: {len(self.platform_configs)} платформ, "
                f"{len(self.bios_registry)} BIOS записей, "
                f"{len(self.launch_profiles)} профилей запуска")

        # Диагностика содержимого
        logger.info(f"📋 Ключи launch_profiles: {list(self.launch_profiles.keys())}")

    def _load_all_platform_configs(self) -> dict:
        """Загружаем конфиги всех платформ"""
        platforms_dir = self.project_root / 'app' / 'registry' / 'platforms'
        configs = {}

        if not platforms_dir.exists():
            logger.error(f"❌ Директория платформ не найдена: {platforms_dir}")
            return configs

        for platform_dir in platforms_dir.iterdir():
            if platform_dir.is_dir():
                config = self._load_platform_config(platform_dir.name)
                if config:
                    configs[platform_dir.name] = config
                    logger.info(f"✅ Загружена конфигурация платформы: {platform_dir.name}")

        return configs

    def _load_platform_config(self, platform_name: str) -> dict:
        """Загружаем конфиг конкретной платформы"""
        config_file = self.project_root / 'app' / 'registry' / 'platforms' / platform_name / 'config.py'

        if not config_file.exists():
            logger.warning(f"⚠️ Конфиг платформы {platform_name} не найден: {config_file}")
            return None

        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(f"{platform_name}_config", config_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, 'get_config'):
                config = module.get_config()
                config['id'] = platform_name
                return config
            else:
                logger.warning(f"⚠️ Конфиг платформы {platform_name} не содержит функцию get_config")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки конфига платформы {platform_name}: {e}")
            return None

    def _load_bios_registry(self) -> dict:
        """Загружаем реестр BIOS"""
        registry_path = self.project_root / 'app' / 'registry' / 'registry_bios.json'
        if registry_path.exists():
            try:
                with open(registry_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки BIOS реестра: {e}")
        return {}

    def _load_launch_profiles(self) -> dict:
        """Загружаем профили запуска"""
        profiles_path = self.project_root / 'app' / 'registry' / 'registry_launch_profiles.json'
        if profiles_path.exists():
            try:
                with open(profiles_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки профилей запуска: {e}")
        return {}

    def _load_platform_aliases(self) -> dict:
        """Загружаем алиасы платформ"""
        aliases_path = self.project_root / 'app' / 'registry' / 'registry_platform_aliases.json'
        if aliases_path.exists():
            try:
                with open(aliases_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('platform_aliases', {})
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки алиасов: {e}")
        return {}

    def get_complete_game_config(self) -> dict:
        """ГЛАВНЫЙ МЕТОД - собирает ВСЮ конфигурацию игры"""
        if self.game_config:
            return self.game_config

        logger.info(f"🎯 Собираем полную конфигурацию для: {self.game_data.get('title')}")

        self.game_config = {
            'game_data': self.game_data,
            'emulator_config': self._get_emulator_config(),
            'bios_config': self._get_bios_config(),
            'platform_config': self._get_platform_config(),
            'launch_config': self._get_launch_config(),
            'installation_paths': self._get_installation_paths(),
            'supported_formats': self._get_supported_formats()
        }

        # Диагностика
        self._debug_config()

        return self.game_config

    def _get_emulator_config(self) -> dict:
        """Находим конфиг эмулятора для игры"""
        game_title = self.game_data.get('title', 'Unknown Game')

        # 1. Ищем по platform_module
        platform_module = self.game_data.get('platform_module')
        if platform_module and platform_module in self.platform_configs:
            logger.info(f"🔍 Найден эмулятор по platform_module '{platform_module}' для '{game_title}'")
            return self.platform_configs[platform_module]

        # 2. Ищем по platform
        platform = self.game_data.get('platform', '')
        if platform and platform in self.platform_configs:
            logger.info(f"🔍 Найден эмулятор по platform '{platform}' для '{game_title}'")
            return self.platform_configs[platform]

        # 3. Ищем через алиасы
        platform_lower = platform.lower()
        for alias, actual_platform in self.platform_aliases.items():
            if alias.lower() == platform_lower and actual_platform in self.platform_configs:
                logger.info(f"🔍 Найден эмулятор по алиасу '{platform}' -> '{actual_platform}' для '{game_title}'")
                return self.platform_configs[actual_platform]

        # 4. Проверяем preferred_emulator
        preferred_emulator = self.game_data.get('preferred_emulator')
        if preferred_emulator:
            preferred_lower = preferred_emulator.lower()
            for alias, actual_platform in self.platform_aliases.items():
                if alias.lower() == preferred_lower and actual_platform in self.platform_configs:
                    logger.info(f"🔍 Найден эмулятор по preferred_emulator '{preferred_emulator}' -> '{actual_platform}' для '{game_title}'")
                    return self.platform_configs[actual_platform]

        logger.warning(f"⚠️ Не удалось определить эмулятор для '{game_title}'")
        return {}

    def _get_bios_config(self) -> dict:
        """Получаем конфиг BIOS - ТЕПЕРЬ ПО ЭМУЛЯТОРУ"""
        # Сначала получаем конфиг эмулятора
        emulator_config = self._get_emulator_config()
        emulator_name = emulator_config.get('name', '').lower()

        # Ищем BIOS конфиг по имени эмулятора
        bios_config = self.bios_registry.get(emulator_name, {})

        if bios_config:
            logger.info(f"🔧 Найден BIOS конфиг для эмулятора '{emulator_name}'")
        else:
            logger.info(f"🔧 BIOS не требуется для эмулятора '{emulator_name}'")
        return bios_config

    def _get_platform_config(self) -> dict:
        """Получаем конфиг платформы"""
        platform = self.game_data.get('platform')
        platform_config = self.platform_configs.get(platform, {})
        if platform_config:
            logger.info(f"📁 Найден конфиг платформы '{platform}'")
        else:
            logger.warning(f"📁 Конфиг платформы '{platform}' не найден")
        return platform_config

    def _get_launch_config(self) -> dict:
        """Получаем конфиг запуска - ГИБКИЙ ПОИСК"""
        emulator_name = self.game_data.get('preferred_emulator', '').lower()

        logger.info(f"🔍 Поиск профиля запуска для: '{emulator_name}'")
        logger.info(f"📋 Доступные профили: {list(self.launch_profiles.keys())}")

        # 1. Прямой поиск по ключу
        if emulator_name in self.launch_profiles:
            logger.info(f"✅ Найден профиль запуска по ключу: '{emulator_name}'")
            return self.launch_profiles[emulator_name]

        # 2. Поиск по полю 'name' (регистронезависимый)
        for profile_key, profile_data in self.launch_profiles.items():
            if profile_data.get('name', '').lower() == emulator_name:
                logger.info(f"✅ Найден профиль запуска по name: '{profile_key}' -> '{emulator_name}'")
                return profile_data

        # 3. Fallback: поиск по platform_module
        platform_module = self.game_data.get('platform_module', '').lower()
        if platform_module in self.launch_profiles:
            logger.info(f"✅ Найден профиль запуска по platform_module: '{platform_module}'")
            return self.launch_profiles[platform_module]

        logger.warning(f"🚀 Профиль запуска для эмулятора '{emulator_name}' не найден")
        logger.warning(f"🔍 Искали в: {list(self.launch_profiles.keys())}")
        return {}

    def _get_installation_paths(self) -> dict:
        """Генерируем пути установки"""
        from core import get_users_subpath

        platform = self.game_data.get('platform')
        game_id = self.game_data.get('id')

        paths = {
            'install_dir': Path(get_users_subpath("games")) / platform,
            'config_dir': Path(get_users_subpath("configs")) / platform,
            'bios_dir': Path(get_users_subpath("bios")) / platform,
            'images_dir': Path(get_users_subpath("images")) / platform / game_id,
            'launchers_dir': Path(get_users_subpath("launchers"))
        }

        logger.info(f"📂 Пути установки: {paths}")
        return paths

    def _get_supported_formats(self) -> list:
        """Получаем поддерживаемые форматы"""
        platform_config = self._get_platform_config()
        formats = platform_config.get('supported_formats', [])
        logger.info(f"📄 Поддерживаемые форматы: {formats}")
        return formats

    def _debug_config(self):
        """Выводим диагностику конфигурации"""
        config = self.game_config
        logger.info("=== 🎯 ДИАГНОСТИКА КОНФИГУРАЦИИ ИГРЫ ===")
        logger.info(f"🎮 Игра: {config['game_data'].get('title')}")
        logger.info(f"🆔 ID: {config['game_data'].get('id')}")
        logger.info(f"🎯 Платформа: {config['game_data'].get('platform')}")
        logger.info(f"⚙️ Эмулятор: {config['emulator_config'].get('name', 'N/A')}")
        logger.info(f"📁 Форматы: {config['supported_formats']}")
        logger.info(f"🔧 BIOS: {'Требуется' if config['bios_config'] else 'Не требуется'}")
        logger.info(f"🚀 Профиль запуска: {'Найден' if config['launch_config'] else 'Не найден'}")
        logger.info("=== КОНЕЦ ДИАГНОСТИКИ ===")

    def get_installed_games(self):
        """Возвращает словарь установленных игр"""
        if self.installed_games_file.exists():
            try:
                with open(self.installed_games_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _find_primary_game_path(self) -> Path:
        """Умно определяет, что передавать в эмулятор: ISO, PKG, папку и т.д."""
        priority_extensions = [
            '.cue', '.iso', '.chd', '.cso', '.wbfs', '.rvz', '.nsp', '.xci',
            '.pkg', '.dol', '.gcm', '.bin', '.img'
        ]

        for ext in priority_extensions:
            matches = list(self.game_install_dir.rglob(f'*{ext}'))
            if matches:
                return matches[0]  # берём первый найденный

        # Если ничего не нашли — значит это folder-based эмулятор (RPCS3, Yuzu, Dolphin и т.д.)
        return self.game_install_dir

    def _on_controller_cancelled(self):
        """Обработчик отмены от контроллера"""
        logger.info("Получен сигнал отмены от контроллера")
        self._was_cancelled = True

        # Сигнализируем об отмене
        self.cancelled.emit()

    def _get_stage_config(self):
        """Единая конфигурация этапов для всех типов установки."""
        return {
            'emulator_progress': 5,
            'emulator_msg': "Проверка эмулятора...",
            'bios_start': 30,
            'bios_end': 35,
            'bios_msg': "Проверка системных файлов...",
            'bios_warn_msg': "⚠️ BIOS не установлен, продолжаем...",
            'bios_ok_msg': "✅ Подготовка прошла успешно",
            'bios_skip_msg': "✅ системные файлы не требуются",
            'download_range': (40, 70),      # от 40% до 70% общего прогресса
            'download_start_msg': "Загрузка игры...",
            'extraction_range': (70, 85),    # от 70% до 85% общего прогресса
            'extraction_start_msg': "Распаковка файлов...",
            'config_progress': 85,
            'config_msg': "Настройка конфигурации...",
            'launcher_progress': 90,
            'launcher_msg': "Создание ярлыка запуска...",
            'final_progress': 100,
            'final_msg': "✅ Игра успешно добавлена в библиотеку!",
        }


    def _check_emulator(self):
        if self.controller.is_cancelled():
            self._cancel_and_exit()
            return

        cfg = self.stage_config
        self.progress_updated.emit(cfg['emulator_progress'], cfg['emulator_msg'])

        emulator_config = self.game_config['emulator_config']
        if not emulator_config:
            self.error_occurred.emit("Не удалось определить эмулятор.")
            return

        emulator_id = emulator_config.get('id')
        if not self.emulator_manager.ensure_emulator(emulator_id, emulator_config):
            self.error_occurred.emit("Ошибка при установке эмулятора.")
            return

        self._check_bios()

    def _check_bios(self):
        if self.controller.is_cancelled():
            self._cancel_and_exit()
            return

        cfg = self.stage_config
        self.progress_updated.emit(cfg['bios_start'], cfg['bios_msg'])

        bios_config = self.game_config['bios_config']
        platform = self.game_config['game_data'].get('platform')

        if bios_config:
            bios_result = self.bios_manager.ensure_bios_for_platform(platform, bios_config)
            if not bios_result:
                self.progress_updated.emit(cfg['bios_end'], cfg['bios_warn_msg'])
            else:
                self.progress_updated.emit(cfg['bios_end'], cfg['bios_ok_msg'])
        else:
            self.progress_updated.emit(cfg['bios_end'], cfg['bios_skip_msg'])

        # Если пользовательская игра с локальным источником (не торрент) – сразу обрабатываем локальный источник
        if self.is_user_game and not self.game_data.get('torrent_url'):
            self._determine_source_and_start()
        else:
            self._start_download()

    def _start_download(self):
        if self.controller.is_cancelled():
            self._cancel_and_exit()
            return

        cfg = self.stage_config
        start_percent, end_percent = cfg['download_range']
        self.download_range = (start_percent, end_percent)
        self.progress_updated.emit(start_percent, cfg['download_start_msg'])

        self.game_downloader.progress_updated.connect(self._on_download_progress)
        self.game_downloader.finished.connect(self._on_download_finished)
        self.game_downloader.error_occurred.connect(self._on_download_error)

        self.controller.set_current_task(self.game_downloader)
        self.game_downloader.start()

    def _on_download_progress(self, percent, msg):
        start, end = self.download_range
        scaled = start + int(percent * (end - start) / 100)
        self.progress_updated.emit(scaled, msg)

    def _on_download_finished(self):
        self.game_downloader.progress_updated.disconnect(self._on_download_progress)
        self.game_downloader.finished.disconnect(self._on_download_finished)
        self.game_downloader.error_occurred.disconnect(self._on_download_error)

        if self.controller.is_cancelled():
            self._cancel_and_exit()
            return

        # Для пользовательских игр после скачивания нужно определить тип и путь
        if self.is_user_game:
            downloaded = self.game_downloader.get_downloaded_file_path()
            if not downloaded or not downloaded.exists():
                self.error_occurred.emit("Скачанный файл не найден.")
                return
            if downloaded.is_file():
                self.user_source_type = 'archive' if self._is_archive_file(downloaded) else 'file'
            else:
                self.user_source_type = 'folder'
            self.user_source_path = downloaded
            self._handle_local_source()
        else:
            # Каталоговая игра – сразу распаковка
            self._start_extraction()

    def _on_download_error(self, err_msg):
        self.game_downloader.progress_updated.disconnect(self._on_download_progress)
        self.game_downloader.finished.disconnect(self._on_download_finished)
        self.game_downloader.error_occurred.disconnect(self._on_download_error)
        self.error_occurred.emit(f"Ошибка загрузки: {err_msg}")

    def _start_extraction(self):
        if self.controller.is_cancelled():
            self._cancel_and_exit()
            return

        cfg = self.stage_config
        start_percent, end_percent = cfg['extraction_range']
        self.extraction_range = (start_percent, end_percent)
        self.progress_updated.emit(start_percent, cfg['extraction_start_msg'])

        self.archive_extractor.progress_updated.connect(self._on_extraction_progress)
        self.archive_extractor.finished.connect(self._on_extraction_finished)
        self.archive_extractor.error_occurred.connect(self._on_extraction_error)
        self.archive_extractor.files_extracted.connect(self.on_files_extracted)

        self.controller.set_current_task(self.archive_extractor)
        self.archive_extractor.start()

    def _on_extraction_progress(self, percent, msg):
        start, end = self.extraction_range
        scaled = start + int(percent * (end - start) / 100)
        self.progress_updated.emit(scaled, f"📦 {msg}")

    def _on_extraction_finished(self):
        self.archive_extractor.progress_updated.disconnect(self._on_extraction_progress)
        self.archive_extractor.finished.disconnect(self._on_extraction_finished)
        self.archive_extractor.error_occurred.disconnect(self._on_extraction_error)
        self.archive_extractor.files_extracted.disconnect(self.on_files_extracted)

        if self.controller.is_cancelled():
            self._cancel_and_exit()
            return

        self._normalize_game_folder_after_extraction()
        self._apply_configs()

    def _on_extraction_error(self, err_msg):
        self.archive_extractor.progress_updated.disconnect(self._on_extraction_progress)
        self.archive_extractor.finished.disconnect(self._on_extraction_finished)
        self.archive_extractor.error_occurred.disconnect(self._on_extraction_error)
        self.error_occurred.emit(f"Ошибка распаковки: {err_msg}")

    def _apply_configs(self):
        if self.controller.is_cancelled():
            self._cancel_and_exit()
            return

        cfg = self.stage_config
        self.progress_updated.emit(cfg['config_progress'], cfg['config_msg'])

        try:
            self.config_manager.apply_config(
                self.game_data.get('id'),
                self.game_data.get('platform'),
                self.game_data.get('preferred_emulator')
            )
        except Exception as e:
            logger.error(f"Ошибка конфигов: {e}")

        self.progress_updated.emit(cfg['launcher_progress'], cfg['launcher_msg'])

        game_file = self.find_game_file()
        if not game_file or not game_file.exists():
            self.error_occurred.emit("Не удалось найти файл игры после установки")
            return

        success = self.launch_manager.create_launcher(self.game_data, game_file)
        if not success:
            self.error_occurred.emit("Не удалось создать лаунчер для игры")
            return

        # Регистрация игры
        launcher_path = self.launch_manager.scripts_dir / f"{self.game_data.get('id')}.sh"
        cover_path = self.launch_manager._get_cover_path(self.game_data)
        installed_games = self.get_installed_games()
        game_info = {
            'title': self.game_data.get('title'),
            'platform': self.game_data.get('platform'),
            'install_path': str(game_file.absolute()),
            'launcher_path': str(launcher_path.absolute()),
            'install_date': time.time(),
            'cover_path': cover_path
        }
        installed_games[self.game_data.get('id')] = game_info
        with open(self.installed_games_file, 'w', encoding='utf-8') as f:
            json.dump(installed_games, f, ensure_ascii=False, indent=2)

        self.progress_updated.emit(cfg['final_progress'], cfg['final_msg'])
        self.finished.emit(self.game_data)

    def _determine_source_and_start(self):
        torrent_url = self.game_data.get('torrent_url')
        source_path = self.game_data.get('source_path')

        if torrent_url:
            self.user_source_type = 'torrent'
            self.user_source_path = torrent_url
            self._start_download()
        elif source_path:
            src_path = Path(source_path)
            if src_path.is_file():
                self.user_source_type = 'archive' if self._is_archive_file(src_path) else 'file'
            elif src_path.is_dir():
                self.user_source_type = 'folder'
            else:
                self.error_occurred.emit("Источник не найден.")
                return
            self.user_source_path = src_path
            self._handle_local_source()
        else:
            self.error_occurred.emit("Не указан источник игры.")

    def _copy_folder(self):
        src = self.user_source_path
        dest = self.install_dir / src.name

        # Если исходная папка уже внутри install_dir – не копируем
        try:
            if src.resolve().is_relative_to(self.install_dir.resolve()):
                logger.info(f"Папка уже внутри install_dir: {src}")
                self.install_dir = src
                self._apply_configs()
                return
        except AttributeError:
            # fallback для Python <3.9
            if self.install_dir.resolve() in src.resolve().parents:
                self.install_dir = src
                self._apply_configs()
                return

        self.progress_updated.emit(70, "Копирование папки...")
        shutil.copytree(src, dest, dirs_exist_ok=True)
        self.install_dir = dest
        self.progress_updated.emit(75, "Папка скопирована")
        self._apply_configs()

    def _copy_file(self):
        src = self.user_source_path
        dest = self.install_dir / src.name

        # Если файл уже на месте – не копируем
        if src.resolve() == dest.resolve():
            logger.info(f"Файл уже на месте: {dest}")
            self._apply_configs()
            return

        self.progress_updated.emit(70, "Копирование файла...")
        shutil.copy2(src, dest)
        self.progress_updated.emit(75, "Файл скопирован")
        self._apply_configs()

    def _handle_local_source(self):
        if self.controller.is_cancelled():
            self._cancel_and_exit()
            return

        if self.user_source_type == 'archive':
            self._start_extraction()
        elif self.user_source_type == 'folder':
            self._copy_folder()
        elif self.user_source_type == 'file':
            self._copy_file()
        else:
            self.error_occurred.emit("Неизвестный тип источника.")

    def _is_archive_file(self, file_path: Path) -> bool:
        """Проверяет, является ли файл архивом"""
        # Используем логику из ArchiveExtractor
        try:
            from .archive_extractor import ArchiveExtractor
            return ArchiveExtractor._is_archive_file(file_path)
        except:
            # Fallback проверка
            archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'}
            return file_path.suffix.lower() in archive_extensions

    def _copy_file_with_progress(self, src: Path, dst: Path, progress_base: int, progress_range: int):
        """Копирует файл с отображением прогресса"""
        try:
            total_size = src.stat().st_size
            copied = 0

            with open(src, 'rb') as f_src, open(dst, 'wb') as f_dst:
                while chunk := f_src.read(8192):
                    # Проверка отмены
                    if self.controller.is_cancelled():
                        return False

                    f_dst.write(chunk)
                    copied += len(chunk)

                    # Обновляем прогресс каждые 1%
                    if total_size > 0 and (copied * 100 // total_size) != ((copied - len(chunk)) * 100 // total_size):
                        progress = progress_base + int((copied / total_size) * progress_range)
                        mb_copied = copied / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)

                        self.progress_updated.emit(
                            progress,
                            f"📋 Копирование: {mb_copied:.1f}MB / {mb_total:.1f}MB"
                        )

            logger.info(f"✅ Файл скопирован: {src.name} → {dst.name}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка копирования файла: {e}")
            return False

    def _find_main_file_in_folder(self, folder: Path, config: dict) -> Optional[Path]:
        """Находит главный файл игры в папке"""
        supported_formats = config.get('supported_formats', [])

        if not supported_formats:
            # Стандартные форматы по умолчанию
            supported_formats = ['.iso', '.bin', '.cue', '.chd', '.pkg', '.zip', '.7z', '.rar']

        # Ищем по расширениям
        for fmt in supported_formats:
            files = list(folder.rglob(f"*{fmt}"))
            if files:
                # Выбираем самый большой файл
                return max(files, key=lambda f: f.stat().st_size)

        # Ищем по ключевым именам
        key_names = ['eboot.bin', 'game.bin', 'disc.bin', 'main.bin', 'default.xex', 'default.elf']
        for name in key_names:
            for file_path in folder.rglob(name):
                if file_path.exists():
                    return file_path

        # Если ничего не нашли, возвращаем саму папку
        return folder

    def run(self):
        try:
            self.stage_config = self._get_stage_config()
            self.game_config = self.get_complete_game_config()
            self._check_emulator()
        except Exception as e:
            logger.error(f"❌ Непредвиденная ошибка: {e}")
            self.error_occurred.emit(str(e))

    def _cancel_and_exit(self):
        if not self._was_cancelled:
            self._was_cancelled = True
            self.cancelled.emit()

    def _normalize_game_folder_after_extraction(self):
        """
        После распаковки архива почти всегда есть вложенная папк игр.
        Этот метод удаляет эту вложенную папку, перенося содержимое наверх
        """
        if not self.install_dir.exists():
            return

        items = list(self.install_dir.iterdir())
        if len(items) != 1:
            logger.info("Структура папки нормальная — оставляем как есть")
            return

        inner = items[0]
        if not inner.is_dir():
            return

        logger.info(f"Обнаружена вложенная папка — поднимаем содержимое: {inner.name}")

        # Перемещаем всё из inner → install_dir
        for item in inner.iterdir():
            target = self.install_dir / item.name
            if target.exists():
                if item.is_dir() and target.is_dir():
                    # Если конфликт папок — рекурсивно объединяем
                    for sub in item.rglob('*'):
                        dest = target / sub.relative_to(item)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        if sub.is_file():
                            shutil.move(str(sub), dest)
                    # После слияния удаляем исходную папку
                    try:
                        item.rmdir()
                    except:
                        pass
                else:
                    logger.warning(f"Конфликт имени: {item.name} — пропускаем")
            else:
                shutil.move(str(item), target)

        # Удаляем теперь пустую вложенную папку
        try:
            inner.rmdir()
            logger.info("Вложенная папка успешно удалена")
        except OSError as e:
            if e.errno == 39:  # Directory not empty
                logger.error(f"Не удалось удалить папку {inner} — она не пуста! Содержимое:")
                for x in inner.rglob('*'):
                    logger.error(f"  → {x}")
            else:
                raise

    def on_files_extracted(self, files_list):
        """Сохраняем список распакованных файлов"""
        self.extracted_files = files_list
        logger.info(f"📋 Получен список распакованных файлов: {[f.name for f in files_list]}")

    def find_game_file(self):
        """Находит файл игры с улучшенной логикой для PS3"""
        try:
            platform_id = self.game_data.get('platform')
            game_id = self.game_data.get('id', '').lower()
            game_type = self.game_data.get('game_type', 'unknown')

            logger.info(f"🔍 Поиск файлов игры для платформы: {platform_id}")
            logger.info(f"🎮 ID игры: {game_id}, тип из JSON: {game_type}")

            # === Логика для игр PS3 ===
            if platform_id.upper() == 'PS3':
                return self._find_ps3_game_file(game_id, game_type)

            # Логика для других платформ
            return self._find_standard_game_file(platform_id, game_id)

        except Exception as e:
            logger.error(f"❌ Ошибка при поиске файла игры: {e}")
            return None

    def _find_ps3_game_file(self, game_id: str, game_type: str) -> Optional[Path]:
        """Находит файлы для PS3 игры с рекурсивным поиском"""
        try:
            logger.info(f"🎮 Поиск PS3 игры типа: {game_type}")

            # Рекурсивно ищем все возможные файлы PS3
            ps3_files = []

            for file_path in self.install_dir.rglob('*'):
                if file_path.is_file():
                    filename_lower = file_path.name.lower()

                    # Ищем EBOOT.BIN в любой папке
                    if filename_lower == 'eboot.bin':
                        logger.info(f"🎮 Найден EBOOT.BIN: {file_path}")
                        ps3_files.append(file_path)

                    # Ищем PKG файлы
                    elif file_path.suffix.lower() == '.pkg':
                        logger.info(f"📦 Найден PKG: {file_path}")
                        ps3_files.append(file_path)

                    # Ищем ISO файлы
                    elif file_path.suffix.lower() == '.iso':
                        logger.info(f"💿 Найден ISO: {file_path}")
                        ps3_files.append(file_path)

            logger.info(f"📋 Найдено PS3 файлов: {len(ps3_files)}")

            # Если нашли файлы, выбираем самый подходящий
            if ps3_files:
                # Для типа 'folder' приоритет - EBOOT.BIN
                if game_type == 'folder':
                    eboot_files = [f for f in ps3_files if f.name.lower() == 'eboot.bin']
                    if eboot_files:
                        result = eboot_files[0]
                        logger.info(f"✅ Для типа 'folder' выбран EBOOT: {result}")
                        return result

                # Для типа 'pkg' приоритет - PKG файлы
                elif game_type == 'pkg':
                    pkg_files = [f for f in ps3_files if f.suffix.lower() == '.pkg']
                    if pkg_files:
                        result = max(pkg_files, key=lambda f: f.stat().st_size)
                        logger.info(f"✅ Для типа 'pkg' выбран PKG: {result}")
                        return result

                # Для типа 'iso' приоритет - ISO файлы
                elif game_type == 'iso':
                    iso_files = [f for f in ps3_files if f.suffix.lower() == '.iso']
                    if iso_files:
                        result = max(iso_files, key=lambda f: f.stat().st_size)
                        logger.info(f"✅ Для типа 'iso' выбран ISO: {result}")
                        return result

                # Fallback: берем самый большой файл
                result = max(ps3_files, key=lambda f: f.stat().st_size)
                logger.info(f"⚠️ Тип {game_type}, выбран самый большой файл: {result}")
                return result

            # Если файлов не найдено, проверяем есть ли папки с игрой
            logger.info("🔍 Файлы не найдены, проверяем структуру папок...")

            # Ищем папки с кодами дисков (BLUS, BCES, NPEA и т.д.)
            for dir_path in self.install_dir.rglob('*'):
                if dir_path.is_dir():
                    dir_name = dir_path.name.upper()
                    if any(code in dir_name for code in ['BLUS', 'BCES', 'NPEA', 'NPUA', 'BLES', 'BCUS']):
                        logger.info(f"🏷️ Найдена папка с кодом диска: {dir_path}")
                        # Проверяем есть ли EBOOT внутри
                        eboot_candidate = dir_path / 'PS3_GAME' / 'USRDIR' / 'EBOOT.BIN'
                        if eboot_candidate.exists():
                            logger.info(f"✅ Найден EBOOT в папке с кодом диска: {eboot_candidate}")
                            return eboot_candidate
                        else:
                            # Если EBOOT нет, используем саму папку
                            logger.info(f"⚠️ EBOOT не найден, использую папку: {dir_path}")
                            return dir_path

            logger.error("❌ Не найдено ни одного файла или папки PS3")
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка поиска PS3 файлов: {e}")
            return None

    def _find_standard_game_file(self, platform_id: str, game_id: str) -> Optional[Path]:
        """Стандартная логика поиска для других платформ"""
        try:
            # Используем форматы из конфига
            config = self.get_complete_game_config()
            supported_formats = config['supported_formats']
            logger.info(f"🔍 Форматы для поиска: {supported_formats}")

            # Сначала проверяем распакованные файлы
            if self.extracted_files:
                logger.info("🔍 Проверяем распакованные файлы...")
                for file_path in self.extracted_files:
                    if (file_path.is_file() and
                        file_path.suffix.lower() in supported_formats):
                        logger.info(f"✅ Найден распакованный файл: {file_path.name}")
                        return file_path

            # Ищем в директории установки
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
                result = max(game_files, key=lambda f: f.stat().st_size)
                logger.info(f"✅ Выбран файл игры: {result.name}")
                return result

            # Fallback: любой подходящий файл
            all_files = [f for f in self.install_dir.iterdir()
                        if f.is_file() and f.suffix.lower() in supported_formats]

            if all_files:
                result = max(all_files, key=lambda f: f.stat().st_size)
                logger.warning(f"⚠️ Точное соответствие не найдено, использую: {result.name}")
                return result

            logger.error("❌ Не найдено ни одного файла в директории установки")
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка при поиске стандартного файла игры: {e}")
            return None

    def on_extraction_finished(self):
        """Обработка завершения обработки файлов"""
        self.progress_updated.emit(80, "✅ Обработка файлов завершена!")

    def on_extraction_error(self, error_msg):
        """Обработка ошибки обработки файлов"""
        self.error_occurred.emit(f"Ошибка обработки файлов: {error_msg}")

    def cancel(self):
        self.controller.request_cancellation()


class InstallDialog(QDialog):
    installation_finished = pyqtSignal()

    def __init__(self, game_data: dict, project_root: Path, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.project_root = project_root
        self.dialog_is_finished = False
        self.installation_cancelled = False
        self.previous_layer = None
        self.cancel_dialog = None
        self.cleanup_timer = None
        self._cancellation_start_time = 0.0

        # Навигация
        self.nav_controller = None
        if parent and hasattr(parent, 'navigation_controller'):
            self.nav_controller = parent.navigation_controller
            self.previous_layer = self.nav_controller.current_layer

        # Путь установки
        platform = game_data.get('platform', 'Unknown')
        self.install_dir = Path(get_users_subpath("games")) / platform
        self.install_dir.mkdir(parents=True, exist_ok=True)

        self.thread = None
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_value = 0
        self.is_indeterminate = False

        self.init_ui()
        self.start_installation()

        if self.nav_controller:
            self.nav_controller.add_managed_window(self)
            self.nav_controller.register_widgets(NavigationLayer.INSTALL, [self.cancel_button, self.show_log_button])
            self.nav_controller.switch_layer(NavigationLayer.INSTALL)
            self.nav_controller.set_dialog_open(True)
            self.show()
        else:
            self.show()

    def init_ui(self):
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        self.setGeometry(screen_geometry)
        self.setWindowTitle("Установка игры")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        self.title_label = QLabel(f"<b>{self.game_data.get('title', 'Игра')}</b>")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        layout.addWidget(self.title_label)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(1100, 350)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("""
            QLabel {
                background-color: #252525;
                border-radius: 15px;
                color: #666666;
                font-size: 120px;
            }
        """)
        self.cover_label.setText("🎮")
        layout.addWidget(self.cover_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("Подготовка к установке...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Arial", 16))
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(34)
        self.progress_bar.setMinimumWidth(int(screen_geometry.width() * 0.85))
        layout.addWidget(self.progress_bar)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(200)
        self.log_output.hide()
        layout.addWidget(self.log_output)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(30)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.show_log_button = QPushButton("Показать лог")
        self.show_log_button.setAutoDefault(False)
        self.show_log_button.setDefault(False)
        self.show_log_button.setMinimumSize(240, 70)
        self.show_log_button.setFont(QFont("Arial", 15, QFont.Weight.Bold))
        self.show_log_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.show_log_button.clicked.connect(self.toggle_log_visibility)

        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.setDefault(False)
        self.cancel_button.setMinimumSize(240, 70)
        self.cancel_button.setFont(QFont("Arial", 15, QFont.Weight.Bold))
        self.cancel_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.cancel_button.clicked.connect(self.on_cancel_button_clicked)

        btn_layout.addWidget(self.show_log_button)
        btn_layout.addWidget(self.cancel_button)
        layout.addLayout(btn_layout)

    # ====================== НАВИГАЦИЯ ======================
    def _restore_navigation(self):
        if self.nav_controller:
            self.nav_controller.remove_managed_window(self)
            self.nav_controller.set_dialog_open(False)
            if self.previous_layer:
                self.nav_controller.switch_layer(self.previous_layer)
            else:
                self.nav_controller.exit_dialog_mode()
            logger.info("✅ Навигация восстановлена после InstallDialog")

    def closeEvent(self, event):
        self._restore_navigation()
        super().closeEvent(event)

    # ====================== ЛОГИКА УСТАНОВКИ ======================
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
        if self.log_output.isVisible():
            self.log_output.append(message)

    def set_progress_indeterminate(self, indeterminate: bool):
        self.is_indeterminate = indeterminate
        if indeterminate:
            self.animation_timer.start(50)
        else:
            self.animation_timer.stop()
            self.progress_bar.setValue(self.progress_bar.value())

    def update_animation(self):
        self.animation_value = (self.animation_value + 3) % 100
        self.progress_bar.setValue(self.animation_value)

    def handle_error(self, message: str):
        self.status_label.setText("❌ " + message)
        self.log_output.append("ОШИБКА: " + message)
        self.log_output.show()
        # Используем кастомный диалог
        show_error(self, "Ошибка", message, nav_controller=self.nav_controller)

    def toggle_log_visibility(self):
        if self.log_output.isVisible():
            self.log_output.hide()
            self.show_log_button.setText("Показать лог")
        else:
            self.log_output.show()
            self.show_log_button.setText("Скрыть лог")

    def on_thread_finished(self, game_data):
        if self.installation_cancelled:
            return

        self.progress_bar.setValue(100)
        self.status_label.setText("✅ Установка завершена!")
        self.dialog_is_finished = True
        self.cancel_button.setText("Закрыть")
        self.animation_timer.stop()
        self.installation_finished.emit()

    def on_thread_cancelled(self):
        self.installation_cancelled = True
        self.status_label.setText("❌ Установка отменена")
        self.log_output.append("❌ Установка отменена пользователем.")
        self.cancel_button.setText("Закрыть")
        self.cancel_button.setEnabled(True)
        self.dialog_is_finished = True
        self.animation_timer.stop()
        if self.cleanup_timer and self.cleanup_timer.isActive():
            self.cleanup_timer.stop()

    def _installation_still_active(self) -> bool:
        """InstallThread может уже завершить run(), пока качается торрент/распаковка."""
        if not self.thread:
            return False
        if self.thread.isRunning():
            return True
        controller = getattr(self.thread, 'controller', None)
        if not controller:
            return False
        for task in controller.all_tasks:
            if task and hasattr(task, 'isRunning') and task.isRunning():
                return True
        return False

    def on_cancel_button_clicked(self):
        if self.dialog_is_finished or self.installation_cancelled:
            self._restore_navigation()
            self.accept()
            return

        if self.cleanup_timer and self.cleanup_timer.isActive():
            return

        if self.cancel_dialog and self.cancel_dialog.isVisible():
            return

        # show() + finished_signal: навигация SYSTEM_DIALOG, отмена через _finish_dialog
        self.cancel_dialog = create_install_cancel_question(self, self.nav_controller)
        self.cancel_dialog.finished_signal.connect(self._on_cancel_confirmation)
        self.cancel_dialog.show()

    def cancel_installation(self):
        """Единая точка отмены: всегда дергаем контроллер, даже если run() уже вышел."""
        self.installation_cancelled = True
        self.status_label.setText("Отмена установки...")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Отмена...")
        self.log_output.append("❌ Запрос на отмену установки...")
        self.animation_timer.stop()

        if self.thread:
            self.thread.cancel()

        self._cancellation_start_time = time.time()
        if self.cleanup_timer is None:
            self.cleanup_timer = QTimer(self)
            self.cleanup_timer.timeout.connect(self._check_cancellation_status)
        self.cleanup_timer.start(500)

    def _check_cancellation_status(self):
        if not self._installation_still_active():
            if self.cleanup_timer:
                self.cleanup_timer.stop()
            if not self.dialog_is_finished:
                self.on_thread_cancelled()
            return

        elapsed = time.time() - self._cancellation_start_time
        if elapsed > 15:
            logger.warning("Принудительная остановка задач установки по таймауту")
            if self.cleanup_timer:
                self.cleanup_timer.stop()
            self._force_stop_installation_tasks()

    def _on_cancel_confirmation(self, result):
        try:
            self.cancel_dialog.finished_signal.disconnect(self._on_cancel_confirmation)
        except TypeError:
            pass

        if result == MessageDialogResult.YES:
            self.cancel_installation()

        if self.cancel_dialog:
            self.cancel_dialog.deleteLater()
            self.cancel_dialog = None

    def _force_stop_installation_tasks(self):
        if not self.thread:
            self.on_thread_cancelled()
            return
        controller = getattr(self.thread, 'controller', None)
        if controller:
            for task in controller.all_tasks:
                if task and hasattr(task, 'isRunning') and task.isRunning():
                    if hasattr(task, 'cancel'):
                        task.cancel()
                    elif hasattr(task, 'terminate'):
                        task.terminate()
        if self.thread.isRunning():
            self.thread.terminate()
            self.thread.wait(2000)
        self.on_thread_cancelled()
