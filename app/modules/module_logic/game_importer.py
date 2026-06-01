# app/modules/module_logic/game_importer.py
import os
import shutil
import json
import time
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from PyQt6.QtWidgets import (
    QInputDialog, QMessageBox, QFileDialog, QDialog, QVBoxLayout,
    QListWidget, QListWidgetItem, QDialogButtonBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer

from app.registry.registry_loader import RegistryLoader
from core import get_users_subpath, get_users_path, BASE_DIR
from app.modules.module_logic.game_data_manager import get_game_data_manager
from app.modules.installer.archive_extractor import ArchiveExtractor
from app.modules.installer.launch_manager import LaunchManager

logger = logging.getLogger('Модуль добавления игр')


class GameImporter:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        logger.info(f"Путь модуля импорта игр 🔍: {self.project_root}")

        # Диагностика RegistryLoader
        try:
            logger.info(f"🔧 Инициализация RegistryLoader...")
            self.loader = RegistryLoader(self.project_root)
            logger.info(f"✅ RegistryLoader инициализирован")

            # Проверим что он может загрузить
            logger.info(f"🔍 Запрос платформ у RegistryLoader...")
            platforms = self.loader.get_all_platform_configs()
            logger.info(f"📊 RegistryLoader загрузил платформ: {len(platforms)}")

            if platforms:
                for platform_id, config in platforms.items():
                    logger.info(f"   - {platform_id}: {config.get('name', 'No name')}")
            else:
                logger.warning("⚠️ RegistryLoader вернул пустой словарь платформ")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации RegistryLoader: {e}")
            import traceback
            logger.error(f"🔍 Трассировка: {traceback.format_exc()}")
            self.loader = None

        # Инициализируем LaunchManager
        try:
            self.launch_manager = LaunchManager(self.project_root)
            logger.info("✅ LaunchManager инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации LaunchManager: {e}")
            self.launch_manager = None

        self.manager = get_game_data_manager(self.project_root)
        self.supported_extensions = self._collect_extensions()

    def _collect_extensions(self) -> set:
        """Собирает все поддерживаемые расширения из всех платформ"""
        exts = set()
        try:
            if not self.loader:
                logger.error("❌ RegistryLoader не инициализирован")
                return exts

            platform_configs = self.loader.get_all_platform_configs()
            logger.info(f"📊 Загружено конфигураций платформ: {len(platform_configs)}")

            for platform_id, config in platform_configs.items():
                logger.info(f"🔧 Платформа {platform_id}: {config.get('name', 'No name')}")
                formats = config.get("supported_formats", [])
                exts.update(formats)
                logger.info(f"📁 {platform_id}: расширения {formats}")

            logger.info(f"✅ Итоговые расширения: {sorted(exts)}")
        except Exception as e:
            logger.error(f"❌ Ошибка сбора расширений: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return exts

    def import_game(self, source_path: str | Path, target_platform: str | None = None) -> Dict[str, Any]:
        source_path = Path(source_path).resolve()

        if not source_path.exists():
            raise ValueError("Файл или папка не существует")

        logger.info(f"🚀 Начинаем импорт игры из: {source_path}")

        # --- 1. Если это одиночный файл игры (не архив) ---
        if source_path.is_file() and not self._is_potential_archive(source_path):
            logger.info(f"🎮 Обнаружен игровой файл: {source_path}")
            return self._process_single_game_file(source_path, target_platform)

        # --- 2. Если это архив или папка - используем старую логику ---
        final_search_dir = source_path
        archive_file = None

        if source_path.is_file() and self._is_potential_archive(source_path):
            archive_file = source_path
            logger.info(f"📦 Обнаружен архив: {archive_file}")

            # Для архива: распаковываем в ту же папку, где находится архив
            archive_dir = source_path.parent
            logger.info(f"📁 Директория архива: {archive_dir}")

        elif source_path.is_dir():
            logger.info(f"🔍 Поиск архивов в папке: {source_path}")
            for f in source_path.iterdir():
                if f.is_file() and self._is_potential_archive(f):
                    archive_file = f
                    logger.info(f"✅ Найден архив в папке: {archive_file.name}")
                    archive_dir = source_path  # Используем саму папку
                    break

        # --- 3. Если архив найден — распаковываем ---
        if archive_file:
            logger.info(f"📂 Распаковка архива: {archive_file} → {archive_dir}")

            fake_game_data = {"title": archive_file.stem}
            extractor = ArchiveExtractor(fake_game_data, archive_dir)

            # Запуск распаковки синхронно
            self._run_extractor_synchronously(extractor)

            logger.info(f"✅ Архив успешно распакован в: {archive_dir}")

            final_search_dir = archive_dir

            # Удаление архива после распаковки
            try:
                if archive_file.exists():
                    archive_file.unlink()
                    logger.info(f"🗑️ Архив удален: {archive_file.name}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить архив {archive_file.name}: {e}")

        # --- 4. Ищем игровые файлы в конечной директории ---
        logger.info(f"🔍 Поиск игровых файлов в: {final_search_dir}")

        found_files = self._find_game_files(final_search_dir)

        if not found_files:
            logger.error(f"❌ В папке {final_search_dir} нет поддерживаемых игровых файлов.")

            # Для диагностики
            all_items = list(final_search_dir.rglob('*'))
            logger.error(f"📦 Содержимое ({len(all_items)} элементов):")
            for item in all_items:
                if item.is_file():
                    logger.error(f"   📄 {item.name} (расширение: {item.suffix})")
                else:
                    logger.error(f"   📁 {item.name}/")

            logger.error(f"🔍 Поддерживаемые расширения: {sorted(self.supported_extensions)}")

            raise ValueError("Не найдено ни одного поддерживаемого игрового файла")

        logger.info(f"🎯 Найдено игровых файлов: {len(found_files)}")
        for f in found_files:
            logger.info(f"   • {f}")

        # --- 5. Если файлов несколько — спрашиваем пользователя ---
        main_file = self._choose_main_file(found_files)
        logger.info(f"🎮 Основной файл выбран: {main_file.name}")

        return self._process_single_game_file(main_file, target_platform)

    def _process_single_game_file(self, game_file: Path, target_platform: str | None = None) -> Dict[str, Any]:
        """Обрабатывает одиночный игровой файл"""
        logger.info(f"🔄 Обработка игрового файла: {game_file}")

        # Определяем платформу по расширению
        platform = target_platform or self._detect_platform_by_extension(game_file.suffix.lower())
        if not platform:
            platform = self._ask_platform()

        logger.info(f"🕹️ Платформа: {platform}")

        # Копируем игру в users/games/<platform>/
        platform_dir = Path(get_users_subpath("games")) / platform
        platform_dir.mkdir(parents=True, exist_ok=True)

        dest_file = platform_dir / game_file.name
        counter = 1
        stem, suffix = game_file.stem, game_file.suffix
        while dest_file.exists():
            dest_file = platform_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        logger.info(f"📥 Копируем игровой файл: {game_file} → {dest_file}")
        shutil.copy2(game_file, dest_file)

        # Генерация ID и сохранение
        title = stem.replace('_', ' ').title()
        game_id = f"{platform}_{stem.lower()}".replace(" ", "_").replace("-", "_")

        installed_info = {
            "title": title,
            "platform": platform,
            "file_path": str(dest_file),
            "file_name": dest_file.name,
            "imported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "user_import"
        }

        # === ИСПРАВЛЕНИЕ: Получаем правильное имя эмулятора ===
        platform_config = self.loader.get_platform_config(platform)

        if platform_config:
            # Получаем эмулятор из конфига
            preferred_emulator = platform_config.get('emulator', '')

            # Если emulator - это строка (как в твоих конфигах)
            if isinstance(preferred_emulator, str):
                emulator_name = preferred_emulator
            # Если emulator - это словарь (новый формат)
            elif isinstance(preferred_emulator, dict):
                emulator_name = preferred_emulator.get('name', '')
            else:
                emulator_name = ''

            logger.info(f"🎮 Эмулятор для платформы {platform}: {emulator_name}")
        else:
            emulator_name = ''
            logger.error(f"❌ Не найден конфиг для платформы {platform}")

        # Добавляем в installed_games.json
        if hasattr(self.manager, 'add_installed_game'):
            self.manager.add_installed_game(game_id, installed_info)
        else:
            # Сохраняем напрямую в файл
            installed_games_file = Path(get_users_path()) / 'installed_games.json'
            installed_games = {}
            if installed_games_file.exists():
                with open(installed_games_file, 'r', encoding='utf-8') as f:
                    installed_games = json.load(f)

            installed_games[game_id] = installed_info

            with open(installed_games_file, 'w', encoding='utf-8') as f:
                json.dump(installed_games, f, ensure_ascii=False, indent=2)

            # Принудительно обновляем менеджер
            self.manager.refresh()

        # Создаем скрипт запуска через LaunchManager
        if self.launch_manager and emulator_name:
            success = self.launch_manager.create_custom_launcher(
                game_title=title,
                game_path=dest_file,
                platform=platform,
                emulator_name=emulator_name,  # ✅ Теперь передаем правильное имя эмулятора
                game_id=game_id
            )

            if success:
                logger.info(f"✅ Скрипт запуска создан через LaunchManager")

                # Обновляем installed_games.json с launcher_path
                installed_games_file = Path(get_users_path()) / 'installed_games.json'
                if installed_games_file.exists():
                    with open(installed_games_file, 'r', encoding='utf-8') as f:
                        installed_games = json.load(f)

                    if game_id in installed_games:
                        # Добавляем launcher_path как у других игр
                        launcher_path = self.launch_manager.scripts_dir / f"{game_id}.sh"
                        installed_games[game_id]["launcher_path"] = str(launcher_path)
                        installed_games[game_id]["install_date"] = time.time()

                        with open(installed_games_file, 'w', encoding='utf-8') as f:
                            json.dump(installed_games, f, ensure_ascii=False, indent=2)

                        logger.info(f"✅ Обновлен installed_games.json с launcher_path")
            else:
                logger.error(f"❌ Не удалось создать скрипт запуска через LaunchManager")
        else:
            if not emulator_name:
                logger.error(f"❌ Не удалось определить эмулятор для платформы {platform}")
            if not self.launch_manager:
                logger.error(f"❌ LaunchManager не доступен, скрипт запуска не создан")

        logger.info(f"🎉 Игра добавлена: {title} ({platform})")
        return {
            "id": game_id,
            "title": title,
            "platform": platform,
            "file_path": str(dest_file),
            "preferred_emulator": emulator_name
        }

    def _detect_platform_by_extension(self, file_extension: str) -> Optional[str]:
        """Определяет платформу по расширению файла"""
        if not self.loader:
            return None
            
        # Получаем все поддерживаемые форматы
        formats_map = self.loader.get_supported_formats()
        logger.info(f"🔍 Поиск платформы для расширения: {file_extension}")
        logger.info(f"📋 Доступные форматы: {formats_map}")
        
        # Ищем платформу по расширению
        if file_extension in formats_map:
            platforms = formats_map[file_extension]
            if platforms:
                # Берем первую подходящую платформу
                platform = platforms[0]
                logger.info(f"✅ Найдена платформа '{platform}' для расширения {file_extension}")
                return platform
        
        logger.warning(f"⚠️ Платформа для расширения {file_extension} не найдена")
        return None

    def _is_potential_archive(self, path: Path) -> bool:
        """Простая проверка по расширению + сигнатуре (берем из твоего extractor)"""
        archive_exts = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tgz', '.tbz2', '.txz'}
        if path.suffix.lower() in archive_exts:
            return True
        
        # Дополнительно проверяем сигнатуру RAR/ZIP/7Z
        try:
            with open(path, 'rb') as f:
                header = f.read(8)
            if header.startswith((b'Rar!', b'PK\x03\x04', b'7z\xBC\xAF\x27\x1C')):
                return True
        except:
            pass
        return False

    def _run_extractor_synchronously(self, extractor: ArchiveExtractor):
        """Запускает ArchiveExtractor и ждёт завершения"""
        finished = False
        error_msg = None

        def on_finished():
            nonlocal finished
            finished = True

        def on_error(msg: str):
            nonlocal error_msg
            error_msg = msg
            finished = True

        extractor.finished.connect(on_finished)
        extractor.error_occurred.connect(on_error)
        extractor.start()

        # Ждём максимум 10 минут
        timeout = time.time() + 600
        while not finished and time.time() < timeout:
            QApplication.processEvents()
            time.sleep(0.1)

        if error_msg:
            raise ValueError(f"Ошибка распаковки: {error_msg}")
        if not finished:
            extractor.cancel()
            raise TimeoutError("Таймаут распаковки архива")

    def _find_game_files(self, directory: Path) -> list[Path]:
        files = []
        for ext in self.supported_extensions:
            files.extend(directory.rglob(f"*{ext}"))
        return files

    def _choose_main_file(self, files: list[Path]) -> Path:
        """Диалог выбора основного файла, если найдено несколько"""
        if len(files) == 1:
            return files[0]

        dialog = QDialog(QApplication.activeWindow())
        dialog.setWindowTitle("Выберите основной файл игры")
        layout = QVBoxLayout(dialog)

        listw = QListWidget()
        for f in files:
            item = QListWidgetItem(f.name)
            item.setData(Qt.ItemDataRole.UserRole, str(f))
            listw.addItem(item)
        layout.addWidget(listw)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            raise ValueError("Пользователь отменил выбор файла")
        current = listw.currentItem()
        if not current:
            raise ValueError("Файл не выбран")
        return Path(current.data(Qt.ItemDataRole.UserRole))

    def _ask_platform(self) -> str:
        """Спрашивает у пользователя платформу, если не удалось определить автоматически"""
        platforms = sorted(self.loader.get_all_platform_configs().keys())
        platform, ok = QInputDialog.getItem(
            None,
            "Выберите платформу",
            "Не удалось определить платформу автоматически:",
            platforms,
            0,
            False
        )
        if not ok or not platform:
            raise ValueError("Платформа не выбрана")
        return platform
