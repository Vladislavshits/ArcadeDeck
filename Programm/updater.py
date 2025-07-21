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
    def __init__(self, current_version, new_version, changelog, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Доступно обновление!")
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        title = QLabel(f"Доступна новая версия: {new_version}")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)
        
        current_label = QLabel(f"Текущая версия: {current_version}")
        current_label.setFont(QFont("Arial", 12))
        layout.addWidget(current_label)
        
        layout.addSpacing(20)
        
        changelog_label = QLabel("Изменения в новой версии:")
        changelog_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(changelog_label)
        
        self.changelog_area = QTextEdit()
        self.changelog_area.setReadOnly(True)
        self.changelog_area.setPlainText(changelog)
        layout.addWidget(self.changelog_area, 1)
        
        button_layout = QHBoxLayout()
        self.later_button = QPushButton("Напомнить позже")
        self.install_button = QPushButton("Установить обновление")
        button_layout.addWidget(self.later_button)
        button_layout.addWidget(self.install_button)
        
        layout.addLayout(button_layout)
        
        self.later_button.clicked.connect(self.reject)
        self.install_button.clicked.connect(self.accept)

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
