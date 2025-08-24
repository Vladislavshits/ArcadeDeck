# app/modules/module_logic/game_scanner.py
import os
import json

# Корень проекта
from core import BASE_DIR

# Вычисляем абсолютный путь к корню проекта
SUPPORTED_FORMATS_FILE = os.path.join(BASE_DIR, "app", "modules", "ui", "platform.json")
GAMES_DIR = os.path.join(BASE_DIR, "users", "games")


def load_supported_formats():
    """Загружает поддерживаемые форматы из JSON-файла"""
    if not os.path.exists(SUPPORTED_FORMATS_FILE):
        return {}

    try:
        with open(SUPPORTED_FORMATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def scan_games(games_dir=None):
    """Сканирует папку с играми и возвращает список найденных игр"""
    # Отладочная информация
    print("="*50)
    print(f"[DEBUG] File: {__file__}")
    print(f"[DEBUG] BASE_DIR: {BASE_DIR}")
    print(f"[DEBUG] SUPPORTED_FORMATS_FILE: {SUPPORTED_FORMATS_FILE}")
    print(f"[DEBUG] File exists: {os.path.exists(SUPPORTED_FORMATS_FILE)}")

    if os.path.exists(SUPPORTED_FORMATS_FILE):
        print("[DEBUG] File content:")
        with open(SUPPORTED_FORMATS_FILE, "r") as f:
            print(f.read())
    else:
        print("[DEBUG] File NOT FOUND")
    print("="*50)

    supported = load_supported_formats()
    found_games = []

    # Используем переданный путь или путь по умолчанию
    scan_dir = games_dir if games_dir else GAMES_DIR

    # Проверяем существование директории с играми
    if not os.path.exists(scan_dir) or not os.path.isdir(scan_dir):
        return found_games

    try:
        # Рекурсивный поиск игр во вложенных папках
        # Используем scan_dir вместо GAMES_DIR
        for root, dirs, files in os.walk(scan_dir):
            for file in files:
                file_path = os.path.join(root, file)

                # Извлекаем расширение файла (без точки)
                _, ext = os.path.splitext(file)
                ext = ext.lower()[1:] if ext.startswith('.') else ext.lower()

                # Пропускаем файлы без расширения
                if not ext:
                    continue

                # Ищем платформу по расширению
                platform_found = None
                for platform, exts_data in supported.items():
                    # Обрабатываем разные форматы описания расширений
                    if isinstance(exts_data, dict):
                        extensions = exts_data.get("extensions", [])
                    else:
                        extensions = exts_data

                    # Проверяем совпадение расширения
                    if ext in extensions:
                        platform_found = platform
                        break

                if platform_found:
                    # Создаем ID на основе названия файла
                    game_id = os.path.splitext(file)[0].lower().replace(" ", "_")

                    # Добавляем игру в список
                    found_games.append({
                        "title": os.path.splitext(file)[0],
                        "platform": platform_found,
                        "path": file_path,
                        "id": game_id
                    })
    except Exception as e:
        print(f"Ошибка сканирования игр: {str(e)}")

    return found_games


def is_game_installed(game_data):
    """Проверяет, установлена ли игра"""
    if not game_data:
        return False

    # Проверка по пути
    if isinstance(game_data, str):
        return os.path.exists(game_data)

    # Проверка по словарю
    if isinstance(game_data, dict):
        # Проверка по пути
        if "path" in game_data:
            return os.path.exists(game_data["path"])

        # Проверка по ID или названию
        installed_games = scan_games()
        game_id = game_data.get("id")
        game_title = game_data.get("title")

        for game in installed_games:
            if game_id and game.get("id") == game_id:
                return True
            if game_title and game.get("title") == game_title:
                return True

    return False
