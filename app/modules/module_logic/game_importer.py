import os
import shutil
import time
import json
import logging
from pathlib import Path

# Настройка логирования
logger = logging.getLogger('ArcadeDeck')

GAMES_DIR = "users/games/"

class GameImporter:
    """Импортер игр с использованием централизованной системы реестров"""

    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.platform_formats_cache = {}
        self._init_registry_loader()

    def _init_registry_loader(self):
        """Инициализация загрузчика реестров"""
        try:
            from app.registry.registry_loader import RegistryLoader

            # ПРАВИЛЬНЫЙ ПУТЬ К КОРНЮ ПРОЕКТА
            # Поднимаемся на 3 уровня вверх из app/modules/module_logic/
            project_root = Path(__file__).parent.parent.parent.parent
            logger.info(f"📁 Project root: {project_root}")
            logger.info(f"📁 Путь к реестрам: {project_root / 'app' / 'registry'}")

            self.registry_loader = RegistryLoader(project_root)
            logger.info("✅ RegistryLoader инициализирован")

            # ДИАГНОСТИКА
            platforms = self.get_supported_platforms()
            logger.info(f"📊 Загружено платформ: {len(platforms)}")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации RegistryLoader: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.registry_loader = None

    def get_supported_platforms(self):
        """Возвращает все поддерживаемые платформы и их форматы"""
        if not self.registry_loader:
            logger.error("RegistryLoader не инициализирован")
            return {}

        try:
            platform_configs = self.registry_loader.get_all_platform_configs()
            platforms_data = {}

            for platform_id, config in platform_configs.items():
                formats = config.get("supported_formats", [])
                platforms_data[platform_id] = {
                    "formats": formats,
                    "name": config.get("name", platform_id),
                    "emulator": config.get("emulator", "")
                }
                logger.debug(f"📋 {platform_id}: {len(formats)} форматов")

            logger.info(f"✅ Загружено {len(platforms_data)} платформ")
            return platforms_data

        except Exception as e:
            logger.error(f"❌ Ошибка получения платформ: {e}")
            return {}

    def get_file_dialog_filters(self):
        """Возвращает фильтры для QFileDialog со всеми платформами"""
        platforms_data = self.get_supported_platforms()

        # Собираем ВСЕ поддерживаемые форматы
        all_formats = set()
        for platform_id, data in platforms_data.items():
            formats = data.get("formats", [])
            all_formats.update(formats)

        # Главный фильтр - все форматы
        filter_string = "Все поддерживаемые форматы ("
        filter_string += " ".join([f"*{fmt}" for fmt in sorted(all_formats)])
        filter_string += ")"

        # Фильтры для отдельных платформ
        platform_filters = []
        for platform_id, data in platforms_data.items():
            platform_name = data.get("name", platform_id)
            formats = data.get("formats", [])
            if formats:
                platform_filter = f"{platform_name} ("
                platform_filter += " ".join([f"*{fmt}" for fmt in sorted(formats)])
                platform_filter += ")"
                platform_filters.append(platform_filter)

        # Объединяем все фильтры
        all_filters = [filter_string] + sorted(platform_filters) + ["Все файлы (*.*)"]
        file_filter = ";;".join(all_filters)

        logger.info(f"📁 Создано фильтров: {len(platform_filters)} платформ")
        return file_filter

    # Функция для обратной совместимости
    def get_file_filters(project_root):
        """Возвращает фильтры файлов для диалога выбора"""
        importer = GameImporter(project_root)
        return importer.get_file_dialog_filters()

    def detect_platform(self, file_path):
        """Определяет платформу по расширению файла через RegistryLoader"""
        ext = os.path.splitext(file_path)[1].lower()
        logger.info(f"🔍 Определение платформы для: {file_path}")
        logger.info(f"📁 Расширение: {ext}")

        if not ext:
            logger.warning("⚠️ Файл без расширения")
            return None

        # Если RegistryLoader не доступен, используем fallback
        if not self.registry_loader:
            logger.warning("🔄 Используем fallback detection")
            return self._fallback_detect_platform(ext)

        try:
            # Получаем все конфиги платформ
            platform_configs = self.registry_loader.get_all_platform_configs()

            # Ищем платформу по расширению
            for platform_id, config in platform_configs.items():
                formats = config.get("supported_formats", [])
                if ext in formats:
                    logger.info(f"✅ СОВПАДЕНИЕ: {ext} -> {platform_id}")
                    return platform_id

            # Если не нашли, пробуем fallback
            logger.warning(f"❌ Платформа не найдена в реестре для {ext}")
            return self._fallback_detect_platform(ext)

        except Exception as e:
            logger.error(f"💥 Ошибка определения платформы: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._fallback_detect_platform(ext)

    def _fallback_detect_platform(self, ext):
        """Резервное определение платформы по расширению"""
        extension_map = {
            # PSP
            '.iso': 'psp', '.cso': 'psp', '.pbp': 'psp', '.cho': 'psp',
            '.chd': 'psp', '.prx': 'psp', '.elf': 'psp',

            # PS1
            '.bin': 'ps1', '.cue': 'ps1', '.img': 'ps1', '.mdf': 'ps1',
            '.chd': 'ps1',

            # PS2
            '.iso': 'ps2', '.mdf': 'ps2', '.mds': 'ps2', '.chd': 'ps2',

            # Nintendo DS
            '.nds': 'nds', '.srl': 'nds',

            # Nintendo 3DS
            '.3ds': '3ds', '.cia': '3ds', '.cxi': '3ds',

            # GameCube
            '.iso': 'gamecube', '.gcm': 'gamecube', '.rvz': 'gamecube',

            # Wii
            '.iso': 'wii', '.wbfs': 'wii', '.rvz': 'wii',

            # Dreamcast
            '.cdi': 'dreamcast', '.gdi': 'dreamcast',

            # Xbox
            '.iso': 'xbox', '.xbe': 'xbox',
        }

        platform = extension_map.get(ext)
        if platform:
            logger.info(f"🔄 Fallback: {ext} -> {platform}")
        else:
            logger.warning(f"🔄 Fallback: расширение {ext} не распознано")

        return platform

    def get_platform_info(self, platform_id):
        """Получает информацию о платформе из реестра"""
        if not self.registry_loader:
            return None

        try:
            config = self.registry_loader.get_platform_config(platform_id.lower())
            if config:
                return {
                    "id": platform_id,
                    "name": config.get("name", platform_id),
                    "emulator": config.get("emulator", ""),
                    "supported_formats": config.get("supported_formats", []),
                    "bios_required": config.get("bios_required", False),
                    "bios_files": config.get("bios_files", [])
                }
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о платформе {platform_id}: {e}")

        return None

    def import_game(self, file_path, target_platform=None):
        """Импортирует игру в библиотеку"""
        logger.info(f"🎮 Начало импорта игры: {file_path}")

        if not os.path.exists(file_path):
            raise ValueError("Файл не существует")

        # Определяем платформу
        if target_platform:
            platform = target_platform
            logger.info(f"🎯 Используем указанную платформу: {platform}")
        else:
            platform = self.detect_platform(file_path)

        if not platform:
            raise ValueError(f"Неподдерживаемый формат файла: {os.path.splitext(file_path)[1]}")

        # Получаем информацию о платформе
        platform_info = self.get_platform_info(platform)
        platform_name = platform_info.get("name", platform) if platform_info else platform

        # Создаем директорию для платформы, если не существует
        platform_dir = os.path.join(GAMES_DIR, platform)
        os.makedirs(platform_dir, exist_ok=True)
        logger.info(f"📁 Директория платформы: {platform_dir}")

        # Копируем файл в соответствующую директорию платформы
        filename = os.path.basename(file_path)
        new_path = os.path.join(platform_dir, filename)

        # Если файл уже существует, добавляем суффикс
        counter = 1
        base_name, ext = os.path.splitext(filename)
        while os.path.exists(new_path):
            new_path = os.path.join(platform_dir, f"{base_name}_{counter}{ext}")
            counter += 1

        logger.info(f"📋 Копируем файл в: {new_path}")
        shutil.copy2(file_path, new_path)

        # Создаем метаданные игры
        title = base_name.replace('_', ' ').title()

        game_data = {
            "id": f"{platform}_{base_name.lower()}",
            "title": title,
            "platform": platform,
            "platform_name": platform_name,
            "file_name": filename,
            "file_path": new_path,
            "file_size": os.path.getsize(new_path),
            "imported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "imported"
        }

        # Добавляем информацию об эмуляторе, если доступна
        if platform_info:
            game_data["emulator"] = platform_info.get("emulator")
            game_data["bios_required"] = platform_info.get("bios_required", False)

        logger.info(f"✅ Игра импортирована: {title} ({platform_name})")
        return game_data

    def batch_import(self, file_paths):
        """Пакетный импорт нескольких игр"""
        results = {
            "successful": [],
            "failed": [],
            "total": len(file_paths)
        }

        for file_path in file_paths:
            try:
                game_data = self.import_game(file_path)
                results["successful"].append(game_data)
            except Exception as e:
                results["failed"].append({
                    "file": file_path,
                    "error": str(e)
                })
                logger.error(f"❌ Ошибка импорта {file_path}: {e}")

        logger.info(f"📊 Импорт завершен: {len(results['successful'])} успешно, {len(results['failed'])} с ошибками")
        return results


# Функции для обратной совместимости
def create_importer(project_root):
    """Создает экземпляр импортера (для использования из других модулей)"""
    return GameImporter(project_root)


def detect_platform(file_path, project_root):
    """Определяет платформу для файла (обратная совместимость)"""
    importer = GameImporter(project_root)
    return importer.detect_platform(file_path)


def import_game(file_path, project_root, target_platform=None):
    """Импортирует игру (обратная совместимость)"""
    importer = GameImporter(project_root)
    return importer.import_game(file_path, target_platform)


# Диагностическая функция
def debug_platforms_detection(project_root):
    """Диагностика определения платформ"""
    print("\n" + "="*50)
    print("🔍 ДИАГНОСТИКА ОПРЕДЕЛЕНИЯ ПЛАТФОРМ")
    print("="*50)

    importer = GameImporter(project_root)
    platforms = importer.get_supported_platforms()

    print(f"📊 Загружено платформ: {len(platforms)}")

    for platform_id, data in platforms.items():
        formats = data.get("formats", [])
        emulator = data.get("emulator", "N/A")
        print(f"   🎮 {platform_id} ({emulator}): {len(formats)} форматов")
        if formats:
            print(f"      📁 {', '.join(formats[:5])}{'...' if len(formats) > 5 else ''}")

    print("="*50)
    return platforms


# Пример использования
if __name__ == "__main__":
    # Тестирование импортера
    project_root = Path(__file__).parent.parent
    importer = GameImporter(project_root)

    # Диагностика
    debug_platforms_detection(project_root)

    # Пример импорта
    test_file = "/path/to/game.iso"
    if os.path.exists(test_file):
        try:
            game_data = importer.import_game(test_file)
            print(f"✅ Успешно импортировано: {game_data}")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
