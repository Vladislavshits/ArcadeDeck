import os
import shutil
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor
import logging

logger = logging.getLogger('ArcadeDeck.MigrationDialog')

class MigrationWorker(QThread):
    """Поток для выполнения перемещения файлов"""
    progress_update = pyqtSignal(str, int, int)
    finished = pyqtSignal(bool, str)

    def __init__(self, source_path, target_path):
        super().__init__()
        self.source_path = Path(source_path)
        self.target_path = Path(target_path)
        self.cancelled = False

    def run(self):
        try:
            # Создаем целевую директорию
            self.target_path.mkdir(parents=True, exist_ok=True)

            # Собираем список всех файлов для перемещения
            all_files = []
            for root, dirs, files in os.walk(self.source_path):
                for file in files:
                    file_path = Path(root) / file
                    all_files.append(file_path)

            total_files = len(all_files)
            processed_files = 0

            # Перемещаем файлы
            for file_path in all_files:
                if self.cancelled:
                    break

                # Вычисляем относительный путь
                relative_path = file_path.relative_to(self.source_path)
                target_file = self.target_path / relative_path

                # Создаем целевую директорию если нужно
                target_file.parent.mkdir(parents=True, exist_ok=True)

                # Обновляем прогресс
                self.progress_update.emit(
                    f"Перемещение: {relative_path}",
                    processed_files,
                    total_files
                )

                # Перемещаем файл
                shutil.move(str(file_path), str(target_file))
                processed_files += 1

            if self.cancelled:
                self.finished.emit(False, "Перемещение отменено")
            else:
                # Удаляем пустые папки после перемещения
                self._cleanup_empty_dirs()
                self.finished.emit(True, f"Успешно перемещено {processed_files} файлов")

        except Exception as e:
            logger.error(f"Ошибка при перемещении: {e}")
            self.finished.emit(False, f"Ошибка: {str(e)}")

    def _cleanup_empty_dirs(self):
        """Удаляет пустые директории после перемещения"""
        for root, dirs, files in os.walk(self.source_path, topdown=False):
            current_dir = Path(root)
            if not any(current_dir.iterdir()):
                try:
                    current_dir.rmdir()
                except OSError:
                    pass  # Директория не пуста или нет прав

    def cancel(self):
        self.cancelled = True


class MigrationDialog(QDialog):
    """Диалоговое окно с прогрессом перемещения"""
    def __init__(self, source_path, target_path, parent=None):
        super().__init__(parent)
        self.source_path = source_path
        self.target_path = target_path
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Перемещение данных")
        self.setModal(True)
        self.setFixedSize(500, 400)

        layout = QVBoxLayout(self)

        # Заголовок
        title = QLabel("Перемещение данных")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Информация о путях
        paths_info = QLabel(
            f"Из: {self.source_path}\n"
            f"В: {self.target_path}"
        )
        paths_info.setWordWrap(True)
        layout.addWidget(paths_info)

        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # Текстовое поле для логов
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 9))
        layout.addWidget(self.log_text)

        # Кнопка отмены
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.cancel_migration)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def start_migration(self):
        """Запускает процесс перемещения"""
        self.worker = MigrationWorker(self.source_path, self.target_path)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.finished.connect(self.migration_finished)
        self.worker.start()

    def update_progress(self, message, current, total):
        """Обновляет прогресс"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)

        self.add_log(message)

    def add_log(self, message):
        """Добавляет сообщение в лог"""
        self.log_text.append(message)
        # Автопрокрутка к последнему сообщению
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def cancel_migration(self):
        """Отменяет перемещение"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.add_log("Отмена перемещения...")

    def migration_finished(self, success, message):
        """Завершает процесс перемещения"""
        self.add_log(message)
        self.cancel_btn.setText("Закрыть")
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.accept)

        if success:
            self.progress_bar.setValue(100)
        else:
            self.progress_bar.setValue(0)
