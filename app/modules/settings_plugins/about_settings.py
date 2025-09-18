# app/modules/settings_plugins/about_settings.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer
from app.updater import Updater, UpdateDialog
from app.core import APP_VERSION
import logging

logger = logging.getLogger('AboutPage')


class AboutPage(QWidget):
    """Страница 'О ArcadeDeck' с версией и кнопкой проверки обновлений."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.updater = Updater(parent)
        self.updater.update_available.connect(self.on_update_available)
        self.updater.update_check_complete.connect(self.on_update_check_complete)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("О ArcadeDeck")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        version_label = QLabel(f"Текущая версия: {APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setFont(QFont("Arial", 12))
        layout.addWidget(version_label)

        check_btn = QPushButton("Проверить обновления")
        check_btn.setFixedWidth(260)
        check_btn.clicked.connect(self.check_updates)
        layout.addWidget(check_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)

    def check_updates(self):
        """Запускает проверку обновлений"""
        logger.info("Запуск проверки обновлений из AboutPage")
        self.updater.check_for_updates()

    def on_update_available(self, info: dict):
        """Обработчик доступного обновления"""
        logger.info(f"Обновление найдено: {info['version']}")

        # Создаем диалог обновления
        dialog = UpdateDialog(
            APP_VERSION,
            info['version'],
            info['release'].get("body", "Нет информации об изменениях"),
            info['download_url'],
            self.updater.install_dir,
            info['asset_name'],
            parent=self.window()
        )

        # Отключаем сигнал обновлений, чтобы избежать повторного вызова
        try:
            self.updater.update_available.disconnect(self.on_update_available)
        except:
            pass

        dialog.exec()

        # После закрытия диалога снова подключаем сигнал
        self.updater.update_available.connect(self.on_update_available)

    def on_update_check_complete(self, has_update):
        """Обработчик завершения проверки обновлений"""
        if not has_update:
            QMessageBox.information(
                self,
                "Обновлений нет",
                "У вас уже установлена самая последняя версия ArcadeDeck."
            )
