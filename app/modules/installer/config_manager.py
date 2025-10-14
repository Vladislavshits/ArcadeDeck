#!/usr/bin/env python3
import shutil
import configparser
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable


class ConfigManager:
    def __init__(self, project_root: Path, logs_callback=None, test_mode=False):
        self.project_root = project_root
        self.logs_callback = logs_callback or (lambda msg: print(msg))
        self.test_mode = test_mode
        self._cancelled = False

        # Универсальная поддержка форматов
        self.SUPPORTED_FORMATS = {
            'ini': self._handle_ini_config,
            'json': self._handle_json_config,
            'cfg': self._handle_cfg_config,
            'conf': self._handle_conf_config
        }

        # Карта форматов для эмуляторов (на основе документации)
        self.EMULATOR_FORMATS = {
            # Sony
            'duckstation': {'format': 'ini', 'main_file': 'settings.ini', 'game_specific': True},
            'pcsx2': {'format': 'ini', 'main_file': 'PCSX2.ini', 'game_specific': False},
            'ppsspp': {'format': 'ini', 'main_file': 'ppsspp.ini', 'game_specific': True},
            'retroarch': {'format': 'cfg', 'main_file': 'retroarch.cfg', 'game_specific': False},

            # Nintendo
            'yuzu': {'format': 'ini', 'main_file': 'qt-config.ini', 'game_specific': True},
            'ryujinx': {'format': 'json', 'main_file': 'settings.json', 'game_specific': True},
            'dolphin': {'format': 'ini', 'main_file': 'Dolphin.ini', 'game_specific': True},
            'citra': {'format': 'ini', 'main_file': 'qt-config.ini', 'game_specific': True},

            # Sega
            'flycast': {'format': 'ini', 'main_file': 'emu.cfg', 'game_specific': False},

            # Default
            'default': {'format': 'ini', 'main_file': 'settings.ini', 'game_specific': False}
        }

    def _log(self, message: str):
        ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        line = f"{ts} [ConfigManager] {message}"
        self.logs_callback(line)

    def _get_emulator_config(self, emulator_name: str) -> Dict:
        """Получает конфигурацию формата для эмулятора"""
        return self.EMULATOR_FORMATS.get(emulator_name, self.EMULATOR_FORMATS['default'])

    def _handle_ini_config(self, source_path: Path, target_path: Path, game_id: str = None):
        """Обработчик INI конфигов с поддержкой game-specific настроек"""
        try:
            if not self.test_mode:
                # Для INI файлов можем добавлять game-specific секции
                if game_id and source_path.exists():
                    config = configparser.ConfigParser()
                    config.read(source_path)

                    # Добавляем секцию для конкретной игры (если нужно)
                    game_section = f"GameSettings_{game_id}"
                    if not config.has_section(game_section):
                        config.add_section(game_section)
                        config.set(game_section, 'GameID', game_id)

                    # Сохраняем обновленный конфиг
                    with open(target_path, 'w') as f:
                        config.write(f)
                    self._log(f"✅ INI конфиг обогащен game-specific настройками: {target_path.name}")
                else:
                    # Просто копируем как есть
                    shutil.copy(source_path, target_path)
                    self._log(f"✅ INI конфиг скопирован: {source_path.name}")
            else:
                self._log(f"[TEST MODE] Обработка INI: {source_path.name} -> {target_path.name}")

        except Exception as e:
            self._log(f"❌ Ошибка обработки INI конфига: {e}")
            if not self.test_mode and source_path.exists():
                shutil.copy(source_path, target_path)  # Fallback

    def _handle_json_config(self, source_path: Path, target_path: Path, game_id: str = None):
        """Обработчик JSON конфигов"""
        try:
            if not self.test_mode:
                if game_id and source_path.exists():
                    # Для JSON можем добавить game-specific поля
                    with open(source_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)

                    # Добавляем идентификатор игры
                    if 'game_specific' not in config_data:
                        config_data['game_specific'] = {}
                    config_data['game_specific'][game_id] = {
                        'game_id': game_id,
                        'configured': True
                    }

                    with open(target_path, 'w', encoding='utf-8') as f:
                        json.dump(config_data, f, indent=2, ensure_ascii=False)
                    self._log(f"✅ JSON конфиг обогащен game-specific настройками: {target_path.name}")
                else:
                    shutil.copy(source_path, target_path)
                    self._log(f"✅ JSON конфиг скопирован: {source_path.name}")
            else:
                self._log(f"[TEST MODE] Обработка JSON: {source_path.name} -> {target_path.name}")

        except Exception as e:
            self._log(f"❌ Ошибка обработки JSON конфига: {e}")
            if not self.test_mode and source_path.exists():
                shutil.copy(source_path, target_path)  # Fallback

    def _handle_cfg_config(self, source_path: Path, target_path: Path, game_id: str = None):
        """Обработчик CFG конфигов (RetroArch)"""
        if not self.test_mode:
            shutil.copy(source_path, target_path)
            self._log(f"✅ CFG конфиг скопирован: {source_path.name}")
        else:
            self._log(f"[TEST MODE] Обработка CFG: {source_path.name} -> {target_path.name}")

    def _handle_conf_config(self, source_path: Path, target_path: Path, game_id: str = None):
        """Обработчик CONF конфигов (DOSBox)"""
        if not self.test_mode:
            shutil.copy(source_path, target_path)
            self._log(f"✅ CONF конфиг скопирован: {source_path.name}")
        else:
            self._log(f"[TEST MODE] Обработка CONF: {source_path.name} -> {target_path.name}")

    def apply_config(self, game_id: str, platform: str, emulator_name: str) -> bool:
        """
        Универсальное применение конфигурации для игры
        Теперь копирует ВСЮ папку эмулятора с готовыми конфигами!
        """
        if self._cancelled:
            return False

        self._log(f"🎯 Применение конфига для {game_id} ({platform}) эмулятор: {emulator_name}")

        platform_dir = self.project_root / 'app' / 'emulators' / platform
        target_dir = self.project_root / 'users' / 'configs' / platform

        # СПЕЦИАЛЬНАЯ ЛОГИКА ДЛЯ PCSX2
        if emulator_name.lower() == 'pcsx2':
            emulator_folders = [
                # 1. Основная папка PCSX2 с подпапками
                platform_dir / 'PCSX2',
                # 2. Папка с именем эмулятора (для совместимости)
                platform_dir / emulator_name,
                # 3. Папка games/эмулятор
                platform_dir / 'games' / emulator_name,
                # 4. Папка с настройками по умолчанию
                platform_dir / 'preset_default'
            ]
        else:
            # Стандартная логика для других эмуляторов
            emulator_folders = [
                platform_dir / emulator_name,
                platform_dir / 'games' / emulator_name,
                platform_dir / 'preset_default'
            ]

        for source_folder in emulator_folders:
            if source_folder.exists() and source_folder.is_dir():
                # СОХРАНЯЕМ ОРИГИНАЛЬНОЕ ИМЯ ПАПКИ, а не используем emulator_name
                target_emulator_folder = target_dir / source_folder.name

                self._log(f"📁 Найдена папка эмулятора: {source_folder}")

                # Копируем ВСЮ папку эмулятора
                if not self.test_mode:
                    target_emulator_folder.mkdir(parents=True, exist_ok=True)

                    # Рекурсивно копируем все файлы и папки
                    for item in source_folder.iterdir():
                        target_item = target_emulator_folder / item.name
                        if item.is_dir():
                            shutil.copytree(item, target_item, dirs_exist_ok=True)
                        else:
                            shutil.copy2(item, target_item)

                    self._log(f"✅ Папка эмулятора скопирована: {target_emulator_folder}")
                else:
                    self._log(f"[TEST MODE] Копирование папки: {source_folder} -> {target_emulator_folder}")

                return True

        # Fallback: старая логика с отдельными конфигами
        return self._apply_legacy_config(game_id, platform, emulator_name)

    def _apply_legacy_config(self, game_id: str, platform: str, emulator_name: str) -> bool:
        """Старая логика для обратной совместимости"""
        emulator_config = self._get_emulator_config(emulator_name)
        config_format = emulator_config['format']

        platform_dir = self.project_root / 'app' / 'emulators' / platform
        target_dir = self.project_root / 'users' / 'configs' / platform

        # Старая логика поиска отдельных конфигов
        config_sources = [
            (platform_dir / 'games' / f"{game_id}.{config_format}", f"{game_id}.{config_format}"),
            (platform_dir / f"preset_default.{config_format}", f"{game_id}.{config_format}"),
        ]

        for source_path, target_filename in config_sources:
            if source_path.exists():
                target_path = target_dir / target_filename
                self._log(f"📄 Найден конфиг: {source_path}")

                if not self.test_mode:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, target_path)
                    self._log(f"✅ Конфиг скопирован: {target_path}")
                else:
                    self._log(f"[TEST MODE] Копирование конфига: {source_path} -> {target_path}")

                return True

        self._log(f"⚠️ Не найден подходящий конфиг для {platform}/{game_id}")
        return False

    def _apply_single_config(self, source_path: Path, target_path: Path,
                           config_format: str, game_id: str = None) -> bool:
        """Применяет одиночный конфиг с обработчиком формата"""
        if self._cancelled:
            return False

        handler = self.SUPPORTED_FORMATS.get(config_format)
        if not handler:
            self._log(f"❌ Неподдерживаемый формат конфига: {config_format}")
            return False

        if not self.test_mode:
            target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            handler(source_path, target_path, game_id)
            return True
        except Exception as e:
            self._log(f"❌ Ошибка применения конфига {source_path}: {e}")
            return False

    def cancel(self):
        """Отмена операции"""
        self._cancelled = True
