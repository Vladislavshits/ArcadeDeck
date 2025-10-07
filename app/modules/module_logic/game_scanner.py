import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger('PixelDeck')

# Корень проекта
from core import BASE_DIR

# Импорт пути к игровым данным
from core import get_users_subpath

# Вычисляем абсолютный путь к корню проекта
REGISTRY_PLATFORM_FILE = os.path.join(BASE_DIR, "app", "registry", "registry_platforms.json")
GAMES_DIR = get_users_subpath("games")

def load_supported_formats():
    """Загружает поддерживаемые форматы через RegistryLoader"""
    try:
        # ПЫТАЕМСЯ ИСПОЛЬЗОВАТЬ НОВЫЙ REGISTRYLOADER
        from app.registry.registry_loader import RegistryLoader
        loader = RegistryLoader(Path(BASE_DIR))
        platform_configs = loader.get_all_platform_configs()

        # Преобразуем в старый формат для совместимости
        supported = {}
        for platform_id, config in platform_configs.items():
            supported[platform_id] = {
                "name": config.get("name", platform_id),
                "supported_formats": config.get("supported_formats", [])
            }

        logger.info(f"✅ Загружено {len(supported)} платформ через RegistryLoader")
        return supported

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки через RegistryLoader: {e}")

        # Fallback на старый файл
        if not os.path.exists(REGISTRY_PLATFORM_FILE):
            logger.warning(f"Registry platform file not found: {REGISTRY_PLATFORM_FILE}")
            return {}

        try:
            with open(REGISTRY_PLATFORM_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"🔄 Загружено {len(data)} платформ из старого файла")
                return data
        except Exception as e2:
            logger.error(f"❌ Ошибка загрузки старого файла: {e2}")
            return {}

def scan_games(games_dir=None) -> List[Dict[str, Any]]:
    """Сканирует папку с играми и возвращает список найденных игр"""
    # Пытаемся использовать централизованный менеджер
    try:
        from .game_data_manager import get_game_data_manager
        manager = get_game_data_manager(Path(BASE_DIR))
        if manager:
            logger.info(f"🎯 Используем централизованный GameDataManager")
            return manager.get_all_games()
        else:
            logger.warning(f"⚠️ GameDataManager не инициализирован")
    except ImportError as e:
        logger.warning(f"⚠️ GameDataManager не доступен: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка доступа к GameDataManager: {e}")

    # Fallback для обратной совместимости
    logger.warning("🔄 GameDataManager не доступен, используем fallback сканирование")
    return _fallback_scan_games(games_dir)

def _fallback_scan_games(games_dir=None) -> List[Dict[str, Any]]:
    """Резервная функция сканирования"""
    logger.info("="*50)
    logger.info(f"Scanning games...")
    logger.info(f"BASE_DIR: {BASE_DIR}")
    logger.info(f"REGISTRY_PLATFORM_FILE: {REGISTRY_PLATFORM_FILE}")
    logger.info(f"File exists: {os.path.exists(REGISTRY_PLATFORM_FILE)}")

    supported = load_supported_formats()
    logger.info(f"Supported platforms: {list(supported.keys())}")

    found_games = []

    # Используем переданный путь или путь по умолчанию
    scan_dir = games_dir if games_dir else GAMES_DIR
    logger.info(f"Scanning directory: {scan_dir}")
    logger.info(f"Directory exists: {os.path.exists(scan_dir)}")

    # Проверяем существование директории с играми
    if not os.path.exists(scan_dir) or not os.path.isdir(scan_dir):
        logger.warning(f"Directory does not exist: {scan_dir}")
        return found_games

    try:
        # Рекурсивный поиск игр во вложенных папках
        file_count = 0
        for root, dirs, files in os.walk(scan_dir):
            for file in files:
                file_count += 1
                file_path = os.path.join(root, file)
                logger.debug(f"File {file_count}: {file}")

                # Извлекаем расширение файла
                filename, ext = os.path.splitext(file)
                ext = ext.lower()
                logger.debug(f"Extension: {ext}")

                # Пропускаем файлы без расширения
                if not ext:
                    logger.debug(f"Skipping - no extension")
                    continue

                # Ищем платформу по расширению
                platform_found = None
                platform_name = None

                for platform_id, platform_data in supported.items():
                    if isinstance(platform_data, dict):
                        # Получаем расширения из registry_platforms
                        extensions = platform_data.get("supported_formats", [])
                        platform_name = platform_data.get("name", platform_id)
                        logger.debug(f"Platform {platform_id} ({platform_name}) extensions: {extensions}")

                        # Проверяем совпадение расширения
                        if ext in extensions:
                            platform_found = platform_id
                            logger.info(f"MATCH: {ext} -> {platform_id} ({platform_name})")
                            break

                if platform_found:
                    # Создаем ID на основе названия файла
                    game_id = filename.lower().replace(" ", "_").replace(".", "_")

                    # Добавляем игру в список
                    game_data = {
                        "title": filename,
                        "platform": platform_found,
                        "platform_name": platform_name,
                        "path": file_path,
                        "id": game_id,
                        "file_name": file
                    }
                    found_games.append(game_data)
                    logger.info(f"ADDED: {game_data['title']} ({game_data['platform']})")
                else:
                    logger.debug(f"SKIPPED: Unsupported format {ext}")

        logger.info(f"Total files processed: {file_count}")

    except Exception as e:
        logger.error(f"Error scanning games: {str(e)}")
        import traceback
        traceback.print_exc()

    logger.info(f"Found {len(found_games)} games")
    logger.info("="*50)
    return found_games

def is_game_installed(game_data: Dict[str, Any]) -> bool:
    """Проверяет, установлена ли игра"""
    try:
        from .game_data_manager import get_game_data_manager
        manager = get_game_data_manager(Path(BASE_DIR))
        if manager and 'id' in game_data:
            return manager.is_game_installed(game_data['id'])
    except Exception as e:
        logger.error(f"❌ Ошибка проверки установки игры: {e}")
    return False

def get_installed_games() -> List[Dict[str, Any]]:
    """Возвращает список всех установленных игр"""
    try:
        from .game_data_manager import get_game_data_manager
        manager = get_game_data_manager(Path(BASE_DIR))
        if manager:
            return manager.get_installed_games()
    except Exception as e:
        logger.error(f"❌ Ошибка получения менеджера данных: {e}")
    return []

def scan_installed_games():
    """Алиас для обратной совместимости"""
    return get_installed_games()
