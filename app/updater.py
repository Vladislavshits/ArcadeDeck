#!/usr/bin/env python3
# Programm/updater.py
import sys
import os
from packaging import version

# Активация окружения через venv_manager
# Добавляем путь к корневой директории проекта
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Явно добавляем путь к текущей папке Programm
programm_dir = os.path.dirname(os.path.abspath(__file__))
if programm_dir not in sys.path:
    sys.path.insert(0, programm_dir)

from venv_manager import enforce_virtualenv
enforce_virtualenv()

import requests
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, 
    QPushButton, QHBoxLayout, QApplication, QMessageBox,
    QProgressDialog
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from core import APP_VERSION, STYLES_DIR, THEME_FILE

# Настройки пользователя
CONFIG_DIR = os.path.join(os.path.expanduser("~"), "PixelDeck")
CONFIG_PATH = os.path.join(CONFIG_DIR, "updater.json")

class Updater:
    def __init__(self, parent=None):
        self.parent = parent
        self.github_repo = "Vladislavshits/PixelDeck"
        # Проверяем, содержит ли APP_VERSION подстроку 'beta' в любом регистре
        self.is_beta = "beta" in APP_VERSION.lower()
        
    def check_for_updates(self):
        try:
            # Загружаем список пропущенных версий
            skipped_versions = self.get_skip_config()
            
            # Для стабильной версии: получаем "Latest Release"
            if not self.is_beta:
                latest_url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
                response = requests.get(latest_url, timeout=10)
                response.raise_for_status()
                latest_release = response.json()
                
                latest_version = latest_release['tag_name']
                
                # Если версия пропущена - игнорируем
                if latest_version in skipped_versions:
                    return None
                
                current_version = APP_VERSION
                if version.parse(latest_version.lstrip('v')) > version.parse(current_version):
                    return latest_release
            
            # Для бета-версии: получаем все пре-релизы
            else:
                releases_url = f"https://api.github.com/repos/{self.github_repo}/releases"
                response = requests.get(releases_url, timeout=10)
                response.raise_for_status()
                releases = response.json()
                
                # Фильтруем только пре-релизы
                beta_releases = [r for r in releases if r['prerelease']]
                
                if not beta_releases:
                    return None
                    
                # Сортируем по версии (новые сверху)
                sorted_releases = sorted(
                    beta_releases,
                    key=lambda x: version.parse(x['tag_name'].lstrip('v')),
                    reverse=True
                )
                
                latest_beta = sorted_releases[0]
                latest_version = latest_beta['tag_name']
                
                # Если версия пропущена - игнорируем
                if latest_version in skipped_versions:
                    return None
                
                # Удаляем различные варианты написания 'beta' из текущей версии
                current_version = APP_VERSION
                for suffix in [' BETA', ' beta', ' Beta']:
                    current_version = current_version.replace(suffix, '')
                
                if version.parse(latest_version.lstrip('v')) > version.parse(current_version):
                    return latest_beta
                
        except Exception as e:
            print(f"Ошибка при проверке обновлений: {str(e)}")
            return None
            
        return None

    def get_skip_config(self):
        """Возвращает список пропущенных версий из конфига"""
        skipped_versions = []
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                    skipped_versions = config.get('skipped_versions', [])
            except:
                pass
        return skipped_versions

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

def run_updater(dark_theme=True, current_version=None):
    """Запуск процесса проверки обновлений"""
    try:
        app = QApplication(sys.argv)
        
        # Загрузка стилей
        try:
            with open(THEME_FILE, 'r', encoding='utf-8') as f:
                global_stylesheet = f.read()
            app.setStyleSheet(global_stylesheet)
        except Exception as e:
            print(f"Ошибка загрузки стилей: {e}")
        
        # Устанавливаем класс темы
        app.setProperty("class", "dark-theme" if dark_theme else "light-theme")
        
        # Если версия не передана, используем из common
        if current_version is None:
            current_version = APP_VERSION
        
        # Диагностический вывод
        print(f"Запуск обновления с параметрами:")
        print(f"Тема: {'Тёмная' if dark_theme else 'Светлая'}")
        print(f"Текущая версия: {current_version}")
        
        updater = Updater()
        release = updater.check_for_updates()
        
        if release:
            latest_version = release['tag_name']
            changelog = release.get("body", "Нет информации об изменениях")
            assets = release.get('assets', [])
            download_url = assets[0].get('browser_download_url') if assets else None
            
            if download_url:
                dialog = UpdateDialog(current_version, latest_version, changelog, download_url)
                dialog.exec()
    except Exception as e:
        print(f"Критическая ошибка в updater: {e}")

if __name__ == "__main__":
    # Парсинг аргументов по умолчанию
    dark_theme = False
    current_version = None
    
    # Обработка аргументов командной строки
    args = sys.argv[1:]  # Пропускаем первый аргумент (имя скрипта)
    
    # Определение темы интерфейса
    if "--dark" in args:
        dark_theme = True
    if "--light" in args:
        dark_theme = False
        
    # Поиск версии в аргументах
    for arg in args:
        if arg.startswith("--current-version="):
            # Разделяем аргумент по знаку '=' и берем вторую часть
            current_version = arg.split('=', 1)[1]
    
    # Запуск основного процесса обновления
    run_updater(dark_theme, current_version)