#!/usr/bin/env python3
# app/updater.py

# Импорты стандартных библиотек Python
import sys
import os
import hashlib
import json
import logging
logger = logging.getLogger('Updater')
import re
import shutil
import subprocess
import tarfile
from datetime import datetime

# Импорты сторонних библиотек
import requests
from packaging import version
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QMessageBox, QProgressDialog, QWidget,
    QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout,
)

# Активация окружения через venv_manager
# Добавляем путь к корневой директории проекта
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Явно добавляем путь к текущей папке app
programm_dir = os.path.dirname(os.path.abspath(__file__))
if programm_dir not in sys.path:
    sys.path.insert(0, programm_dir)

from venv_manager import enforce_virtualenv
enforce_virtualenv()

# Импорты локальных модулей (после активации окружения)
from core import APP_VERSION, STYLES_DIR, THEME_FILE
from settings import app_settings
from app.ui_assets.theme_manager import theme_manager

# Настройки пользователя
CONFIG_DIR = os.path.join(os.path.expanduser("~"), "ArcadeDeck")
CONFIG_PATH = os.path.join(CONFIG_DIR, "updater.json")


class Updater(QObject):
    update_available = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.github_repo = "Vladislavshits/ArcadeDeck"
        self.is_beta = "beta" in APP_VERSION.lower()
        self.install_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))

        self.update_channel = "stable"  # По умолчанию стабильный канал
        self.latest_info = None

    def set_update_channel(self, channel):
        """Устанавливает канал обновлений (stable/beta)"""
        self.update_channel = channel
        logger.info(f"Установлен канал обновлений: {channel}")

    def normalize_version(self, version_str):
        """Нормализует версию для корректного сравнения"""
        # Удаляем префикс 'v' и суффиксы beta
        clean_version = version_str.lstrip('v').lower()

        # Заменяем различные написания beta на стандартное (регистронезависимо)
        clean_version = re.sub(
            r'[\s\-_]?beta[\s\-_]?', '', clean_version, flags=re.IGNORECASE)

        # Разбиваем на части и преобразуем
        # числа в int для корректного сравнения
        parts = []
        for part in clean_version.split('.'):
            if part.isdigit():
                parts.append(int(part))
            else:
                # Для нечисловых частей (например, суффиксов)
                # оставляем строкой
                parts.append(part)

        return parts

    def check_for_updates(self):
        """Проверяет наличие обновлений с учетом выбранного канала"""
        try:
            skipped_versions = self.get_skip_config()
            update_info = None
            latest_version = None
            app_version = version.parse(APP_VERSION.lstrip('v'))  # Инициализируем здесь!

            # Для стабильной версии
            if not self.is_beta:
                latest_url = (
                    f"https://api.github.com/repos/"
                    f"{self.github_repo}/releases/latest"
                )

                response = requests.get(latest_url, timeout=15)
                response.raise_for_status()
                latest_release = response.json()

                latest_version = latest_release['tag_name'].lstrip('v')

                if latest_version in skipped_versions:
                    logger.debug(f"Версия {latest_version} пропущена пользователем")
                    return None

                latest_version_parsed = version.parse(latest_version)

                if latest_version_parsed > app_version:
                    # Ищем архив с обновлением
                    for asset in latest_release.get('assets', []):
                        if not asset['name'].endswith('.tar.gz'):
                            continue

                        if "ArcadeDeck" in asset['name']:
                            # Кастомный архив
                            update_info = {
                                'release': latest_release,
                                'download_url': asset['browser_download_url'],
                                'version': latest_version,
                                'type': 'stable',
                                'asset_name': asset['name'],
                            }
                            break  # Выходим из цикла после нахождения

                        if "Source code" in asset['name']:
                            # Автогенерированный архив
                            update_info = {
                                'release': latest_release,
                                'download_url': asset['browser_download_url'],
                                'version': latest_version,
                                'type': 'stable',
                                'asset_name': (
                                    f"ArcadeDeck-{latest_version}.tar.gz"
                                ),
                            }
                            break  # Выходим из цикла после нахождения

                    if not update_info:
                        logger.error(
                            "He найден подходящий архив обновления в релизе")

            # Для бета-версии
            else:
                releases_url = (
                    f"https://api.github.com/repos/{self.github_repo}/releases"
                )
                response = requests.get(releases_url, timeout=15)
                response.raise_for_status()
                releases = response.json()

                beta_releases = [
                    r for r in releases
                    if r['prerelease']
                    and 'beta' in r['tag_name'].lower()]

                if not beta_releases:
                    logger.debug("Нет доступных бета-релизов")
                    return None

                sorted_releases = sorted(
                    beta_releases,
                    key=lambda r: version.parse(r['tag_name'].lstrip('v')),
                    reverse=True
                )

                latest_beta = sorted_releases[0]
                latest_version = latest_beta['tag_name'].lstrip('v')

                if latest_version in skipped_versions:
                    logger.debug(
                        f"Бета-версия {latest_version} пропущена пользователем"
                        )
                    return None

                latest_version_parsed = version.parse(latest_version)

                if latest_version_parsed > app_version:
                    for asset in latest_beta.get('assets', []):
                        if not asset['name'].endswith('.tar.gz'):
                            continue

                        if (
                            "ArcadeDeck" in asset['name']
                            and 'beta' in asset['name'].lower()
                        ):
                            update_info = {
                                'release': latest_beta,
                                'download_url': asset['browser_download_url'],
                                'version': latest_version,
                                'type': 'beta',
                                'asset_name': asset['name'],
                            }
                            break

                        if "Source code" in asset['name']:
                            update_info = {
                                'release': latest_beta,
                                'download_url': asset['browser_download_url'],
                                'version': latest_version,
                                'type': 'beta',
                                'asset_name': (
                                    f"ArcadeDeck-{latest_version}-beta.tar.gz"
                                ),
                            }

            # Если найдено обновление - отправляем сигнал
            if update_info:
                logger.info(f"Найдено обновление: {update_info['version']}")
                self.latest_info = update_info
                self.update_available.emit(update_info)
                return update_info
            else:
                self.latest_info = None
                logger.debug("Подходящих обновлений не найдено")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при проверке обновлений: {e}")
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при проверке обновлений: {e}")
            return None

    def get_skip_config(self):
        """Возвращает список пропущенных версий из конфига"""
        skipped_versions = []
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    skipped_versions = config.get('skipped_versions', [])
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Ошибка чтения файла",
                    f"Не удалось прочитать файл настроек updater.json.\n\n"
                    f"Возможно, файл повреждён или у вас нет прав доступа.\n"
                    f"Подробности: {e}"
                )
                # Возвращаем пустой список,
                # чтобы программа могла работать дальше
                skipped_versions = []
        return skipped_versions

    def stop_checking(self):
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()


