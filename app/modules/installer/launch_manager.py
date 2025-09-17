#!/usr/bin/env python3
import json
import logging
import shutil
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger('LaunchManager')


class LaunchManager:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.launch_profiles = self._load_launch_profiles()
        self.scripts_dir = self.project_root / 'users' / 'launchers'
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.installed_games_file = project_root / 'users' / 'installed_games.json'
        self.installed_games = self._load_installed_games()

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
                'cover_path': self._get_cover_path(game_data)  # Добавляем путь к обложке
            }
            self._save_installed_games()

    def _get_cover_path(self, game_data: dict) -> str:
        """Получить путь к обложке игры"""
        game_id = game_data.get('id')
        platform = game_data.get('platform')

        if not game_id or not platform:
            logger.warning(f"⚠️ Не удалось получить game_id или platform для поиска обложки")
            return ""

        # Используем правильный путь: project_root/users/images/{platform}/{game_id}/
        cover_dir = self.project_root / "users" / "images" / platform / game_id
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

        # Возвращаем стандартную обложку, если пользовательской нет
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

    def get_cover_path(self, game_id: str) -> str:
        """Получить путь к обложке игры по ID"""
        game_info = self.installed_games.get(game_id, {})
        cover_path = game_info.get('cover_path', '')

        if cover_path:
            # Проверяем существование файла обложки
            cover_path_obj = Path(cover_path)
            if not cover_path_obj.exists():
                logger.warning(f"⚠️ Обложка не существует по указанному пути: {cover_path}")
                return ""

        logger.info(f"🔍 Путь к обложке для игры {game_id}: {cover_path}")
        return cover_path

    def update_cover_path(self, game_id: str, cover_path: str):
        """Обновить путь к обложке игры"""
        if game_id in self.installed_games:
            self.installed_games[game_id]['cover_path'] = cover_path
            self._save_installed_games()

    def create_launcher(self, game_data: dict, game_install_path: Path) -> bool:
        """
        Создает скрипт для запуска игры.
        game_data: данные из registry_games.json
        game_install_path: путь к установленной игре (файлу .iso, .pbp и т.д.)
        """
        try:
            logger.info(f"🎯 Создание лаунчера для игры: {game_data.get('title')}")
            logger.info(f"📁 Путь к игре: {game_install_path}")
            logger.info(f"🎮 ID игры: {game_data.get('id')}")
            logger.info(f"🕹️ Эмулятор: {game_data.get('preferred_emulator')}")
            logger.info(f"📋 Платформа: {game_data.get('platform')}")

            emulator_name = game_data.get('preferred_emulator')
            platform = game_data.get('platform')
            game_id = game_data.get('id')

            if not all([emulator_name, platform, game_id]):
                logger.error("❌ В данных игры отсутствует preferred_emulator, platform или id")
                return False

            # Ищем профиль по имени эмулятора
            profile = self._find_launch_profile_by_name(emulator_name)
            if not profile:
                logger.error(f"❌ Не найден профиль запуска для эмулятора '{emulator_name}'")
                return False

            # Получаем шаблон команды из профиля
            command_template = profile.get('command_template')
            if not command_template:
                logger.error(f"❌ Не найден command_template для эмулятора '{emulator_name}'")
                return False

            # Получаем flatpak_id из профиля
            flatpak_id = profile.get('flatpak_id', '')

            # Подготавливаем переменные для подстановки в шаблон
            template_vars = {
                'config_dir': f'"{str(self.project_root / "users" / "configs" / platform)}"',
                'game_path': f'"{str(game_install_path)}"',  # Путь в кавычках!
                'game_id': game_id,
                'project_root': f'"{str(self.project_root)}"',
                'emulator_name': emulator_name,
                'flatpak_id': flatpak_id
            }

            # Заменяем плейсхолдеры в шаблоне на реальные значения
            launch_command = command_template.format(**template_vars)

            logger.info(f"🔧 Сформирована команда запуска: {launch_command}")
            logger.info(f"📁 Config dir: {template_vars['config_dir']}")
            logger.info(f"🎮 Game path: {template_vars['game_path']}")

            # Добавляем environment variables если они есть
            env_variables = profile.get('env_variables', {})
            if env_variables:
                env_lines = []
                for key, value in env_variables.items():
                    env_lines.append(f"export {key}=\"{value}\"")
                env_section = "\n".join(env_lines) + "\n"
            else:
                env_section = ""

            # Добавляем post-launch actions если они есть
            post_actions = profile.get('post_launch_actions', [])
            if post_actions:
                post_actions_section = "\n" + "\n".join(post_actions) + "\n"
            else:
                post_actions_section = ""

            # Создаем содержимое bash-скрипта
            script_content = f"""#!/bin/bash
# Launcher for {game_data.get('title')}
# Generated by ArcadeDeck

cd "{self.project_root}"
{env_section}
{launch_command}
{post_actions_section}
"""

            # Путь к файлу скрипта-лаунчера
            launcher_path = self.scripts_dir / f"{game_id}.sh"

            # Записываем скрипт
            with open(launcher_path, 'w', encoding='utf-8') as f:
                f.write(script_content)

            # Даем права на выполнение
            launcher_path.chmod(0o755)

            logger.info(f"✅ Создан лаунчер для игры {game_id}: {launcher_path}")
            logger.info(f"📝 Команда запуска: {launch_command}")

            # После успешного создания лаунчера обновляем статус игры
            self.register_installed_game(game_data, game_install_path)

            # Добавляем путь к лаунчеру в информацию об игре
            if game_id in self.installed_games:
                self.installed_games[game_id]['launcher_path'] = str(launcher_path)
                self._save_installed_games()

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка создания лаунчера: {e}")
            return False

    def get_install_info(self, game_id: str) -> Optional[Dict]:
        """Возвращает информацию об установке игры"""
        return self.installed_games.get(game_id)

    def is_game_installed(self, game_id: str) -> bool:
        """Проверяет, установлена ли игра"""
        installed_games = self.get_installed_games()
        return game_id in installed_games

    def get_all_installed_games(self) -> List[Dict]:
        """Возвращает список всех установленных игр"""
        return list(self.installed_games.values())

    def launch_game(self, game_id: str):
        """Запускает игру через созданный скрипт-лаунчер"""
        # Получаем информацию об установленной игре
        game_info = self.installed_games.get(game_id)
        if not game_info:
            logger.error(f"❌ Игра {game_id} не установлена")
            return False

        # Используем путь из launcher_path
        launcher_path = Path(game_info.get('launcher_path', ''))

        if not launcher_path.exists():
            logger.error(f"❌ Лаунчер для игры {game_id} не найден по пути: {launcher_path}")
            return False

        try:
            import subprocess
            # Запускаем в отдельном процессе, не блокируя UI
            subprocess.Popen(['bash', str(launcher_path)], start_new_session=True)
            logger.info(f"🎮 Запускаем игру {game_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка запуска игры: {e}")
            return False

    def uninstall_game(self, game_id: str) -> bool:
        """Удаляет игру из реестра"""
        try:
            installed_games = self.get_installed_games()
            if game_id in installed_games:
                # Удаляем файл лаунчера
                launcher_path = Path(installed_games[game_id].get('launcher_path', ''))
                if launcher_path.exists():
                    launcher_path.unlink()

                # Удаляем из реестра
                del installed_games[game_id]

                # Сохраняем обновленный реестр
                with open(self.installed_games_file, 'w', encoding='utf-8') as f:
                    json.dump(installed_games, f, ensure_ascii=False, indent=2)

                return True
        except Exception as e:
            print(f"Ошибка при удалении игры: {e}")
        return False
