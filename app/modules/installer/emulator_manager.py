#!/usr/bin/env python3
import os
import subprocess
import logging
import time
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
import json  # Добавляем для парсинга JSON от GitHub API

logger = logging.getLogger('EmulatorManager')

class EmulatorManager(QObject):
    def __init__(self, project_root: Path, test_mode=False):
        super().__init__()
        self.project_root = project_root
        self.test_mode = test_mode
        self._cancelled = False

        # ✅ ОСТАВЛЯЕМ ТОЛЬКО ЭТО - больше не загружаем конфиги здесь
        logger.info("✅ EmulatorManager инициализирован (конфиги загружаются в install.py)")

    # Сигнал для отправки обновлений прогресса в UI
    progress_updated = pyqtSignal(int, str)

    def ensure_emulator(self, emulator_id: str, emulator_config: dict = None) -> bool:
        """
        Проверяет и устанавливает эмулятор по ID.
        ТЕПЕРЬ ПРИНИМАЕТ ГОТОВЫЙ КОНФИГ ЭМУЛЯТОРА
        """
        # 🆕 ПРОВЕРКА ОТМЕНЫ
        if self._cancelled:
            return False

        logger.info(f"🔍 Проверяю наличие эмулятора: {emulator_id}")

        # 🆕 ИСПОЛЬЗУЕМ ПЕРЕДАННЫЙ КОНФИГ ВМЕСТО ПОИСКА
        if not emulator_config:
            logger.error(f"❌ Для эмулятора '{emulator_id}' не передан конфиг")
            return False

        install_method = emulator_config.get('install_method')

        if install_method == 'flatpak':
            return self._ensure_flatpak(emulator_config)
        elif install_method == 'appimage':
            return self._ensure_appimage(emulator_config)
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

    def _ensure_appimage(self, emu_config: dict) -> bool:
        """
        Устанавливает эмулятор из AppImage.
        ТЕПЕРЬ ПРИНИМАЕТ ГОТОВЫЙ КОНФИГ
        """
        # 🆕 ПРОВЕРКА ОТМЕНЫ
        if self._cancelled:
            return False

        name = emu_config.get('name', 'AppImage')

        # 🆕 ДИНАМИЧЕСКОЕ ПОЛУЧЕНИЕ LATEST PRE-RELEASE ДЛЯ PCSX2
        if name == "PCSX2" and emu_config.get('auto_update', False):
            logger.info(f"🔄 Получаю последнюю версию PCSX2 с GitHub...")

            # 🆕 ПРОВЕРКА ОТМЕНЫ ПЕРЕД СЕТЕВЫМ ЗАПРОСОМ
            if self._cancelled:
                return False

            success = self._update_pcsx2_config(emu_config)
            if not success:
                return False

        appimage_url = emu_config.get('appimage_url')
        appimage_filename = emu_config.get('appimage_filename')

        if not appimage_url or not appimage_filename:
            logger.error(f"❌ Не указаны URL или имя файла для AppImage {name}")
            return False

        logger.info(f"⬇️ Проверка/установка AppImage: {name}")

        # 🆕 ОСОБАЯ ОБРАБОТКА ДЛЯ MELONDS (ZIP АРХИВ)
        if 'melonds' in name.lower() or 'melonDS' in name.lower():
            return self._ensure_melonds_from_zip(emu_config)

        # Создаем директорию для AppImage если нужно
        appimage_dir = self.project_root / "app" / "emulators" / "appimages"
        appimage_dir.mkdir(parents=True, exist_ok=True)

        appimage_path = appimage_dir / appimage_filename

        # 🆕 ПРОВЕРКА ОТМЕНЫ
        if self._cancelled:
            return False

        # Проверяем, уже ли скачан AppImage
        if appimage_path.exists():
            # Делаем исполняемым если нужно
            if not os.access(appimage_path, os.X_OK):
                appimage_path.chmod(0o755)
            logger.info(f"✅ AppImage {name} уже установлен")
            self.progress_updated.emit(100, f"✅ {name} уже установлен")
            return True

        if self.test_mode:
            logger.info("[TEST MODE] Симуляция установки AppImage")
            return True

        try:
            self.progress_updated.emit(10, f"🔄 Скачивание {name}...")

            # Скачиваем AppImage
            download_command = ["wget", appimage_url, "-O", str(appimage_path)]

            process = subprocess.Popen(
                download_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Чтение и отправка вывода
            for line in process.stdout:
                # 🆕 ПРОВЕРКА ОТМЕНЫ ВО ВРЕМЯ СКАЧИВАНИЯ
                if self._cancelled:
                    process.terminate()
                    if appimage_path.exists():
                        appimage_path.unlink()
                    return False
                self.progress_updated.emit(50, line.strip())

            process.wait(timeout=300)

            # 🆕 ПРОВЕРКА ОТМЕНЫ ПОСЛЕ СКАЧИВАНИЯ
            if self._cancelled:
                if appimage_path.exists():
                    appimage_path.unlink()
                return False

            if process.returncode == 0:
                appimage_path.chmod(0o755)
                self.progress_updated.emit(100, f"✅ {name} успешно установлен.")
                return True
            else:
                error_msg = f"Ошибка при скачивании AppImage: код {process.returncode}"
                self.progress_updated.emit(0, error_msg)
                logger.error(error_msg)
                if appimage_path.exists():
                    appimage_path.unlink()
                return False

        except subprocess.TimeoutExpired:
            error_msg = "❌ Скачивание AppImage заняло слишком много времени."
            self.progress_updated.emit(0, error_msg)
            logger.error(error_msg)
            if appimage_path.exists():
                appimage_path.unlink()
            return False
        except Exception as e:
            error_msg = f"❌ Ошибка при установке AppImage: {e}"
            self.progress_updated.emit(0, error_msg)
            logger.error(error_msg)
            if appimage_path.exists():
                appimage_path.unlink()
            return False

    def _update_pcsx2_config(self, emu_config: dict) -> bool:
        """
        Динамически обновляет конфиг PCSX2 с последней версией с GitHub
        """
        try:
            api_url = "https://api.github.com/repos/PCSX2/pcsx2/releases"

            # Используем curl для получения JSON
            process = subprocess.Popen(
                ["curl", "-s", "-L", api_url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            output, err = process.communicate(timeout=30)

            if self._cancelled:
                return False

            if process.returncode != 0:
                raise ValueError(f"Ошибка curl: {err}")

            releases = json.loads(output)

            # Фильтруем релизы в зависимости от настройки
            if emu_config.get('include_prerelease', False):
                # Ищем пре-релизы (более свежие версии)
                target_releases = [r for r in releases if r.get('prerelease', False)]
                if not target_releases:
                    # Если пре-релизов нет, берем последний стабильный
                    target_releases = [r for r in releases if not r.get('prerelease', False)]
            else:
                # Только стабильные релизы
                target_releases = [r for r in releases if not r.get('prerelease', False)]

            if not target_releases:
                raise ValueError("Не найдено подходящих релизов")

            latest_release = target_releases[0]  # Самый свежий релиз
            tag = latest_release['tag_name']
            assets = latest_release['assets']

            # Ищем AppImage для Linux
            appimage_asset = None
            for asset in assets:
                asset_name = asset['name']
                if (asset_name.endswith('.AppImage') or
                    'linux' in asset_name.lower() or
                    'appimage' in asset_name.lower()):
                    appimage_asset = asset
                    break

            if not appimage_asset:
                raise ValueError("Не найден AppImage-файл в релизе")

            # Обновляем конфиг
            emu_config['appimage_url'] = appimage_asset['browser_download_url']
            emu_config['appimage_filename'] = appimage_asset['name']
            emu_config['version'] = tag

            logger.info(f"✅ Найдена версия PCSX2: {tag}")
            logger.info(f"📦 Файл: {emu_config['appimage_filename']}")
            self.progress_updated.emit(20, f"✅ Найдена последняя версия PCSX2: {tag}")
            return True

        except subprocess.TimeoutExpired:
            error_msg = "❌ Таймаут при получении информации о версии PCSX2"
            logger.error(error_msg)
            self.progress_updated.emit(0, error_msg)
            return False
        except Exception as e:
            error_msg = f"❌ Не удалось получить последнюю версию PCSX2: {e}"
            logger.error(error_msg)
            self.progress_updated.emit(0, error_msg)
            return False

    def _ensure_melonds_from_zip(self, emu_config: dict) -> bool:
        """
        Специальная обработка для melonDS - скачивает ZIP и извлекает AppImage
        """
        # 🆕 ПРОВЕРКА ОТМЕНЫ
        if self._cancelled:
            return False

        appimage_url = emu_config.get('appimage_url')
        appimage_filename = emu_config.get('appimage_filename')
        name = emu_config.get('name', 'melonDS')

        if not appimage_url or not appimage_filename:
            logger.error(f"❌ Не указаны URL или имя файла для {name}")
            return False

        logger.info(f"⬇️ Установка {name} из ZIP архива")

        # Создаем директорию для AppImage
        appimage_dir = self.project_root / "app" / "emulators" / "appimages"
        appimage_dir.mkdir(parents=True, exist_ok=True)

        # Временная директория для распаковки
        temp_dir = appimage_dir / "temp_melonds"
        temp_dir.mkdir(exist_ok=True)

        appimage_path = appimage_dir / appimage_filename

        # 🆕 ПРОВЕРКА ОТМЕНЫ
        if self._cancelled:
            return False

        # Проверяем, уже ли установлен AppImage
        if appimage_path.exists():
            if not os.access(appimage_path, os.X_OK):
                appimage_path.chmod(0o755)
            logger.info(f"✅ {name} уже установлен")
            self.progress_updated.emit(100, f"✅ {name} уже установлен")
            # Очищаем временную директорию если есть
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)
            return True

        if self.test_mode:
            logger.info("[TEST MODE] Симуляция установки melonDS из ZIP")
            return True

        try:
            self.progress_updated.emit(10, f"🔄 Скачивание {name}...")

            # Скачиваем ZIP архив
            zip_path = temp_dir / "melonDS.zip"

            download_command = ["wget", appimage_url, "-O", str(zip_path)]

            process = subprocess.Popen(
                download_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in process.stdout:
                # 🆕 ПРОВЕРКА ОТМЕНЫ ВО ВРЕМЯ СКАЧИВАНИЯ
                if self._cancelled:
                    process.terminate()
                    return False
                if line.strip():  # Только непустые строки
                    self.progress_updated.emit(30, f"📥 {line.strip()}")

            process.wait(timeout=300)

            # 🆕 ПРОВЕРКА ОТМЕНЫ ПОСЛЕ СКАЧИВАНИЯ
            if self._cancelled:
                return False

            if process.returncode != 0:
                error_msg = f"Ошибка при скачивании melonDS: код {process.returncode}"
                self.progress_updated.emit(0, error_msg)
                logger.error(error_msg)
                return False

            self.progress_updated.emit(50, "📦 Распаковка архива...")

            # Распаковываем архив
            import zipfile
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            except zipfile.BadZipFile:
                error_msg = "❌ Скачанный файл не является корректным ZIP архивом"
                self.progress_updated.emit(0, error_msg)
                logger.error(error_msg)
                return False

            # Ищем AppImage файл в распакованных файлах
            appimage_files = list(temp_dir.glob("*.AppImage"))
            if not appimage_files:
                # Ищем рекурсивно
                appimage_files = list(temp_dir.rglob("*.AppImage"))

            if not appimage_files:
                error_msg = "❌ Не найден AppImage файл в архиве"
                self.progress_updated.emit(0, error_msg)
                logger.error(error_msg)
                # Выводим содержимое для диагностики
                contents = list(temp_dir.rglob("*"))
                logger.error(f"📋 Содержимое архива: {[f.name for f in contents]}")
                return False

            # Копируем AppImage в целевую директорию
            appimage_source = appimage_files[0]
            import shutil
            shutil.copy2(appimage_source, appimage_path)

            # Даем права на выполнение
            appimage_path.chmod(0o755)

            # Очищаем временные файлы
            shutil.rmtree(temp_dir)

            self.progress_updated.emit(100, f"✅ {name} успешно установлен из ZIP архива")
            logger.info(f"✅ {name} установлен в: {appimage_path}")
            return True

        except Exception as e:
            error_msg = f"❌ Ошибка при установке melonDS: {e}"
            self.progress_updated.emit(0, error_msg)
            logger.error(error_msg)
            # Очищаем временные файлы при ошибке
            import shutil
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            return False

    def get_emulator_path(self, emulator_id: str, emulator_config: dict = None) -> str | None:
        """
        Возвращает путь к исполняемому файлу эмулятора.
        ТЕПЕРЬ ПРИНИМАЕТ КОНФИГ
        """
        # 🆕 ИСПОЛЬЗУЕМ ПЕРЕДАННЫЙ КОНФИГ
        if emulator_config:
            install_method = emulator_config.get('install_method')

            if install_method == 'appimage':
                appimage_filename = emulator_config.get('appimage_filename')
                if appimage_filename:
                    appimage_path = self.project_root / "app" / "emulators" / "appimages" / appimage_filename
                    return str(appimage_path) if appimage_path.exists() else None

            elif install_method == 'flatpak':
                return emulator_config.get('flatpak_id')

            elif install_method == 'system':
                return emulator_config.get('command', emulator_id.lower())

        return None

    def _ensure_flatpak(self, emu_config: dict) -> bool:
        """
        Устанавливает Flatpak эмулятор.
        ТЕПЕРЬ ПРИНИМАЕТ КОНФИГ
        """
        # 🆕 ПРОВЕРКА ОТМЕНЫ
        if self._cancelled:
            return False

        flatpak_id = emu_config.get('flatpak_id')
        name = emu_config.get('name')
        logger.info(f"⬇️ Проверка/установка Flatpak-пакета: {flatpak_id} ({name})")

        # 🆕 ПРОВЕРКА ОТМЕНЫ
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
                install_command = ["flatpak", "install", "--noninteractive", "flathub", flatpak_id, "-y"]

                process = subprocess.Popen(
                    install_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                for line in process.stdout:
                    # 🆕 ПРОВЕРКА ОТМЕНЫ ВО ВРЕМЯ УСТАНОВКИ
                    if self._cancelled:
                        process.terminate()
                        return False
                    self.progress_updated.emit(50, line.strip())

                process.wait(timeout=300)

                # 🆕 ПРОВЕРКА ОТМЕНЫ ПОСЛЕ УСТАНОВКИ
                if self._cancelled:
                    return False

                if process.returncode == 0:
                    self.progress_updated.emit(100, f"✅ {name} успешно установлен.")
                    return True
                else:
                    error_msg = f"Ошибка при установке Flatpak: код {process.returncode}"
                    self.progress_updated.emit(0, error_msg)
                    logger.error(error_msg)
                    return False

        except FileNotFoundError:
            error_msg = "❌ Утилита 'flatpak' не найдена."
            self.progress_updated.emit(0, error_msg)
            logger.error(error_msg)
            return False
        except subprocess.TimeoutExpired:
            error_msg = "❌ Установка Flatpak заняла слишком много времени."
            self.progress_updated.emit(0, error_msg)
            logger.error(error_msg)
            return False
        except Exception as e:
            error_msg = f"❌ Ошибка при работе с Flatpak: {e}"
            self.progress_updated.emit(0, error_msg)
            logger.error(error_msg)
            return False

    def get_supported_formats(self, emulator_config: dict) -> list:
        """
        Возвращает список поддерживаемых форматов файлов для эмулятора.
        ТЕПЕРЬ ПРИНИМАЕТ КОНФИГ
        """
        if emulator_config and 'supported_formats' in emulator_config:
            return emulator_config['supported_formats']
        return []

    def cancel(self):
        """🆕 ОТМЕНА ВСЕХ ОПЕРАЦИЙ ЭМУЛЯТОРА"""
        self._cancelled = True
        logger.info("EmulatorManager: все операции отменены")
