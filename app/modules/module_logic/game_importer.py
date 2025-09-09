import os
import shutil
import json
import logging
from pathlib import Path

# Настройка логирования
logger = logging.getLogger('ArcadeDeck')

# Новый путь к реестру платформ
REGISTRY_PLATFORMS_FILE = "app/registry/registry_platforms.json"
GAMES_DIR = "users/games/"


def detect_platform(file_path):
    """Определяет платформу по расширению файла используя новый реестр"""
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        # Загружаем новый реестр платформ
        if not os.path.exists(REGISTRY_PLATFORMS_FILE):
            logger.error(f"Registry file not found: {REGISTRY_PLATFORMS_FILE}")
            return None
            
        with open(REGISTRY_PLATFORMS_FILE, "r", encoding="utf-8") as f:
            platforms_data = json.load(f)
        
        # Ищем платформу по расширению в новом реестре
        for platform_id, platform_info in platforms_data.items():
            supported_formats = platform_info.get("supported_formats", [])
            if ext in supported_formats:
                logger.info(f"Detected platform {platform_id} for file {file_path}")
                return platform_id
                
        logger.warning(f"No platform found for extension {ext}")
        return None
        
    except Exception as e:
        logger.error(f"Error detecting platform: {e}")
        return None

def import_game(file_path):
    """Импортирует игру в библиотеку"""
    if not os.path.exists(file_path):
        raise ValueError("Файл не существует")

    platform = detect_platform(file_path)
    if not platform:
        raise ValueError("Неподдерживаемый формат файла")

    # Создаем директорию для платформы, если не существует
    platform_dir = os.path.join(GAMES_DIR, platform)
    os.makedirs(platform_dir, exist_ok=True)

    # Копируем файл в соответствующую директорию платформы
    filename = os.path.basename(file_path)
    new_path = os.path.join(platform_dir, filename)
    
    # Если файл уже существует, добавляем суффикс
    counter = 1
    base_name, ext = os.path.splitext(filename)
    while os.path.exists(new_path):
        new_path = os.path.join(platform_dir, f"{base_name}_{counter}{ext}")
        counter += 1

    shutil.copy2(file_path, new_path)

    # Создаем базовые метаданные игры
    title = base_name.replace('_', ' ').title()

    return {
        "title": title,
        "platform": platform,
        "path": new_path,
        "file_name": filename,
        "id": f"{platform}_{base_name.lower()}"
    }
