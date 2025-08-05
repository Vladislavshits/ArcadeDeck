# app/modules/settings_plugins/about_settings.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer
from app.updater import Updater, UpdateDialog
from app.core import APP_VERSION

class AboutPage(QWidget):
    """Страница 'О PixelDeck' с версией и кнопкой проверки обновлений."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.updater = Updater(parent)
        self.updater.update_available.connect(self.on_update_available)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("О PixelDeck")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        version_label = QLabel(f"Текущая версия: {APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setFont(QFont("Arial", 12))
        layout.addWidget(version_label)

        check_btn = QPushButton("Проверить обновления")
        check_btn.setFixedWidth(200)
        check_btn.clicked.connect(self.check_updates)
        layout.addWidget(check_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)
    
    def check_updates(self):
        QTimer.singleShot(0, self.updater.check_for_updates)

    def on_update_available(self, info: dict):
        dialog = UpdateDialog(
            APP_VERSION,
            info['version'],
            info['release'].get("body", "Нет информации об изменениях"),
            info['download_url'],
            self.updater.install_dir,
            info['asset_name'],
            parent=self.window()
        )
        dialog.exec()
