import os
import json
import logging
import shutil
import time
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

# Импорт каталога игровых данных
from core import get_users_path
from core import get_users_subpath

logger = logging.getLogger('LaunchManager')


class LaunchManager:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.launch_profiles = self._load_launch_profiles()

        # Используем путь из настроек для лаунчеров
        users_path = Path(get_users_path())
        self.scripts_dir = users_path / 'launchers'
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

        self.installed_games_file = users_path / 'installed_games.json'
        self.installed_games = self._load_installed_games()

        # === НОВЫЙ ПУТЬ ДЛЯ УСТАНОВЛЕННЫХ ИГР PS3 ===
        # Директория для хранения папок с кодами дисков (например, BLUS30001)
        # Эта папка будет использоваться как новый источник для EBOOT.BIN
        self.ps3_games_dir = Path(get_users_subpath("games")) / "PS3"
        self.ps3_games_dir.mkdir(parents=True, exist_ok=True)

    def get_installed_games(self):
        """Возвращает словарь установленных игр"""
        if self.installed_games_file.exists():
            try:
                with open(self.installed_games_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _load_launch_profiles(self) -> Dict[str, Any]:
        """Загружает реестр профилей запуска эмуляторов"""
        profiles_path = self.project_root / 'app' / 'registry' / 'registry_launch_profiles.json'
        try:
            with open(profiles_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки реестра запуска: {e}")
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

    def _save_installed_games(self):
        """Сохраняет информацию об установленных играх"""
        try:
            self.installed_games_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.installed_games_file, 'w', encoding='utf-8') as f:
                json.dump(self.installed_games, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения installed_games: {e}")

    def _find_launch_profile_by_name(self, emulator_name: str) -> Optional[Dict[str, Any]]:
        """Ищет профиль запуска по имени эмулятора"""
        # Сначала ищем прямое совпадение
        for profile_key, profile_data in self.launch_profiles.items():
            if profile_data.get('name') == emulator_name:
                return profile_data

        # Если не нашли, пробуем найти по ключу профиля
        if emulator_name in self.launch_profiles:
            return self.launch_profiles[emulator_name]

        # Загружаем алиасы платформ
        aliases_path = self.project_root / 'app' / 'registry' / 'registry_platform_aliases.json'
        platform_aliases = {}
        if aliases_path.exists():
            try:
                with open(aliases_path, 'r', encoding='utf-8') as f:
                    aliases_data = json.load(f)
                    platform_aliases = aliases_data.get('platform_aliases', {})
            except Exception as e:
                logger.warning(f"⚠️ Не удалось загрузить алиасы платформ: {e}")

        # Если не нашли, пробуем алиасы
        if emulator_name in platform_aliases:
            alternative_id = platform_aliases[emulator_name]
            # Ищем по альтернативному ID
            for profile_key, profile_data in self.launch_profiles.items():
                if profile_data.get('name') == alternative_id:
                    logger.info(f"🔁 Использую альтернативный ID для запуска: {alternative_id}")
                    return profile_data
            # Или ищем по ключу профиля
            if alternative_id in self.launch_profiles:
                logger.info(f"🔁 Использую альтернативный ключ профиля: {alternative_id}")
                return self.launch_profiles[alternative_id]

        logger.error(f"❌ Не найден профиль запуска для эмулятора '{emulator_name}'")
        return None

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

    def register_installed_game(self, game_data: dict, install_path: Path):
        """Регистрирует установленную игру"""
        game_id = game_data.get('id')
        if game_id:
            self.installed_games[game_id] = {
                'title': game_data.get('title'),
                'platform': game_data.get('platform'),
                'install_path': str(install_path),
                'install_date': time.time(),
                'emulator': game_data.get('preferred_emulator'),
                'game_type': game_data.get('game_type', 'default'),
                'cover_path': self._get_cover_path(game_data),
                'status': 'installed'
            }
            self._save_installed_games()

    def _detect_ps3_game_type(self, game_path: Path) -> str:
        """Автоматически определяет тип PS3 игры по файлу"""
        if game_path.suffix.lower() == '.pkg':
            return 'pkg'
        elif game_path.suffix.lower() == '.iso':
            return 'iso'
        elif game_path.is_dir():
            # Проверяем, является ли папка корнем игры (наличие PS3_GAME, USRDIR, EBOOT.BIN)
            # или это папка с кодом диска.
            if (game_path / 'PS3_GAME').exists() or (game_path / 'USRDIR' / 'EBOOT.BIN').exists() or (game_path / 'EBOOT.BIN').exists():
                return 'folder'
            # Если папка - это просто код диска, то считаем ее EBOOT-запуском
            elif (game_path / 'EBOOT.BIN').exists() or (game_path.name.startswith(('NPEA', 'NPUA', 'BLES', 'BLUS', 'NPUB', 'BCES', 'BCUS'))):
                return 'eboot'
            else:
                return 'folder' # По умолчанию для папки, не PKG/ISO
        else:
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
        Ищет самую новую папку с кодом диска (например, BLUS30001) в dev_hdd0/game
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

            # Ищем папки, отсортированные по времени изменения (самая новая - только что установленная)
            game_dirs = [d for d in games_base_dir.iterdir() if d.is_dir() and d.name.startswith(('NPEA', 'NPUA', 'BLES', 'BLUS', 'NPUB', 'BCES', 'BCUS'))]

            if not game_dirs:
                logger.warning("❌ Папки игр с кодами дисков не найдены")
                # Выведем все папки для диагностики
                all_dirs = [d.name for d in games_base_dir.iterdir() if d.is_dir()]
                logger.info(f"📁 Все папки в {games_base_dir}: {all_dirs}")
                return None

            # Сортируем по времени последнего изменения (mtime)
            game_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # Берем самую новую папку
            latest_game_dir = game_dirs[0]
            logger.info(f"✅ Найден код диска: {latest_game_dir.name}")

            return latest_game_dir

        except Exception as e:
            logger.error(f"❌ Ошибка поиска кода диска: {e}")
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
        Ищет EBOOT.BIN в перемещенной папке игры.
        Ищет как в корне папки, так и в USRDIR.
        """
        # 1. Поиск в корне папки с кодом диска
        eboot_root = game_dir / "EBOOT.BIN"
        if eboot_root.exists():
            return eboot_root

        # 2. Поиск в USRDIR
        eboot_usrdir = game_dir / "USRDIR" / "EBOOT.BIN"
        if eboot_usrdir.exists():
            return eboot_usrdir

        logger.error(f"❌ EBOOT.BIN не найден в папке: {game_dir}")
        return None

    # === ОСНОВНОЙ МЕТОД СОЗДАНИЯ ЛАУНЧЕРОВ ===

    def create_launcher(self, game_data: dict, game_install_path: Path) -> bool:
        """
        Создает лаунчер для игры
        """
        try:
            logger.info(f"🎯 Создание лаунчера для игры: {game_data.get('title')}")
            logger.info(f"📁 Путь к игре: {game_install_path}")

            emulator_name = game_data.get('preferred_emulator')
            platform = game_data.get('platform')
            game_id = game_data.get('id')

            if not all([emulator_name, platform, game_id]):
                logger.error("❌ В данных игры отсутствует preferred_emulator, platform или id")
                return False

            # Для PS3 игр используем специальную логику
            if platform == 'PS3' and emulator_name == 'rpcs3':
                return self._create_ps3_launcher(game_data, game_install_path)

            # Для всех остальных платформ - стандартная логика
            else:
                return self._create_standard_launcher(game_data, game_install_path, platform, game_id, emulator_name)

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

            # === НОВАЯ ЛОГИКА ДЛЯ PKG ===
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

                # 3. Перемещаем папку игры в целевой каталог
                target_game_dir = self._move_ps3_game_folder(source_game_dir)
                if not target_game_dir:
                    logger.error("❌ Не удалось переместить папку игры")
                    return False

                # 4. Ищем EBOOT.BIN в новом каталоге
                eboot_path = self._find_eboot_after_installation(target_game_dir)
                if not eboot_path:
                    logger.error("❌ EBOOT.BIN не найден в перемещенной папке")
                    return False

                # 5. Создаем лаунчер, который запускает найденный EBOOT.BIN
                return self._create_simple_ps3_launcher(game_data, eboot_path, "eboot")

            # Для ISO, EBOOT и FOLDER - создаем лаунчер напрямую
            else:
                # В случае типа folder, убедимся, что game_install_path - это папка с игрой
                if game_type == 'folder':
                    # Для folder (Jailbreak) путь для запуска - сама папка
                    game_launch_path = game_install_path
                elif game_type == 'eboot':
                    # Для eboot путь для запуска - это EBOOT.BIN или папка, если это папка-EBOOT
                    if game_install_path.is_file():
                        game_launch_path = game_install_path
                    else:
                        # Если пользователь указал папку с кодом диска
                        found_eboot = self._find_eboot_after_installation(game_install_path)
                        if found_eboot:
                            game_launch_path = found_eboot
                        else:
                            game_launch_path = game_install_path # Fallback на папку
                else:
                    # Для iso и других
                    game_launch_path = game_install_path

                return self._create_simple_ps3_launcher(game_data, game_launch_path, game_type)

        except Exception as e:
            logger.error(f"❌ Ошибка создания PS3 лаунчера: {e}")
            return False

    def _create_simple_ps3_launcher(self, game_data: dict, game_path: Path, game_type: str) -> bool:
        """
        Создает простой лаунчер для PS3 игры с использованием реестра.
        """
        try:
            game_id = game_data.get('id')
            game_title = game_data.get('title')
            emulator_name = 'rpcs3' # Всегда rpcs3

            # Ищем профиль RPCS3 в реестре
            profile = self._find_launch_profile_by_name(emulator_name)
            if not profile:
                logger.error(f"❌ Не найден профиль запуска для {emulator_name}")
                return False

            emulator_path = self._find_appimage(emulator_name)
            if not emulator_path:
                logger.error(f"❌ {emulator_name} не найден")
                return False

            # Используем game_types из реестра launch_profiles
            if 'game_types' in profile and game_type in profile['game_types']:
                command_template = profile['game_types'][game_type]
            else:
                # Фолбэк на основной шаблон
                command_template = profile.get('command_template', f'"{emulator_path}" --no-gui --fullscreen ' + '"{game_path}"')
                logger.warning(f"⚠️ Шаблон для типа '{game_type}' не найден. Использую основной шаблон.")

            # Переменные для шаблона
            template_vars = {
                'emulator_path': f'"{emulator_path}"',
                'game_path': f'"{str(game_path)}"',
            }

            launch_command = command_template.format(**template_vars)

            # === ВАЖНО: Используем правильный путь к конфигам PS3 ===
            from core import get_users_subpath
            ps3_config_dir = Path(get_users_subpath("configs")) / "PS3" / "rpcs3"
            ps3_config_dir.mkdir(parents=True, exist_ok=True)

            # Добавляем переменные окружения из реестра
            env_vars = profile.get('env_variables', {})
            env_script = ""
            for key, value in env_vars.items():
                env_script += f'export {key}="{value}"\n'

            # Добавляем post_launch_actions
            post_actions = profile.get('post_launch_actions', [])
            post_actions_script = "\n".join(post_actions) + "\n" if post_actions else ""

            # Создаем скрипт запуска
            script_content = f"""#!/bin/bash
    cd "{self.project_root}"

    # === ВАЖНО: Правильный путь к конфигам PS3 ===
    export XDG_CONFIG_HOME="{ps3_config_dir.parent}"  # Папка PS3, содержащая rpcs3
    export XDG_DATA_HOME="{ps3_config_dir}"
    export SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS="0"

    # Дополнительные переменные окружения из реестра
    {env_script}

    echo "🎮 Запуск {game_title}..."
    echo "🚀 Команда: {launch_command}"
    echo "📁 Каталог настроек: {ps3_config_dir}"

    # Запуск игры
    {launch_command}

    # Действия после завершения игры
    {post_actions_script}

    echo "🔚 Игра завершена"
    """

            # Сохраняем скрипт
            launcher_path = self.scripts_dir / f"{game_id}.sh"
            with open(launcher_path, 'w', encoding='utf-8') as f:
                f.write(script_content)

            launcher_path.chmod(0o755)

            logger.info(f"✅ Создан лаунчер: {launcher_path}")
            logger.info(f"📁 Каталог настроек PS3: {ps3_config_dir}")

            # Обновляем информацию об игре
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
            logger.error(f"❌ Ошибка создания лаунчера: {e}")
            return False

    # === СТАНДАРТНАЯ ЛОГИКА ДЛЯ ВСЕХ ДРУГИХ ЭМУЛЯТОРОВ ===

    def _create_standard_launcher(self, game_data: dict, game_install_path: Path,
                                platform: str, game_id: str, emulator_name: str) -> bool:
        """Создает стандартный лаунчер для игры (для всех эмуляторов кроме PS3)"""
        try:
            logger.info(f"🎯 Создание стандартного лаунчера для: {game_data.get('title')}")

            # Ищем профиль эмулятора
            profile = self._find_launch_profile_by_name(emulator_name)
            if not profile:
                logger.error(f"❌ Не найден профиль запуска для эмулятора '{emulator_name}'")
                return False

            # Определяем путь к эмулятору
            installation_type = profile.get('installation_type', 'flatpak')
            emulator_path = ""

            if installation_type == 'appimage':
                emulator_path = self._find_appimage(emulator_name)
                if not emulator_path:
                    logger.error(f"❌ Не удалось найти AppImage для эмулятора '{emulator_name}'")
                    return False
            else:
                emulator_path = profile.get('flatpak_id', '')
                logger.info(f"🔧 Используется Flatpak: {emulator_path}")

            # Подготавливаем переменные для шаблона
            configs_dir = Path(get_users_subpath("configs"))
            bios_dir = Path(get_users_subpath("bios")) / platform

            template_vars = {
                'config_dir': f'"{str(configs_dir / platform)}"',
                'game_path': f'"{str(game_install_path)}"',
                'game_id': game_id,
                'project_root': f'"{str(self.project_root)}"',
                'emulator_name': emulator_name,
                'emulator_path': emulator_path,
                'flatpak_id': emulator_path,
                'bios_dir': f'"{str(bios_dir)}"'
            }

            # === НОВОЕ: Проверяем наличие game_types в реестре ===
            game_type = game_data.get('game_type', 'default')
            if 'game_types' in profile and game_type in profile['game_types']:
                # Используем специальный шаблон для типа игры
                command_template = profile['game_types'][game_type]
                launch_command = command_template.format(**template_vars)
                logger.info(f"🎮 Используется шаблон для типа игры: {game_type}")

            # === Старая логика для обратной совместимости ===
            elif emulator_name == 'duckstation':
                launch_command = self._get_duckstation_launch_command(
                    emulator_path, game_install_path, configs_dir / platform
                )
            elif emulator_name == 'pcsx2':
                launch_command = self._get_pcsx2_launch_command(
                    emulator_path, game_install_path, configs_dir / platform
                )
            elif emulator_name == 'ppsspp':
                launch_command = self._get_ppsspp_launch_command(
                    emulator_path, game_install_path, configs_dir / platform
                )
            else:
                # Используем основной шаблон из реестра
                command_template = profile.get('command_template')
                if not command_template:
                    logger.error(f"❌ Не найден command_template для эмулятора '{emulator_name}'")
                    return False
                launch_command = command_template.format(**template_vars)

            # === НОВОЕ: Добавляем переменные окружения из реестра ===
            env_vars = profile.get('env_variables', {})
            env_script = ""
            for key, value in env_vars.items():
                env_script += f'export {key}="{value}"\n'

            # === НОВОЕ: Добавляем post_launch_actions ===
            post_actions = profile.get('post_launch_actions', [])
            post_actions_script = "\n".join(post_actions) + "\n" if post_actions else ""

            # Создаем финальный скрипт запуска с новыми полями
            script_content = f"""#!/bin/bash
cd "{self.project_root}"

# Настройки окружения для эмулятора
export XDG_CONFIG_HOME="{configs_dir / platform}"
export SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS="0"

# Переменные окружения из реестра
{env_script}

echo "🎮 Запуск {emulator_name}..."

# Запуск игры
{launch_command}

# Действия после запуска
{post_actions_script}

echo "✅ Игра завершена"
"""

            # Путь к финальному лаунчеру
            final_launcher_path = self.scripts_dir / f"{game_id}.sh"

            # Записываем скрипт
            with open(final_launcher_path, 'w', encoding='utf-8') as f:
                f.write(script_content)

            # Даем права на выполнение
            final_launcher_path.chmod(0o755)

            logger.info(f"✅ Создан финальный лаунчер: {final_launcher_path}")

            # Обновляем информацию об игре
            self.installed_games[game_id] = {
                'title': game_data.get('title'),
                'platform': platform,
                'install_path': str(game_install_path),
                'install_date': time.time(),
                'emulator': emulator_name,
                'launcher_path': str(final_launcher_path),
                'status': 'installed'
            }
            self._save_installed_games()

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка создания стандартного лаунчера: {e}")
            return False

    # === МЕТОДЫ ДЛЯ КОНКРЕТНЫХ ЭМУЛЯТОРОВ (СОХРАНЕНЫ!) ===

    def _get_duckstation_launch_command(self, emulator_path: str, game_path: Path, config_dir: Path) -> str:
        """Создает команду запуска для DuckStation (PS1)"""
        return f'"{emulator_path}" -fullscreen -- "{game_path}"'

    def _get_pcsx2_launch_command(self, emulator_path: str, game_path: Path, config_dir: Path) -> str:
        """Создает команду запуска для PCSX2 (PS2)"""
        return f'"{emulator_path}" -fullscreen -- "{game_path}"'

    def _get_ppsspp_launch_command(self, emulator_path: str, game_path: Path, config_dir: Path) -> str:
        """Создает команду запуска для PPSSPP (PSP) - ТОЛЬКО ДЛЯ FLATPAK"""
        # Для PPSSPP всегда используем flatpak run, даже если emulator_path это Flatpak ID
        return f'XDG_CONFIG_HOME="{config_dir}" flatpak run {emulator_path} "{game_path}"'

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

    # === ОСТАЛЬНЫЕ МЕТОДЫ (СОХРАНЕНЫ) ===

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
        if not launcher_path.exists():
            logger.error(f"❌ Лаунчер для игры {game_id} не найден")
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
