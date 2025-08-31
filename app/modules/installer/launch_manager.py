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
        for profile_key, profile_data in self.launch_profiles.items():
            if profile_data.get('name') == emulator_name:
                return profile_data
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
                'emulator': game_data.get('preferred_emulator')
            }
            self._save_installed_games()

    def unregister_installed_game(self, game_id: str):
        """Удаляет игру из списка установленных"""
        if game_id in self.installed_games:
            del self.installed_games[game_id]
            self._save_installed_games()

    def create_launcher(self, game_data: dict, game_install_path: Path) -> bool:
        """
        Создает скрипт для запуска игры.
        game_data: данные из registry_games.json
        game_install_path: путь к установленной игре (файлу .iso, .pbp и т.д.)
        """
        try:
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
