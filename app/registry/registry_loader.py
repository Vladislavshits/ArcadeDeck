# app/registry/registry_loader.py
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger('RegistryLoader')

class RegistryLoader:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.registry_dir = project_root / 'app' / 'registry'
        self.platforms_dir = self.registry_dir / 'platforms'

    def load_all_games(self) -> List[Dict[str, Any]]:
        """Загружает игры из всех модулей платформ"""
        all_games = []

        if not self.platforms_dir.exists():
            logger.error(f"Директория платформ не найдена: {self.platforms_dir}")
            return []

        # Сканируем все папки с платформами
        for platform_dir in self.platforms_dir.iterdir():
            if platform_dir.is_dir():
                games = self._load_platform_games(platform_dir)
                if games:
                    all_games.extend(games)
                    logger.info(f"Загружено {len(games)} игр из платформы {platform_dir.name}")

        logger.info(f"Всего загружено игр: {len(all_games)}")
        return all_games

    def _load_platform_games(self, platform_dir: Path) -> List[Dict[str, Any]]:
        """Загружает игры для конкретной платформы"""
        games_file = platform_dir / 'games.json'

        if not games_file.exists():
            return []

        try:
            with open(games_file, 'r', encoding='utf-8') as f:
                games = json.load(f)

            if not isinstance(games, list):
                logger.warning(f"Файл {games_file} не содержит список игр")
                return []

            # Добавляем информацию о платформе к каждой игре
            platform_name = platform_dir.name
            for game in games:
                if 'platform' not in game:
                    game['platform'] = platform_name.upper()
                game['platform_module'] = platform_name

            return games

        except Exception as e:
            logger.error(f"Ошибка загрузки игр из {games_file}: {e}")
            return []

    def get_platform_config(self, platform: str) -> Optional[Dict[str, Any]]:
        """Получает конфигурацию для платформы"""
        platform_dir = self.platforms_dir / platform
        config_file = platform_dir / 'config.py'

        if not config_file.exists():
            return None

        try:
            # Динамически импортируем конфиг
            import importlib.util
            spec = importlib.util.spec_from_file_location(f"{platform}_config", config_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, 'get_config'):
                config = module.get_config()
                # Добавляем идентификатор платформы
                config['id'] = platform
                return config
            else:
                logger.warning(f"Конфиг платформы {platform} не содержит функцию get_config")
                return None

        except Exception as e:
            logger.error(f"Ошибка загрузки конфига платформы {platform}: {e}")
            return None

    def get_all_platform_configs(self) -> Dict[str, Dict[str, Any]]:
        """Возвращает конфиги всех платформ"""
        platform_configs = {}

        if not self.platforms_dir.exists():
            return {}

        for platform_dir in self.platforms_dir.iterdir():
            if platform_dir.is_dir():
                config = self.get_platform_config(platform_dir.name)
                if config:
                    platform_configs[platform_dir.name] = config

        return platform_configs
