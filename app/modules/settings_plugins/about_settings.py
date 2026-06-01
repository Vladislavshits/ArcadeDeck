from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                             QDialog, QScrollArea, QTextEdit)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer
from app.updater import Updater, UpdateDialog
from app.core import APP_VERSION
import logging

# Импорт кастомных диалогов
from app.modules.ui.message_dialog import show_info, show_warning

logger = logging.getLogger('ArcadeDeck.AboutPage')


class FocusButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("focused", False)

    def focusInEvent(self, event):
        self.setProperty("focused", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.setProperty("focused", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().focusOutEvent(event)


class ContributorsDialog(QDialog):
    def __init__(self, parent=None, nav_controller=None):
        super().__init__(parent)
        self.nav_controller = nav_controller
        self.previous_layer = None
        self.setWindowTitle("Участники проекта")
        self.resize(500, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Arial", 11))
        text_edit.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

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

<p><b>@Dezzmod — Спасибо за помощь с тестированием программы!</b></p>

<h2>Благодарности</h2>

<p>
Спасибо всем, кто принимал участие
в тестировании и развитии проекта!
</p>
        """
        text_edit.setHtml(contributors_text)
        layout.addWidget(text_edit)

        self.close_btn = FocusButton("Закрыть")
        self.close_btn.setFixedWidth(200)
        self.close_btn.setFixedHeight(50)
        self.close_btn.clicked.connect(self.close_dialog)
        layout.addWidget(self.close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.nav_widgets = [self.close_btn]

    def close_dialog(self):
        self.close()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.close_btn.click()
            return
        if key == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            if self.nav_controller:
                from navigation import NavigationLayer
                self.previous_layer = self.nav_controller.current_layer
                self.nav_controller.add_managed_window(self)
                self.nav_controller.set_dialog_open(True)
                self.nav_controller.register_widgets(NavigationLayer.DIALOG, self.nav_widgets)
                self.nav_controller.switch_layer(NavigationLayer.DIALOG)
                self.close_btn.setFocus()
        except Exception:
            logger.exception("Ошибка showEvent ContributorsDialog")

    def closeEvent(self, event):
        try:
            if self.nav_controller:
                self.nav_controller.remove_managed_window(self)
                self.nav_controller.set_dialog_open(False)
                if self.previous_layer:
                    self.nav_controller.switch_layer(self.previous_layer)
        except Exception:
            logger.exception("Ошибка closeEvent ContributorsDialog")
        super().closeEvent(event)


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.updater = Updater(parent)
        self.updater.update_available.connect(self.on_update_available)
        self.current_focus_index = 0
        self.focusable_widgets = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        title = QLabel("О программе")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        version_label = QLabel(f"Текущая версия: {APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setFont(QFont("Arial", 12))
        layout.addWidget(version_label)

        self.check_btn = FocusButton("Проверить обновления")
        self.check_btn.setFixedWidth(260)
        self.check_btn.setFixedHeight(50)
        self.check_btn.clicked.connect(self.check_updates)
        layout.addWidget(self.check_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.contributors_btn = FocusButton("Участники проекта")
        self.contributors_btn.setFixedWidth(260)
        self.contributors_btn.setFixedHeight(50)
        self.contributors_btn.clicked.connect(self.show_contributors)
        layout.addWidget(self.contributors_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        info_label = QLabel(
            "ArcadeDeck - современный лаунчер для эмуляции на Steam Deck\n\n"
            "• Автоматическая настройка эмуляторов\n"
            "• Управление библиотекой игр\n"
            "• Интуитивный интерфейс для геймпада\n"
            "• Поддержка множества платформ"
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setFont(QFont("Arial", 10))
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #cccccc; margin: 20px;")
        layout.addWidget(info_label)
        layout.addStretch(1)

        self.focusable_widgets = [self.check_btn, self.contributors_btn]

    def navigate_up(self):
        if self.focusable_widgets:
            self.current_focus_index = (self.current_focus_index - 1) % len(self.focusable_widgets)
            self._set_focus_on_current()
            return True
        return False

    def navigate_down(self):
        if self.focusable_widgets:
            self.current_focus_index = (self.current_focus_index + 1) % len(self.focusable_widgets)
            self._set_focus_on_current()
            return True
        return False

    def navigate_left(self):
        return False

    def navigate_right(self):
        return False

    def activate_current(self):
        if self.focusable_widgets and 0 <= self.current_focus_index < len(self.focusable_widgets):
            widget = self.focusable_widgets[self.current_focus_index]
            if isinstance(widget, QPushButton):
                QTimer.singleShot(0, widget.click)
                return True
        return False

    def _set_focus_on_current(self):
        if self.focusable_widgets and 0 <= self.current_focus_index < len(self.focusable_widgets):
            for w in self.focusable_widgets:
                w.setProperty("focused", False)
                w.style().unpolish(w)
                w.style().polish(w)
                w.clearFocus()
            current = self.focusable_widgets[self.current_focus_index]
            current.setProperty("focused", True)
            current.style().unpolish(current)
            current.style().polish(current)
            current.setFocus(Qt.FocusReason.TabFocusReason)

    def showEvent(self, event):
        self.current_focus_index = 0
        if self.focusable_widgets:
            self._set_focus_on_current()
        super().showEvent(event)

    def check_updates(self):
        logger.info("🔍 Проверка обновлений...")
        original_text = self.check_btn.text()
        self.check_btn.setText("Проверка...")
        self.check_btn.setEnabled(False)

        # Получаем nav_controller
        nav = self.window().navigation_controller if hasattr(self.window(), 'navigation_controller') else None

        def handle_result():
            try:
                self.updater.check_for_updates()
                if self.updater.latest_info:
                    self.on_update_available(self.updater.latest_info)
                else:
                    show_info(
                        self,
                        "Обновлений нет",
                        "У вас уже установлена самая последняя версия ArcadeDeck.",
                        nav_controller=nav
                    )
            except Exception as e:
                logger.error(f"❌ Ошибка при проверке обновлений: {e}")
                show_warning(
                    self,
                    "Ошибка",
                    f"Не удалось проверить обновления:\n{str(e)}",
                    nav_controller=nav
                )
            finally:
                self.check_btn.setText(original_text)
                self.check_btn.setEnabled(True)
                self._set_focus_on_current()

        QTimer.singleShot(100, handle_result)

    def show_contributors(self):
        nav = None
        if hasattr(self.window(), 'navigation_controller'):
            nav = self.window().navigation_controller
        self.contributors_dialog = ContributorsDialog(parent=self.window(), nav_controller=nav)
        self.contributors_dialog.show()

    def on_update_available(self, info):
        dialog = UpdateDialog(
            APP_VERSION,
            info['version'],
            info['release'].get("body", "Доступно новое обновление"),
            info['download_url'],
            self.updater.install_dir,
            info['asset_name'],
            parent=self.window()
        )
        dialog.exec()
        self._set_focus_on_current()

    def get_navigation_widgets(self):
        return self.focusable_widgets
