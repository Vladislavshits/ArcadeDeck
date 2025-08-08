import os
import json

SUPPORTED_FORMATS_FILE = "app/modules/ui/platform.json"
GAMES_DIR = "users/games/"

def load_supported_formats():
    with open(SUPPORTED_FORMATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    
def is_game_installed(game_data):
    return os.path.exists(game_data.get("path", ""))  # или своя логика по hash/id

def scan_games():
    supported = load_supported_formats()
    found_games = []

    for file in os.listdir(GAMES_DIR):
        path = os.path.join(GAMES_DIR, file)
        if not os.path.isfile(path):
            continue

        ext = os.path.splitext(file)[1].lower()
        for platform, formats in supported.items():
            if ext in formats:
                found_games.append({
                    "title": os.path.splitext(file)[0],
                    "platform": platform,
                    "path": path
                })
                break

    return found_games
