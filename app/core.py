import os
import sys
import json
import logging
from pathlib import Path

from PyQt6.QtWidgets import QApplication

logger = logging.getLogger('Модуль путей')

APP_VERSION = "0.1.98-beta"
USER_HOME = os.path.expanduser("~")

# Определяем базовые пути
if getattr(sys, 'frozen', False):
    # Для собранного приложения (PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Для запуска из исходников
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Пути к корню проекта
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Определяем путь к виртуальному окружению
VENV_PATH = os.path.join(BASE_DIR, "app", "venv")

# Пути к модулям программы
STYLES_DIR = os.path.join(BASE_DIR, "app", "ui_assets")
THEME_FILE = os.path.join(STYLES_DIR, "theme.qs5")

# Путь к конфигурации настроек
CONFIG_DIR = os.path.join(BASE_DIR, "app", "config")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.ini")

# Функция для получения пути к users из настроек
def get_users_path():
    """Возвращает путь к папке users из настроек"""
    try:
        from app.settings import app_settings
        app_settings._ensure_settings()
        return app_settings.get_users_path()
    except Exception as e:
        # Fallback на путь по умолчанию
        default_path = os.path.join(BASE_DIR, "users")
        print(f"⚠️ Не удалось загрузить путь из настроек, использую по умолчанию: {default_path}")
        return default_path

# Функция для получения пути к конкретной подпапке users
def get_users_subpath(subfolder):
    """Возвращает путь к подпапке внутри users (games, saves, images и т.д.)"""
    users_path = get_users_path()
    return os.path.join(users_path, subfolder)

def update_launcher_scripts(old_users_path, new_users_path):
    """
    Обновляет пути в скриптах запуска игр после изменения расположения users
    """
    try:
        logger.info(f"🔄 Обновление скриптов запуска:")
        logger.info(f"   Старый путь: {old_users_path}")
        logger.info(f"   Новый путь: {new_users_path}")

        # Путь к папке с лаунчерами в НОВОМ расположении
        new_launchers_dir = Path(new_users_path) / "launchers"

        # Проверяем существование папки со скриптами в НОВОМ пути
        if not new_launchers_dir.exists():
            logger.info(f"ℹ️ Папка со скриптами не найдена: {new_launchers_dir}")
            return True

        # Получаем все файлы скриптов из НОВОГО расположения
        script_files = list(new_launchers_dir.glob("*.sh"))

        if not script_files:
            logger.info("ℹ️ Скрипты запуска не найдены")
            return True

        updated_scripts = 0

        for script_file in script_files:
            try:
                # Читаем содержимое скрипта
                with open(script_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Сохраняем оригинальное содержимое для сравнения
                old_content = content

                # Ищем ВСЕ пути, содержащие "ArcadeDeck/users" и заменяем их
                import re

                # Паттерн для поиска всех путей ArcadeDeck/users
                pattern = r'/home/deck/[^/]+/ArcadeDeck/users'

                # Заменяем все старые пути на новый
                content = re.sub(pattern, new_users_path, content)

                # Дополнительно: заменяем конкретный старый путь, если он отличается от pattern
                if old_users_path in content:
                    content = content.replace(old_users_path, new_users_path)

                # Если изменения были, сохраняем обновленный скрипт
                if content != old_content:
                    # Перезаписываем тот же файл
                    with open(script_file, 'w', encoding='utf-8') as f:
                        f.write(content)

                    # Делаем скрипт исполняемым (на всякий случай)
                    script_file.chmod(0o755)

                    updated_scripts += 1
                    logger.info(f"✅ Обновлен скрипт: {script_file.name}")

                    # Детальное логирование изменений
                    old_lines = old_content.split('\n')
                    new_lines = content.split('\n')

                    for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines)):
                        if old_line != new_line:
                            logger.info(f"   Строка {i+1}:")
                            logger.info(f"     Было: {old_line}")
                            logger.info(f"     Стало: {new_line}")
                else:
                    logger.info(f"ℹ️ Скрипт {script_file.name} не требует обновления")

            except Exception as e:
                logger.error(f"❌ Ошибка при обновлении скрипта {script_file.name}: {e}")
                continue

        logger.info(f"✅ Обновлено скриптов: {updated_scripts}/{len(script_files)}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении скриптов запуска: {e}")
        import traceback
        logger.error(f"📋 Подробности ошибки: {traceback.format_exc()}")
        return False

