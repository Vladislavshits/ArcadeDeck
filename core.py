# core.py
import os
import sys
from PyQt5.QtCore import QFile, QTextStream

APP_VERSION = "0.1.7.0 (70) BETA"
USER_HOME = os.path.expanduser("~")

# Определяем BASE_DIR как директорию, содержащую core.py
if getattr(sys, 'frozen', False):
    # Для собранного приложения (PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Для запуска из исходников
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Определяем CONTENT_DIR как папку Content в корне проекта
CONTENT_DIR = os.path.join(BASE_DIR, "Content")

# Путь к стилям теперь в data/style
STYLES_DIR = os.path.join(BASE_DIR, "data", "style")

# Пути к файлам контента
GUIDES_JSON_PATH = os.path.join(CONTENT_DIR, "guides.json")
GAME_LIST_GUIDE_JSON_PATH = os.path.join(CONTENT_DIR, "game-list-guides.json")

# Пути к файлам стилей
DARK_STYLE = os.path.join(STYLES_DIR, "Dark-style.qss")
LIGHT_STYLE = os.path.join(STYLES_DIR, "Light-style.qss")

# Создаем необходимые директории при импорте
os.makedirs(CONTENT_DIR, exist_ok=True)
os.makedirs(STYLES_DIR, exist_ok=True)

def load_stylesheet(filename):
    """Загружает файл стилей"""
    file = QFile(filename)
    if file.exists() and file.open(QFile.ReadOnly | QFile.Text):
        stream = QTextStream(file)
        return stream.readAll()
    return ""
