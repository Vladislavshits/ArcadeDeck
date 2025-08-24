#!/usr/bin/env python3
import subprocess
import json
from pathlib import Path
import logging
import time
from datetime import datetime
import platform as sys_platform

# Создаем логгер для этого модуля
logger = logging.getLogger('EmulatorManager')


class EmulatorManager:
    def __init__(self, project_root: Path, test_mode=False):
        self.project_root = project_root
        self.test_mode = test_mode
        # read registry platforms if present in app/registry
        registry_path = self.project_root / "app" / "registry" / "registry_platforms.json"
        self.registry = {}
        if registry_path.exists():
            try:
                with open(registry_path, 'r', encoding='utf-8') as f:
                    self.registry = json.load(f)
            except Exception as e:
                logger.warning(f"⚠️ Не удалось прочитать реестр платформ: {e}")

    def get_emulator_info(self, emulator_id: str) -> dict | None:
        """
        Получает информацию об эмуляторе из реестра платформ.
        Возвращает словарь с данными или None, если не найдено.
        """
        return self.registry.get(emulator_id)

    def ensure_emulator(self, emulator_id: str) -> bool:
        logger.info(f"🔍 Проверяю наличие эмулятора: {emulator_id}")
        time.sleep(0.5)

        emu_info = self.registry.get(emulator_id) or {}
        install_method = emu_info.get('install_method')
        flatpak_id = emu_info.get('flatpak_id')

        # Special-case PPSSPP: try flatpak on Linux (Steam Deck)
        if flatpak_id and sys_platform.system().lower() == 'linux' and install_method == 'flatpak':
            return self._ensure_flatpak(flatpak_id, emu_info.get('name', emulator_id))

        # Otherwise, check for local platform folder (app/emulators/<emulator_id>)
        local_path = self.project_root / 'app' / 'emulators' / emulator_id
        if local_path.exists():
            self._log(f"✅ Локальные файлы эмулятора обнаружены: {local_path}")
            return True

        # not found locally: in test_mode we simulate ok, otherwise fail
        if self.test_mode:
            self._log(f"[TEST MODE] Эмулятор {emulator_id} не найден, но симулируем установку.")
            return True
        else:
            self._log(f"❌ Эмулятор {emulator_id} не найден и test_mode=False — не могу продолжить.")
            return False

    def get_supported_formats(self, emulator_id: str) -> list:
        """
        Возвращает список поддерживаемых форматов файлов для эмулятора.
        """
        emu_info = self.get_emulator_info(emulator_id)
        if emu_info and 'supported_formats' in emu_info:
            return emu_info['supported_formats']
        return []

    def _is_flatpak_installed(self, flatpak_id: str) -> bool:
        try:
            res = subprocess.run(["flatpak", "list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return flatpak_id in res.stdout
        except FileNotFoundError:
            logger.warning("⚠️ flatpak не найден в системе.")
            return False

    def _ensure_flatpak(self, flatpak_id: str, name: str) -> bool:
        logger.info(f"⬇️ Проверка/установка Flatpak-пакета: {flatpak_id} ({name})")
        time.sleep(0.5) # <-- Добавляем задержку
        if self.test_mode:
            logger.info("[TEST MODE] Симуляция установки Flatpak")
            return True
        try:
            if self._is_flatpak_installed(flatpak_id):
                logger.info(f"✅ {name} уже установлен через Flatpak")
                return True

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Ошибка при установке Flatpak: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Непредвиденная ошибка при установке Flatpak: {e}")
            return False
