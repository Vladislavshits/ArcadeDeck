#!/usr/bin/env python3
# Programm/updater.py

import sys
import os

# Родительская директорию в путь поиска модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import requests
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, 
    QPushButton, QHBoxLayout, QApplication
)
from PyQt5.QtGui import QFont
from common import APP_VERSION, STYLES_DIR, DARK_STYLE, LIGHT_STYLE, load_stylesheet

class UpdateDialog(QDialog):
    # ... (реализация из PixelDeck.py) ...

def check_for_updates():
    """Проверяет наличие обновлений на GitHub"""
    try:
        api_url = "https://api.github.com/repos/Vladislavshits/PixelDeck/releases/latest"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        release_data = response.json()
        latest_version = release_data.get("tag_name", "")
        
        if latest_version and latest_version != APP_VERSION:
            changelog = release_data.get("body", "Нет информации об изменениях")
            return latest_version, changelog
    except Exception as e:
        print(f"Ошибка при проверке обновлений: {e}")
    return None, None

def run_updater(dark_theme=True):
    """Запуск процесса проверки обновлений"""
    app = QApplication(sys.argv)
    
    # Применение стилей
    style_path = DARK_STYLE if dark_theme else LIGHT_STYLE
    style = load_stylesheet(style_path)
    if style:
        app.setStyleSheet(style)
    
    latest_version, changelog = check_for_updates()
    if latest_version:
        dialog = UpdateDialog(APP_VERSION, latest_version, changelog)
        dialog.exec_()

if __name__ == "__main__":
    # Получаем тему из аргументов
    dark_theme = "--dark" in sys.argv
    run_updater(dark_theme)
