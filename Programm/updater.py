#!/usr/bin/env python3
# Programm/updater.py

import sys
import os
import requests
import subprocess
import platform
import json
from datetime import datetime

# Правильно добавляем корень проекта в путь поиска модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, 
    QPushButton, QHBoxLayout, QApplication, QMessageBox,
    QProgressDialog
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from common import APP_VERSION, STYLES_DIR, DARK_STYLE, LIGHT_STYLE, load_stylesheet

# Настройки пользователя
CONFIG_DIR = os.path.join(os.path.expanduser("~"), "PixelDeck")
CONFIG_PATH = os.path.join(CONFIG_DIR, "updater.json")

class UpdateDownloaderThread(QThread):
    """Поток для скачивания обновления в фоновом режиме"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, download_url, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.download_path = None

    def run(self):
        try:
            # Создаем директорию для загрузок
            download_dir = os.path.join(CONFIG_DIR, "downloads")
            os.makedirs(download_dir, exist_ok=True)
            
            # Формируем имя файла
            filename = f"PixelDeck_Update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            self.download_path = os.path.join(download_dir, filename)
            
            # Скачиваем файл с прогрессом
            response = requests.get(self.download_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 8192
            
            with open(self.download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress.emit(progress)
            
            self.finished.emit(self.download_path)
        except Exception as e:
            self.error.emit(str(e))

class UpdateDialog(QDialog):
    def __init__(self, current_version, new_version, changelog, download_url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Доступно обновление!")
        self.setMinimumSize(500, 400)
        self.download_url = download_url
        self.new_version = new_version
        
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
        self.skip_button = QPushButton("Пропустить эту версию")
        self.install_button = QPushButton("Установить обновление")
        button_layout.addWidget(self.later_button)
        button_layout.addWidget(self.skip_button)
        button_layout.addWidget(self.install_button)
        
        layout.addLayout(button_layout)
        
        self.later_button.clicked.connect(self.reject)
        self.skip_button.clicked.connect(self.skip_version)
        self.install_button.clicked.connect(self.start_download)
        
    def skip_version(self):
        """Добавляет версию в список пропущенных"""
        skipped_versions = []
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                    skipped_versions = config.get('skipped_versions', [])
            except:
                pass
        
        if self.new_version not in skipped_versions:
            skipped_versions.append(self.new_version)
            
        with open(CONFIG_PATH, 'w') as f:
            json.dump({'skipped_versions': skipped_versions}, f)
        
        self.reject()
        
    def start_download(self):
        """Начинает процесс скачивания обновления"""
        # Создаем прогресс-диалог
        self.progress_dialog = QProgressDialog("Скачивание обновления...", "Отмена", 0, 100, self)
        self.progress_dialog.setWindowTitle("Скачивание обновления")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.canceled.connect(self.cancel_download)
        
        # Создаем и запускаем поток скачивания
        self.download_thread = UpdateDownloaderThread(self.download_url)
        self.download_thread.progress.connect(self.progress_dialog.setValue)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.error.connect(self.on_download_error)
        self.download_thread.start()
        
        self.progress_dialog.show()
        
    def cancel_download(self):
        """Отменяет скачивание"""
        if self.download_thread.isRunning():
            self.download_thread.terminate()
        self.progress_dialog.close()
        
    def on_download_finished(self, file_path):
        """Вызывается при успешном скачивании"""
        self.progress_dialog.close()
        self.accept()
        
        # Показываем сообщение с инструкциями
        QMessageBox.information(
            self.parent(),
            "Скачивание завершено",
            f"Обновление успешно скачано в:\n{file_path}\n\n"
            "Для завершения установки:\n"
            "1. Закройте PixelDeck\n"
            "2. Распакуйте архив\n"
            "3. Запустите установочный скрипт"
        )
        
    def on_download_error(self, error_msg):
        """Вызывается при ошибке скачивания"""
        self.progress_dialog.close()
        QMessageBox.critical(
            self,
            "Ошибка скачивания",
            f"Не удалось скачать обновление:\n{error_msg}"
        )

def check_for_updates(current_version):
    """Проверяет наличие обновлений на GitHub"""
    try:
        # Проверяем пропущенные версии
        skipped_versions = []
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                    skipped_versions = config.get('skipped_versions', [])
            except:
                pass
        
        api_url = "https://api.github.com/repos/Vladislavshits/PixelDeck/releases/latest"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        release_data = response.json()
        latest_version = release_data.get("tag_name", "")
        
        # Если версия пропущена - не показываем
        if latest_version in skipped_versions:
            return None, None, None
        
        # Если есть новая версия
        if latest_version and latest_version != current_version:
            changelog = release_data.get("body", "Нет информации об изменениях")
            
            # Ищем URL для скачивания (берем первый asset)
            assets = release_data.get('assets', [])
            download_url = assets[0].get('browser_download_url') if assets else None
            
            return latest_version, changelog, download_url
    except Exception as e:
        print(f"Ошибка при проверке обновлений: {e}")
    return None, None, None

def run_updater(dark_theme=True, current_version=None):
    """Запуск процесса проверки обновлений"""
    try:
        app = QApplication(sys.argv)
        
        # Применение стилей
        style_path = DARK_STYLE if dark_theme else LIGHT_STYLE
        style = load_stylesheet(style_path)
        if style:
            app.setStyleSheet(style)
        
        # Если версия не передана, используем из common
        if current_version is None:
            current_version = APP_VERSION
        
        latest_version, changelog, download_url = check_for_updates(current_version)
        if latest_version and download_url:
            dialog = UpdateDialog(current_version, latest_version, changelog, download_url)
            dialog.exec_()
    except Exception as e:
        print(f"Критическая ошибка в updater: {e}")

if __name__ == "__main__":
    # Парсим аргументы командной строки
    dark_theme = "--dark" in sys.argv
    current_version = None
    
    for arg in sys.argv:
        if arg.startswith("--current-version="):
            current_version = arg.split('=')[1]
    
    run_updater(dark_theme, current_version)