def update_installation_paths(old_users_path, new_users_path):
    """
    Обновляет пути в installed_games.json и скриптах запуска после изменения расположения users
    """
    try:
        # Ищем installed_games.json в СТАРОМ пути (где он реально находится)
        old_installed_games_file = Path(old_users_path) / "installed_games.json"
        new_installed_games_file = Path(new_users_path) / "installed_games.json"

        logger.info(f"🔍 Поиск installed_games.json:")
        logger.info(f"   Старый путь: {old_installed_games_file}")
        logger.info(f"   Новый путь: {new_installed_games_file}")

        # Сначала проверяем старый путь (где файл реально находится)
        installed_games_file = None
        if old_installed_games_file.exists():
            installed_games_file = old_installed_games_file
            logger.info(f"✅ Найден installed_games.json в старом пути")
        elif new_installed_games_file.exists():
            installed_games_file = new_installed_games_file
            logger.info(f"✅ Найден installed_games.json в новом пути")
        else:
            logger.info("❌ Файл installed_games.json не найден ни в старом, ни в новом пути")
            return True

        # Читаем файл
        logger.info(f"📖 Чтение файла: {installed_games_file}")
        with open(installed_games_file, 'r', encoding='utf-8') as f:
            installed_games = json.load(f)

        updated = False

        for game_id, game_info in installed_games.items():
            # Обновляем путь к лаунчеру (скрипту запуска)
            if game_info.get('launcher_path'):
                old_launcher_path = game_info['launcher_path']

                # Извлекаем относительный путь от старой папки users
                if old_users_path in old_launcher_path:
                    relative_launcher_path = Path(old_launcher_path).relative_to(Path(old_users_path))
                    new_launcher_path = str(Path(new_users_path) / relative_launcher_path)
                    game_info['launcher_path'] = new_launcher_path
                    updated = True
                    logger.info(f"🔄 Обновлен путь лаунчера для {game_id}:")
                    logger.info(f"   Было: {old_launcher_path}")
                    logger.info(f"   Стало: {new_launcher_path}")

            # Обновляем путь к файлу игры
            if game_info.get('install_path'):
                old_install_path = game_info['install_path']

                # Извлекаем относительный путь от старой папки users
                if old_users_path in old_install_path:
                    relative_install_path = Path(old_install_path).relative_to(Path(old_users_path))
                    new_install_path = str(Path(new_users_path) / relative_install_path)
                    game_info['install_path'] = new_install_path
                    updated = True
                    logger.info(f"🔄 Обновлен путь игры для {game_id}:")
                    logger.info(f"   Было: {old_install_path}")
                    logger.info(f"   Стало: {new_install_path}")

        if updated:
            # Сохраняем обновленный файл в НОВОМ пути
            new_installed_games_file.parent.mkdir(parents=True, exist_ok=True)
            with open(new_installed_games_file, 'w', encoding='utf-8') as f:
                json.dump(installed_games, f, ensure_ascii=False, indent=2)

            # Если файл был в старом пути, удаляем его оттуда
            if installed_games_file == old_installed_games_file and old_installed_games_file.exists():
                old_installed_games_file.unlink()
                logger.info(f"🗑️ Удален старый файл installed_games.json: {old_installed_games_file}")

            logger.info("✅ Все пути в installed_games.json успешно обновлены")

            # Логируем результат для проверки
            logger.info("📋 Итоговые пути в installed_games.json:")
            for game_id, game_info in installed_games.items():
                logger.info(f"   {game_id}:")
                logger.info(f"     install_path: {game_info.get('install_path')}")
                logger.info(f"     launcher_path: {game_info.get('launcher_path')}")

        else:
            logger.info("ℹ️ Обновление путей не требуется (пути уже актуальны)")

        # ОБНОВЛЯЕМ СКРИПТЫ ЗАПУСКА
        scripts_updated = update_launcher_scripts(old_users_path, new_users_path)

        return updated and scripts_updated

    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении путей: {e}")
        import traceback
        logger.error(f"📋 Подробности ошибки: {traceback.format_exc()}")
        return False


# Создаем необходимые директории
os.makedirs(STYLES_DIR, exist_ok=True)
