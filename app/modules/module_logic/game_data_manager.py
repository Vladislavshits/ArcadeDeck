import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger('GameData')

class GameDataManager:
    """Централизованный менеджер данных об играх"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.registry_games_file = project_root / 'app' / 'registry' / 'registry_games.json'
        self.installed_games_file = project_root / 'users' / 'installed_games.json'
        logger.info(f"[GameData] 🎮 Инициализация менеджера данных игр")
        logger.info(f"[GameData] 📁 Реестр игр: {self.registry_games_file}")
        logger.info(f"[GameData] 📁 Установленные игры: {self.installed_games_file}")

        self.registry_games = self._load_registry_games()
        self.installed_games = self._load_installed_games()

        logger.info(f"[GameData] ✅ Загружено {len(self.registry_games)} игр из реестра")
        logger.info(f"[GameData] ✅ Загружено {len(self.installed_games)} установленных игр")

    def _load_registry_games(self) -> List[Dict[str, Any]]:
        """Загружает игры из всех модулей платформ"""
        try:
            from app.registry.registry_loader import RegistryLoader
            loader = RegistryLoader(self.project_root)
            games = loader.load_all_games()
            logger.info(f"[GameData] 📋 Загружено {len(games)} игр из модулей платформ")
            return games
        except Exception as e:
            logger.error(f"[GameData] ❌ Ошибка загрузки модулей платформ: {e}")
            return []

    def _load_installed_games(self) -> Dict[str, Dict[str, Any]]:
        """Загружает установленные игры"""
        try:
            if self.installed_games_file.exists():
                with open(self.installed_games_file, 'r', encoding='utf-8') as f:
                    games = json.load(f)
                    logger.info(f"[GameData] 📋 Установленные игры успешно загружены")
                    return games
            else:
                logger.info(f"[GameData] 📋 Файл установленных игр не найден, создадим новый при установке")
        except Exception as e:
            logger.error(f"[GameData] ❌ Ошибка загрузки установленных игр: {e}")
        return {}

    def get_all_games(self) -> List[Dict[str, Any]]:
        """Возвращает ТОЛЬКО установленные игры из installed_games.json"""
        logger.info(f"[GameData] 🔍 Получение всех установленных игр...")
        result = []
        used_ids = set()

        # Добавляем игры из installed_games.json
        for game_id, installed_data in self.installed_games.items():
            if game_id not in used_ids:
                # Пытаемся найти полные данные игры в реестре
                registry_game = self._find_game_in_registry(game_id)

                if registry_game:
                    # Используем данные из реестра + информацию об установке
                    game_data = registry_game.copy()
                    game_data['is_installed'] = True
                    game_data['installed_info'] = installed_data
                    game_data['is_user_game'] = False
                else:
                    # Создаем базовые данные из installed_games.json
                    game_data = {
                        'id': game_id,
                        'title': installed_data.get('title', 'Unknown Game'),
                        'platform': installed_data.get('platform', 'Unknown'),
                        'is_installed': True,
                        'installed_info': installed_data,
                        'is_user_game': True  # Помечаем как пользовательскую, если нет в реестре
                    }

                result.append(game_data)
                used_ids.add(game_id)

        logger.info(f"[GameData] ✅ Всего установленных игр: {len(result)}")
        return result

    def _find_game_in_registry(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Ищет игру в реестре по ID"""
        for game in self.registry_games:
            if game.get('id') == game_id:
                return game
        return None

    def _scan_user_games_directly(self) -> List[Dict[str, Any]]:
        """Сканирует пользовательские игры, но только для информации (не для отображения)"""
        # Этот метод теперь используется только для внутренних целей,
        # а не для отображения игр в библиотеке
        games_dir = self.project_root / 'users' / 'games'
        if not games_dir.exists():
            return []

        logger.info(f"[GameData] 🔍 Сканирование пользовательских игр (информационно)...")

        supported_formats = self._load_supported_formats(
            self.project_root / 'app' / 'registry' / 'registry_platforms.json'
        )

        found_games = []

        try:
            for root, dirs, files in os.walk(games_dir):
                for file in files:
                    if file.startswith('.') or '.' not in file:
                        continue

                    filename, ext = os.path.splitext(file)
                    ext = ext.lower()

                    # Определяем платформу по расширению
                    platform_found = None
                    for platform_id, platform_data in supported_formats.items():
                        if isinstance(platform_data, dict):
                            extensions = platform_data.get("supported_formats", [])
                            if ext in extensions:
                                platform_found = platform_id
                                break

                    if platform_found:
                        # Генерируем временные данные (только для информации)
                        game_id = filename.lower().replace(' ', '_').replace('.', '_')
                        game_data = {
                            "title": filename.replace('_', ' ').title(),
                            "platform": platform_found,
                            "path": str(Path(root) / file),
                            "id": game_id,
                            "file_name": file
                        }
                        found_games.append(game_data)

            logger.info(f"[GameData] 📊 Найдено файлов игр: {len(found_games)}")

        except Exception as e:
            logger.error(f"[GameData] ❌ Ошибка сканирования: {e}")

        return found_games

    def _normalize_title(self, title: str) -> str:
        """Нормализует название игры для сравнения"""
        if not title:
            return ""

        # Приводим к нижнему регистру, удаляем лишние символы
        normalized = title.lower()
        normalized = normalized.replace(':', '')
        normalized = normalized.replace('-', '')
        normalized = normalized.replace('_', ' ')
        normalized = normalized.replace('.', ' ')
        normalized = ' '.join(normalized.split())  # Удаляем лишние пробелы

        return normalized.strip()

    def _load_supported_formats(self, registry_platform_file: Path) -> Dict:
        """Загружает поддерживаемые форматы"""
        if not registry_platform_file.exists():
            logger.warning(f"[GameData] ⚠️ Файл платформ не найден: {registry_platform_file}")
            return {}

        try:
            with open(registry_platform_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"[GameData] 📋 Поддерживаемые форматы загружены")
                return data
        except Exception as e:
            logger.error(f"[GameData] ❌ Ошибка загрузки форматов: {e}")
            return {}

    def get_game_by_id(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Получает игру по ID"""
        for game in self.get_all_games():
            if game.get('id') == game_id:
                return game
        return None

    def is_game_installed(self, game_id: str) -> bool:
        """Проверяет, установлена ли игра"""
        return game_id in self.installed_games

    def refresh(self):
        """Обновляет данные"""
        logger.info(f"[GameData] 🔄 Обновление данных менеджера...")
        self.registry_games = self._load_registry_games()
        self.installed_games = self._load_installed_games()
        logger.info(f"[GameData] ✅ Данные обновлены")

    def get_installed_games(self) -> List[Dict[str, Any]]:
        """Возвращает только установленные игры"""
        installed = [game for game in self.get_all_games() if game.get('is_installed')]
        logger.info(f"[GameData] 🎯 Установленных игр: {len(installed)}")
        return installed

    def get_uninstalled_games(self) -> List[Dict[str, Any]]:
        """Возвращает только не установленные игры (только для отладки)"""
        # Этот метод теперь практически не будет использоваться,
        # так как мы не показываем не установленные игры из реестра
        uninstalled = [game for game in self.get_all_games() if not game.get('is_installed')]
        logger.info(f"[GameData] 📦 Не установленных игр: {len(uninstalled)}")
        return uninstalled

    def get_all_available_games(self) -> List[Dict[str, Any]]:
        """Возвращает все игры из реестра (для поиска и установки)"""
        """Используется только в установщике/поиске, не в библиотеке"""
        result = []
        for game in self.registry_games:
            game_copy = game.copy()
            game_id = game.get('id')
            game_copy['is_installed'] = game_id in self.installed_games if game_id else False
            game_copy['installed_info'] = self.installed_games.get(game_id, {}) if game_id else {}
            result.append(game_copy)

        logger.info(f"[GameData] 📚 Всего доступных игр в реестре: {len(result)}")
        return result

# Глобальный экземпляр
_game_data_manager = None

def get_game_data_manager(project_root: Path = None) -> GameDataManager:
    """Получает глобальный экземпляр менеджера данных"""
    global _game_data_manager
    if _game_data_manager is None and project_root:
        _game_data_manager = GameDataManager(project_root)
        logger.info(f"[GameData] 🌟 Глобальный менеджер инициализирован")
    elif _game_data_manager:
        logger.info(f"[GameData] 🔄 Менеджер уже инициализирован")
    else:
        logger.warning(f"[GameData] ⚠️ Менеджер не инициализирован (project_root не передан)")
    return _game_data_manager

def set_game_data_manager(manager: GameDataManager):
    """Устанавливает глобальный экземпляр менеджера"""
    global _game_data_manager
    _game_data_manager = manager
    logger.info(f"[GameData] 🔧 Менеджер установлен вручную")
