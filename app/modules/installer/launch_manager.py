import os
import json
import logging
import shutil
import time
import subprocess
import shlex
from pathlib import Path
from typing import Optional, Dict, Any, List

# Импорт каталога игровых данных
from core import get_users_path, get_users_subpath

logger = logging.getLogger('LaunchManager')


class LaunchManager:
    def __init__(self, project_root: Path):
        self.project_root = project_root

        users_path = Path(get_users_path())
        self.scripts_dir = Path(get_users_subpath("launchers"))
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

        self.installed_games_file = users_path / 'installed_games.json'
        self.installed_games = self._load_installed_games()

        # Папка для игр PS3
        self.ps3_games_dir = Path(get_users_subpath("games")) / "PS3"
        self.ps3_games_dir.mkdir(parents=True, exist_ok=True)

        logger.info("✅ LaunchManager инициализирован (профили загружаются в install.py)")

    def get_installed_games(self):
        """Возвращает словарь установленных игр"""
        if self.installed_games_file.exists():
            try:
                with open(self.installed_games_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _load_installed_games(self) -> Dict[str, Any]:
        """Загружает информацию об установленных играх"""
        try:
            if self.installed_games_file.exists():
                with open(self.installed_games_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Ошибка загрузки installed_games: {e}")
            return {}

    def _find_launch_profile_by_name(self, emulator_name: str) -> Optional[Dict]:
        """
        Ищет профиль запуска по имени эмулятора в реестре launch_profiles.
        """
        try:
            # Загружаем реестр профилей запуска
            profiles_path = self.project_root / 'app' / 'registry' / 'registry_launch_profiles.json'

            if not profiles_path.exists():
                logger.error(f"❌ Файл профилей запуска не найден: {profiles_path}")
                return None

            with open(profiles_path, 'r', encoding='utf-8') as f:
                launch_profiles = json.load(f)

            logger.info(f"🔍 Поиск профиля запуска для: '{emulator_name}'")
            logger.info(f"📋 Доступные профили: {list(launch_profiles.keys())}")

            # 1. Прямой поиск по ключу
            if emulator_name in launch_profiles:
                logger.info(f"✅ Найден профиль запуска по ключу: '{emulator_name}'")
                return launch_profiles[emulator_name]

            # 2. Поиск по полю 'name' (регистронезависимый)
            for profile_key, profile_data in launch_profiles.items():
                if profile_data.get('name', '').lower() == emulator_name.lower():
                    logger.info(f"✅ Найден профиль запуска по name: '{profile_key}' -> '{emulator_name}'")
                    return profile_data

            # 3. Поиск по platform_module (если есть в game_data)
            if hasattr(self, 'game_data'):
                platform_module = self.game_data.get('platform_module', '').lower()
                if platform_module in launch_profiles:
                    logger.info(f"✅ Найден профиль запуска по platform_module: '{platform_module}'")
                    return launch_profiles[platform_module]

            logger.warning(f"❌ Профиль запуска для эмулятора '{emulator_name}' не найден")
            logger.warning(f"🔍 Искали в: {list(launch_profiles.keys())}")
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка поиска профиля запуска: {e}")
            return None

    def _save_installed_games(self):
        """Сохраняет информацию об установленных играх"""
        try:
            self.installed_games_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.installed_games_file, 'w', encoding='utf-8') as f:
                json.dump(self.installed_games, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения installed_games: {e}")

    def _find_appimage(self, emulator_name: str) -> str:
        """Ищет файл AppImage для эмулятора"""
        appimages_dir = self.project_root / 'app' / 'emulators' / 'appimages'

        if not appimages_dir.exists():
            logger.error(f"❌ Директория AppImage не существует: {appimages_dir}")
            return ""

        # Ищем файлы AppImage в директории
        for file_path in appimages_dir.iterdir():
            if file_path.is_file() and file_path.suffix == '.AppImage':
                # Проверяем, содержит ли имя файла название эмулятора
                filename_lower = file_path.name.lower()
                emulator_name_lower = emulator_name.lower()

                if emulator_name_lower in filename_lower:
                    logger.info(f"✅ Найден AppImage: {file_path}")
                    return str(file_path)

        logger.error(f"❌ AppImage не найден для эмулятора '{emulator_name}' в {appimages_dir}")
        return ""

    def _get_cover_path(self, game_data: dict) -> str:
        """Получить путь к обложке игры"""
        game_id = game_data.get('id')
        platform = game_data.get('platform')

        if not game_id or not platform:
            logger.warning(f"⚠️ Не удалось получить game_id или platform для поиска обложки")
            return ""

        # Используем путь из настроек для images
        images_dir = Path(get_users_subpath("images"))
        cover_dir = images_dir / platform / game_id
        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.webp']

        # Создаем директорию для обложек, если её нет
        try:
            cover_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Создана/проверена директория для обложек: {cover_dir}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания директории для обложек: {e}")
            return ""

        # Ищем существующие обложки
        for ext in image_extensions:
            cover_path = cover_dir / f"cover{ext}"
            if cover_path.exists():
                logger.info(f"✅ Найдена пользовательская обложка: {cover_path}")
                return str(cover_path)

        # Возвращаем стандартную обложке, если пользовательской нет
        default_cover = game_data.get('image_path', '')
        if default_cover:
            # Проверяем, является ли путь абсолютным или относительным
            default_cover_path = Path(default_cover)
            if not default_cover_path.is_absolute():
                # Если путь относительный, делаем его абсолютным относительно project_root
                default_cover_path = self.project_root / default_cover_path

            if default_cover_path.exists():
                logger.info(f"📋 Используется стандартная обложка: {default_cover_path}")
                return str(default_cover_path)
            else:
                logger.warning(f"⚠️ Стандартная обложка не существует: {default_cover_path}")

        logger.warning(f"⚠️ Ни пользовательская, ни стандартная обложка не найдены для игры {game_id}")
        return ""

    def register_installed_game(self, game_data: dict, game_file: Path):
        """Регистрирует установленную игру"""
        game_id = game_data.get('id')
        launcher_path = self.scripts_dir / f"{game_id}.sh"
        cover_path = self._get_cover_path(game_data)

        game_info = {
            'title': game_data.get('title'),
            'platform': game_data.get('platform'),
            'install_path': str(game_file.absolute()),
            'launcher_path': str(launcher_path.absolute()) if launcher_path.exists() else None,  # Фикс: если sh существует
            'install_date': time.time(),
            'cover_path': cover_path,
            'emulator': game_data.get('preferred_emulator'),
            'game_type': game_data.get('game_type', 'unknown'),
            'status': 'installed'
        }

        self.installed_games[game_id] = game_info
        self._save_installed_games()
        logger.info(f"✅ Игра {game_id} зарегистрирована")

    def _detect_ps3_game_type(self, game_path: Path) -> str:
        """Автоматически определяет тип PS3 игры по файлу"""
        if not game_path or not game_path.exists():
            return 'unknown'

        # PKG файл
        if game_path.suffix.lower() == '.pkg':
            return 'pkg'

        # ISO файл
        if game_path.suffix.lower() == '.iso':
            return 'iso'

        # Для папок
        if game_path.is_dir():
            # Проверяем паттерн кода диска (4 буквы + 5 цифр)
            dir_name = game_path.name.upper()
            if len(dir_name) == 9:
                letters = dir_name[:4]
                digits = dir_name[4:]
                if letters.isalpha() and digits.isdigit():
                    return 'eboot'  # Папка с кодом диска

            # Проверяем известные префиксы
            known_prefixes = [
                'NPEA', 'NPEB', 'NPUA', 'NPUB', 'BLES', 'BLUS',
                'BCES', 'BCUS', 'NPEG', 'NPJG', 'NPHG', 'NPJB',
                'NPJH', 'NPHB', 'NPHH'
            ]

            for prefix in known_prefixes:
                if dir_name.startswith(prefix):
                    return 'eboot'  # Папка с кодом диска

            # Проверяем структуру PS3
            if (game_path / 'EBOOT.BIN').exists():
                return 'eboot'

            if (game_path / 'PS3_GAME' / 'PARAM.SFO').exists():
                return 'folder'

            if (game_path / 'USRDIR' / 'EBOOT.BIN').exists():
                return 'folder'

            # Любая папка - считаем как folder
            return 'folder'

        return 'unknown'

    def _install_pkg(self, pkg_path: Path, platform: str) -> bool:
        """
        Устанавливает PKG файл - ДОЖИДАЕМСЯ ЗАВЕРШЕНИЯ УСТАНОВКИ
        """
        try:
            print(f"🔍 ДИАГНОСТИКА: Начало установки PKG")

            emulator_path = self._find_appimage('rpcs3')
            if not emulator_path:
                logger.error("❌ RPCS3 не найден")
                return False

            print(f"🔍 ДИАГНОСТИКА: Emulator path: {emulator_path}")
            print(f"🔍 ДИАГНОСТИКА: PKG path: {pkg_path}")

            # Проверяем существование файлов
            emulator_exists = Path(emulator_path).exists()
            pkg_exists = pkg_path.exists()
            print(f"🔍 ДИАГНОСТИКА: Emulator exists: {emulator_exists}")
            print(f"🔍 ДИАГНОСТИКА: PKG exists: {pkg_exists}")

            if not emulator_exists or not pkg_exists:
                logger.error("❌ Файлы не найдены")
                return False

            configs_dir = Path(get_users_subpath("configs"))
            print(f"🔍 ДИАГНОСТИКА: Config dir: {configs_dir / platform}")

            # Команда установки
            install_command = [
                emulator_path,
                '--installpkg',
                str(pkg_path)
            ]

            print(f"🔍 ДИАГНОСТИКА: Command: {install_command}")

            # Подготавливаем окружение
            env = os.environ.copy()
            env['XDG_CONFIG_HOME'] = str(configs_dir / platform)
            env['SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS'] = '0'

            print(f"🔍 ДИАГНОСТИКА: Environment: XDG_CONFIG_HOME={env['XDG_CONFIG_HOME']}")

            logger.info(f"📦 Установка PKG: {pkg_path.name}")
            logger.info(f"🚀 Команда установки: {' '.join(install_command)}")

            # Запускаем процесс БЕЗ ожидания вывода (для GUI)
            print(f"🔍 ДИАГНОСТИКА: Запуск subprocess...")

            process = subprocess.Popen(
                install_command,
                env=env
                # НЕ используем stdout/stderr PIPE - это может блокировать GUI приложение
            )

            print(f"🔍 ДИАГНОСТИКА: Process PID: {process.pid}")
            logger.info(f"🔄 Процесс установки запущен (PID: {process.pid}). Ожидаем завершения...")

            # Ждем завершения БЕЗ таймаута - пользователь сам закроет окно
            print(f"🔍 ДИАГНОСТИКА: Ожидаем завершения установки...")
            return_code = process.wait()  # Ждем пока пользователь закроет RPCS3

            print(f"🔍 ДИАГНОСТИКА: Return code: {return_code}")

            if return_code == 0:
                logger.info("✅ PKG установлен успешно! Пользователь закрыл эмулятор.")
                # Даем время для завершения фоновых процессов
                time.sleep(5)
                return True
            else:
                logger.warning(f"⚠️ RPCS3 завершился с кодом: {return_code}. Возможно пользователь прервал установку.")
                return False

        except Exception as e:
            print(f"🔍 ДИАГНОСТИКА: Исключение: {e}")
            import traceback
            traceback.print_exc()
            logger.error(f"❌ Ошибка установки PKG: {e}")
            return False

    def _find_ps3_game_code_dir(self) -> Optional[Path]:
        """
        Ищет самую новую папку с кодом диска в dev_hdd0/game
        после установки PKG.
        """
        try:
            configs_dir = Path(get_users_subpath("configs"))
            # ПРАВИЛЬНЫЙ путь: добавляем папку rpcs3
            games_base_dir = configs_dir / "PS3" / "rpcs3" / "dev_hdd0" / "game"

            logger.info(f"🔍 Поиск папки с кодом диска в: {games_base_dir}")

            if not games_base_dir.exists():
                logger.warning(f"❌ Директория игр RPCS3 не найдена: {games_base_dir}")
                # Выведем все содержимое родительской папки для диагностики
                parent_dir = games_base_dir.parent
                if parent_dir.exists():
                    contents = [item.name for item in parent_dir.iterdir()]
                    logger.info(f"📁 Содержимое {parent_dir}: {contents}")
                return None

            # Все возможные префиксы кодов PS3 игр:
            # NPEA, NPEB, NPUA, NPUB, NPJB, NPJH, BLES, BLUS, BCES, BCUS, NPEG, NPJG и т.д.
            # Паттерн: 4 буквы + 5 цифр

            all_dirs = [d for d in games_base_dir.iterdir() if d.is_dir()]
            logger.info(f"📁 Все папки в {games_base_dir}: {[d.name for d in all_dirs]}")

            # Ищем папки с кодами игр PS3 (4 буквы + 5 цифр)
            game_dirs = []
            for d in all_dirs:
                dir_name = d.name.upper()

                # Игнорируем системные папки
                if dir_name in ['＄LOCKS', 'TEST12345', 'TEST00001']:
                    continue

                # Проверяем паттерн 4 буквы + 5 цифр
                if len(dir_name) == 9:
                    letters = dir_name[:4]
                    digits = dir_name[4:]

                    if letters.isalpha() and digits.isdigit():
                        game_dirs.append(d)
                        logger.info(f"✅ Найдена папка с кодом игры: {dir_name}")

                # Также проверяем дополнительные форматы
                elif len(dir_name) >= 4 and dir_name[:4] in ['NPEA', 'NPEB', 'NPUA', 'NPUB', 'BLES', 'BLUS', 'BCES', 'BCUS', 'NPEG', 'NPJG', 'NPHG']:
                    game_dirs.append(d)
                    logger.info(f"✅ Найдена папка с кодом игры (по префиксу): {dir_name}")

            if not game_dirs:
                logger.warning("❌ Папки игр с кодами дисков не найдены")
                return None

            # Сортируем по времени последнего изменения (mtime) - самая новая первая
            game_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # Берем самую новую папку
            latest_game_dir = game_dirs[0]
            logger.info(f"✅ Выбран самый новый код диска: {latest_game_dir.name} (изменен: {time.ctime(latest_game_dir.stat().st_mtime)})")

            # Проверим содержимое папки
            logger.info(f"🔍 Проверяем содержимое папки {latest_game_dir.name}...")
            contents = list(latest_game_dir.rglob('*'))
            logger.info(f"📋 Содержимое папки ({len(contents)} элементов):")
            for item in contents[:10]:  # Показываем первые 10 элементов
                logger.info(f"  - {item.relative_to(latest_game_dir)}")

            return latest_game_dir

        except Exception as e:
            logger.error(f"❌ Ошибка поиска кода диска: {e}")
            import traceback
            logger.error(f"🔍 Подробности: {traceback.format_exc()}")
            return None

    def _move_ps3_game_folder(self, source_path: Path) -> Optional[Path]:
        """
        Перемещает папку игры (код диска) из папки RPCS3 в целевую папку игр.
        """
        try:
            destination_path = self.ps3_games_dir / source_path.name
            logger.info(f"🚚 Перемещение {source_path.name} в {destination_path}...")

            if destination_path.exists():
                logger.warning(f"⚠️ Целевая папка уже существует. Удаляем её: {destination_path}")
                shutil.rmtree(destination_path)

            shutil.move(str(source_path), str(self.ps3_games_dir))
            logger.info(f"✅ Папка успешно перемещена.")
            return destination_path

        except Exception as e:
            logger.error(f"❌ Ошибка перемещения папки: {e}")
            return None

    def _find_eboot_after_installation(self, game_dir: Path) -> Optional[Path]:
        """
        Ищет EBOOT.BIN в папке игры PS3.
        Проверяет все возможные места.
        """
        try:
            logger.info(f"🔍 Поиск EBOOT.BIN в папке: {game_dir}")

            # Все возможные пути к EBOOT.BIN в PS3 игре:
            possible_eboot_paths = [
                # 1. В корне папки (для EBOOT-папок)
                game_dir / "EBOOT.BIN",

                # 2. В USRDIR (стандартная структура)
                game_dir / "USRDIR" / "EBOOT.BIN",

                # 3. В PS3_GAME/USRDIR (структура Blu-ray)
                game_dir / "PS3_GAME" / "USRDIR" / "EBOOT.BIN",

                # 4. В подпапках USRDIR
                game_dir / "USRDIR" / "EBOOT.BIN",

                # 5. Рекурсивный поиск (на всякий случай)
            ]

            # Сначала проверяем четко определенные пути
            for eboot_path in possible_eboot_paths:
                if eboot_path.exists():
                    logger.info(f"✅ Найден EBOOT.BIN: {eboot_path.relative_to(game_dir)}")
                    return eboot_path

            # Рекурсивный поиск EBOOT.BIN
            logger.info("🔍 Рекурсивный поиск EBOOT.BIN...")
            for eboot_file in game_dir.rglob("EBOOT.BIN"):
                if eboot_file.exists():
                    logger.info(f"✅ Найден EBOOT.BIN (рекурсивно): {eboot_file.relative_to(game_dir)}")
                    return eboot_file

            # Рекурсивный поиск eboot.bin (нижний регистр)
            for eboot_file in game_dir.rglob("eboot.bin"):
                if eboot_file.exists():
                    logger.info(f"✅ Найден eboot.bin (нижний регистр): {eboot_file.relative_to(game_dir)}")
                    return eboot_file

            # Если EBOOT.BIN не найден, возможно это папка с кодом диска без EBOOT
            # Проверяем, есть ли внутри PS3_GAME или другие признаки PS3 игры
            has_ps3_structure = False
            ps3_markers = ['PS3_GAME', 'USRDIR', 'PARAM.SFO', 'ICON0.PNG']

            for marker in ps3_markers:
                if any(game_dir.rglob(marker)):
                    has_ps3_structure = True
                    logger.info(f"✅ Найден маркер PS3: {marker}")
                    break

            if has_ps3_structure:
                logger.info(f"⚠️ EBOOT.BIN не найден, но найдена структура PS3. Использую папку: {game_dir}")
                return game_dir

            logger.error(f"❌ EBOOT.BIN не найден в папке: {game_dir}")

            # Диагностика: что есть в папке
            logger.info(f"📋 Содержимое папки {game_dir}:")
            try:
                for item in game_dir.iterdir():
                    if item.is_dir():
                        logger.info(f"  📁 {item.name}/")
                    else:
                        logger.info(f"  📄 {item.name}")
            except Exception as e:
                logger.error(f"❌ Не удалось прочитать содержимое папки: {e}")

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка поиска EBOOT.BIN: {e}")
            return None

    # === Основной метод создания лаунчеров ===

    def create_launcher(self, game_data: dict, game_install_path: Path) -> bool:
        """
        Создает лаунчер для игры - ЕДИНЫЙ ДЛЯ ВСЕХ ТИПОВ ИГР
        """
        try:
            logger.info(f"🎯 Создание лаунчера для игры: {game_data.get('title')}")
            logger.info(f"📁 Путь к игре: {game_install_path}")
            
            # Определяем тип игры
            is_user_game = game_data.get('is_user_game', False)
            
            emulator_name = game_data.get('preferred_emulator')
            platform = game_data.get('platform')
            game_id = game_data.get('id')
            
            if not all([emulator_name, platform, game_id]):
                logger.error("❌ В данных игры отсутствует preferred_emulator, platform или id")
                return False
            
            # === ВАЖНО: ВСЕ ИГРЫ ОБРАБАТЫВАЕМ ОДИНАКОВО ===
            if platform == 'PS3' and emulator_name == 'rpcs3':
                return self._create_ps3_launcher(game_data, game_install_path)
            else:
                return self._create_standard_launcher(game_data, game_install_path, 
                                                    platform, game_id, emulator_name)

        except Exception as e:
            logger.error(f"❌ Ошибка создания лаунчера: {e}")
            return False

    # === СПЕЦИАЛЬНАЯ ЛОГИКА ДЛЯ PS3 ===

    def _create_ps3_launcher(self, game_data: dict, game_install_path: Path) -> bool:
        """Создает лаунчер для PS3 игры (PKG, ISO, EBOOT)"""
        try:
            game_id = game_data.get('id')
            game_title = game_data.get('title')

            logger.info(f"🎮 Создание лаунчера для PS3: {game_title}")

            # Определяем тип игры
            game_type = self._detect_ps3_game_type(game_install_path)
            logger.info(f"📁 Тип игры: {game_type}")

            # === УЛУЧШЕННАЯ ЛОГИКА ДЛЯ PKG ===
            if game_type == 'pkg':
                logger.info("📦 Обнаружен PKG файл, начинаем установку...")

                # 1. Устанавливаем PKG (пользователь закрывает окно после установки)
                success = self._install_pkg(game_install_path, "PS3")
                if not success:
                    return False

                # 2. Ищем папку с кодом диска, которую создал RPCS3
                source_game_dir = self._find_ps3_game_code_dir()
                if not source_game_dir:
                    logger.error("❌ Не удалось найти папку с кодом диска после установки")
                    return False

                logger.info(f"✅ Найдена папка с игрой: {source_game_dir.name}")

                # 3. Проверяем содержимое папки
                eboot_path = self._find_eboot_after_installation(source_game_dir)

                if eboot_path:
                    # 4. Если найден EBOOT, перемещаем папку
                    target_game_dir = self._move_ps3_game_folder(source_game_dir)
                    if not target_game_dir:
                        logger.error("❌ Не удалось переместить папку игры")
                        return False

                    # 5. Ищем EBOOT в новом месте
                    eboot_path = self._find_eboot_after_installation(target_game_dir)
                    if eboot_path:
                        logger.info(f"✅ Найден EBOOT.BIN после перемещения: {eboot_path}")
                        # Создаем лаунчер для EBOOT
                        return self._create_simple_ps3_launcher(game_data, eboot_path, "eboot")
                    else:
                        # Если EBOOT не найден, создаем лаунчер для папки
                        logger.warning("⚠️ EBOOT не найден после перемещения, использую папку")
                        return self._create_simple_ps3_launcher(game_data, target_game_dir, "folder")
                else:
                    # Если EBOOT не найден в исходной папке, все равно перемещаем
                    logger.warning("⚠️ EBOOT не найден в исходной папке, перемещаем как есть")
                    target_game_dir = self._move_ps3_game_folder(source_game_dir)
                    if target_game_dir:
                        return self._create_simple_ps3_launcher(game_data, target_game_dir, "folder")
                    else:
                        return self._create_simple_ps3_launcher(game_data, source_game_dir, "folder")

            # Для ISO, EBOOT и FOLDER - создаем лаунчер напрямую
            else:
                # Определяем путь для запуска
                if game_type == 'folder':
                    # Для folder путь для запуска - сама папка
                    game_launch_path = game_install_path
                elif game_type == 'eboot':
                    # Для eboot ищем EBOOT.BIN
                    if game_install_path.is_file():
                        game_launch_path = game_install_path
                    else:
                        # Если это папка с кодом диска
                        found_eboot = self._find_eboot_after_installation(game_install_path)
                        if found_eboot:
                            game_launch_path = found_eboot
                        else:
                            game_launch_path = game_install_path
                else:
                    # Для iso и других
                    game_launch_path = game_install_path

                return self._create_simple_ps3_launcher(game_data, game_launch_path, game_type)

        except Exception as e:
            logger.error(f"❌ Ошибка создания PS3 лаунчера: {e}")
            import traceback
            logger.error(f"🔍 Подробности: {traceback.format_exc()}")
            return False

    def _create_simple_ps3_launcher(self, game_data: dict, game_path: Path, game_type: str) -> bool:
        """
        Создает простой лаунчер для PS3 игры с минимальным использованием echo
        и правильным экранированием.
        """
        try:
            game_id = game_data.get('id')
            game_title = game_data.get('title', 'Unknown Game')
            emulator_name = 'rpcs3'

            profile = self._find_launch_profile_by_name(emulator_name)
            if not profile:
                logger.error(f"❌ Не найден профиль запуска для {emulator_name}")
                return False

            emulator_path = self._find_appimage(emulator_name)
            if not emulator_path:
                logger.error(f"❌ {emulator_name} не найден")
                return False

            # === КРИТИЧНОЕ ЭКРАНИРОВАНИЕ ===
            emulator_path_quoted = shlex.quote(str(emulator_path))
            game_path_quoted = shlex.quote(str(game_path))

            # Получаем шаблон команды
            if 'game_types' in profile and game_type in profile['game_types']:
                command_template = profile['game_types'][game_type]
            else:
                command_template = profile.get('command_template', 
                    '{emulator_path} --no-gui --fullscreen {game_path}')

            launch_command = command_template.format(
                emulator_path=emulator_path_quoted,
                game_path=game_path_quoted
            )

            # === Конфиги PS3 ===
            ps3_config_dir = Path(get_users_subpath("configs")) / "PS3" / "rpcs3"
            ps3_config_dir.mkdir(parents=True, exist_ok=True)

            # Переменные окружения
            env_vars = profile.get('env_variables', {})
            env_script = "".join(f'export {key}="{value}"\n' for key, value in env_vars.items())

            post_actions = profile.get('post_launch_actions', [])
            post_actions_script = "\n".join(post_actions) + "\n" if post_actions else ""

            # === МИНИМАЛЬНЫЙ И БЕЗОПАСНЫЙ СКРИПТ ===
            script_content = f"""#!/bin/bash
# =============================================
# Лаунчер для: {game_title}
# =============================================
cd "{self.project_root}"

# === Настройки окружения ===
export XDG_CONFIG_HOME="{ps3_config_dir.parent}"
export XDG_DATA_HOME="{ps3_config_dir}"
export SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS="0"

# Дополнительные переменные из профиля
{env_script}

echo "🎮 Запуск: {game_title}"

# Запуск игры
{launch_command}

# Действия после завершения игры
{post_actions_script}

echo "🔚 Игра завершена"
"""

            # Сохраняем лаунчер
            launcher_path = self.scripts_dir / f"{game_id}.sh"
            with open(launcher_path, 'w', encoding='utf-8') as f:
                f.write(script_content)

            launcher_path.chmod(0o755)

            logger.info(f"✅ Создан PS3 лаунчер: {launcher_path}")
            logger.info(f"🎯 Команда: {launch_command}")

            # Обновляем реестр
            self.installed_games[game_id] = {
                'title': game_title,
                'platform': 'PS3',
                'install_path': str(game_path),
                'install_date': time.time(),
                'emulator': 'rpcs3',
                'game_type': game_type,
                'launcher_path': str(launcher_path),
                'status': 'installed'
            }
            self._save_installed_games()

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка создания PS3 лаунчера: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    # === СТАНДАРТНАЯ ЛОГИКА ДЛЯ ВСЕХ ДРУГИХ ЭМУЛЯТОРОВ ===

    def _create_standard_launcher(self, game_data: dict, game_install_path: Path,
                                platform: str, game_id: str, emulator_name: str) -> bool:
        """
        Создаёт стандартный лаунчер для игры с безопасным экранированием
        и поддержкой старых эмуляторов (duckstation, pcsx2, ppsspp).
        Стиль кода унифицирован с PS3-лаунчером.
        """
        try:
            game_title = game_data.get('title', 'Unknown Game')
            logger.info(f"🎯 Создание стандартного лаунчера для: {game_title}")

            profile = self._find_launch_profile_by_name(emulator_name)
            if not profile:
                logger.error(f"❌ Не найден профиль запуска для '{emulator_name}'")
                return False

            # === Определение пути к эмулятору ===
            installation_type = profile.get('installation_type', 'flatpak')
            if installation_type == 'appimage':
                emulator_path = self._find_appimage(emulator_name)
                if not emulator_path:
                    logger.error(f"❌ AppImage не найден для {emulator_name}")
                    return False
            else:
                emulator_path = profile.get('flatpak_id', emulator_name)

            # === КРИТИЧНОЕ ЭКРАНИРОВАНИЕ ===
            emulator_path_quoted = shlex.quote(str(emulator_path))
            game_path_quoted = shlex.quote(str(game_install_path))

            # === Формирование команды запуска с обратной совместимостью ===
            game_type = game_data.get('game_type', 'default')
            launch_command = None

            # 1. Приоритет: специальные типы игры из профиля
            if 'game_types' in profile and game_type in profile['game_types']:
                command_template = profile['game_types'][game_type]
                launch_command = command_template.format(
                    emulator_path=emulator_path_quoted,
                    game_path=game_path_quoted,
                    **{k: shlex.quote(str(v)) for k, v in {
                        'config_dir': Path(get_users_subpath("configs")) / platform,
                        'bios_dir': Path(get_users_subpath("bios")) / platform,
                        'project_root': self.project_root
                    }.items()}
                )
            # 2. Обратная совместимость: старые эмуляторы с жёсткой логикой
            elif emulator_name == 'duckstation':
                configs_dir = Path(get_users_subpath("configs")) / platform
                launch_command = self._get_duckstation_launch_command(
                    emulator_path, game_install_path, configs_dir
                )
            elif emulator_name == 'pcsx2':
                configs_dir = Path(get_users_subpath("configs")) / platform
                launch_command = self._get_pcsx2_launch_command(
                    emulator_path, game_install_path, configs_dir
                )
            elif emulator_name == 'ppsspp':
                configs_dir = Path(get_users_subpath("configs")) / platform
                launch_command = self._get_ppsspp_launch_command(
                    emulator_path, game_install_path, configs_dir
                )
            # 3. Общий шаблон из профиля
            else:
                command_template = profile.get('command_template')
                if not command_template:
                    logger.error(f"❌ Не найден command_template для эмулятора '{emulator_name}'")
                    return False
                launch_command = command_template.format(
                    emulator_path=emulator_path_quoted,
                    game_path=game_path_quoted,
                    **{k: shlex.quote(str(v)) for k, v in {
                        'config_dir': Path(get_users_subpath("configs")) / platform,
                        'bios_dir': Path(get_users_subpath("bios")) / platform,
                        'project_root': self.project_root
                    }.items()}
                )

            if not launch_command:
                logger.error(f"❌ Не удалось сформировать команду для {emulator_name}")
                return False

            # === Конфигурационные директории ===
            configs_dir = Path(get_users_subpath("configs")) / platform
            configs_dir.mkdir(parents=True, exist_ok=True)

            bios_dir = Path(get_users_subpath("bios")) / platform
            # bios_dir может не существовать — не создаём принудительно

            # === Переменные окружения (безопасное экранирование) ===
            env_vars = profile.get('env_variables', {})
            env_script = ""
            for key, value in env_vars.items():
                env_script += f"export {key}={shlex.quote(value)}\n"

            post_actions = profile.get('post_launch_actions', [])
            post_actions_script = "\n".join(post_actions) + "\n" if post_actions else ""

            # === МИНИМАЛЬНЫЙ И БЕЗОПАСНЫЙ СКРИПТ ===
            script_content = f"""#!/bin/bash
# =============================================
# Лаунчер для: {game_title}
# Платформа: {platform} | Эмулятор: {emulator_name}
# =============================================
cd "{self.project_root}"

# === Настройки окружения ===
export XDG_CONFIG_HOME="{configs_dir.parent}"
export SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS="0"

# Дополнительные переменные из профиля
{env_script}

echo "🎮 Запуск: {game_title}"

# Запуск игры
{launch_command}

# Действия после завершения игры
{post_actions_script}

echo "🔚 Игра завершена"
"""

            launcher_path = self.scripts_dir / f"{game_id}.sh"
            with open(launcher_path, 'w', encoding='utf-8') as f:
                f.write(script_content)

            launcher_path.chmod(0o755)

            logger.info(f"✅ Создан лаунчер: {launcher_path}")
            logger.info(f"🎯 Команда: {launch_command}")

            # === Регистрация игры ===
            self.installed_games[game_id] = {
                'title': game_title,
                'platform': platform,
                'install_path': str(game_install_path),
                'install_date': time.time(),
                'emulator': emulator_name,
                'game_type': game_type,
                'launcher_path': str(launcher_path),
                'status': 'installed'
            }
            self._save_installed_games()

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка создания стандартного лаунчера: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    # === МЕТОДЫ ДЛЯ КОНКРЕТНЫХ ЭМУЛЯТОРОВ ===

    def _get_duckstation_launch_command(self, emulator_path: str, game_path: Path, config_dir: Path) -> str:
        """Создает команду запуска для DuckStation (PS1)"""
        return f'{shlex.quote(emulator_path)} -fullscreen -- {shlex.quote(str(game_path))}'

    def _get_pcsx2_launch_command(self, emulator_path: str, game_path: Path, config_dir: Path) -> str:
        """Создает команду запуска для PCSX2 (PS2)"""
        return f'{shlex.quote(emulator_path)} -fullscreen -- {shlex.quote(str(game_path))}'

    def _get_ppsspp_launch_command(self, emulator_path: str, game_path: Path, config_dir: Path) -> str:
        """Создает команду запуска для PPSSPP (PSP) - ТОЛЬКО ДЛЯ FLATPAK"""
        # Для PPSSPP всегда используем flatpak run, даже если emulator_path это Flatpak ID
        return f'XDG_CONFIG_HOME={shlex.quote(str(config_dir))} flatpak run {emulator_path} {shlex.quote(str(game_path))}'

    # === МЕТОДЫ ДЛЯ СОЗДАНИЯ ЛАУНЧЕРОВ ДЛЯ ПОЛЬЗОВАТЕЛЬСКИХ ИГР ===

    def create_custom_launcher(self, game_title: str, game_path: Path, platform: str,
                             emulator_name: str, game_id: str = None) -> bool:
        """Создает лаунчер для пользовательской игры"""
        try:
            if game_id is None:
                game_id = f"custom_{int(time.time())}"

            game_data = {
                'id': game_id,
                'title': game_title,
                'platform': platform,
                'preferred_emulator': emulator_name
            }

            # Для PS3 игр используем специальную логику
            if platform == 'PS3' and emulator_name == 'rpcs3':
                game_type = self._detect_ps3_game_type(game_path)
                return self._create_simple_ps3_launcher(game_data, game_path, game_type)
            else:
                return self._create_standard_launcher(game_data, game_path, platform, game_id, emulator_name)

        except Exception as e:
            logger.error(f"❌ Ошибка создания пользовательского лаунчера: {e}")
            return False

    def create_iso_launcher(self, game_title: str, iso_path: Path, platform: str,
                          emulator_name: str, game_id: str = None) -> bool:
        """Создает лаунчер для ISO игры"""
        return self.create_custom_launcher(game_title, iso_path, platform, emulator_name, game_id)

    def create_eboot_launcher(self, game_title: str, eboot_path: Path, platform: str,
                            game_id: str = None) -> bool:
        """Создает лаунчер для игры из EBOOT.BIN"""
        return self.create_custom_launcher(game_title, eboot_path, platform, 'rpcs3', game_id)

    # === ОСТАЛЬНЫЕ МЕТОДЫ ===

    def get_install_info(self, game_id: str) -> Optional[Dict]:
        """Возвращает информацию об установке игры"""
        return self.installed_games.get(game_id)

    def is_game_installed(self, game_id: str) -> bool:
        """Проверяет, установлена ли игра"""
        return game_id in self.installed_games

    def launch_game(self, game_id: str) -> bool:
        """Запускает игру через созданный скрипт-лаунчер"""
        game_info = self.installed_games.get(game_id)
        if not game_info:
            logger.error(f"❌ Игра {game_id} не установлена")
            return False

        launcher_path = Path(game_info.get('launcher_path', ''))
        if not launcher_path or not launcher_path.exists():
            logger.error(f"❌ Лаунчер для игры {game_id} не найден: {launcher_path}")
            return False

        try:
            subprocess.Popen(['bash', str(launcher_path)], start_new_session=True)
            logger.info(f"🎮 Запускаем игру {game_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка запуска игры: {e}")
            return False

    def uninstall_game(self, game_id: str) -> bool:
        """Удаляет игру из реестра"""
        try:
            if game_id in self.installed_games:
                # Удаляем файл лаунчера
                launcher_path = Path(self.installed_games[game_id].get('launcher_path', ''))
                if launcher_path.exists():
                    launcher_path.unlink()

                # Удаляем из реестра
                del self.installed_games[game_id]
                self._save_installed_games()
                return True
        except Exception as e:
            logger.error(f"Ошибка при удалении игры: {e}")
        return False
