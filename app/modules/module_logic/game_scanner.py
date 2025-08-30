# app/modules/module_logic/game_scanner.py
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# Настройка логирования
logger = logging.getLogger('PixelDeck')

# Корень проекта
from core import BASE_DIR

# Вычисляем абсолютный путь к корню проекта
REGISTRY_PLATFORM_FILE = os.path.join(BASE_DIR, "app", "registry", "registry_platforms.json")
GAMES_DIR = os.path.join(BASE_DIR, "users", "games")


def load_supported_formats():
    """Загружает поддерживаемые форматы из registry_platforms.json"""
    if not os.path.exists(REGISTRY_PLATFORM_FILE):
        logger.warning(f"Registry platform file not found: {REGISTRY_PLATFORM_FILE}")
        return {}

    try:
        with open(REGISTRY_PLATFORM_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"Loaded registry platform data")
            return data
    except Exception as e:
        logger.error(f"Error loading registry platform: {e}")
        return {}


def scan_games(games_dir=None) -> List[Dict[str, Any]]:
    """Сканирует папку с играми и возвращает список найденных игр"""
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


def is_game_installed(game_data) -> bool:
    """
    Проверяет, установлена ли игра используя новую систему манифестов
    """
    if not game_data:
        return False

    try:
        # Импортируем LaunchManager
        from app.modules.installer.launch_manager import LaunchManager
        
        # Создаем экземпляр LaunchManager
        launch_manager = LaunchManager(Path(BASE_DIR))
        
        # Получаем ID игры
        if isinstance(game_data, dict):
            game_id = game_data.get('id')
        elif isinstance(game_data, str):
            game_id = game_data
        else:
            return False
            
        # Проверяем через новую систему
        return launch_manager.is_game_installed(game_id)
        
    except ImportError:
        # Fallback: старая система проверки через сканирование файлов
        logger.warning("LaunchManager not available, using fallback scanning")
        
        if isinstance(game_data, str):
            return os.path.exists(game_data)

        if isinstance(game_data, dict):
            # Проверка по пути
            if "path" in game_data:
                return os.path.exists(game_data["path"])

            # Проверка по ID или названию через сканирование
            installed_games = scan_games()
            game_id = game_data.get("id")
            game_title = game_data.get("title")

            for game in installed_games:
                if game_id and game.get("id") == game_id:
                    return True
                if game_title and game.get("title") == game_title:
                    return True

        return False
    except Exception as e:
        logger.error(f"Error checking if game is installed: {e}")
        return False


def get_installed_games() -> List[Dict[str, Any]]:
    """
    Возвращает список всех установленных игр используя новую систему манифестов
    """
    try:
        from app.modules.installer.launch_manager import LaunchManager
        launch_manager = LaunchManager(Path(BASE_DIR))
        return launch_manager.get_all_installed_games()
    except ImportError:
        logger.warning("LaunchManager not available, using fallback scanning")
        return scan_games()
    except Exception as e:
        logger.error(f"Error getting installed games: {e}")
        return []


# Сохраняем обратную совместимость для существующего кода
def scan_installed_games():
    """Алиас для обратной совместимости"""
    return get_installed_games()
