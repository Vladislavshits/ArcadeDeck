# core.py
import os
import sys
from PyQt6.QtWidgets import QApplication

APP_VERSION = "0.1.73-beta"
USER_HOME = os.path.expanduser("~")

# Определяем базовые пути
if getattr(sys, 'frozen', False):
    # Для собранного приложения (PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Для запуска из исходников
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Пути к компонентам программы
CONTENT_DIR = os.path.join(BASE_DIR, "Content")
STYLES_DIR = os.path.join(BASE_DIR, "app", "ui_assets")
THEME_FILE = os.path.join(STYLES_DIR, "theme.qs5")
GUIDES_JSON_PATH = os.path.join(CONTENT_DIR, "guides.json")
GAME_LIST_GUIDE_JSON_PATH = os.path.join(CONTENT_DIR, "game-list-guides.json")

# Создаем необходимые директории
os.makedirs(CONTENT_DIR, exist_ok=True)
os.makedirs(STYLES_DIR, exist_ok=True)
