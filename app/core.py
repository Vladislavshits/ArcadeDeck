# core.py
import os
import sys
import re
from PyQt6.QtCore import QFile, QTextStream

APP_VERSION = "0.1.7.0 (70) BETA"
USER_HOME = os.path.expanduser("~")

# Определяем BASE_DIR как директорию, содержащую core.py
if getattr(sys, 'frozen', False):
    # Для собранного приложения (PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Для запуска из исходников
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))

# Определяем CONTENT_DIR как папку Content в корне проекта
CONTENT_DIR = os.path.join(BASE_DIR, "Content")

# Путь к стилям теперь в data/style
STYLES_DIR = os.path.join(BASE_DIR, "app", "ui_assets")

# Пути к файлам контента
GUIDES_JSON_PATH = os.path.join(CONTENT_DIR, "guides.json")
GAME_LIST_GUIDE_JSON_PATH = os.path.join(CONTENT_DIR, "game-list-guides.json")

# Путь к единому файлу стилей
THEME_FILE = os.path.join(STYLES_DIR, "theme.qs5")

# Создаем необходимые директории при импорте
os.makedirs(CONTENT_DIR, exist_ok=True)
os.makedirs(STYLES_DIR, exist_ok=True)  # Это app/ui_assets

def load_stylesheet(theme_name='dark'):
    """
    Загружает стили из файла theme.qs5 и возвращает строку с CSS для указанной темы.
    :param theme_name: 'dark' или 'light'
    :return: Строка со стилями
    """
    try:
        # Проверяем существование файла стилей
        if not os.path.exists(THEME_FILE):
            print(f"Файл стилей не найден: {THEME_FILE}")
            return ""
        
        # Читаем весь файл
        with open(THEME_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Извлекаем нужную тему
        pattern = rf'/\* {theme_name.upper()} THEME \*/(.*?)/\* END {theme_name.upper()} THEME \*/'
        match = re.search(pattern, content, re.DOTALL)
        
        return match.group(1).strip() if match else ""
    except Exception as e:
        print(f"Ошибка загрузки стилей: {e}")
        return ""
