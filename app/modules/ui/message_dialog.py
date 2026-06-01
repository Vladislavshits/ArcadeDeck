import logging
from enum import auto, Enum
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame, QApplication
)

from navigation import NavigationLayer

logger = logging.getLogger('ArcadeDeck.MessageDialog')


class MessageDialogResult(Enum):
    YES = auto()
    NO = auto()
    OK = auto()
    CANCEL = auto()
    CLOSE = auto()
    NONE = auto()


class MessageDialog(QDialog):
    """
    Универсальный диалог сообщений с поддержкой геймпадной навигации.
    Заменяет QMessageBox.
    """
    finished_signal = pyqtSignal(object)  # передаёт результат

    def __init__(self,
                 title: str,
                 text: str,
                 icon_type: str = "info",  # info, warning, critical, question
                 buttons=None,
                 parent=None,
                 nav_controller=None,
                 modal=True):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.text = text                    # ← сохраняем текст
        self.icon_type = icon_type
        self.nav_controller = nav_controller
        self.previous_layer = None
        self.buttons = buttons or [("OK", MessageDialogResult.OK)]
        self.result = MessageDialogResult.NONE
        self._widgets_for_nav = []
        self._finished = False
        self._modal = modal

        if modal:
            self.setModal(True)
            self.setWindowModality(Qt.WindowModality.ApplicationModal)
        else:
            # show() поверх InstallDialog: слой SYSTEM_DIALOG + без вложенного exec()
            self.setModal(False)
            self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.init_ui()
        self.setup_navigation()
        QTimer.singleShot(100, self.raise_and_activate)

    def raise_and_activate(self):
        self.raise_()
        self.activateWindow()
        if self._buttons:
            self._buttons[0].setFocus(Qt.FocusReason.OtherFocusReason)

    def init_ui(self):
        # Основной контейнер
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(25)

        # Заголовок
        self.title_label = QLabel(self.windowTitle())
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("Arial", 18, QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        main_layout.addWidget(self.title_label)

        # Иконка (текстовая эмуляция)
        icon_char = self._get_icon_char()
        if icon_char:
            icon_label = QLabel(icon_char)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setFont(QFont("Segoe UI", 48))
            main_layout.addWidget(icon_label)

        # Текст сообщения
        self.message_label = QLabel(self.text)   # ← используем сохранённый текст
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setFont(QFont("Arial", 14))
        self.message_label.setMinimumWidth(400)
        main_layout.addWidget(self.message_label)

        # Панель кнопок
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._buttons = []
        for btn_text, btn_result in self.buttons:
            btn = QPushButton(btn_text)
            btn.setAutoDefault(False)      # добавить
            btn.setDefault(False)          # добавить
            btn.setMinimumSize(140, 50)
            btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            btn.clicked.connect(lambda checked, res=btn_result: self._on_button_click(res))
            self._buttons.append(btn)
            button_layout.addWidget(btn)

        main_layout.addLayout(button_layout)

        # Устанавливаем стили в зависимости от типа
        self._apply_style()

    def _get_icon_char(self) -> str:
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "❌",
            "question": "❓"
        }
        return icons.get(self.icon_type, "")

    def _apply_style(self):
        colors = {
            "info": "#3a6ea5",
            "warning": "#e6a017",
            "critical": "#c7452c",
            "question": "#4c9a7a"
        }
        accent = colors.get(self.icon_type, "#3a6ea5")

        self.setStyleSheet(f"""
            QDialog {{
                border-radius: 15px;
            }}
            QLabel {{
                color: #ffffff;
                background: transparent;
            }}
        """)

    def setup_navigation(self):
        if not self.nav_controller:
            return

        self.previous_layer = self.nav_controller.current_layer

        # Регистрируем кнопки для SYSTEM_DIALOG
        self.nav_controller.register_widgets(NavigationLayer.SYSTEM_DIALOG, self._buttons)

        # Принудительно переключаем слой
        self.nav_controller.switch_layer(NavigationLayer.SYSTEM_DIALOG)
        self.nav_controller.set_dialog_open(True)
        self.nav_controller.add_managed_window(self)
        self.nav_controller.update_hints()

        # Фокус с небольшой задержкой
        if self._buttons:
            QTimer.singleShot(50, lambda: self._buttons[0].setFocus(Qt.FocusReason.OtherFocusReason))

    def _teardown_navigation(self):
        """Восстановление слоя навигации (accept() не вызывает closeEvent)."""
        if not self.nav_controller:
            return

        self.nav_controller.remove_managed_window(self)
        self.nav_controller.set_dialog_open(False)

        if self.previous_layer and self.previous_layer != NavigationLayer.SYSTEM_DIALOG:
            self.nav_controller.switch_layer(self.previous_layer)
        else:
            parent = self.parent()
            fallback = (
                NavigationLayer.INSTALL
                if parent and hasattr(parent, 'nav_controller')
                else NavigationLayer.MAIN
            )
            self.nav_controller.switch_layer(fallback)
        self.nav_controller.update_hints()

    def dismiss_as_no(self):
        """Закрыть вопрос как «Нет» (кнопка B на геймпаде)."""
        for _, res in self.buttons:
            if res in (MessageDialogResult.NO, MessageDialogResult.CANCEL, MessageDialogResult.CLOSE):
                self._finish_dialog(res)
                return
        self._finish_dialog(MessageDialogResult.NO)

    def _finish_dialog(self, result):
        """
        Завершение диалога: emit сигнала и cleanup.
        При show() + accept() Qt вызывает hide(), но не closeEvent — без этого
        finished_signal не доходит до слотов (например, отмена установки).
        """
        if self._finished:
            return
        self._finished = True
        self.result = result
        self.finished_signal.emit(self.result)
        self._teardown_navigation()
        self.accept()

    def _on_button_click(self, result):
        self._finish_dialog(result)

    def _safe_set_focus(self):
        """Безопасно устанавливает фокус на первую кнопку, если она существует."""
        try:
            if self._buttons and self._buttons[0]:
                self._buttons[0].setFocus(Qt.FocusReason.OtherFocusReason)
        except RuntimeError:
            # объект кнопки уже удалён – игнорируем
            pass

    def showEvent(self, event):
        super().showEvent(event)
        if self.nav_controller:
            self.nav_controller.add_managed_window(self)
            if not self._modal:
                QTimer.singleShot(0, self.raise_and_activate)

    def closeEvent(self, event):
        if not self._finished:
            self._finished = True
            self.finished_signal.emit(self.result)
            self._teardown_navigation()
        super().closeEvent(event)

