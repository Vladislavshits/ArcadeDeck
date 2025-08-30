#!/usr/bin/env python3
import subprocess
import json
from pathlib import Path
import logging
import time
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal

import platform as sys_platform

# Создаем логгер для этого модуля
logger = logging.getLogger('EmulatorManager')

class EmulatorManager(QObject):
    def __init__(self, project_root: Path, test_mode=False):
        super().__init__()
        self.project_root = project_root
        self.test_mode = test_mode
        self._cancelled = False
        # read registry platforms if present in app/registry
        registry_path = self.project_root / "app" / "registry" / "registry_platforms.json"
        self.registry = {}
        if registry_path.exists():
            try:
                with open(registry_path, 'r', encoding='utf-8') as f:
                    self.registry = json.load(f)
            except Exception as e:
                logger.warning(f"⚠️ Не удалось прочитать реестр платформ: {e}")

    # Сигнал для отправки обновлений прогресса в UI
    progress_updated = pyqtSignal(int, str)

    def get_emulator_info(self, emulator_id: str) -> dict | None:
        """
        Получает информацию об эмуляторе из реестра платформ.
        Возвращает словарь с данными или None, если не найдено.
        """
        return self.registry.get(emulator_id)

    def ensure_emulator(self, emulator_id: str) -> bool:
        if self._cancelled:
            return False
            
        logger.info(f"🔍 Проверяю наличие эмулятора: {emulator_id}")

        emu_info = self.registry.get(emulator_id) or {}
        install_method = emu_info.get('install_method')

        if not emu_info:
            logger.error(f"❌ Информация об эмуляторе '{emulator_id}' не найдена в реестра.")
            return False

        if install_method == 'flatpak':
            return self._ensure_flatpak(emu_info)
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
                install_command = emu_info.get('install_command')
                if install_command:
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
                else:
                    logger.error(f"❌ Команда установки не найдена для эмулятора: {flatpak_id}")
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
        emu_info = self.get_emulator_info(emulator_id)
        if emu_info and 'supported_formats' in emu_info:
            return emu_info['supported_formats']
        return []

    def cancel(self):
        self._cancelled = True
