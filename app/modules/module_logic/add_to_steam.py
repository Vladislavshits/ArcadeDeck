# app/modules/module_logic/add_to_steam.py
import os
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger('ArcadeDeck.AddToSteam')

def add_game_to_steam(game_data, project_root):
    """
    Добавляет игру в Steam

    Args:
        game_data (dict): Данные игры
        project_root (Path): Корневая директория проекта

    Returns:
        bool: Успешно ли добавление
    """
    try:
        # Получаем ID игры и платформу
        game_id = game_data.get('id')
        platform = game_data.get('platform')

        if not game_id or not platform:
            logger.error("❌ Не удалось определить ID игры или платформу")
            return False

        # Формируем путь к лаунчеру игры
        from core import get_users_subpath
        launcher_path = Path(get_users_subpath("launchers")) / f"{game_id}.sh"

        if not launcher_path.exists():
            logger.error(f"❌ Лаунчер игры не найден: {launcher_path}")
            return False

        # Выполняем команду добавления в Steam
        cmd = ["steamos-add-to-steam", str(launcher_path)]
        logger.info(f"🎮 Добавление игры в Steam: {cmd}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info(f"✅ Игра успешно добавлена в Steam: {game_data.get('title')}")
            return True
        else:
            logger.error(f"❌ Ошибка добавления в Steam: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка при добавлении в Steam: {e}")
        return False
