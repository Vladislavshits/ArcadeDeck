# app/modules/ui/add_game_dialog.py
import logging
import re
import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QInputDialog, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from navigation import NavigationLayer
from app.modules.installer.install import InstallDialog
from app.modules.module_logic.user_game_converter import UserGameConverter
from app.core import get_users_subpath

logger = logging.getLogger("Модуль добавления игр")


class AddGameDialog(QDialog):
    """Диалог добавления игры в библиотеку с поддержкой геймпада"""
    game_imported = pyqtSignal()  # сигнал для обновления библиотеки

    def __init__(self, project_root: Path, library_widget, parent=None):
        try:
            logger.info("=== Инициализация AddGameDialog ===")
            # ... весь код
        except Exception:
            logger.exception("Критическая ошибка в AddGameDialog.__init__")
            raise

        super().__init__(parent)
        self.project_root = project_root
        self.library_widget = library_widget

        # Для навигации
        self.nav_controller = None
        self.previous_layer = None
        if parent and hasattr(parent.window(), 'navigation_controller'):
            self.nav_controller = parent.window().navigation_controller
            self.previous_layer = self.nav_controller.current_layer if self.nav_controller else None

        # Настройки окна
        self.setWindowTitle("Добавить свою игру")
        self.setModal(True)
        self.resize(1280, 780)
        self.setMinimumSize(1100, 680)

        self.init_ui()
        self.setup_navigation()

    def init_ui(self):
        """Создание интерфейса (стиль из первого файла)"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(50, 45, 50, 45)
        main_layout.setSpacing(30)

        # Заголовок
        title = QLabel("Как вы хотите добавить игру?")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        main_layout.addSpacing(20)

        # Контент (две колонки)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(40)

        # Левая колонка: торрент / magnet
        left_column = QVBoxLayout()
        left_column.setSpacing(24)
        self.btn_torrent = self._create_big_button(
            "📥", "Из torrent-файла", "Выбрать .torrent файл и скачать игру"
        )
        self.btn_magnet = self._create_big_button(
            "🔗", "Из magnet-ссылки", "Вставить magnet-ссылку для загрузки"
        )
        left_column.addWidget(self.btn_torrent)
        left_column.addWidget(self.btn_magnet)
        left_column.addStretch()

        # Правая колонка: локальные файлы
        right_column = QVBoxLayout()
        right_column.setSpacing(24)
        self.btn_file = self._create_big_button(
            "📄", "Файл игры", "Выбрать одиночный файл (.iso, .chd и др.)"
        )
        self.btn_folder = self._create_big_button(
            "📁", "Папка с игрой", "Выбрать уже готовую папку с файлами"
        )
        self.btn_archive = self._create_big_button(
            "📦", "Архив с игрой", "Выбрать .zip, .7z, .rar и распаковать"
        )
        right_column.addWidget(self.btn_file)
        right_column.addWidget(self.btn_folder)
        right_column.addWidget(self.btn_archive)
        right_column.addStretch()

        content_layout.addLayout(left_column, 1)
        content_layout.addLayout(right_column, 1)
        main_layout.addLayout(content_layout)

        # Кнопка Закрыть
        bottom = QHBoxLayout()
        self.btn_cancel = QPushButton("Закрыть")
        self.btn_cancel.setFixedHeight(70)
        self.btn_cancel.setFont(QFont("Arial", 15, QFont.Weight.Bold))
        self.btn_cancel.clicked.connect(self.reject)
        bottom.addStretch()
        bottom.addWidget(self.btn_cancel)
        main_layout.addLayout(bottom)

        # Подключение сигналов к обработчикам (функциональность из второго файла)
        self.btn_torrent.clicked.connect(self.on_torrent)
        self.btn_magnet.clicked.connect(self.on_magnet)
        self.btn_file.clicked.connect(self.on_single_file)
        self.btn_folder.clicked.connect(self.on_folder)
        self.btn_archive.clicked.connect(self.on_archive)

    def _create_big_button(self, emoji: str, title: str, subtitle: str) -> QPushButton:
        """Создаёт стилизованную кнопку с эмодзи, заголовком и подзаголовком"""
        btn = QPushButton()
        btn.setFixedHeight(138)
        btn.setFlat(True)   # убирает стандартную рамку

        # Внутренний layout
        main_layout = QVBoxLayout(btn)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(30, 18, 30, 18)

        # Эмодзи
        emoji_label = QLabel(emoji)
        emoji_label.setFont(QFont("Segoe UI", 34))
        emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emoji_label.setStyleSheet("background: transparent;")

        # Заголовок
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 15, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("background: transparent;")

        # Подзаголовок
        subtitle_label = QLabel(subtitle)
        subtitle_label.setFont(QFont("Arial", 11))
        subtitle_label.setStyleSheet("color: #bbbbbb; background: transparent;")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setWordWrap(True)

        main_layout.addWidget(emoji_label)
        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle_label)

        return btn

        # Добавляем стили для всех кнопок в диалоге
        for btn in [self.btn_torrent, self.btn_magnet,
                    self.btn_file, self.btn_folder, self.btn_archive,
                    self.btn_cancel]:
            # Сохраняем оригинальный стиль, но добавляем наши правила
            orig_style = btn.styleSheet()
            btn.setStyleSheet(orig_style + focus_style)

    # ====================== Логика добавления (из второго файла) ======================

    def on_torrent(self):
        """Выбор .torrent файла"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите .torrent файл", "", "Torrent (*.torrent)"
        )
        if path:
            self._start_installation_with_user_data(
                source=path,
                source_type='torrent',
                suggested_title=Path(path).stem
            )

    def on_magnet(self):
        """Ввод magnet-ссылки"""
        magnet, ok = QInputDialog.getText(self, "Magnet-ссылка", "Вставьте magnet-ссылку:")
        if ok and magnet.strip():
            if not magnet.startswith("magnet:"):
                QMessageBox.warning(self, "Ошибка", "Некорректная magnet-ссылка")
                return
            self._start_installation_with_user_data(
                source=magnet,
                source_type='magnet',
                suggested_title="Игра из magnet"
            )

    def on_single_file(self):
        """Выбор одного файла игры"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Файл игры", "",
            "Game files (*.iso *.chd *.bin *.rom *.xci *.nsp)"
        )
        if path:
            self._start_installation_with_user_data(
                source=path,
                source_type='file',
                suggested_title=Path(path).stem
            )

    def on_folder(self):
        """Выбор папки с игрой"""
        path = QFileDialog.getExistingDirectory(self, "Папка с игрой")
        if path:
            self._start_installation_with_user_data(
                source=path,
                source_type='folder',
                suggested_title=Path(path).name
            )

    def on_archive(self):
        """Выбор архива с игрой"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Архив с игрой", "",
            "Archives (*.zip *.7z *.rar *.tar.gz *.tar.xz)"
        )
        if path:
            self._start_installation_with_user_data(
                source=path,
                source_type='archive',
                suggested_title=Path(path).stem
            )

    def _start_installation_with_user_data(self, source: str, source_type: str, suggested_title: str):
        """Запрашивает у пользователя название и платформу, затем запускает установку"""
        try:
            # Название игры
            title, ok = QInputDialog.getText(
                self, "Название игры", "Введите название игры:",
                text=suggested_title
            )
            if not ok or not title.strip():
                return

            # Платформа
            platforms = [
                "PS1", "PS2", "PS3", "PSP", "PSVITA",
                "NS1", "NDS", "GBA", "XBOX", "XBOX360",
                "WII", "WIIU", "GC", "SNES", "NES", "MD"
            ]
            platform, ok = QInputDialog.getItem(
                self, "Платформа", "Выберите платформу:",
                platforms, 0, False
            )
            if not ok:
                return

            # Создаём game_data через UserGameConverter
            game_data = UserGameConverter.create_game_data(
                source=source,
                source_type=source_type,
                title=title.strip(),
                platform=platform,
                description=f"Пользовательская игра - добавлена {time.strftime('%Y-%m-%d')}",
                game_type=UserGameConverter.detect_game_type(
                    Path(source) if source_type not in ('torrent', 'magnet') else None
                )
            )

            # Закрываем диалог добавления
            self.accept()

            # Запускаем установку
            self._start_installation(game_data)

        except Exception as e:
            logger.error(f"❌ Ошибка создания игры: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать игру: {str(e)}")

    def _start_installation(self, game_data: dict):
        """Запускает InstallDialog и подключает обновление библиотеки"""
        try:
            logger.info(f"🚀 Запуск установки пользовательской игры: {game_data.get('title')}")

            # Закрываем текущий диалог добавления
            self.accept()   # <-- закрываем AddGameDialog

            # Создаём диалог установки (он сам покажется через show_dialog в своём __init__)
            install_dialog = InstallDialog(
                game_data=game_data,
                project_root=self.project_root,
                parent=self.parent()   # родитель – главное окно (в нём есть navigation_controller)
            )

            if self.library_widget:
                install_dialog.installation_finished.connect(
                    lambda: self.library_widget.load_games()
                )
                install_dialog.installation_finished.connect(self.game_imported)

            # НЕ вызываем exec() – диалог откроется автоматически через navigation_controller

        except Exception as e:
            logger.error(f"❌ Ошибка запуска установки: {e}")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось запустить установку:\n{str(e)}"
            )

    # ====================== Навигация (из первого файла) ======================

    def setup_navigation(self):
        """Регистрирует кнопки в навигационном контроллере"""
        if not self.nav_controller:
            return

        self.nav_controller.set_dialog_open(True)
        self.nav_controller.switch_layer(NavigationLayer.DIALOG)

        self.buttons = [
            self.btn_torrent, self.btn_magnet,
            self.btn_file, self.btn_folder, self.btn_archive,
            self.btn_cancel
        ]

        self.nav_controller.register_widgets(NavigationLayer.DIALOG, self.buttons)

        # Устанавливаем фокус на первую кнопку
        QTimer.singleShot(60, lambda: self.btn_torrent.setFocus())

    def reject(self):
        """Закрытие диалога (кнопка Отмена, B на геймпаде)"""
        self._restore_navigation()
        super().reject()

    def accept(self):
        """Закрытие после успешного добавления"""
        self._restore_navigation()
        super().accept()

    def _restore_navigation(self):
        """Восстанавливает предыдущий слой навигации"""
        if self.nav_controller:
            self.nav_controller.set_dialog_open(False)
            if self.previous_layer:
                self.nav_controller.switch_layer(self.previous_layer)

    def closeEvent(self, event):
        self._restore_navigation()
        super().closeEvent(event)
