import sys
import json
import os
import time
from typing import Dict, Optional
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QLabel,
                           QProgressBar, QPushButton, QHBoxLayout, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import logging

# Импорты системы установки
from .auto_installer import AutoInstaller
from .emulator_manager import EmulatorManager
from .bios_manager import BIOSManager
from .config_manager import ConfigManager
from .game_downloader import GameDownloader

# Создаем основной логгер приложения
logger = logging.getLogger('PixelDeck')


class InstallThread(QThread):
    """
    Класс потока для выполнения установки в фоновом режиме.
    """
    # Сигналы для связи с основным потоком GUI
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    stopped = pyqtSignal()

    def __init__(self, game_data: dict, install_dir: Path, project_root: Path, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.install_dir = install_dir
        self.project_root = project_root

        # Создаем экземпляр AutoInstaller, отключая тестовый режим
        self.installer = AutoInstaller(
            game_data=self.game_data,
            install_dir=self.install_dir,
            project_root=self.project_root,
            test_mode=False
        )
        # Подключаем сигналы от installer напрямую к сигналам потока
        self.installer.progress_updated.connect(self.progress_updated.emit)
        self.installer.finished.connect(self.finished.emit)
        self.installer.error_occurred.connect(self.error_occurred.emit)

    def run(self):
        """Выполняет основную работу в потоке."""
        try:
            self.installer.run()
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.stopped.emit()

    def stop(self):
        """Метод для безопасной остановки потока."""
        if self.installer:
            self.installer.stop()


class InstallValidator:
    """Класс для валидации данных перед установкой."""
    @staticmethod
    def validate_game_data(game_data: Dict) -> Optional[str]:
        required_fields = ['id', 'title', 'platform', 'torrent_url']
        missing = [f for f in required_fields if f not in game_data]
        if missing:
            return f"Отсутствуют обязательные поля: {', '.join(missing)}"
        if not isinstance(game_data['torrent_url'], str):
            return "Некорректный формат torrent_url"
        if not game_data['torrent_url'].startswith(('magnet:', 'http://', 'https://')):
            return "Неподдерживаемый тип ссылки для скачивания"
        return None

    @staticmethod
    def prepare_install_dir(platform: str, base_path: Path) -> Path:
        install_dir = base_path / "users" / "games" / platform
        try:
            install_dir.mkdir(parents=True, exist_ok=True)
            if not os.access(install_dir, os.W_OK):
                raise PermissionError("Нет прав на запись в директорию")
            return install_dir
        except Exception as e:
            raise RuntimeError(f"Ошибка подготовки директории: {str(e)}")


class InstallDialog(QDialog):
    """Диалог установки с индикатором прогресса."""

    def __init__(self, game_data: Dict, project_root: Path, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.project_root = project_root
        self.thread = None
        self.setWindowTitle("Установка игры")
        self.resize(500, 350)
        self._init_ui()
        self.validate_and_start()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        self.status_label = QLabel("Подготовка к установке...", self)
        main_layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.progress_bar)

        self.pause_button = QPushButton("Пауза", self)
        self.cancel_button = QPushButton("Отмена", self)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.pause_button)
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addStretch(1)

        main_layout.addLayout(buttons_layout)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.cancel_button.clicked.connect(self.cancel_install)

    def on_progress_updated(self, progress: int, status: str):
        """Обрабатывает сигнал обновления прогресса и статуса."""
        self.progress_bar.setValue(progress)
        self.status_label.setText(status)

    def _handle_installation_end(self, status: str, message: str = ""):
        """Единый метод для обработки завершения потока установки."""
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

        if status == "error":
            QMessageBox.warning(self, "Ошибка установки", f"Произошла ошибка: {message}")
            self.show_retry_option()
        elif status == "finished":
            QMessageBox.information(self, "Установка завершена", "Игра успешно установлена.")
            self.close()
        elif status == "stopped":
            QMessageBox.information(self, "Установка отменена", "Установка была отменена пользователем.")
            self.close()

    def show_retry_option(self):
        """Показывает диалог с предложением о повторной попытке."""
        reply = QMessageBox.question(self, 'Установка завершена с ошибкой',
                                     "Хотите попробовать еще раз?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.validate_and_start()
        else:
            self.close()

    def validate_and_start(self):
        """Валидация и запуск установки."""
        try:
            if error := InstallValidator.validate_game_data(self.game_data):
                raise ValueError(error)

            install_dir = InstallValidator.prepare_install_dir(
                self.game_data['platform'],
                self.project_root
            )

            self.status_label.setText("Запуск установки...")
            self.progress_bar.setValue(0)
            self.progress_bar.setHidden(False)
            self.cancel_button.setHidden(False)

            self.thread = InstallThread(self.game_data, install_dir, self.project_root)

            # Подключение сигналов потока к методам диалога.
            self.thread.progress_updated.connect(self.on_progress_updated)
            self.thread.finished.connect(lambda: self._handle_installation_end("finished"))
            self.thread.error_occurred.connect(lambda msg: self._handle_installation_end("error", msg))
            self.thread.stopped.connect(lambda: self._handle_installation_end("stopped"))

            self.thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось начать установку: {e}")
            self.close()

    def cancel_install(self):
        """Безопасная отмена установки по запросу пользователя."""
        if self.thread and self.thread.isRunning():
            reply = QMessageBox.question(self, 'Отмена установки',
                                         "Вы уверены, что хотите отменить установку?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.status_label.setText("Отмена установки...")
                self.thread.stop()
                self.cancel_button.setEnabled(False)

    def toggle_pause(self):
        # Метод для паузы/возобновления установки
        pass

    def closeEvent(self, event):
        """Переопределяем closeEvent для обработки закрытия окна."""
        if self.thread and self.thread.isRunning():
            reply = QMessageBox.question(self, "Отмена установки", "Вы уверены, что хотите отменить установку?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.thread.stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python install.py <game_data.json> <project_root>")
        sys.exit(1)

    try:
        with open(sys.argv[1], 'r') as f:
            game_data = json.load(f)
        app = QApplication(sys.argv)
        dialog = InstallDialog(game_data, Path(sys.argv[2]))
        dialog.exec()
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        sys.exit(1)
