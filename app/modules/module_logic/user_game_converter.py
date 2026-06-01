"""
Конвертер пользовательских игр в формат системы установки
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger('UserGameConverter')


class UserGameConverter:
    """
    Преобразует пользовательские игры в формат, понятный системе install.py
    """
    
    # Карта платформа → эмулятор
    PLATFORM_EMULATOR_MAP = {
        'PS1': 'duckstation',
        'PS2': 'pcsx2', 
        'PS3': 'rpcs3',
        'PSP': 'ppsspp',
        'PSVITA': 'vita3k',
        'NS1': 'yuzu',
        'NDS': 'melonds',
        'XBOX': 'xemu',
        'XBOX360': 'xenia',
        'PS4': 'rpcsx',
        'PS5': 'rpcsx',
        'WII': 'dolphin',
        'WIIU': 'cemu',
        'GC': 'dolphin',
        'GBA': 'mgba',
        'SNES': 'snes9x',
        'NES': 'mesen',
        'MD': 'genesis_plus_gx'
    }
    
    @staticmethod
    def create_game_data(
        source: str,
        source_type: str,
        title: str,
        platform: str,
        description: str = "",
        game_type: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Создает структуру game_data для системы установки
        
        Аргументы:
            source: Путь к файлу/папке или torrent/magnet ссылка
            source_type: 'file', 'folder', 'archive', 'torrent', 'magnet'
            title: Название игры
            platform: Платформа (PS1, PS2, etc.)
            description: Описание игры
            game_type: Тип игры (iso, folder, pkg, etc.)
        
        Возвращает:
            Словарь game_data в формате install.py
        """
        # Генерируем уникальный ID
        unique_hash = hashlib.md5(f"{title}{platform}{int(time.time())}".encode()).hexdigest()
        game_id = f"user_{unique_hash[:12]}"
        
        # Нормализуем платформу
        normalized_platform = platform.upper().strip()
        
        # Определяем эмулятор
        emulator = UserGameConverter.PLATFORM_EMULATOR_MAP.get(
            normalized_platform, 
            normalized_platform.lower()
        )
        
        # Базовая структура
        game_data = {
            'id': game_id,
            'title': title.strip(),
            'platform': normalized_platform,
            'platform_module': normalized_platform.lower(),
            'description': description.strip(),
            'preferred_emulator': emulator,
            'game_type': game_type.lower(),
            'is_user_game': True,  # Ключевое поле для InstallThread
            'developer': 'Пользовательская игра',
            'year': time.strftime("%Y"),
            'language': 'RU/EN',
            'genre': 'Разное',
            'rating': '0',
            'fps': '30'
        }
        
        # Добавляем источник в зависимости от типа
        if source_type in ['file', 'folder', 'archive']:
            game_data['source_path'] = source
        elif source_type in ['torrent', 'magnet']:
            game_data['torrent_url'] = source
        
        logger.info(f"✅ Создана игровая запись: '{title}' ({normalized_platform})")
        logger.info(f"📁 Тип источника: {source_type}")
        
        return game_data
    
    @staticmethod
    def detect_game_type(file_path: Optional[Path]) -> str:
        """
        Автоматически определяет тип игры по файлу
        
        Возвращает:
            'iso', 'folder', 'pkg', 'archive', 'file'
        """
        if not file_path:
            return 'unknown'
            
        if file_path.is_dir():
            # Проверяем, это папка с игрой PS3?
            if (file_path / 'EBOOT.BIN').exists() or (file_path / 'PS3_GAME').exists():
                return 'folder'
            else:
                return 'folder'
        
        extension = file_path.suffix.lower()
        
        if extension in ['.iso', '.bin', '.cue', '.chd', '.gcm', '.wbfs', '.rvz', '.nsp', '.xci']:
            return 'iso'
        elif extension == '.pkg':
            return 'pkg'
        elif extension in ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz']:
            return 'archive'
        else:
            return 'file'