# ⚡ Вспомогательные функции для быстрой замены QMessageBox

def show_info(parent, title, text, nav_controller=None):
    dialog = MessageDialog(title, text, "info", [("OK", MessageDialogResult.OK)],
                           parent, nav_controller)
    dialog.exec()
    return True


def show_warning(parent, title, text, nav_controller=None):
    dialog = MessageDialog(title, text, "warning", [("OK", MessageDialogResult.OK)],
                           parent, nav_controller)
    dialog.exec()
    return True


def show_error(parent, title, text, nav_controller=None):
    dialog = MessageDialog(title, text, "critical", [("OK", MessageDialogResult.OK)],
                           parent, nav_controller)
    dialog.exec()
    return True


def show_question(parent, title, text, nav_controller=None, use_show=False) -> bool:
    """
    use_show=False (по умолчанию): exec(), результат сразу — удаление игры и т.п.
    use_show=True: только создаёт диалог; показать через .show() и слушать finished_signal.
    """
    dialog = MessageDialog(
        title, text, "question",
        [("Да", MessageDialogResult.YES), ("Нет", MessageDialogResult.NO)],
        parent, nav_controller,
        modal=not use_show,
    )

    if use_show:
        return dialog

    dialog.exec()
    return dialog.result == MessageDialogResult.YES


def create_install_cancel_question(parent, nav_controller=None) -> MessageDialog:
    """Немодальный вопрос отмены установки (геймпад + finished_signal)."""
    dialog = MessageDialog(
        "Отмена установки",
        "Отменить установку игры?",
        icon_type="question",
        buttons=[("Да", MessageDialogResult.YES), ("Нет", MessageDialogResult.NO)],
        parent=parent,
        nav_controller=nav_controller,
        modal=False,
    )
    return dialog
