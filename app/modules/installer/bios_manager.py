# bios_manager.py (обновлённый)
#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import json
import zipfile
import urllib.request
import shutil
import logging

logger = logging.getLogger('BIOSManager')


class BIOSManager:
    """
    Класс для управления файлами BIOS.
    Отвечает за проверку наличия и установку необходимых файлов BIOS для эмуляторов.
    """
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.registry_path = self.project_root / 'app' / 'registry' / 'registry_bios.json'

    def ensure_bios_for_platform(self, platform: str):
        """
        Проверяет наличие необходимых файлов BIOS для указанной платформы.

        Args:
            platform (str): Название платформы (например, 'ppsspp').

        Returns:
            bool: True, если BIOS не требуется или все файлы найдены.
                  False, если произошла ошибка или файлы отсутствуют.
        """
        logger.info(f"🔍 Проверяю BIOS для платформы: {platform}")

        # Шаг 1: Проверка наличия файла реестра BIOS
        if not self.registry_path.exists():
            logger.info("ℹ️ registry_bios.json не найден — пропускаю проверку BIOS.")
            return True # Возвращаем True, так как BIOS не требуется, и это не ошибка

        # Шаг 2: Чтение файла реестра BIOS
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                registry_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"❌ Ошибка чтения или декодирования registry_bios.json: {e}")
            return False # Возвращаем False, так как это критическая ошибка

        # Шаг 3: Поиск информации о BIOS для платформы
        # Ищем по названию платформы или по названию в верхнем регистре
        bios_info = registry_data.get(platform) or registry_data.get(platform.upper())

        # Если информации о BIOS для платформы нет, значит, он не требуется
        if not bios_info:
            logger.info(f"ℹ️ BIOS для {platform} не требуется по реестру.")
            return True # Возвращаем True, так как BIOS не требуется

        # Шаг 4: Проверка наличия обязательных файлов BIOS
        required_files = bios_info.get('bios_files', [])

        # Если в реестре нет обязательных файлов, считаем, что BIOS не нужен
        if not required_files:
            logger.info(f"ℹ️ BIOS для {platform} не имеет обязательных файлов. Проверка завершена.")
            return True

        # Проверяем, существует ли папка для BIOS
        bios_dir = self.project_root / 'users' / 'bios' / platform
        bios_dir.mkdir(parents=True, exist_ok=True)

        # Находим отсутствующие файлы
        missing_files = [
            fn for fn in required_files
            if not (bios_dir / fn).exists()
        ]

        # Шаг 5: Обработка результатов
        if not missing_files:
            logger.info(f"✅ Все BIOS файлы для {platform} присутствуют.")
            return True # Все файлы на месте, возвращаем True
        else:
            bios_url = bios_info.get('bios_url', 'URL не указан')
            logger.info(f"⬇️ Не найдены BIOS файлы: {missing_files}. Требуется загрузка с: {bios_url}")
            # Здесь должна быть логика скачивания файлов
            # Пока что мы возвращаем False, чтобы сигнализировать о необходимости установки
            return False
