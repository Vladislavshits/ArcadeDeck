import os
import shutil
import json

SUPPORTED_FORMATS_FILE = "app/modules/ui/platform.json"
GAMES_DIR = "users/games/"

def detect_platform(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    with open(SUPPORTED_FORMATS_FILE, "r", encoding="utf-8") as f:
        formats = json.load(f)
        for platform, exts in formats.items():
            if ext in exts:
                return platform
    return None

def import_game(file_path):
    if not os.path.exists(file_path):
        raise ValueError("Файл не существует")

    platform = detect_platform(file_path)
    if not platform:
        raise ValueError("Неподдерживаемый формат файла")

    title = os.path.splitext(os.path.basename(file_path))[0]
    new_path = os.path.join(GAMES_DIR, f"{title}{os.path.splitext(file_path)[1]}")
    shutil.copy(file_path, new_path)

    return {
        "title": title,
        "platform": platform,
        "path": new_path
    }
