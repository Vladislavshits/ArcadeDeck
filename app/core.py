# core.py
import os
import sys
import re
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from settings import app_settings

APP_VERSION = "0.1.7.10 (71) BETA"
USER_HOME = os.path.expanduser("~")

# Определяем базовые пути
if getattr(sys, 'frozen', False):
    # Для собранного приложения (PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Для запуска из исходников
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONTENT_DIR = os.path.join(BASE_DIR, "Content")
STYLES_DIR = os.path.join(BASE_DIR, "app", "ui_assets")
THEME_FILE = os.path.join(STYLES_DIR, "theme.qs5")

# Создаем необходимые директории
os.makedirs(CONTENT_DIR, exist_ok=True)
os.makedirs(STYLES_DIR, exist_ok=True)

def load_stylesheet(theme_name='dark'):
    """
    Загружает стили из файла theme.qs5
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

def apply_theme(app, theme_name=None):
    """
    Применяет тему ко всему приложению
    :param app: Экземпляр QApplication
    :param theme_name: 'dark' или 'light' (если None, используется системная настройка)
    """
    from settings import app_settings
    
    # Определяем тему
    if theme_name is None:
        theme_name = app_settings.get_theme()
    
    # Загружаем стили
    style = load_stylesheet(theme_name)
    
    if style:
        # Применяем кастомные стили
        app.setStyleSheet(style)
        print(f"Применена тема: {theme_name} (кастомная)")
    else:
        # Используем стандартную тему Fusion
        app.setStyle("Fusion")
        
        # Сбрасываем любые ранее примененные стили
        app.setStyleSheet("")
        
        # Создаем палитру в зависимости от темы
        palette = QPalette()
        
        if theme_name == 'dark':
            # Настройки для темной темы
            palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        else:
            # Настройки для светлой темы
            palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 240, 240))
            palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Highlight, QColor(100, 160, 220))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        
        # Применяем палитру
        app.setPalette(palette)
        print(f"Применена стандартная тема: {theme_name}")