class UpdateDownloaderThread(QThread):
    """Поток для скачивания и установки обновления"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, download_url, install_dir, asset_name, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.install_dir = install_dir
        self.asset_name = asset_name
        self.download_path = None

    def run(self):
        try:
            # Создаем временную директорию
            temp_dir = os.path.join(
                os.path.expanduser("~"), "ArcadeDeck", "temp_update")
            os.makedirs(temp_dir, exist_ok=True)

            # Формируем имя файла
            self.download_path = os.path.join(temp_dir, self.asset_name)

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

            # Распаковываем архив
            self.progress.emit(101)  # Сигнал начала распаковки
            with tarfile.open(self.download_path, "r:gz") as tar:
                tar.extractall(temp_dir)

            # Ищем директорию с обновлением
            update_dir = None
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path) and "ArcadeDeck" in item:
                    update_dir = item_path
                    break

            if not update_dir:
                raise Exception("He найдена директория c обновлением в архиве")

            # Копируем файлы
            self.progress.emit(102)  # Сигнал копирования файлов

            # Игнорируем некоторые файлы/директории
            ignore = shutil.ignore_patterns(
                'venv', '*.log', '*.bak', '__pycache__',
                'user_settings.json', 'downloads', 'temp_update',
                'updater.json', 'arcadedeck.log'
            )

            # Копируем с заменой существующих файлов
            for item in os.listdir(update_dir):
                src = os.path.join(update_dir, item)
                dst = os.path.join(self.install_dir, item)

                if os.path.isdir(src):
                    shutil.copytree(
                        src, dst, ignore=ignore, dirs_exist_ok=True
                        )
                else:
                    # Создаем директорию если нужно
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)

            # Очищаем временные файлы
            shutil.rmtree(temp_dir, ignore_errors=True)

            self.finished.emit(self.install_dir)

        except Exception as e:
            self.error.emit(str(e))


class UpdateDialog(QDialog):
    def __init__(self, current_version, new_version, changelog,
                 download_url, install_dir, asset_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Доступно обновление!")
        self.setMinimumSize(500, 400)
        self.download_url = download_url
        self.new_version = new_version
        self.install_dir = install_dir
        self.asset_name = asset_name

        layout = QVBoxLayout(self)

        title = QLabel(f"Доступна новая версия: {new_version}")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        current_label = QLabel(f"Текущая версия: {current_version}")
        current_label.setFont(QFont("Arial", 14))
        layout.addWidget(current_label)

        layout.addSpacing(20)

        changelog_label = QLabel("Изменения в новой версии:")
        changelog_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
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

        # Применяем текущую тему
        self.apply_theme(theme_manager.current_theme)

    def apply_theme(self, theme_name):
        """Применяет указанную тему к диалогу"""
        try:
            # Устанавливаем свойство класса для самого диалога
            self.setProperty("class", f"{theme_name}-theme")

            # Применяем стили ко всем виджетам в диалоге
            for widget in self.findChildren(QWidget):
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
        except Exception as e:
            print(f"Ошибка применения темы в диалоге обновления: {e}")

    def skip_version(self):
        """Добавляет версию в список пропущенных"""
        skipped_versions = []
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    skipped_versions = config.get('skipped_versions', [])
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Ошибка чтения файла",
                    f"He удалось прочитать файл настроек updater.json.\n\n"
                    f"Возможно, файл повреждён или y вас нет прав доступа.\n"
                    f"Подробности: {e}"
                )
                # Возвращаем пустой список,
                # чтобы программа могла работать дальше
                skipped_versions = []

        if self.new_version not in skipped_versions:
            skipped_versions.append(self.new_version)

        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump({'skipped_versions': skipped_versions}, f)

        self.reject()

    def start_download(self):
        """Начинает процесс скачивания и установки"""
        # Создаем прогресс-диалог
        self.progress_dialog = QProgressDialog(
            "Скачивание обновления...", "Отмена", 0, 103, self)
        self.progress_dialog.setWindowTitle("Обновление ArcadeDeck")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.canceled.connect(self.cancel_download)

        # Добавляем текстовые метки для этапов
        self.progress_dialog.setLabelText("Скачивание обновления...")

        # Создаем и запускаем поток скачивания
        self.download_thread = UpdateDownloaderThread(
            self.download_url,
            self.install_dir,
            self.asset_name
        )
        self.download_thread.progress.connect(self.update_progress)
        self.download_thread.finished.connect(self.on_install_finished)
        self.download_thread.error.connect(self.on_download_error)
        self.download_thread.start()

        self.progress_dialog.show()

    def update_progress(self, value):
        """Обновляет прогресс с учетом этапов"""
        if value == 101:
            self.progress_dialog.setLabelText("Распаковка архива...")
            self.progress_dialog.setValue(value)
        elif value == 102:
            self.progress_dialog.setLabelText("Установка файлов...")
            self.progress_dialog.setValue(value)
        else:
            self.progress_dialog.setValue(value)

    def cancel_download(self):
        """Отменяет скачивание"""
        if self.download_thread.isRunning():
            self.download_thread.terminate()
        self.progress_dialog.close()

    def on_install_finished(self, install_dir):
        """Вызывается при успешной установке"""
        self.progress_dialog.close()
        self.accept()

        # Показываем сообщение об успехе
        QMessageBox.information(
            self.parent(),
            "Обновление установлено",
            f"ArcadeDeck успешно обновлен до версии {self.new_version}!\n\n"
            "Программа будет перезапущена для применения изменений."
        )

        # Перезапускаем программу
        self.restart_application()

    def on_download_error(self, error_msg):
        """Вызывается при ошибке скачивания"""
        self.progress_dialog.close()
        QMessageBox.critical(
            self,
            "Ошибка обновления",
            f"He удалось установить обновление:\n{error_msg}"
        )

    def restart_application(self):
        """Перезапускает приложение"""
        try:
            # Определяем путь к основному скрипту
            main_script = os.path.join(self.install_dir, "app.py")

            # Для Windows
            if sys.platform == "win32":
                subprocess.Popen([sys.executable, main_script])

            # Для Linux/Steam Deck
            else:
                # Проверяем, запущен ли через ./install.sh
                if os.path.exists(os.path.join(self.install_dir, "install.sh")):
                    subprocess.Popen([os.path.join(self.install_dir, "install.sh")])
                else:
                    subprocess.Popen([sys.executable, main_script])

            # Завершаем текущий процесс
            QApplication.instance().quit()

        except Exception as e:
            print(f"Ошибка при перезапуске: {e}")
            QMessageBox.warning(
                self,
                "Перезапуск",
                "Пожалуйста, перезапустите ArcadeDeck" /
                "вручную для применения обновлений."
            )

    def run_updater(dark_theme=None, current_version=None):
        try:
            app = QApplication(sys.argv)

            # Инициализация темы до загрузки стилей
            app_settings._ensure_settings()
            current_theme = app_settings.get_theme()

            # Применяем тему к приложению
            app.setProperty("class", f"{current_theme}-theme")

            # Загрузка и применение стилей
            with open(THEME_FILE, 'r', encoding='utf-8') as f:
                stylesheet = f.read()
                app.setStyleSheet(stylesheet)

            # Инициализируем менеджер тем
            theme_manager.set_theme(current_theme)

            # Если версия не передана, используем из common
            if current_version is None:
                current_version = APP_VERSION

            # Диагностический вывод
            print(f"Запуск обновления с параметрами:")
            print(f"Тема: {'Тёмная' if dark_theme else 'Светлая'}")
            print(f"Текущая версия: {current_version}")
            mode = (
                'BETA' if 'beta' in current_version.lower() else 'Стабильный'
            )
            print(f"Режим: {mode}")

            # Определяем директорию установки
            install_dir = (
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )

            updater = Updater()
            update_info = updater.check_for_updates()

            if update_info:
                latest_version = update_info['version']
                changelog = (
                            update_info['release'].get(
                                "body", "Нет информации об изменениях")
                                )
                download_url = update_info['download_url']
                asset_name = update_info['asset_name']

                print(f"[DEBUG] Найдено обновление: {latest_version}")
                dialog = UpdateDialog(
                    current_version,
                    latest_version,
                    changelog,
                    download_url,
                    install_dir,
                    asset_name
                )
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
