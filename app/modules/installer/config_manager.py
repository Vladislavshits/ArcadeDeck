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
        Копирует всю папку с готовыми конфигами и обновляет пути!
        """
        # 🆕 ПРОВЕРКА ОТМЕНЫ
        if self._cancelled:
            return False

        self._log(f"🎯 Применение конфига для {game_id} ({platform}) эмулятор: {emulator_name}")

        platform_dir = self.project_root / 'app' / 'emulators' / platform

        # ИСПРАВЛЕНИЕ: Используем get_users_subpath вместо жесткого пути
        from core import get_users_subpath
        target_dir = Path(get_users_subpath("configs")) / platform

        # СПЕЦИАЛЬНАЯ ЛОГИКА ДЛЯ PCSX2
        if emulator_name.lower() == 'pcsx2':
            emulator_folders = [
                platform_dir / 'PCSX2',
                platform_dir / emulator_name,
                platform_dir / 'games' / emulator_name,
                platform_dir / 'preset_default'
            ]
        else:
            emulator_folders = [
                platform_dir / emulator_name,
                platform_dir / 'games' / emulator_name,
                platform_dir / 'preset_default'
            ]

        for source_folder in emulator_folders:
            # 🆕 ПРОВЕРКА ОТМЕНЫ ПЕРЕД КАЖДОЙ ПАПКОЙ
            if self._cancelled:
                return False

            if source_folder.exists() and source_folder.is_dir():
                target_emulator_folder = target_dir / source_folder.name

                self._log(f"📁 Найдена папка эмулятора: {source_folder}")

                # Копируем ВСЮ папку эмулятора
                if not self.test_mode:
                    target_emulator_folder.mkdir(parents=True, exist_ok=True)

                    # Рекурсивно копируем все файлы и папки
                    for item in source_folder.iterdir():
                        # 🆕 ПРОВЕРКА ОТМЕНЫ ПЕРЕД КАЖДЫМ ФАЙЛОМ
                        if self._cancelled:
                            return False

                        target_item = target_emulator_folder / item.name
                        if item.is_dir():
                            shutil.copytree(item, target_item, dirs_exist_ok=True)
                        else:
                            shutil.copy2(item, target_item)

                    self._log(f"✅ Папка эмулятора скопирована: {target_emulator_folder}")

                    # ОБНОВЛЯЕМ ПУТИ В КОНФИГАХ ПОСЛЕ КОПИРОВАНИЯ
                    self._update_emulator_config_paths(target_emulator_folder, platform, emulator_name)

                else:
                    self._log(f"[TEST MODE] Копирование папки: {source_folder} -> {target_emulator_folder}")

                return True

        self._log(f"⚠️ Не найдена папка эмулятора для {platform}/{emulator_name}")
        return False

    def _update_emulator_config_paths(self, emulator_folder: Path, platform: str, emulator_name: str):
        """Обновляет пути в конфигах эмуляторов в соответствии с текущим путем users"""
        try:
            from core import get_users_path

            # Получаем базовый путь к users
            users_base_path = Path(get_users_path())
            self._log(f"🔄 Обновление путей в конфигах для {emulator_name}. Базовый путь: {users_base_path}")

            if emulator_name.lower() == 'duckstation' and platform.upper() == 'PS1':
                self._update_duckstation_config(emulator_folder, users_base_path)
            elif emulator_name.lower() == 'pcsx2' and platform.upper() == 'PS2':
                self._update_pcsx2_config(emulator_folder, users_base_path)
            elif emulator_name.lower() == 'rpcs3' and platform.upper() == 'PS3':
                self._update_rpcs3_config(emulator_folder, users_base_path)

        except Exception as e:
            self._log(f"⚠️ Не удалось обновить пути в конфигах: {e}")

    def _update_duckstation_config(self, emulator_folder: Path, users_base_path: Path):
        """Обновляет пути в конфиге DuckStation (PS1)"""
        try:
            config_file = emulator_folder / "settings.ini"
            if not config_file.exists():
                self._log(f"⚠️ Конфиг DuckStation не найден: {config_file}")
                return

            config = configparser.ConfigParser()
            config.read(config_file)

            # Обновляем путь к BIOS
            new_bios_path = users_base_path / "bios" / "PS1"
            if config.has_section('BIOS'):
                config.set('BIOS', 'searchdirectory', str(new_bios_path))
                self._log(f"✅ Обновлен путь к BIOS DuckStation: {new_bios_path}")

            # Сохраняем изменения
            with open(config_file, 'w') as f:
                config.write(f)

            self._log("✅ Конфиг DuckStation обновлен")

        except Exception as e:
            self._log(f"❌ Ошибка обновления конфига DuckStation: {e}")

    def _update_pcsx2_config(self, emulator_folder: Path, users_base_path: Path):
        """Обновляет пути в конфиге PCSX2 (PS2)"""
        try:
            config_file = emulator_folder / "PCSX2.ini"
            if not config_file.exists():
                self._log(f"⚠️ Конфиг PCSX2 не найден: {config_file}")
                return

            config = configparser.ConfigParser()
            config.read(config_file)

            # Обновляем путь к BIOS (относительный путь от папки конфигов)
            if config.has_section('Folders'):
                # Вычисляем относительный путь от папки конфигов к папке bios
                configs_path = emulator_folder.parent  # platform/configs/
                bios_relative_path = os.path.relpath(
                    users_base_path / "bios" / "pcsx2",
                    configs_path
                )
                config.set('Folders', 'Bios', bios_relative_path)
                self._log(f"✅ Обновлен путь к BIOS PCSX2: {bios_relative_path}")

            # Сохраняем изменения
            with open(config_file, 'w') as f:
                config.write(f)

            self._log("✅ Конфиг PCSX2 обновлен")

        except Exception as e:
            self._log(f"❌ Ошибка обновления конфига PCSX2: {e}")

    def _update_rpcs3_config(self, emulator_folder: Path, users_base_path: Path):
        """Обновляет пути в конфиге RPCS3 (PS3)"""
        try:
            # RPCS3 хранит конфиги в подпапке GuiConfigs
            config_file = emulator_folder / "GuiConfigs" / "CurrentSettings.ini"
            if not config_file.exists():
                self._log(f"⚠️ Конфиг RPCS3 не найден: {config_file}")
                return

            config = configparser.ConfigParser()
            config.read(config_file)

            # Обновляем путь к BIOS
            new_bios_path = users_base_path / "bios" / "rpcs3"
            if config.has_section('main_window'):
                config.set('main_window', 'lastExplorePathPUP', str(new_bios_path))
                self._log(f"✅ Обновлен путь к BIOS RPCS3: {new_bios_path}")

            # Сохраняем изменения
            with open(config_file, 'w') as f:
                config.write(f)

            self._log("✅ Конфиг RPCS3 обновлен")

        except Exception as e:
            self._log(f"❌ Ошибка обновления конфига RPCS3: {e}")

    def _apply_single_config(self, source_path: Path, target_path: Path,
                           config_format: str, game_id: str = None) -> bool:
        """Применяет одиночный конфиг с обработчиком формата"""
        # ПРОВЕРКА ОТМЕНЫ
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
        """ОТМЕНА ВСЕХ ОПЕРАЦИЙ КОНФИГОВ"""
        self._cancelled = True
        logger.info("🛑 ConfigManager: все операции отменены")
