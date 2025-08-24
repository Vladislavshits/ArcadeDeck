# install_ui.py
import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, 
                           QProgressBar, QApplication, QPushButton, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QObject
from pathlib import Path
import time


class DownloaderThread(QThread):
    progress_updated = pyqtSignal(int, str)
    download_finished = pyqtSignal()
    download_error = pyqtSignal(str)
    stopped = pyqtSignal()

    def __init__(self, game_downloader, source, dest_dir):
        super().__init__()
        self.game_downloader = game_downloader
        self.source = source
        self.dest_dir = dest_dir
        self._stop_requested = False

    def run(self):
        try:
            self.game_downloader.download_game(
                source=self.source,
                dest_dir=self.dest_dir,
                progress_callback=self.update_progress,
                stop_flag=lambda: self._stop_requested
            )
            if not self._stop_requested:
                self.download_finished.emit()
        except Exception as e:
            if not self._stop_requested:
                self.download_error.emit(str(e))
        finally:
            if self._stop_requested:
                self.stopped.emit()

    def update_progress(self, progress: int, status: str):
        self.progress_updated.emit(progress, status)

    def stop(self):
        self._stop_requested = True


class InstallUI(QWidget):
    def __init__(self, game_data, game_downloader, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.game_downloader = game_downloader
        self.thread = None
        self._init_ui()
        self._start_download()

    def _init_ui(self):
        self.layout = QVBoxLayout(self)
        self.status_label = QLabel("Подготовка к загрузке...")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.layout.addWidget(self.status_label)
        self.layout.addWidget(self.progress_bar)

    def _start_download(self):
        self.thread = DownloaderThread(
            game_downloader=self.game_downloader,
            source=self.game_data.get('torrent_url'),
            dest_dir=Path.cwd() / "users" / "downloads"
        )
        self.thread.progress_updated.connect(self.update_progress)
        self.thread.download_finished.connect(self._on_download_finished)
        self.thread.download_error.connect(self._on_download_error)
        self.thread.start()

    def update_progress(self, progress: int, status: str):
        self.progress_bar.setValue(progress)
        self.status_label.setText(status)

    def _on_download_finished(self):
        QMessageBox.information(
            self, "Успех", "Загрузка успешно завершена."
        )
        self.thread = None

    def _on_download_error(self, error_message: str):
        QMessageBox.critical(
            self, "Ошибка", f"Произошла ошибка загрузки: {error_message}"
        )
        self.thread = None
