# app/modules/module_logic/game_art_manager.py
import os
import logging
from pathlib import Path
from typing import Optional, Tuple
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

logger = logging.getLogger('GameArtManager')

class GameArtManager:
    def __init__(self, project_root: Path):
        self.images_root = project_root / "users" / "images"
        logger.info(f"Инициализация GameArtManager")
        logger.info(f"   Путь к артам: {self.images_root}")

    def get_art_dir(self, platform: str, title: str) -> Path:
        art_dir = self.images_root / platform.upper() / title
        logger.debug(f"   Папка арта: {art_dir}")
        return art_dir

    def get_cover_path(self, platform: str, title: str) -> Optional[str]:
        art_dir = self.get_art_dir(platform, title)
        if not art_dir.exists():
            logger.warning(f"   Папка не существует: {art_dir}")
            return None

        extensions = ['.png', '.jpg', '.jpeg', '.webp', '.bmp']
        for ext in extensions:
            path = art_dir / f"cover{ext}"
            if path.exists():
                logger.info(f"   Найдена пользовательская обложка: {path}")
                return str(path)

        logger.info(f"   Обложка не найдена в: {art_dir}")
        return None

    def get_pixmap(self, platform: str, title: str, size: Tuple[int, int] = None) -> Optional[QPixmap]:
        path = self.get_cover_path(platform, title)
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if pixmap.isNull():
                logger.error(f"   Не удалось загрузить изображение: {path}")
                return None
            if size:
                pixmap = pixmap.scaled(
                    size[0], size[1],
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            logger.info(f"   Обложка успешно загружена и масштабирована: {path}")
            return pixmap

        logger.info(f"   Пользовательская обложка не найдена для {platform}/{title}")
        return None

    def refresh_game_cover_optimized(self, game_data: dict, container_size: tuple) -> Optional[QPixmap]:
        """Единая точка входа для загрузки обложки — используется везде"""
        platform = game_data.get('platform')
        title = game_data.get('title')

        if not platform or not title:
            logger.warning("   Нет platform или title — нельзя загрузить обложку")
            return None

        logger.info(f"Загрузка обложки для: {platform} — {title}")

        # Попробуем пользовательскую обложку
        pixmap = self.get_pixmap(platform, title, container_size)
        if pixmap:
            logger.info(f"   Пользовательская обложка загружена")
            return pixmap

        # Fallback на стандартную из реестра
        image_path = game_data.get('image_path')
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    container_size[0], container_size[1],
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                logger.info(f"   Загружена стандартная обложка: {image_path}")
                return scaled

        logger.warning(f"   Обложка НЕ найдена нигде для {title}")
        return None
