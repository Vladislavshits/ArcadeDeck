#!/usr/bin/env python3
import subprocess
import json
from pathlib import Path
import logging
import time
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
import importlib.util

# Создаем логгер для этого модуля
logger = logging.getLogger('EmulatorManager')

class EmulatorManager(QObject):
    def __init__(self, project_root: Path, test_mode=False):
        super().__init__()
        self.project_root = project_root
        self.test_mode = test_mode
        self._cancelled = False

        # Загружаем конфигурации всех платформ
        self.platform_configs = self._load_all_platform_configs()
        logger.info(f"✅ Загружено конфигураций платформ: {len(self.platform_configs)}")

        # Загружаем алиасы платформ
        self.platform_aliases = {}
        aliases_path = self.project_root / "app" / "registry" / "registry_platform_aliases.json"
        if aliases_path.exists():
            try:
                with open(aliases_path, 'r', encoding='utf-8') as f:
                    aliases_data = json.load(f)
                    self.platform_aliases = aliases_data.get('platform_aliases', {})
                    logger.info(f"✅ Загружено алиасов платформ: {len(self.platform_aliases)}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось прочитать реестр алиасов: {e}")

    # Сигнал для отправки обновлений прогресса в UI
    progress_updated = pyqtSignal(int, str)

    def _load_all_platform_configs(self) -> dict:
        """Загружает конфигурации всех платформ из папок platforms/"""
        platforms_dir = self.project_root / "app" / "registry" / "platforms"
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

    def _load_platform_config(self, platform_name: str) -> dict | None:
        """Загружает конфигурацию конкретной платформы"""
        config_file = self.project_root / "app" / "registry" / "platforms" / platform_name / "config.py"

        if not config_file.exists():
            logger.warning(f"⚠️ Конфиг платформы {platform_name} не найден: {config_file}")
            return None

        try:
            # Динамически импортируем конфиг
            spec = importlib.util.spec_from_file_location(f"{platform_name}_config", config_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, 'get_config'):
                config = module.get_config()
                # Добавляем идентификатор платформы
                config['id'] = platform_name
                return config
            else:
                logger.warning(f"⚠️ Конфиг платформы {platform_name} не содержит функцию get_config")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки конфига платформы {platform_name}: {e}")
            return None

    def get_emulator_info_for_game(self, game_data: dict) -> dict | None:
        """
        Получает информацию об эмуляторе на основе данных игры.
        Ищет по platform_module, platform или определяет по расширению файла.
        """
        game_title = game_data.get('title', 'Unknown Game')

        # 1. Пытаемся найти по platform_module (новый формат)
        platform_module = game_data.get('platform_module')
        if platform_module and platform_module in self.platform_configs:
            logger.info(f"🔍 Найден эмулятор по platform_module '{platform_module}' для игры '{game_title}'")
            return self.platform_configs[platform_module]

        # 2. Пытаемся найти по platform (старый формат)
        platform = game_data.get('platform', '')
        if platform:
            # Проверяем прямые совпадения (регистрозависимо)
            if platform in self.platform_configs:
                logger.info(f"🔍 Найден эмулятор по platform '{platform}' для игры '{game_title}'")
                return self.platform_configs[platform]

            # Проверяем алиасы (регистронезависимо)
            platform_lower = platform.lower()
            for alias, actual_platform in self.platform_aliases.items():
                if alias.lower() == platform_lower and actual_platform in self.platform_configs:
                    logger.info(f"🔍 Найден эмулятор по алиасу '{platform}' -> '{actual_platform}' для игры '{game_title}'")
                    return self.platform_configs[actual_platform]

        # 3. Проверяем preferred_emulator из данных игры
        preferred_emulator = game_data.get('preferred_emulator')
        if preferred_emulator:
            # Ищем алиас для preferred_emulator (регистронезависимо)
            preferred_lower = preferred_emulator.lower()
            for alias, actual_platform in self.platform_aliases.items():
                if alias.lower() == preferred_lower and actual_platform in self.platform_configs:
                    logger.info(f"🔍 Найден эмулятор по preferred_emulator '{preferred_emulator}' -> '{actual_platform}' для игры '{game_title}'")
                    return self.platform_configs[actual_platform]

        # 4. Если не нашли по данным игры, пытаемся определить по расширению файла
        file_path = game_data.get('file_name') or game_data.get('path', '')
        if file_path and '.' in file_path:
            file_extension = '.' + file_path.split('.')[-1].lower()
            emulator_info = self._find_emulator_by_extension(file_extension)
            if emulator_info:
                logger.info(f"🔍 Найден эмулятор по расширению '{file_extension}' для игры '{game_title}'")
                return emulator_info

        logger.warning(f"⚠️ Не удалось определить эмулятор для игры '{game_title}': platform_module={platform_module}, platform={platform}, preferred_emulator={preferred_emulator}")
        return None

    def _find_emulator_by_extension(self, extension: str) -> dict | None:
        """
        Ищет эмулятор по расширению файла.
        """
        for platform_id, platform_info in self.platform_configs.items():
            supported_formats = platform_info.get('supported_formats', [])
            if extension in supported_formats:
                logger.info(f"🔍 Расширение '{extension}' соответствует платформе '{platform_id}'")
                return platform_info
        return None

    def ensure_emulator_for_game(self, game_data: dict) -> bool:
        """
        Проверяет и устанавливает эмулятор для конкретной игры.
        """
        if self._cancelled:
            return False

        game_title = game_data.get('title', 'Unknown Game')
        logger.info(f"🔍 Проверяю эмулятор для игры: {game_title}")

        # Получаем информацию об эмуляторе для этой игры
        emulator_info = self.get_emulator_info_for_game(game_data)
        if not emulator_info:
            logger.error(f"❌ Не удалось определить эмулятор для игры: {game_title}")
            self.progress_updated.emit(0, f"❌ Не удалось определить эмулятор для {game_title}")
            return False

        # Получаем ID эмулятора (используем ключ из конфигураций)
        emulator_id = emulator_info.get('id')
        if not emulator_id:
            logger.error(f"❌ Не удалось найти ID для эмулятора игры '{game_title}'")
            return False

        return self.ensure_emulator(emulator_id, emulator_info)

    def ensure_emulator(self, emulator_id: str, emulator_info: dict = None) -> bool:
        """
        Проверяет и устанавливает эмулятор по ID.
        """
        if self._cancelled:
            return False

        logger.info(f"🔍 Проверяю наличие эмулятора: {emulator_id}")

        if not emulator_info:
            emulator_info = self.platform_configs.get(emulator_id)
            if not emulator_info:
                logger.error(f"❌ Информация об эмуляторе '{emulator_id}' не найдена в конфигурациях платформ.")
                return False

        install_method = emulator_info.get('install_method')

        if install_method == 'flatpak':
            return self._ensure_flatpak(emulator_info)
        elif install_method == 'system':
            logger.info(f"✅ Эмулятор '{emulator_id}' использует системную установку")
            return True
        elif install_method == 'none':
            logger.info(f"✅ Эмулятор '{emulator_id}' не требует установки")
            return True
        else:
            logger.error(f"❌ Неподдерживаемый метод установки: {install_method}")
            return False

    def _is_flatpak_installed(self, flatpak_id: str) -> bool:
        try:
            res = subprocess.run(["flatpak", "list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            return flatpak_id in res.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("⚠️ flatpak не найден в системе или проверка заняла слишком много времени.")
            return False

    def _ensure_flatpak(self, emu_info: dict) -> bool:
        if self._cancelled:
            return False

        flatpak_id = emu_info.get('flatpak_id')
        name = emu_info.get('name')
        logger.info(f"⬇️ Проверка/установка Flatpak-пакета: {flatpak_id} ({name})")

        if self._cancelled:
            return False

        if self.test_mode:
            logger.info("[TEST MODE] Симуляция установки Flatpak")
            return True

        try:
            if self._is_flatpak_installed(flatpak_id):
                self.progress_updated.emit(100, f"✅ {name} уже установлен через Flatpak")
                return True
            else:
                self.progress_updated.emit(10, f"🔄 Установка {name} через Flatpak...")
                # Добавляем флаг --noninteractive для автоматического подтверждения
                install_command = ["flatpak", "install", "--noninteractive", "flathub", flatpak_id, "-y"]

                process = subprocess.Popen(
                    install_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                # Чтение и отправка вывода
                for line in process.stdout:
                    if self._cancelled:
                        process.terminate()
                        return False
                    self.progress_updated.emit(50, line.strip())

                process.wait(timeout=300)  # Таймаут 5 минут

                if self._cancelled:
                    return False

                if process.returncode == 0:
                    self.progress_updated.emit(100, f"✅ {name} успешно установлен.")
                    return True
                else:
                    error_msg = f"Ошибка при установке Flatpak: процесс завершился с кодом {process.returncode}"
                    self.progress_updated.emit(0, error_msg)
                    logger.error(error_msg)
                    return False
        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Ошибка при установке Flatpak: {e.stderr}"
            self.progress_updated.emit(0, error_msg)
            logger.error(error_msg)
            return False
        except FileNotFoundError:
            error_msg = "❌ Утилита 'flatpak' не найдена. Пожалуйста, убедитесь, что она установлена и доступна в PATH."
            self.progress_updated.emit(0, error_msg)
            logger.error(error_msg)
            return False
        except subprocess.TimeoutExpired:
            error_msg = "❌ Установка Flatpak заняла слишком много времени."
            self.progress_updated.emit(0, error_msg)
            logger.error(error_msg)
            return False
        except Exception as e:
            error_msg = f"❌ Непредвиденная ошибка при работе с Flatpak: {e}"
            self.progress_updated.emit(0, error_msg)
            logger.error(error_msg)
            return False

    def get_supported_formats(self, emulator_id: str) -> list:
        """
        Возвращает список поддерживаемых форматов файлов для эмулятора.
        """
        emulator_info = self.platform_configs.get(emulator_id)
        if emulator_info and 'supported_formats' in emulator_info:
            return emulator_info['supported_formats']
        return []

    def cancel(self):
        self._cancelled = True
