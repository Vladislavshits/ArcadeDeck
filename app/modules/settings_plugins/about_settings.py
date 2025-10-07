from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                             QMessageBox, QDialog, QScrollArea, QTextEdit)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer
from app.updater import Updater, UpdateDialog
from app.core import APP_VERSION

class ContributorsDialog(QDialog):
    """Диалоговое окно с информацией о разработчиках и тестировщиках."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Участники проекта")
        self.resize(500, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Создаем текстовое поле для отображения информации
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Arial", 11))
        text_edit.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        # Формируем текст с информацией об участниках
        contributors_text = """
<h2>Разработка</h2>
<p><b>@vladislavshits (Владислав Шиц)</b> - автор программы, основной разработчик</p>

<h2>Тестирование и поддержка</h2>
<p><b>@Cybertehbryansk</b></p>
<p><b>@exterminatus13</b></p>
<p><b>@antongvit</b></p>
<p><b>@yuriygilbert</b></p>
<p><b>@ONEPK9669</b></p>
<p><b>@Hooligan_ZS</b></p>
<p><b>@pakhom2888</b></p>
<p><b>@Dispara</b></p>

<h2>Благодарности</h2>
<p>Спасибо всем, кто принимал участие в тестировании и развитии проекта!</p>

<p style="color: #666; font-style: italic;">
Если вы участвовали в разработке или тестировании и хотите быть упомянутыми здесь,
свяжитесь с автором проекта.
</p>
        """

        text_edit.setHtml(contributors_text)
        layout.addWidget(text_edit)

        # Кнопка закрытия
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


class AboutPage(QWidget):
    """Страница 'О программе' с версией, кнопкой проверки обновлений и информацией об участниках."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.updater = Updater(parent)
        self.updater.update_available.connect(self.on_update_available)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("О программе")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        version_label = QLabel(f"Текущая версия: {APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setFont(QFont("Arial", 12))
        layout.addWidget(version_label)

        # Кнопка проверки обновлений
        check_btn = QPushButton("Проверить обновления")
        check_btn.setFixedWidth(260)
        check_btn.clicked.connect(self.check_updates)
        layout.addWidget(check_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Кнопка просмотра участников проекта
        contributors_btn = QPushButton("Участники проекта")
        contributors_btn.setFixedWidth(260)
        contributors_btn.clicked.connect(self.show_contributors)
        layout.addWidget(contributors_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)

    def check_updates(self):
        def handle_result():
            self.updater.check_for_updates()  # запускаем проверку

            if self.updater.latest_info:
                # Обновление найдено → вызываем стандартный диалог
                self.on_update_available(self.updater.latest_info)
            else:
                # Обновлений нет → показываем сообщение
                QMessageBox.information(
                    self,
                    "Обновлений нет",
                    "У вас уже установлена самая последняя версия ArcadeDeck."
                )

        QTimer.singleShot(0, handle_result)

    def show_contributors(self):
        """Показывает диалоговое окно с информацией об участниках проекта."""
        dialog = ContributorsDialog(parent=self.window())
        dialog.exec()

    def on_update_available(self, info: dict):
        dialog = UpdateDialog(
            APP_VERSION,
            info['version'],
            info['release'].get("body", "У вас самая актуальная версия"),
            info['download_url'],
            self.updater.install_dir,
            info['asset_name'],
            parent=self.window()
        )
        dialog.exec()
